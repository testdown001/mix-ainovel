package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/arboris-novel/gateway/internal/lock"
	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/arboris-novel/gateway/internal/models"
	"github.com/arboris-novel/gateway/internal/repository"
	"github.com/redis/go-redis/v9"
	"github.com/stripe/stripe-go/v81"
	"github.com/stripe/stripe-go/v81/checkout/session"
	"github.com/stripe/stripe-go/v81/webhook"
	"go.uber.org/zap"
	"gorm.io/gorm"
)

var (
	ErrOrderAlreadyPaid     = errors.New("order already paid")
	ErrOrderAlreadyRefunded = errors.New("order already refunded")
	ErrInvalidPlan          = errors.New("invalid or inactive plan")
	ErrWebhookSignature     = errors.New("invalid webhook signature")
	ErrSubNotFound          = errors.New("no active subscription found")
)

type PaymentService struct {
	repo     *repository.PaymentRepository
	quotaSvc *QuotaService
	lockMgr  *lock.Manager
	rdb      *redis.Client

	stripeKey       string
	stripeWebhookSecret string
	successURL      string
	cancelURL       string
}

type PaymentConfig struct {
	StripeSecretKey     string
	StripeWebhookSecret string
	SuccessURL          string
	CancelURL           string
}

func NewPaymentService(
	repo *repository.PaymentRepository,
	quotaSvc *QuotaService,
	lockMgr *lock.Manager,
	rdb *redis.Client,
	cfg PaymentConfig,
) *PaymentService {
	stripe.Key = cfg.StripeSecretKey

	return &PaymentService{
		repo:                repo,
		quotaSvc:            quotaSvc,
		lockMgr:             lockMgr,
		rdb:                 rdb,
		stripeKey:           cfg.StripeSecretKey,
		stripeWebhookSecret: cfg.StripeWebhookSecret,
		successURL:          cfg.SuccessURL,
		cancelURL:           cfg.CancelURL,
	}
}

// --- Order Creation (distributed lock + idempotency) ---

type CreateOrderRequest struct {
	UserID         int    `json:"user_id"`
	PlanID         int    `json:"plan_id"`
	Channel        string `json:"channel"`
	IdempotencyKey string `json:"idempotency_key"`
}

type CreateOrderResponse struct {
	OrderID    uint64 `json:"order_id"`
	CheckoutURL string `json:"checkout_url,omitempty"`
	Status     string `json:"status"`
}

func (s *PaymentService) CreateOrder(ctx context.Context, req CreateOrderRequest) (*CreateOrderResponse, error) {
	// Distributed lock: prevent duplicate orders from rapid clicks
	dlock := s.lockMgr.NewLock(
		fmt.Sprintf("pay:order:create:%d", req.UserID),
		lock.WithTTL(30*time.Second),
		lock.WithRetry(3, 100*time.Millisecond),
	)
	if err := dlock.Acquire(ctx); err != nil {
		return nil, fmt.Errorf("too many requests, please try again: %w", err)
	}
	defer dlock.Release(ctx)

	// Idempotency check
	existing, err := s.repo.FindOrderByIdempotencyKey(ctx, req.IdempotencyKey)
	if err != nil {
		return nil, err
	}
	if existing != nil {
		return &CreateOrderResponse{
			OrderID: existing.ID,
			Status:  existing.Status,
		}, nil
	}

	plan, err := s.repo.FindPlanByID(ctx, req.PlanID)
	if err != nil || !plan.IsActive {
		return nil, ErrInvalidPlan
	}

	amountCents := int64(plan.Price * 100)

	order := &models.PaymentOrder{
		UserID:         req.UserID,
		PlanID:         req.PlanID,
		IdempotencyKey: req.IdempotencyKey,
		Amount:         amountCents,
		Currency:       "cny",
		Status:         models.OrderStatusPending,
		Channel:        req.Channel,
	}

	if err := s.repo.CreateOrder(ctx, order); err != nil {
		return nil, fmt.Errorf("failed to create order: %w", err)
	}

	resp := &CreateOrderResponse{
		OrderID: order.ID,
		Status:  order.Status,
	}

	// Create Stripe Checkout Session if channel is stripe
	if req.Channel == models.ChannelStripe && s.stripeKey != "" {
		checkoutURL, err := s.createStripeCheckout(ctx, order, plan)
		if err != nil {
			logger.Error("stripe checkout creation failed", zap.Error(err))
			return resp, nil
		}
		resp.CheckoutURL = checkoutURL
	}

	return resp, nil
}

