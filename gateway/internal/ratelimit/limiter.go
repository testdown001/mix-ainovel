package ratelimit

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/arboris-novel/gateway/internal/config"
	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/arboris-novel/gateway/pkg/models"
	"github.com/gofiber/fiber/v2"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// Limiter 限流器
type Limiter struct {
	redis      *redis.Client
	config     *config.RateLimitConfig
	semaphores sync.Map // map[int]*semaphore (user_id -> semaphore)
}

// semaphore 并发槽控制
type semaphore struct {
	ch chan struct{}
}

func newSemaphore(size int) *semaphore {
	return &semaphore{
		ch: make(chan struct{}, size),
	}
}

func (s *semaphore) Acquire() bool {
	select {
	case s.ch <- struct{}{}:
		return true
	default:
		return false
	}
}

func (s *semaphore) Release() {
	select {
	case <-s.ch:
	default:
	}
}

// NewLimiter 创建限流器
func NewLimiter(redisClient *redis.Client, cfg *config.RateLimitConfig) *Limiter {
	return &Limiter{
		redis:  redisClient,
		config: cfg,
	}
}

// Middleware 限流中间件
func (l *Limiter) Middleware() fiber.Handler {
	return func(c *fiber.Ctx) error {
		// 获取用户信息
		userID, ok := c.Locals("user_id").(int)
		if !ok || userID == 0 {
			// 未认证用户，使用 IP 限流
			return l.checkIPRateLimit(c)
		}

		isPremium, _ := c.Locals("is_premium").(bool)
		isAdmin, _ := c.Locals("is_admin").(bool)

		// 管理员不限流
		if isAdmin {
			return c.Next()
		}

		// 获取限流配置
		info := l.getRateLimitInfo(isPremium)

		// 1. 检查并发槽
		if !l.acquireConcurrentSlot(userID, info.Concurrent) {
			return c.Status(fiber.StatusTooManyRequests).JSON(fiber.Map{
				"error": fmt.Sprintf("并发请求数超限，最多 %d 个并发请求", info.Concurrent),
			})
		}
		defer l.releaseConcurrentSlot(userID)

		// 2. 检查 RPM (Requests Per Minute)
		if !l.checkRPM(c.Context(), userID, info.RPM) {
			return c.Status(fiber.StatusTooManyRequests).JSON(fiber.Map{
				"error": fmt.Sprintf("请求频率超限，最多 %d 请求/分钟", info.RPM),
			})
		}

		// 3. 检查 RPS (Requests Per Second)
		if !l.checkRPS(c.Context(), userID, info.RPS) {
			return c.Status(fiber.StatusTooManyRequests).JSON(fiber.Map{
				"error": fmt.Sprintf("请求频率超限，最多 %d 请求/秒", info.RPS),
			})
		}

		return c.Next()
	}
}

// getRateLimitInfo 获取限流配置
func (l *Limiter) getRateLimitInfo(isPremium bool) models.RateLimitInfo {
	if isPremium {
		return models.RateLimitInfo{
			TPM:        l.config.PremiumTPM,
			Concurrent: l.config.PremiumConcurrent,
			RPM:        l.config.PremiumRPM,
			RPS:        l.config.PremiumRPS,
		}
	}
	return models.RateLimitInfo{
		TPM:        l.config.DefaultTPM,
		Concurrent: l.config.DefaultConcurrent,
		RPM:        l.config.DefaultRPM,
		RPS:        l.config.DefaultRPS,
	}
}

// acquireConcurrentSlot 获取并发槽
func (l *Limiter) acquireConcurrentSlot(userID, maxConcurrent int) bool {
	// 获取或创建 semaphore
	val, _ := l.semaphores.LoadOrStore(userID, newSemaphore(maxConcurrent))
	sem := val.(*semaphore)
	return sem.Acquire()
}

// releaseConcurrentSlot 释放并发槽
func (l *Limiter) releaseConcurrentSlot(userID int) {
	if val, ok := l.semaphores.Load(userID); ok {
		sem := val.(*semaphore)
		sem.Release()
	}
}

// checkRPM 检查每分钟请求数
func (l *Limiter) checkRPM(ctx context.Context, userID, limit int) bool {
	key := fmt.Sprintf("ratelimit:rpm:%d", userID)
	return l.checkRedisLimit(ctx, key, limit, time.Minute)
}

// checkRPS 检查每秒请求数
func (l *Limiter) checkRPS(ctx context.Context, userID, limit int) bool {
	key := fmt.Sprintf("ratelimit:rps:%d", userID)
	return l.checkRedisLimit(ctx, key, limit, time.Second)
}

// checkRedisLimit 使用 Redis 检查限流
func (l *Limiter) checkRedisLimit(ctx context.Context, key string, limit int, window time.Duration) bool {
	// 使用 Redis INCR + EXPIRE 实现滑动窗口限流
	pipe := l.redis.Pipeline()
	incr := pipe.Incr(ctx, key)
	pipe.Expire(ctx, key, window)

	_, err := pipe.Exec(ctx)
	if err != nil {
		logger.Error("Redis rate limit check failed", zap.Error(err))
		// Redis 失败时放行（避免影响服务）
		return true
	}

	count := incr.Val()
	return count <= int64(limit)
}

// checkIPRateLimit 基于 IP 的限流（未认证用户）
func (l *Limiter) checkIPRateLimit(c *fiber.Ctx) error {
	ip := c.IP()
	key := fmt.Sprintf("ratelimit:ip:%s", ip)

	// 未认证用户限制更严格：120 req/min
	if !l.checkRedisLimit(c.Context(), key, 120, time.Minute) {
		return c.Status(fiber.StatusTooManyRequests).JSON(fiber.Map{
			"error": "请求频率超限，请登录后继续使用",
		})
	}

	return c.Next()
}

// CheckTPM 检查 Token 消耗限流（用于 LLM 调用）
func (l *Limiter) CheckTPM(ctx context.Context, userID int, tokens int, isPremium bool) bool {
	info := l.getRateLimitInfo(isPremium)
	key := fmt.Sprintf("ratelimit:tpm:%d", userID)

	// 获取当前消耗
	val, err := l.redis.Get(ctx, key).Int()
	if err != nil && err != redis.Nil {
		logger.Error("Redis TPM check failed", zap.Error(err))
		return true // Redis 失败时放行
	}

	// 检查是否超限
	if val+tokens > info.TPM {
		return false
	}

	// 增加消耗
	pipe := l.redis.Pipeline()
	pipe.IncrBy(ctx, key, int64(tokens))
	pipe.Expire(ctx, key, time.Minute)
	_, err = pipe.Exec(ctx)

	if err != nil {
		logger.Error("Redis TPM increment failed", zap.Error(err))
	}

	return true
}
