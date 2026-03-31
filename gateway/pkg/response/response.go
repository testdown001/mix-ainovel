package response

import "github.com/gofiber/fiber/v2"

type APIResponse struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data,omitempty"`
	Error   string      `json:"error,omitempty"`
	Code    string      `json:"code,omitempty"`
}

type PaginatedData struct {
	Items      interface{} `json:"items"`
	Total      int64       `json:"total"`
	Page       int         `json:"page"`
	PageSize   int         `json:"page_size"`
	TotalPages int         `json:"total_pages"`
}

func OK(c *fiber.Ctx, data interface{}) error {
	return c.JSON(APIResponse{Success: true, Data: data})
}

func Created(c *fiber.Ctx, data interface{}) error {
	return c.Status(fiber.StatusCreated).JSON(APIResponse{Success: true, Data: data})
}

func Paginated(c *fiber.Ctx, items interface{}, total int64, page, pageSize int) error {
	totalPages := int(total) / pageSize
	if int(total)%pageSize > 0 {
		totalPages++
	}
	return c.JSON(APIResponse{
		Success: true,
		Data: PaginatedData{
			Items:      items,
			Total:      total,
			Page:       page,
			PageSize:   pageSize,
			TotalPages: totalPages,
		},
	})
}

func Fail(c *fiber.Ctx, status int, code, message string) error {
	return c.Status(status).JSON(APIResponse{
		Success: false,
		Error:   message,
		Code:    code,
	})
}

func BadRequest(c *fiber.Ctx, message string) error {
	return Fail(c, fiber.StatusBadRequest, "BAD_REQUEST", message)
}

func Unauthorized(c *fiber.Ctx, message string) error {
	return Fail(c, fiber.StatusUnauthorized, "UNAUTHORIZED", message)
}

func Forbidden(c *fiber.Ctx, message string) error {
	return Fail(c, fiber.StatusForbidden, "FORBIDDEN", message)
}

func NotFound(c *fiber.Ctx, message string) error {
	return Fail(c, fiber.StatusNotFound, "NOT_FOUND", message)
}

func Conflict(c *fiber.Ctx, message string) error {
	return Fail(c, fiber.StatusConflict, "CONFLICT", message)
}

func TooManyRequests(c *fiber.Ctx, message string) error {
	return Fail(c, fiber.StatusTooManyRequests, "RATE_LIMITED", message)
}

func InternalError(c *fiber.Ctx, message string) error {
	return Fail(c, fiber.StatusInternalServerError, "INTERNAL_ERROR", message)
}