func (s *PaymentService) createStripeCheckout(ctx context.Context, order *models.PaymentOrder, plan *models.Plan) (string, error) {
	params := &stripe.CheckoutSessionParams{
		Mode: stripe.String(string(stripe.CheckoutSessionModePayment)),
		LineItems: []*stripe.CheckoutSessionLineItemParams{
			{
				PriceData: &stripe.CheckoutSessionLineItemPriceDataParams{
					Currency: stripe.String(order.Currency),
					ProductData: &stripe.CheckoutSessionLineItemPriceDataProductDataParams{
						Name:        stripe.String(plan.Name),
						Description: plan.Description,
					},
					UnitAmount: stripe.Int64(order.Amount),
				},
				Quantity: stripe.Int64(1),
			},
		},
		SuccessURL: stripe.String(fmt.Sprintf("%s?order_id=%d", s.successURL, order.ID)),
		CancelURL:  stripe.String(fmt.Sprintf("%s?order_id=%d", s.cancelURL, order.ID)),
		ClientReferenceID: stripe.String(fmt.Sprintf("%d", order.ID)),
		Metadata: map[string]string{
			"order_id": fmt.Sprintf("%d", order.ID),
			"user_id":  fmt.Sprintf("%d", order.UserID),
			"plan_id":  fmt.Sprintf("%d", order.PlanID),
		},
	}

	sess, err := session.New(params)
	if err != nil {
		return "", err
	}

	externalID := sess.ID
	order.ExternalID = &externalID
	_ = s.repo.UpdateOrder(ctx, order)

	return sess.URL, nil
}

// --- Webhook Handling (distributed lock + event idempotency) ---

func (s *PaymentService) HandleStripeWebhook(ctx context.Context, payload []byte, signature string) error {
	event, err := webhook.ConstructEvent(payload, signature, s.stripeWebhookSecret)
	if err != nil {
		return ErrWebhookSignature
	}

	eventID := event.ID

	// Distributed lock: prevent concurrent processing of same event
	dlock := s.lockMgr.NewLock(
		fmt.Sprintf("pay:webhook:%s", eventID),
		lock.WithTTL(300*time.Second),
		lock.WithWatchdog(),
	)
	if err := dlock.Acquire(ctx); err != nil {
		// Another instance is processing this event
		return nil
	}
	defer dlock.Release(ctx)

	// Idempotency check: was this event already processed?
	exists, err := s.repo.ExistsByExternalEventID(ctx, eventID)
	if err != nil {
		return err
	}
	if exists {
		return nil
	}

	switch event.Type {
	case "checkout.session.completed":
		return s.handleCheckoutCompleted(ctx, &event)
	default:
		logger.Info("unhandled stripe event", zap.String("type", string(event.Type)))
	}

	return nil
}

func (s *PaymentService) handleCheckoutCompleted(ctx context.Context, event *stripe.Event) error {
	var sess stripe.CheckoutSession
	if err := decodeStripeObject(event.Data.Raw, &sess); err != nil {
		return err
	}

	externalID := sess.ID
	order, err := s.repo.FindOrderByExternalID(ctx, externalID)
	if err != nil {
		return err
	}
	if order == nil {
		logger.Warn("order not found for stripe session", zap.String("session_id", externalID))
		return nil
	}

	if order.Status == models.OrderStatusPaid {
		return nil // already processed
	}

	// Transaction: update order + create/update subscription + update quota
	return s.repo.Transaction(func(tx *gorm.DB) error {
		now := time.Now().UTC()
		eventID := event.ID

		order.Status = models.OrderStatusPaid
		order.PaidAt = &now
		order.ExternalEventID = &eventID

		if err := tx.WithContext(ctx).Save(order).Error; err != nil {
			return err
		}

		plan, err := s.repo.FindPlanByID(ctx, order.PlanID)
		if err != nil {
			return err
		}

		periodEnd := now.AddDate(0, 1, 0)
		if plan.Period == "yearly" {
			periodEnd = now.AddDate(1, 0, 0)
		}

		sub, _ := s.repo.FindSubscriptionByUser(ctx, order.UserID)
		if sub == nil {
			sub = &models.Subscription{
				UserID:             order.UserID,
				PlanID:             order.PlanID,
				Status:             models.SubStatusActive,
				CurrentPeriodStart: now,
				CurrentPeriodEnd:   periodEnd,
			}
			if err := tx.WithContext(ctx).Create(sub).Error; err != nil {
				return err
			}
		} else {
			sub.PlanID = order.PlanID
			sub.Status = models.SubStatusActive
			sub.CurrentPeriodStart = now
			sub.CurrentPeriodEnd = periodEnd
			sub.CancelledAt = nil
			if err := tx.WithContext(ctx).Save(sub).Error; err != nil {
				return err
			}
		}

		// Upgrade user quota
		if err := s.quotaSvc.UpgradeToPremium(ctx, order.UserID, periodEnd); err != nil {
			logger.Error("failed to upgrade quota", zap.Int("user_id", order.UserID), zap.Error(err))
		}

		// Broadcast quota change via Redis Pub/Sub
		s.rdb.Publish(ctx, "cache:invalidate", fmt.Sprintf("user:quota:%d", order.UserID))

		logger.Info("payment completed",
			zap.Uint64("order_id", order.ID),
			zap.Int("user_id", order.UserID),
			zap.Int("plan_id", order.PlanID),
		)

		return nil
	})
}

