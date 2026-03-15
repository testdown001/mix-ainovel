package llmgateway

import (
	"bufio"

	"github.com/arboris-novel/gateway/internal/auth"
	"github.com/arboris-novel/gateway/internal/llmgateway/provider"
	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/gofiber/fiber/v2"
	"go.uber.org/zap"
)

// Handler LLM Gateway HTTP 处理器
type Handler struct {
	gateway *Gateway
}

// NewHandler 创建处理器
func NewHandler(gateway *Gateway) *Handler {
	return &Handler{
		gateway: gateway,
	}
}

// Generate 生成文本
func (h *Handler) Generate(c *fiber.Ctx) error {
	// 解析请求
	var req provider.GenerateRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
			"error": "Invalid request body",
		})
	}

	// 获取用户信息
	userID := auth.GetUserID(c)
	isPremium := auth.IsPremium(c)

	logger.Info("LLM generate request",
		zap.Int("user_id", userID),
		zap.String("model", req.Model),
		zap.Bool("stream", req.Stream),
		zap.Bool("is_premium", isPremium),
	)

	// 流式请求
	if req.Stream {
		return h.generateStream(c, &req)
	}

	// 普通请求
	resp, err := h.gateway.Generate(c.Context(), &req)
	if err != nil {
		logger.Error("Generate failed", zap.Error(err))
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"error": err.Error(),
		})
	}

	return c.JSON(resp)
}

// generateStream 流式生成
func (h *Handler) generateStream(c *fiber.Ctx, req *provider.GenerateRequest) error {
	// 设置 SSE 响应头
	c.Set("Content-Type", "text/event-stream")
	c.Set("Cache-Control", "no-cache")
	c.Set("Connection", "keep-alive")
	c.Set("Transfer-Encoding", "chunked")

	// 获取流式响应
	ch, err := h.gateway.GenerateStream(c.Context(), req)
	if err != nil {
		return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
			"error": err.Error(),
		})
	}

	// 发送流式响应
	c.Context().SetBodyStreamWriter(func(w *bufio.Writer) {
		for chunk := range ch {
			if chunk.Error != nil {
				logger.Error("Stream chunk error", zap.Error(chunk.Error))
				w.WriteString("data: {\"error\": \"" + chunk.Error.Error() + "\"}\n\n")
				w.Flush()
				break
			}

			// 发送数据
			data := "data: " + marshalChunk(chunk) + "\n\n"
			if _, err := w.WriteString(data); err != nil {
				logger.Error("Stream write error", zap.Error(err))
				break
			}

			// 刷新缓冲区
			if err := w.Flush(); err != nil {
				logger.Error("Stream flush error", zap.Error(err))
				break
			}

			// 结束标记
			if chunk.Done {
				w.WriteString("data: [DONE]\n\n")
				w.Flush()
				break
			}
		}
	})

	return nil
}

// HealthCheck 健康检查
func (h *Handler) HealthCheck(c *fiber.Ctx) error {
	results := h.gateway.HealthCheck(c.Context())

	allHealthy := true
	for _, err := range results {
		if err != nil {
			allHealthy = false
			break
		}
	}

	status := fiber.StatusOK
	if !allHealthy {
		status = fiber.StatusServiceUnavailable
	}

	return c.Status(status).JSON(fiber.Map{
		"status":    allHealthy,
		"providers": results,
	})
}

// GetStats 获取统计信息
func (h *Handler) GetStats(c *fiber.Ctx) error {
	stats := h.gateway.GetStats()
	return c.JSON(stats)
}

// marshalChunk 序列化流式块
func marshalChunk(chunk provider.StreamChunk) string {
	// 简化的 JSON 序列化
	if chunk.Done {
		return "{\"done\": true}"
	}
	return "{\"delta\": \"" + escapeJSON(chunk.Delta) + "\", \"done\": false}"
}

// escapeJSON 转义 JSON 字符串
func escapeJSON(s string) string {
	// 简单的转义实现
	result := ""
	for _, c := range s {
		switch c {
		case '"':
			result += "\\\""
		case '\\':
			result += "\\\\"
		case '\n':
			result += "\\n"
		case '\r':
			result += "\\r"
		case '\t':
			result += "\\t"
		default:
			result += string(c)
		}
	}
	return result
}
