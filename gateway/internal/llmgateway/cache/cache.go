package cache

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"time"

	"github.com/arboris-novel/gateway/internal/llmgateway/provider"
	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// SemanticCache 语义缓存
type SemanticCache struct {
	redis               *redis.Client
	ttl                 time.Duration
	similarityThreshold float64
	enabled             bool

	// 统计
	hits   int64
	misses int64
}

// Config 缓存配置
type Config struct {
	Enabled             bool
	TTL                 time.Duration
	SimilarityThreshold float64
	MaxCacheSize        int
}

// NewSemanticCache 创建语义缓存
func NewSemanticCache(redisClient *redis.Client, config *Config) *SemanticCache {
	return &SemanticCache{
		redis:               redisClient,
		ttl:                 config.TTL,
		similarityThreshold: config.SimilarityThreshold,
		enabled:             config.Enabled,
	}
}

// Get 获取缓存
func (c *SemanticCache) Get(ctx context.Context, req *provider.GenerateRequest) (*provider.GenerateResponse, bool) {
	if !c.enabled {
		return nil, false
	}

	// 生成缓存键
	key := c.generateKey(req)

	// 从 Redis 获取
	data, err := c.redis.Get(ctx, key).Bytes()
	if err != nil {
		if err != redis.Nil {
			logger.Error("Cache get error", zap.Error(err))
		}
		c.misses++
		return nil, false
	}

	// 反序列化
	var resp provider.GenerateResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		logger.Error("Cache unmarshal error", zap.Error(err))
		c.misses++
		return nil, false
	}

	c.hits++
	logger.Debug("Cache hit",
		zap.String("key", key),
		zap.Int64("hits", c.hits),
	)

	return &resp, true
}

// Set 设置缓存
func (c *SemanticCache) Set(ctx context.Context, req *provider.GenerateRequest, resp *provider.GenerateResponse) error {
	if !c.enabled {
		return nil
	}

	// 生成缓存键
	key := c.generateKey(req)

	// 序列化
	data, err := json.Marshal(resp)
	if err != nil {
		return err
	}

	// 存入 Redis
	err = c.redis.Set(ctx, key, data, c.ttl).Err()
	if err != nil {
		logger.Error("Cache set error", zap.Error(err))
		return err
	}

	logger.Debug("Cache set",
		zap.String("key", key),
		zap.Duration("ttl", c.ttl),
	)

	return nil
}

// generateKey 生成缓存键
func (c *SemanticCache) generateKey(req *provider.GenerateRequest) string {
	// 构建缓存键的内容
	keyContent := struct {
		Model       string
		Messages    []provider.Message
		MaxTokens   int
		Temperature float64
	}{
		Model:       req.Model,
		Messages:    req.Messages,
		MaxTokens:   req.MaxTokens,
		Temperature: req.Temperature,
	}

	// 序列化
	data, _ := json.Marshal(keyContent)

	// 计算 SHA256 哈希
	hash := sha256.Sum256(data)
	hashStr := hex.EncodeToString(hash[:])

	return "llm_cache:" + hashStr
}

// Invalidate 失效缓存
func (c *SemanticCache) Invalidate(ctx context.Context, pattern string) error {
	if !c.enabled {
		return nil
	}

	// 扫描匹配的键
	var cursor uint64
	var keys []string

	for {
		var scanKeys []string
		var err error

		scanKeys, cursor, err = c.redis.Scan(ctx, cursor, pattern, 100).Result()
		if err != nil {
			return err
		}

		keys = append(keys, scanKeys...)

		if cursor == 0 {
			break
		}
	}

	// 删除键
	if len(keys) > 0 {
		err := c.redis.Del(ctx, keys...).Err()
		if err != nil {
			return err
		}

		logger.Info("Cache invalidated",
			zap.Int("count", len(keys)),
			zap.String("pattern", pattern),
		)
	}

	return nil
}

// GetStats 获取统计信息
func (c *SemanticCache) GetStats() CacheStats {
	total := c.hits + c.misses
	hitRate := 0.0
	if total > 0 {
		hitRate = float64(c.hits) / float64(total)
	}

	return CacheStats{
		Hits:    c.hits,
		Misses:  c.misses,
		HitRate: hitRate,
	}
}

// CacheStats 缓存统计
type CacheStats struct {
	Hits    int64
	Misses  int64
	HitRate float64
}

// Clear 清空缓存
func (c *SemanticCache) Clear(ctx context.Context) error {
	return c.Invalidate(ctx, "llm_cache:*")
}

// Warmup 预热缓存
func (c *SemanticCache) Warmup(ctx context.Context, requests []*provider.GenerateRequest) error {
	if !c.enabled {
		return nil
	}

	logger.Info("Starting cache warmup",
		zap.Int("count", len(requests)),
	)

	// TODO: 实现预热逻辑
	// 1. 批量生成响应
	// 2. 存入缓存

	return nil
}
