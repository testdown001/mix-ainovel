package router

import (
	"context"
	"errors"
	"math/rand"
	"sync"
	"sync/atomic"
	"time"

	"github.com/arboris-novel/gateway/internal/llmgateway/provider"
	"github.com/arboris-novel/gateway/internal/logger"
	"go.uber.org/zap"
)

// Router 模型路由器
type Router struct {
	providers       map[string]provider.Provider
	defaultProvider string
	fallbackEnabled bool
	strategy        LoadBalanceStrategy

	// 负载均衡状态
	roundRobinIndex uint32
	latencyStats    sync.Map // map[string]*LatencyStats
}

// LoadBalanceStrategy 负载均衡策略
type LoadBalanceStrategy string

const (
	RoundRobin   LoadBalanceStrategy = "round_robin"
	LeastLatency LoadBalanceStrategy = "least_latency"
	Random       LoadBalanceStrategy = "random"
)

// LatencyStats 延迟统计
type LatencyStats struct {
	avgLatency time.Duration
	requestCount uint64
	mu sync.RWMutex
}

// NewRouter 创建路由器
func NewRouter(defaultProvider string, fallbackEnabled bool, strategy LoadBalanceStrategy) *Router {
	return &Router{
		providers:       make(map[string]provider.Provider),
		defaultProvider: defaultProvider,
		fallbackEnabled: fallbackEnabled,
		strategy:        strategy,
	}
}

// RegisterProvider 注册 Provider
func (r *Router) RegisterProvider(p provider.Provider) {
	r.providers[p.Name()] = p
	r.latencyStats.Store(p.Name(), &LatencyStats{})

	logger.Info("Registered LLM provider",
		zap.String("provider", p.Name()),
		zap.Strings("models", p.GetModels()),
	)
}

// Route 路由请求到合适的 Provider
func (r *Router) Route(ctx context.Context, req *provider.GenerateRequest) (*provider.GenerateResponse, error) {
	// 1. 尝试默认 Provider
	p := r.getProvider(r.defaultProvider)
	if p == nil {
		return nil, errors.New("default provider not found")
	}

	start := time.Now()
	resp, err := p.Generate(ctx, req)

	if err == nil {
		// 记录延迟
		r.recordLatency(p.Name(), time.Since(start))
		return resp, nil
	}

	logger.Warn("Default provider failed",
		zap.String("provider", p.Name()),
		zap.Error(err),
	)

	// 2. 如果启用了 fallback，尝试备用 Provider
	if !r.fallbackEnabled {
		return nil, err
	}

	// 获取备用 Provider
	fallbackProvider := r.selectFallbackProvider(p.Name())
	if fallbackProvider == nil {
		return nil, errors.New("no fallback provider available")
	}

	logger.Info("Trying fallback provider",
		zap.String("fallback", fallbackProvider.Name()),
	)

	start = time.Now()
	resp, err = fallbackProvider.Generate(ctx, req)

	if err == nil {
		r.recordLatency(fallbackProvider.Name(), time.Since(start))
	}

	return resp, err
}

// RouteStream 路由流式请求
func (r *Router) RouteStream(ctx context.Context, req *provider.GenerateRequest) (<-chan provider.StreamChunk, error) {
	p := r.getProvider(r.defaultProvider)
	if p == nil {
		return nil, errors.New("default provider not found")
	}

	ch, err := p.GenerateStream(ctx, req)
	if err != nil && r.fallbackEnabled {
		// 尝试 fallback
		fallbackProvider := r.selectFallbackProvider(p.Name())
		if fallbackProvider != nil {
			logger.Info("Trying fallback provider for stream",
				zap.String("fallback", fallbackProvider.Name()),
			)
			return fallbackProvider.GenerateStream(ctx, req)
		}
	}

	return ch, err
}

// getProvider 获取 Provider
func (r *Router) getProvider(name string) provider.Provider {
	return r.providers[name]
}

// selectFallbackProvider 选择备用 Provider
func (r *Router) selectFallbackProvider(excludeName string) provider.Provider {
	var candidates []provider.Provider

	for name, p := range r.providers {
		if name != excludeName {
			candidates = append(candidates, p)
		}
	}

	if len(candidates) == 0 {
		return nil
	}

	switch r.strategy {
	case RoundRobin:
		return r.selectRoundRobin(candidates)
	case LeastLatency:
		return r.selectLeastLatency(candidates)
	case Random:
		return r.selectRandom(candidates)
	default:
		return candidates[0]
	}
}

// selectRoundRobin 轮询选择
func (r *Router) selectRoundRobin(candidates []provider.Provider) provider.Provider {
	index := atomic.AddUint32(&r.roundRobinIndex, 1)
	return candidates[int(index)%len(candidates)]
}

// selectLeastLatency 选择延迟最低的
func (r *Router) selectLeastLatency(candidates []provider.Provider) provider.Provider {
	var best provider.Provider
	var minLatency time.Duration = time.Hour

	for _, p := range candidates {
		if stats, ok := r.latencyStats.Load(p.Name()); ok {
			latencyStats := stats.(*LatencyStats)
			latencyStats.mu.RLock()
			avgLatency := latencyStats.avgLatency
			latencyStats.mu.RUnlock()

			if avgLatency < minLatency {
				minLatency = avgLatency
				best = p
			}
		}
	}

	if best == nil {
		return candidates[0]
	}

	return best
}

// selectRandom 随机选择
func (r *Router) selectRandom(candidates []provider.Provider) provider.Provider {
	return candidates[rand.Intn(len(candidates))]
}

// recordLatency 记录延迟
func (r *Router) recordLatency(providerName string, latency time.Duration) {
	if stats, ok := r.latencyStats.Load(providerName); ok {
		latencyStats := stats.(*LatencyStats)
		latencyStats.mu.Lock()
		defer latencyStats.mu.Unlock()

		// 计算移动平均
		count := atomic.AddUint64(&latencyStats.requestCount, 1)
		if count == 1 {
			latencyStats.avgLatency = latency
		} else {
			// 指数移动平均 (EMA)
			alpha := 0.2
			latencyStats.avgLatency = time.Duration(
				float64(latencyStats.avgLatency)*(1-alpha) + float64(latency)*alpha,
			)
		}
	}
}

// GetStats 获取统计信息
func (r *Router) GetStats() map[string]RouterStats {
	stats := make(map[string]RouterStats)

	r.latencyStats.Range(func(key, value interface{}) bool {
		name := key.(string)
		latencyStats := value.(*LatencyStats)

		latencyStats.mu.RLock()
		stats[name] = RouterStats{
			Provider:     name,
			AvgLatency:   latencyStats.avgLatency,
			RequestCount: atomic.LoadUint64(&latencyStats.requestCount),
		}
		latencyStats.mu.RUnlock()

		return true
	})

	return stats
}

// RouterStats 路由统计
type RouterStats struct {
	Provider     string
	AvgLatency   time.Duration
	RequestCount uint64
}

// HealthCheck 健康检查所有 Provider
func (r *Router) HealthCheck(ctx context.Context) map[string]error {
	results := make(map[string]error)

	for name, p := range r.providers {
		err := p.HealthCheck(ctx)
		results[name] = err

		if err != nil {
			logger.Warn("Provider health check failed",
				zap.String("provider", name),
				zap.Error(err),
			)
		}
	}

	return results
}
