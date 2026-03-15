package llmgateway

import (
	"context"
	"time"

	"github.com/arboris-novel/gateway/internal/llmgateway/cache"
	"github.com/arboris-novel/gateway/internal/llmgateway/pool"
	"github.com/arboris-novel/gateway/internal/llmgateway/provider"
	"github.com/arboris-novel/gateway/internal/llmgateway/retry"
	"github.com/arboris-novel/gateway/internal/llmgateway/router"
	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// Gateway LLM Gateway
type Gateway struct {
	router     *router.Router
	cache      *cache.SemanticCache
	pool       *pool.ConnectionPool
	retryStrategy *retry.Strategy
}

// Config Gateway 配置
type Config struct {
	Pool          *pool.PoolConfig
	Retry         *retry.Strategy
	Cache         *cache.Config
	Router        *RouterConfig
	Providers     []ProviderConfig
}

// RouterConfig 路由配置
type RouterConfig struct {
	DefaultProvider string
	FallbackEnabled bool
	Strategy        router.LoadBalanceStrategy
}

// ProviderConfig Provider 配置
type ProviderConfig struct {
	Name     string
	Type     string // openai, anthropic, ollama
	APIKey   string
	BaseURL  string
	Timeout  time.Duration
	Models   []string
	MaxTokens int
}

// NewGateway 创建 Gateway
func NewGateway(cfg *Config, redisClient *redis.Client) (*Gateway, error) {
	// 创建连接池
	connPool := pool.NewConnectionPool(cfg.Pool)

	// 创建路由器
	rt := router.NewRouter(
		cfg.Router.DefaultProvider,
		cfg.Router.FallbackEnabled,
		cfg.Router.Strategy,
	)

	// 注册 Providers
	for _, providerCfg := range cfg.Providers {
		p, err := createProvider(providerCfg, connPool)
		if err != nil {
			logger.Error("Failed to create provider",
				zap.String("provider", providerCfg.Name),
				zap.Error(err),
			)
			continue
		}
		rt.RegisterProvider(p)
	}

	// 创建缓存
	semanticCache := cache.NewSemanticCache(redisClient, cfg.Cache)

	return &Gateway{
		router:        rt,
		cache:         semanticCache,
		pool:          connPool,
		retryStrategy: cfg.Retry,
	}, nil
}

// Generate 生成文本
func (g *Gateway) Generate(ctx context.Context, req *provider.GenerateRequest) (*provider.GenerateResponse, error) {
	// 1. 尝试从缓存获取
	if cached, hit := g.cache.Get(ctx, req); hit {
		logger.Debug("Cache hit for generate request")
		return cached, nil
	}

	// 2. 带重试的生成
	resp, err := retry.DoWithResult(ctx, g.retryStrategy, func() (*provider.GenerateResponse, error) {
		return g.router.Route(ctx, req)
	})

	if err != nil {
		return nil, err
	}

	// 3. 存入缓存
	if err := g.cache.Set(ctx, req, resp); err != nil {
		logger.Warn("Failed to cache response", zap.Error(err))
	}

	return resp, nil
}

// GenerateStream 流式生成文本
func (g *Gateway) GenerateStream(ctx context.Context, req *provider.GenerateRequest) (<-chan provider.StreamChunk, error) {
	// 流式请求不使用缓存
	return g.router.RouteStream(ctx, req)
}

// HealthCheck 健康检查
func (g *Gateway) HealthCheck(ctx context.Context) map[string]error {
	return g.router.HealthCheck(ctx)
}

// GetStats 获取统计信息
func (g *Gateway) GetStats() Stats {
	return Stats{
		Router: g.router.GetStats(),
		Cache:  g.cache.GetStats(),
		Pool:   g.pool.GetStats(),
	}
}

// Stats 统计信息
type Stats struct {
	Router map[string]router.RouterStats
	Cache  cache.CacheStats
	Pool   []pool.Stats
}

// Close 关闭 Gateway
func (g *Gateway) Close() {
	g.pool.Close()
}

// createProvider 创建 Provider
func createProvider(cfg ProviderConfig, connPool *pool.ConnectionPool) (provider.Provider, error) {
	client := connPool.GetClient(cfg.Name)

	providerCfg := &provider.ProviderConfig{
		Name:      cfg.Name,
		APIKey:    cfg.APIKey,
		BaseURL:   cfg.BaseURL,
		Timeout:   cfg.Timeout,
		Models:    cfg.Models,
		MaxTokens: cfg.MaxTokens,
	}

	switch cfg.Type {
	case "openai":
		return provider.NewOpenAIProvider(providerCfg, client), nil
	// TODO: 添加其他 Provider
	// case "anthropic":
	//     return provider.NewAnthropicProvider(providerCfg, client), nil
	// case "ollama":
	//     return provider.NewOllamaProvider(providerCfg, client), nil
	default:
		return provider.NewOpenAIProvider(providerCfg, client), nil
	}
}
