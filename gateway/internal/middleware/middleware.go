package middleware

import (
	"time"

	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/arboris-novel/gateway/internal/metrics"
	"github.com/gofiber/fiber/v2"
	"go.uber.org/zap"
)

// RequestLogger 请求日志中间件
func RequestLogger() fiber.Handler {
	return func(c *fiber.Ctx) error {
		start := time.Now()
		path := c.Path()
		method := c.Method()

		// 处理请求
		err := c.Next()

		// 记录日志
		duration := time.Since(start)
		status := c.Response().StatusCode()

		logger.Info("HTTP request",
			zap.String("method", method),
			zap.String("path", path),
			zap.Int("status", status),
			zap.Duration("duration", duration),
			zap.String("ip", c.IP()),
			zap.String("user_agent", c.Get("User-Agent")),
		)

		// 记录 Prometheus 指标
		metrics.HTTPRequestsTotal.WithLabelValues(method, path, string(rune(status))).Inc()
		metrics.HTTPRequestDuration.WithLabelValues(method, path).Observe(duration.Seconds())

		return err
	}
}

// Recovery 恢复中间件
func Recovery() fiber.Handler {
	return func(c *fiber.Ctx) error {
		defer func() {
			if r := recover(); r != nil {
				logger.Error("Panic recovered",
					zap.Any("panic", r),
					zap.String("path", c.Path()),
					zap.String("method", c.Method()),
				)

				c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
					"error": "Internal server error",
				})
			}
		}()

		return c.Next()
	}
}

// CORS 跨域中间件
func CORS() fiber.Handler {
	return func(c *fiber.Ctx) error {
		c.Set("Access-Control-Allow-Origin", "*")
		c.Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		c.Set("Access-Control-Max-Age", "3600")

		if c.Method() == "OPTIONS" {
			return c.SendStatus(fiber.StatusNoContent)
		}

		return c.Next()
	}
}
