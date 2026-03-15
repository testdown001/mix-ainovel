package pool

import (
	"context"
	"crypto/tls"
	"net"
	"net/http"
	"sync"
	"time"

	"github.com/arboris-novel/gateway/internal/logger"
	"go.uber.org/zap"
)

// ConnectionPool HTTP/2 连接池
type ConnectionPool struct {
	clients sync.Map // map[string]*http.Client (provider -> client)
	config  *PoolConfig
}

// PoolConfig 连接池配置
type PoolConfig struct {
	MaxIdleConns        int
	MaxConnsPerHost     int
	IdleConnTimeout     time.Duration
	TLSHandshakeTimeout time.Duration
	ExpectContinueTimeout time.Duration
}

// NewConnectionPool 创建连接池
func NewConnectionPool(config *PoolConfig) *ConnectionPool {
	return &ConnectionPool{
		config: config,
	}
}

// GetClient 获取或创建 HTTP 客户端
func (p *ConnectionPool) GetClient(provider string) *http.Client {
	// 尝试从缓存获取
	if client, ok := p.clients.Load(provider); ok {
		return client.(*http.Client)
	}

	// 创建新客户端
	client := p.createClient()

	// 存储到缓存
	actual, loaded := p.clients.LoadOrStore(provider, client)
	if loaded {
		// 已经有其他 goroutine 创建了，使用已有的
		return actual.(*http.Client)
	}

	logger.Info("Created new HTTP client",
		zap.String("provider", provider),
	)

	return client
}

// createClient 创建 HTTP 客户端
func (p *ConnectionPool) createClient() *http.Client {
	// 自定义 Transport，启用 HTTP/2
	transport := &http.Transport{
		// 连接池配置
		MaxIdleConns:        p.config.MaxIdleConns,
		MaxIdleConnsPerHost: p.config.MaxConnsPerHost,
		MaxConnsPerHost:     p.config.MaxConnsPerHost,
		IdleConnTimeout:     p.config.IdleConnTimeout,

		// TLS 配置
		TLSHandshakeTimeout: p.config.TLSHandshakeTimeout,
		TLSClientConfig: &tls.Config{
			MinVersion: tls.VersionTLS12,
		},

		// HTTP/2 配置
		ForceAttemptHTTP2:     true,
		ExpectContinueTimeout: p.config.ExpectContinueTimeout,

		// 连接配置
		DialContext: (&net.Dialer{
			Timeout:   30 * time.Second,
			KeepAlive: 30 * time.Second,
		}).DialContext,

		// 响应头超时
		ResponseHeaderTimeout: 10 * time.Second,
	}

	return &http.Client{
		Transport: transport,
		Timeout:   0, // 不设置全局超时，由每个请求单独控制
	}
}

// HealthCheck 健康检查
func (p *ConnectionPool) HealthCheck(ctx context.Context, provider, url string) error {
	client := p.GetClient(provider)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return err
	}

	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 500 {
		return &HealthCheckError{
			Provider:   provider,
			StatusCode: resp.StatusCode,
		}
	}

	return nil
}

// Close 关闭连接池
func (p *ConnectionPool) Close() {
	p.clients.Range(func(key, value interface{}) bool {
		client := value.(*http.Client)
		if transport, ok := client.Transport.(*http.Transport); ok {
			transport.CloseIdleConnections()
		}
		return true
	})
}

// HealthCheckError 健康检查错误
type HealthCheckError struct {
	Provider   string
	StatusCode int
}

func (e *HealthCheckError) Error() string {
	return "health check failed for provider " + e.Provider
}

// Stats 连接池统计
type Stats struct {
	ActiveClients int
	Provider      string
}

// GetStats 获取统计信息
func (p *ConnectionPool) GetStats() []Stats {
	var stats []Stats
	p.clients.Range(func(key, value interface{}) bool {
		stats = append(stats, Stats{
			Provider:      key.(string),
			ActiveClients: 1,
		})
		return true
	})
	return stats
}
