package handler

import (
	"io"
	"strconv"

	"github.com/arboris-novel/gateway/internal/auth"
	"github.com/arboris-novel/gateway/internal/service"
	"github.com/arboris-novel/gateway/pkg/response"
	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
)

type PaymentHandler struct {
	paymentSvc *service.PaymentService
	webhookPool *service.WebhookWorkerPool
}

func NewPaymentHandler(paymentSvc *service.PaymentService, webhookPool *service.WebhookWorkerPool) *PaymentHandler {
	return &PaymentHandler{paymentSvc: paymentSvc, webhookPool: webhookPool}
}

func (h *PaymentHandler) RegisterRoutes(router fiber.Router) {
	plans := router.Group("/plans")
	plans.Get("/public", h.ListPlans)

	pay := router.Group("/payment", auth.JWTMiddleware())
	pay.Post("/orders", h.CreateOrder)
	pay.Get("/orders", h.ListOrders)
	pay.Get("/subscription", h.GetSubscription)
	pay.Post("/subscription/cancel", h.CancelSubscription)

	admin := router.Group("/admin/payment", auth.JWTMiddleware(), auth.RequireAdmin())
	admin.Post("/orders/:id/refund", h.RefundOrder)

	// Webhook — no auth, verified via signature
	router.Post("/webhooks/stripe", h.StripeWebhook)
}

func (h *PaymentHandler) ListPlans(c *fiber.Ctx) error {
	plans, err := h.paymentSvc.ListPlans(c.Context())
	if err != nil {
		return response.InternalError(c, "failed to list plans")
	}
	return response.OK(c, plans)
}

type CreateOrderReq struct {
	PlanID         int    `json:"plan_id"`
	Channel        string `json:"channel"`
	IdempotencyKey string `json:"idempotency_key"`
}

func (h *PaymentHandler) CreateOrder(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)
	if userID == 0 {
		return response.Unauthorized(c, "not authenticated")
	}

	var req CreateOrderReq
	if err := c.BodyParser(&req); err != nil {
		return response.BadRequest(c, "invalid request body")
	}

	if req.PlanID == 0 {
		return response.BadRequest(c, "plan_id is required")
	}
	if req.Channel == "" {
		req.Channel = "stripe"
	}
	if req.IdempotencyKey == "" {
		req.IdempotencyKey = uuid.New().String()
	}

	result, err := h.paymentSvc.CreateOrder(c.Context(), service.CreateOrderRequest{
		UserID:         userID,
		PlanID:         req.PlanID,
		Channel:        req.Channel,
		IdempotencyKey: req.IdempotencyKey,
	})
	if err != nil {
		if err == service.ErrInvalidPlan {
			return response.BadRequest(c, "invalid or inactive plan")
		}
		return response.TooManyRequests(c, err.Error())
	}

	return response.Created(c, result)
}

func (h *PaymentHandler) ListOrders(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)
	page, _ := strconv.Atoi(c.Query("page", "1"))
	pageSize, _ := strconv.Atoi(c.Query("page_size", "20"))

	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	orders, total, err := h.paymentSvc.ListOrders(c.Context(), userID, page, pageSize)
	if err != nil {
		return response.InternalError(c, "failed to list orders")
	}

	return response.Paginated(c, orders, total, page, pageSize)
}

func (h *PaymentHandler) GetSubscription(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)

	sub, err := h.paymentSvc.GetSubscription(c.Context(), userID)
	if err != nil {
		return response.InternalError(c, "failed to get subscription")
	}
	if sub == nil {
		return response.OK(c, fiber.Map{"subscription": nil})
	}

	return response.OK(c, sub)
}

func (h *PaymentHandler) CancelSubscription(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)

	if err := h.paymentSvc.CancelSubscription(c.Context(), userID); err != nil {
		return response.BadRequest(c, err.Error())
	}

	return response.OK(c, fiber.Map{"message": "subscription cancelled"})
}

func (h *PaymentHandler) RefundOrder(c *fiber.Ctx) error {
	adminUserID := auth.GetUserID(c)
	orderID, err := strconv.ParseUint(c.Params("id"), 10, 64)
	if err != nil {
		return response.BadRequest(c, "invalid order id")
	}

	if err := h.paymentSvc.RefundOrder(c.Context(), orderID, adminUserID); err != nil {
		return response.BadRequest(c, err.Error())
	}

	return response.OK(c, fiber.Map{"message": "order refunded"})
}

// StripeWebhook dispatches incoming webhooks to the Worker Pool for async processing.
func (h *PaymentHandler) StripeWebhook(c *fiber.Ctx) error {
	body, err := io.ReadAll(c.Request().BodyStream())
	if err != nil {
		return response.BadRequest(c, "failed to read body")
	}

	signature := c.Get("Stripe-Signature")
	if signature == "" {
		return response.BadRequest(c, "missing stripe signature")
	}

	task := service.WebhookTask{
		EventID:   "", // will be extracted during processing
		Payload:   body,
		Signature: signature,
	}

	if !h.webhookPool.TrySubmit(task) {
		return response.TooManyRequests(c, "webhook queue full, please retry")
	}

	return c.SendStatus(fiber.StatusOK)
}
