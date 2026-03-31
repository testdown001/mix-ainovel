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

	// 分布式锁指标
	LockAcquired = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "distributed_lock_acquired_total",
			Help: "Total number of locks successfully acquired",
		},
		[]string{"key"},
	)

	LockReleased = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "distributed_lock_released_total",
			Help: "Total number of locks released",
		},
		[]string{"key"},
	)

	LockTimeouts = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "distributed_lock_timeouts_total",
			Help: "Total number of lock acquisition timeouts",
		},
		[]string{"key"},
	)

	LockErrors = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "distributed_lock_errors_total",
			Help: "Total number of lock errors",
		},
		[]string{"key", "operation"},
	)

	LockWaitDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "distributed_lock_wait_seconds",
			Help:    "Time spent waiting to acquire a lock",
			Buckets: []float64{0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5},
		},
		[]string{"key"},
	)

	// DB 连接池指标
	DBPoolOpenConnections = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "db_pool_open_connections",
			Help: "Number of open database connections",
		},
		[]string{"role"},
	)

	DBPoolIdleConnections = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "db_pool_idle_connections",
			Help: "Number of idle database connections",
		},
		[]string{"role"},
	)

	DBPoolWaitCount = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "db_pool_wait_total",
			Help: "Total number of connections waited for",
		},
		[]string{"role"},
	)

	DBPoolWaitDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "db_pool_wait_seconds",
			Help:    "Time spent waiting for a database connection",
			Buckets: []float64{0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1},
		},
		[]string{"role"},
	)

	// Webhook Worker Pool 指标
	WebhookProcessed = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "webhook_processed_total",
			Help: "Total number of webhook events processed successfully",
		},
	)

	WebhookFailed = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "webhook_failed_total",
			Help: "Total number of webhook events that failed processing",
		},
	)

	WebhookQueueDepth = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "webhook_queue_depth",
			Help: "Current number of webhook events in queue",
		},
	)

	WebhookProcessingDuration = prometheus.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "webhook_processing_duration_seconds",
			Help:    "Duration of webhook event processing",
			Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30},
		},
	)

	// 支付指标
	PaymentOrdersCreated = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "payment_orders_created_total",
			Help: "Total payment orders created",
		},
		[]string{"channel", "status"},
	)

	PaymentOrdersCompleted = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "payment_orders_completed_total",
			Help: "Total payment orders completed successfully",
		},
	)

	PaymentOrdersRefunded = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "payment_orders_refunded_total",
			Help: "Total payment orders refunded",
		},
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
		LockAcquired,
		LockReleased,
		LockTimeouts,
		LockErrors,
		LockWaitDuration,
		DBPoolOpenConnections,
		DBPoolIdleConnections,
		DBPoolWaitCount,
		DBPoolWaitDuration,
		WebhookProcessed,
		WebhookFailed,
		WebhookQueueDepth,
		WebhookProcessingDuration,
		PaymentOrdersCreated,
		PaymentOrdersCompleted,
		PaymentOrdersRefunded,
	)
}

// Handler Prometheus 指标处理器
func Handler() fiber.Handler {
	return adaptor.HTTPHandler(promhttp.Handler())
}
