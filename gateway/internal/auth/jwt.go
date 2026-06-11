package auth

import (
	"errors"
	"strconv"
	"strings"
	"time"

	"github.com/arboris-novel/gateway/internal/config"
	"github.com/arboris-novel/gateway/pkg/models"
	"github.com/gofiber/fiber/v2"
	"github.com/golang-jwt/jwt/v5"
)

var (
	ErrMissingToken   = errors.New("missing authorization token")
	ErrInvalidToken   = errors.New("invalid token")
	ErrExpiredToken   = errors.New("token expired")
	ErrInvalidClaims  = errors.New("invalid token claims")
)

// JWTMiddleware JWT 认证中间件
func JWTMiddleware() fiber.Handler {
	return func(c *fiber.Ctx) error {
		// 从 Header 或 Cookie 中提取 token
		token := extractToken(c)
		if token == "" {
			return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
				"error": "未授权：缺少认证令牌",
			})
		}

		// 验证 token
		claims, err := ValidateToken(token)
		if err != nil {
			return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
				"error": "未授权：" + err.Error(),
			})
		}

		// 将用户信息存入上下文
		c.Locals("user_id", claims.UserID)
		c.Locals("username", claims.Username)
		c.Locals("is_premium", claims.IsPremium)
		c.Locals("is_admin", claims.IsAdmin)
		c.Locals("claims", claims)

		return c.Next()
	}
}

// OptionalJWTMiddleware 可选的 JWT 认证中间件（不强制要求 token）
func OptionalJWTMiddleware() fiber.Handler {
	return func(c *fiber.Ctx) error {
		token := extractToken(c)
		if token != "" {
			claims, err := ValidateToken(token)
			if err == nil {
				c.Locals("user_id", claims.UserID)
				c.Locals("username", claims.Username)
				c.Locals("is_premium", claims.IsPremium)
				c.Locals("is_admin", claims.IsAdmin)
				c.Locals("claims", claims)
			}
		}
		return c.Next()
	}
}

// extractToken 从请求中提取 token
func extractToken(c *fiber.Ctx) string {
	// 1. 从 Authorization Header 提取
	auth := c.Get("Authorization")
	if auth != "" {
		// Bearer token
		parts := strings.SplitN(auth, " ", 2)
		if len(parts) == 2 && strings.ToLower(parts[0]) == "bearer" {
			return parts[1]
		}
		// 直接是 token
		return auth
	}

	// 2. 从 Cookie 提取
	token := c.Cookies("access_token")
	if token != "" {
		return token
	}

	// 3. 从 Query 参数提取（用于 WebSocket）
	token = c.Query("token")
	if token != "" {
		return token
	}

	return ""
}

// ValidateToken 验证 JWT token
func ValidateToken(tokenString string) (*models.JWTClaims, error) {
	cfg := config.Get()

	// 解析 token
	token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
		// 验证签名算法
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, ErrInvalidToken
		}
		return []byte(cfg.JWT.Secret), nil
	})

	if err != nil {
		if errors.Is(err, jwt.ErrTokenExpired) {
			return nil, ErrExpiredToken
		}
		return nil, ErrInvalidToken
	}

	if !token.Valid {
		return nil, ErrInvalidToken
	}

	// 提取 claims
	claims, ok := token.Claims.(jwt.MapClaims)
	if !ok {
		return nil, ErrInvalidClaims
	}

	// 验证 issuer / audience：仅当网关配置了非空值时才强制校验，
	// 避免与签发方约定漂移导致全部 token 失效。
	if cfg.JWT.Issuer != "" {
		if iss, ok := claims["iss"].(string); !ok || iss != cfg.JWT.Issuer {
			return nil, ErrInvalidClaims
		}
	}
	if cfg.JWT.Audience != "" {
		if aud, ok := claims["aud"].(string); !ok || aud != cfg.JWT.Audience {
			return nil, ErrInvalidClaims
		}
	}

	// 构建 JWTClaims
	jwtClaims := &models.JWTClaims{}
	if iss, ok := claims["iss"].(string); ok {
		jwtClaims.Issuer = iss
	}
	if aud, ok := claims["aud"].(string); ok {
		jwtClaims.Audience = aud
	}

	if userID, ok := claims["user_id"].(float64); ok {
		jwtClaims.UserID = int(userID)
	} else if sub, ok := claims["sub"].(string); ok {
		// 兼容仅含 sub 的 token：sub 即 user_id
		if id, err := strconv.Atoi(sub); err == nil {
			jwtClaims.UserID = id
		}
	}
	if username, ok := claims["username"].(string); ok {
		jwtClaims.Username = username
	}
	if isPremium, ok := claims["is_premium"].(bool); ok {
		jwtClaims.IsPremium = isPremium
	}
	if isAdmin, ok := claims["is_admin"].(bool); ok {
		jwtClaims.IsAdmin = isAdmin
	}
	if exp, ok := claims["exp"].(float64); ok {
		jwtClaims.ExpiresAt = int64(exp)
	}
	if iat, ok := claims["iat"].(float64); ok {
		jwtClaims.IssuedAt = int64(iat)
	}

	// 验证过期时间
	if jwtClaims.ExpiresAt > 0 && time.Now().Unix() > jwtClaims.ExpiresAt {
		return nil, ErrExpiredToken
	}

	return jwtClaims, nil
}

// GetUserID 从上下文获取用户 ID
func GetUserID(c *fiber.Ctx) int {
	if userID, ok := c.Locals("user_id").(int); ok {
		return userID
	}
	return 0
}

// GetUsername 从上下文获取用户名
func GetUsername(c *fiber.Ctx) string {
	if username, ok := c.Locals("username").(string); ok {
		return username
	}
	return ""
}

// IsPremium 判断是否为 Premium 用户
func IsPremium(c *fiber.Ctx) bool {
	if isPremium, ok := c.Locals("is_premium").(bool); ok {
		return isPremium
	}
	return false
}

// IsAdmin 判断是否为管理员
func IsAdmin(c *fiber.Ctx) bool {
	if isAdmin, ok := c.Locals("is_admin").(bool); ok {
		return isAdmin
	}
	return false
}

// RequireAdmin 要求管理员权限的中间件
func RequireAdmin() fiber.Handler {
	return func(c *fiber.Ctx) error {
		if !IsAdmin(c) {
			return c.Status(fiber.StatusForbidden).JSON(fiber.Map{
				"error": "需要管理员权限",
			})
		}
		return c.Next()
	}
}
