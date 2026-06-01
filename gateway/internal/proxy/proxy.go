package proxy

import (
	"strconv"
	"time"

	"github.com/arboris-novel/gateway/internal/config"
	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/proxy"
	"go.uber.org/zap"
)

// 网关 → 下游 FastAPI 的"已校验身份"头。下游可信任这些头（前提：FastAPI 仅监听内网，
// 不直接对外暴露），从而避免在边缘与业务层重复解析 JWT。
const (
	headerGatewayVerified  = "X-Gateway-Verified"
	headerGatewayUserID    = "X-Gateway-User-Id"
	headerGatewayUsername  = "X-Gateway-Username"
	headerGatewayIsPremium = "X-Gateway-Is-Premium"
	headerGatewayIsAdmin   = "X-Gateway-Is-Admin"
)

// applyVerifiedIdentity 先剥离客户端可能伪造的 X-Gateway-* 头，
// 再用网关已校验（来自 OptionalJWTMiddleware 写入的 Locals）的身份覆盖写入。
func applyVerifiedIdentity(c *fiber.Ctx) {
	// 防伪造：无条件删除客户端传入的网关身份头
	c.Request().Header.Del(headerGatewayVerified)
	c.Request().Header.Del(headerGatewayUserID)
	c.Request().Header.Del(headerGatewayUsername)
	c.Request().Header.Del(headerGatewayIsPremium)
	c.Request().Header.Del(headerGatewayIsAdmin)

	userID, ok := c.Locals("user_id").(int)
	if !ok || userID <= 0 {
		return // 未携带有效 JWT（OptionalJWT 允许匿名），不注入身份
	}
	c.Request().Header.Set(headerGatewayVerified, "1")
	c.Request().Header.Set(headerGatewayUserID, strconv.Itoa(userID))
	if username, ok := c.Locals("username").(string); ok && username != "" {
		c.Request().Header.Set(headerGatewayUsername, username)
	}
	if isPremium, ok := c.Locals("is_premium").(bool); ok {
		c.Request().Header.Set(headerGatewayIsPremium, strconv.FormatBool(isPremium))
	}
	if isAdmin, ok := c.Locals("is_admin").(bool); ok {
		c.Request().Header.Set(headerGatewayIsAdmin, strconv.FormatBool(isAdmin))
	}
}

// ReverseProxy 反向代理到 FastAPI
func ReverseProxy() fiber.Handler {
	cfg := config.Get()
	backendURL := cfg.Backend.FastAPIURL

	return func(c *fiber.Ctx) error {
		// 记录请求
		start := time.Now()
		path := c.Path()
		method := c.Method()

		// 透传网关已校验身份（并剥离客户端伪造头）
		applyVerifiedIdentity(c)

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
