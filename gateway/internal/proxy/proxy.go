package proxy

import (
	"time"

	"github.com/arboris-novel/gateway/internal/config"
	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/proxy"
	"go.uber.org/zap"
)

// ReverseProxy 反向代理到 FastAPI
func ReverseProxy() fiber.Handler {
	cfg := config.Get()
	backendURL := cfg.Backend.FastAPIURL

	return func(c *fiber.Ctx) error {
		// 记录请求
		start := time.Now()
		path := c.Path()
		method := c.Method()

		// 转发请求到 FastAPI
		url := backendURL + path
		if len(c.Request().URI().QueryString()) > 0 {
			url += "?" + string(c.Request().URI().QueryString())
		}

		// 使用 Fiber 的 proxy 中间件
		err := proxy.Do(c, url)

		// 记录响应
		duration := time.Since(start)
		status := c.Response().StatusCode()

		logger.Info("Proxy request",
			zap.String("method", method),
			zap.String("path", path),
			zap.Int("status", status),
			zap.Duration("duration", duration),
		)

		if err != nil {
			logger.Error("Proxy error",
				zap.String("url", url),
				zap.Error(err),
			)
			return c.Status(fiber.StatusBadGateway).JSON(fiber.Map{
				"error": "后端服务暂时不可用",
			})
		}

		return nil
	}
}

// HealthCheck 健康检查
func HealthCheck() fiber.Handler {
	return func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{
			"status":  "ok",
			"service": "arboris-gateway",
			"time":    time.Now().Unix(),
		})
	}
}