// --- Refund (distributed lock) ---

func (s *PaymentService) RefundOrder(ctx context.Context, orderID uint64, adminUserID int) error {
	dlock := s.lockMgr.NewLock(
		fmt.Sprintf("pay:refund:%d", orderID),
		lock.WithTTL(120*time.Second),
		lock.WithRetry(2, 200*time.Millisecond),
	)
	if err := dlock.Acquire(ctx); err != nil {
		return fmt.Errorf("refund in progress, please wait")
	}
	defer dlock.Release(ctx)

	order, err := s.repo.FindOrderByID(ctx, orderID)
	if err != nil {
		return err
	}

	if order.Status != models.OrderStatusPaid {
		return ErrOrderAlreadyRefunded
	}

	return s.repo.Transaction(func(tx *gorm.DB) error {
		now := time.Now().UTC()
		order.Status = models.OrderStatusRefunded
		order.RefundedAt = &now
		if err := tx.WithContext(ctx).Save(order).Error; err != nil {
			return err
		}

		// Downgrade quota
		if err := s.quotaSvc.DowngradeFromPremium(ctx, order.UserID); err != nil {
			logger.Error("failed to downgrade quota", zap.Int("user_id", order.UserID), zap.Error(err))
		}

		// Cancel subscription
		sub, _ := s.repo.FindSubscriptionByUser(ctx, order.UserID)
		if sub != nil {
			sub.Status = models.SubStatusCancelled
			sub.CancelledAt = &now
			tx.WithContext(ctx).Save(sub)
		}

		s.rdb.Publish(ctx, "cache:invalidate", fmt.Sprintf("user:quota:%d", order.UserID))

		logger.Info("order refunded",
			zap.Uint64("order_id", orderID),
			zap.Int("admin", adminUserID),
		)
		return nil
	})
}

// --- Subscription queries ---

func (s *PaymentService) GetSubscription(ctx context.Context, userID int) (*models.Subscription, error) {
	return s.repo.FindSubscriptionByUser(ctx, userID)
}

func (s *PaymentService) ListOrders(ctx context.Context, userID, page, pageSize int) ([]models.PaymentOrder, int64, error) {
	offset := (page - 1) * pageSize
	return s.repo.ListOrdersByUser(ctx, userID, pageSize, offset)
}

func (s *PaymentService) ListPlans(ctx context.Context) ([]models.Plan, error) {
	return s.repo.ListActivePlans(ctx)
}

// --- Cancel Subscription (distributed lock) ---

func (s *PaymentService) CancelSubscription(ctx context.Context, userID int) error {
	dlock := s.lockMgr.NewLock(
		fmt.Sprintf("pay:sub:change:%d", userID),
		lock.WithTTL(60*time.Second),
		lock.WithRetry(2, 200*time.Millisecond),
	)
	if err := dlock.Acquire(ctx); err != nil {
		return fmt.Errorf("subscription change in progress")
	}
	defer dlock.Release(ctx)

	sub, err := s.repo.FindSubscriptionByUser(ctx, userID)
	if err != nil {
		return err
	}
	if sub == nil {
		return ErrSubNotFound
	}

	now := time.Now().UTC()
	sub.Status = models.SubStatusCancelled
	sub.CancelledAt = &now

	if err := s.repo.UpdateSubscription(ctx, sub); err != nil {
		return err
	}

	// Don't immediately downgrade — let it expire at period end
	logger.Info("subscription cancelled",
		zap.Int("user_id", userID),
		zap.Time("period_end", sub.CurrentPeriodEnd),
	)

	return nil
}

// decodeStripeObject decodes raw Stripe event data into a target struct.
func decodeStripeObject(raw []byte, dest interface{}) error {
	return json.Unmarshal(raw, dest)
}
