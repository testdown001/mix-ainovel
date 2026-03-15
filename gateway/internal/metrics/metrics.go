package metrics

import (
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/adaptor"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	// HTTP 请求总数
	HTTPRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests",
		},
		[]string{"method", "path", "status"},
	)

	// HTTP 请求延迟
	HTTPRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request latency in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "path"},
	)

	// WebSocket 连接数
	WebSocketConnections = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "websocket_connections",
			Help: "Current number of WebSocket connections",
		},
	)

	// 限流触发次数
	RateLimitHits = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "rate_limit_hits_total",
			Help: "Total number of rate limit hits",
		},
		[]string{"type", "user_type"},
	)

	// 代理错误次数
	ProxyErrors = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "proxy_errors_total",
			Help: "Total number of proxy errors",
		},
		[]string{"backend"},
	)
)

// Init 初始化 Prometheus 指标
func Init() {
	prometheus.MustRegister(
		HTTPRequestsTotal,
		HTTPRequestDuration,
		WebSocketConnections,
		RateLimitHits,
		ProxyErrors,
	)
}

// Handler Prometheus 指标处理器
func Handler() fiber.Handler {
	return adaptor.HTTPHandler(promhttp.Handler())
}
