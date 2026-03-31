package handler

import (
	"github.com/arboris-novel/gateway/internal/auth"
	"github.com/arboris-novel/gateway/internal/service"
	"github.com/arboris-novel/gateway/pkg/response"
	"github.com/gofiber/fiber/v2"
)

type AuthHandler struct {
	authSvc  *service.AuthService
	quotaSvc *service.QuotaService
}

func NewAuthHandler(authSvc *service.AuthService, quotaSvc *service.QuotaService) *AuthHandler {
	return &AuthHandler{authSvc: authSvc, quotaSvc: quotaSvc}
}

func (h *AuthHandler) RegisterRoutes(router fiber.Router) {
	r := router.Group("/auth")

	r.Post("/users", h.Register)
	r.Post("/token", h.Login)
	r.Get("/users/me", auth.JWTMiddleware(), h.GetCurrentUser)
	r.Put("/users/me/password", auth.JWTMiddleware(), h.ChangePassword)

	q := router.Group("/quota", auth.JWTMiddleware())
	q.Get("/me", h.GetQuotaInfo)
}

type RegisterRequest struct {
	Username string `json:"username"`
	Email    string `json:"email"`
	Password string `json:"password"`
}

func (h *AuthHandler) Register(c *fiber.Ctx) error {
	var req RegisterRequest
	if err := c.BodyParser(&req); err != nil {
		return response.BadRequest(c, "invalid request body")
	}

	if req.Username == "" || req.Password == "" {
		return response.BadRequest(c, "username and password are required")
	}

	if len(req.Password) < 6 {
		return response.BadRequest(c, "password must be at least 6 characters")
	}

	user, err := h.authSvc.Register(c.Context(), req.Username, req.Email, req.Password)
	if err != nil {
		if err.Error() == "UNIQUE constraint failed" || err.Error() == "Error 1062" {
			return response.Conflict(c, "username or email already exists")
		}
		return response.InternalError(c, "registration failed")
	}

	return response.Created(c, fiber.Map{
		"id":       user.ID,
		"username": user.Username,
		"email":    user.Email,
	})
}

func (h *AuthHandler) Login(c *fiber.Ctx) error {
	username := c.FormValue("username")
	password := c.FormValue("password")

	if username == "" || password == "" {
		var body struct {
			Username string `json:"username"`
			Password string `json:"password"`
		}
		if err := c.BodyParser(&body); err == nil {
			username = body.Username
			password = body.Password
		}
	}

	if username == "" || password == "" {
		return response.BadRequest(c, "username and password are required")
	}

	tokenResp, err := h.authSvc.Login(c.Context(), username, password)
	if err != nil {
		return response.Unauthorized(c, "invalid credentials")
	}

	return response.OK(c, tokenResp)
}

func (h *AuthHandler) GetCurrentUser(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)
	if userID == 0 {
		return response.Unauthorized(c, "not authenticated")
	}

	user, err := h.authSvc.GetCurrentUser(c.Context(), userID)
	if err != nil {
		return response.NotFound(c, "user not found")
	}

	return response.OK(c, fiber.Map{
		"id":         user.ID,
		"username":   user.Username,
		"email":      user.Email,
		"is_admin":   user.IsAdmin,
		"is_active":  user.IsActive,
		"created_at": user.CreatedAt,
	})
}

type ChangePasswordRequest struct {
	OldPassword string `json:"old_password"`
	NewPassword string `json:"new_password"`
}

func (h *AuthHandler) ChangePassword(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)
	if userID == 0 {
		return response.Unauthorized(c, "not authenticated")
	}

	var req ChangePasswordRequest
	if err := c.BodyParser(&req); err != nil {
		return response.BadRequest(c, "invalid request body")
	}

	if len(req.NewPassword) < 6 {
		return response.BadRequest(c, "new password must be at least 6 characters")
	}

	if err := h.authSvc.ChangePassword(c.Context(), userID, req.OldPassword, req.NewPassword); err != nil {
		if err == service.ErrInvalidCredentials {
			return response.BadRequest(c, "incorrect old password")
		}
		return response.InternalError(c, "failed to change password")
	}

	return response.OK(c, fiber.Map{"message": "password changed"})
}

func (h *AuthHandler) GetQuotaInfo(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)
	if userID == 0 {
		return response.Unauthorized(c, "not authenticated")
	}

	quota, err := h.quotaSvc.GetQuotaInfo(c.Context(), userID)
	if err != nil {
		return response.InternalError(c, "failed to get quota info")
	}

	return response.OK(c, quota)
}
