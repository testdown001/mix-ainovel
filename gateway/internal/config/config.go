package config

import (
	"strings"
	"time"

	"github.com/spf13/viper"
)

// Config 全局配置
type Config struct {
	Server         ServerConfig         `mapstructure:"server"`
	Backend        BackendConfig        `mapstructure:"backend"`
	JWT            JWTConfig            `mapstructure:"jwt"`
	Redis          RedisConfig          `mapstructure:"redis"`
	Database       DatabaseConfig       `mapstructure:"database"`
	Payment        PaymentGatewayConfig `mapstructure:"payment"`
	RateLimit      RateLimitConfig      `mapstructure:"rate_limit"`
	WebSocket      WebSocketConfig      `mapstructure:"websocket"`
	TaskDispatcher TaskDispatcherConfig `mapstructure:"task_dispatcher"`
	Log            LogConfig            `mapstructure:"log"`
	Metrics        MetricsConfig        `mapstructure:"metrics"`
	CORS           CORSConfig           `mapstructure:"cors"`
}

// CORSConfig 跨域配置。Origins 为空或包含 "*" 时按通配处理；
// 否则仅当请求 Origin 命中白名单才回显该 Origin（与 Python 端 CORS 收紧保持一致）。
type CORSConfig struct {
	Origins []string `mapstructure:"origins"`
}

type PaymentGatewayConfig struct {
	Enabled             bool   `mapstructure:"enabled"`
	StripeSecretKey     string `mapstructure:"stripe_secret_key"`
	StripeWebhookSecret string `mapstructure:"stripe_webhook_secret"`
	SuccessURL          string `mapstructure:"success_url"`
	CancelURL           string `mapstructure:"cancel_url"`
	WebhookWorkers      int    `mapstructure:"webhook_workers"`
	WebhookQueueSize    int    `mapstructure:"webhook_queue_size"`
}

type ServerConfig struct {
	Host         string        `mapstructure:"host"`
	Port         int           `mapstructure:"port"`
	ReadTimeout  time.Duration `mapstructure:"read_timeout"`
	WriteTimeout time.Duration `mapstructure:"write_timeout"`
	Prefork      bool          `mapstructure:"prefork"`
}

type BackendConfig struct {
	FastAPIURL string        `mapstructure:"fastapi_url"`
	Timeout    time.Duration `mapstructure:"timeout"`
}

type JWTConfig struct {
	Secret   string `mapstructure:"secret"`
	Issuer   string `mapstructure:"issuer"`
	Audience string `mapstructure:"audience"`
}

type RedisConfig struct {
	Mode          string   `mapstructure:"mode"` // standalone | sentinel | cluster
	Addr          string   `mapstructure:"addr"`
	Addrs         []string `mapstructure:"addrs"`
	Password      string   `mapstructure:"password"`
	DB            int      `mapstructure:"db"`
	PoolSize      int      `mapstructure:"pool_size"`
	MinIdle       int      `mapstructure:"min_idle"`
	MasterName    string   `mapstructure:"master_name"`
	SentinelAddrs []string `mapstructure:"sentinel_addrs"`
}

type DatabaseConfig struct {
	Enabled  bool   `mapstructure:"enabled"`
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	User     string `mapstructure:"user"`
	Password string `mapstructure:"password"`
	Name     string `mapstructure:"name"`

	ReadHosts []string `mapstructure:"read_hosts"`

	WriterMaxOpen     int           `mapstructure:"writer_max_open"`
	WriterMaxIdle     int           `mapstructure:"writer_max_idle"`
	WriterMaxLifetime time.Duration `mapstructure:"writer_max_lifetime"`
	WriterMaxIdleTime time.Duration `mapstructure:"writer_max_idle_time"`

	ReaderMaxOpen     int           `mapstructure:"reader_max_open"`
	ReaderMaxIdle     int           `mapstructure:"reader_max_idle"`
	ReaderMaxLifetime time.Duration `mapstructure:"reader_max_lifetime"`
	ReaderMaxIdleTime time.Duration `mapstructure:"reader_max_idle_time"`

	SlowThreshold time.Duration `mapstructure:"slow_threshold"`
	LogLevel      string        `mapstructure:"log_level"`
}

type RateLimitConfig struct {
	DefaultTPM        int `mapstructure:"default_tpm"`
	DefaultConcurrent int `mapstructure:"default_concurrent"`
	DefaultRPM        int `mapstructure:"default_rpm"`
	DefaultRPS        int `mapstructure:"default_rps"`
	PremiumTPM        int `mapstructure:"premium_tpm"`
	PremiumConcurrent int `mapstructure:"premium_concurrent"`
	PremiumRPM        int `mapstructure:"premium_rpm"`
	PremiumRPS        int `mapstructure:"premium_rps"`
	// UnauthIPRPM 未认证用户按 IP 的每分钟请求上限（登录前无 JWT 时走此桶）。
	// 默认 120；为 0/未配置时 limiter 回退到 120，避免锁死所有未登录流量。
	UnauthIPRPM int `mapstructure:"unauth_ip_rpm"`
}

type WebSocketConfig struct {
	MaxConnections  int           `mapstructure:"max_connections"`
	ReadBufferSize  int           `mapstructure:"read_buffer_size"`
	WriteBufferSize int           `mapstructure:"write_buffer_size"`
	PingInterval    time.Duration `mapstructure:"ping_interval"`
	PongTimeout     time.Duration `mapstructure:"pong_timeout"`
}

type LogConfig struct {
	Level    string `mapstructure:"level"`
	Format   string `mapstructure:"format"`
	Output   string `mapstructure:"output"`
	FilePath string `mapstructure:"file_path"`
}

type MetricsConfig struct {
	Enabled bool   `mapstructure:"enabled"`
	Path    string `mapstructure:"path"`
}

type TaskDispatcherConfig struct {
	Enabled           bool          `mapstructure:"enabled"`
	MaxConcurrency    int           `mapstructure:"max_concurrency"`
	MaxPerUser        int           `mapstructure:"max_per_user"`
	DefaultTimeout    time.Duration `mapstructure:"default_timeout"`
	BatchTimeout      time.Duration `mapstructure:"batch_timeout"`
	BlueprintTimeout  time.Duration `mapstructure:"blueprint_timeout"`
	MaxRetries        int           `mapstructure:"max_retries"`
	RetryDelay        time.Duration `mapstructure:"retry_delay"`
	PollInterval      time.Duration `mapstructure:"poll_interval"`
	WorkerCallbackURL string        `mapstructure:"worker_callback_url"`
	WorkerGRPCAddr    string        `mapstructure:"worker_grpc_addr"`
	// InternalCallbackSecret 内部回调共享密钥；为空则不校验（向后兼容），
	// 非空时 Worker 进度回调须携带匹配的 X-Internal-Secret 头。
	InternalCallbackSecret string `mapstructure:"internal_callback_secret"`
}

var globalConfig *Config

// Load 加载配置文件
func Load(configPath string) (*Config, error) {
	viper.Reset()
	viper.SetConfigFile(configPath)
	viper.SetConfigType("yaml")

	// 设置默认值
	setDefaults()
	bindEnvOverrides()

	// 读取配置文件
	if err := viper.ReadInConfig(); err != nil {
		return nil, err
	}

	// 解析配置
	var cfg Config
	if err := viper.Unmarshal(&cfg); err != nil {
		return nil, err
	}

	globalConfig = &cfg
	return &cfg, nil
}

// Get 获取全局配置
func Get() *Config {
	return globalConfig
}

func bindEnvOverrides() {
	viper.SetEnvPrefix("GATEWAY")
	viper.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	viper.AutomaticEnv()

	for _, key := range []string{
		"server.host",
		"server.port",
		"server.read_timeout",
		"server.write_timeout",
		"server.prefork",
		"backend.fastapi_url",
		"backend.timeout",
		"jwt.secret",
		"jwt.issuer",
		"jwt.audience",
		"redis.mode",
		"redis.addr",
		"redis.addrs",
		"redis.password",
		"redis.db",
		"redis.pool_size",
		"redis.min_idle",
		"redis.master_name",
		"redis.sentinel_addrs",
		"database.enabled",
		"database.host",
		"database.port",
		"database.user",
		"database.password",
		"database.name",
		"database.read_hosts",
		"database.writer_max_open",
		"database.writer_max_idle",
		"database.writer_max_lifetime",
		"database.writer_max_idle_time",
		"database.reader_max_open",
		"database.reader_max_idle",
		"database.reader_max_lifetime",
		"database.reader_max_idle_time",
		"database.slow_threshold",
		"database.log_level",
		"payment.enabled",
		"payment.stripe_secret_key",
		"payment.stripe_webhook_secret",
		"payment.success_url",
		"payment.cancel_url",
		"payment.webhook_workers",
		"payment.webhook_queue_size",
		"rate_limit.default_tpm",
		"rate_limit.default_concurrent",
		"rate_limit.default_rpm",
		"rate_limit.default_rps",
		"rate_limit.premium_tpm",
		"rate_limit.premium_concurrent",
		"rate_limit.premium_rpm",
		"rate_limit.premium_rps",
		"rate_limit.unauth_ip_rpm",
		"websocket.max_connections",
		"websocket.read_buffer_size",
		"websocket.write_buffer_size",
		"websocket.ping_interval",
		"websocket.pong_timeout",
		"log.level",
		"log.format",
		"log.output",
		"log.file_path",
		"metrics.enabled",
		"metrics.path",
		"cors.origins",
		"task_dispatcher.enabled",
		"task_dispatcher.max_concurrency",
		"task_dispatcher.max_per_user",
		"task_dispatcher.default_timeout",
		"task_dispatcher.batch_timeout",
		"task_dispatcher.blueprint_timeout",
		"task_dispatcher.max_retries",
		"task_dispatcher.retry_delay",
		"task_dispatcher.poll_interval",
		"task_dispatcher.worker_callback_url",
		"task_dispatcher.worker_grpc_addr",
		"task_dispatcher.internal_callback_secret",
	} {
		_ = viper.BindEnv(key)
	}
}

func setDefaults() {
	viper.SetDefault("server.host", "0.0.0.0")
	viper.SetDefault("server.port", 3000)
	viper.SetDefault("server.read_timeout", "10s")
	viper.SetDefault("server.write_timeout", "120s")
	viper.SetDefault("server.prefork", false)

	viper.SetDefault("backend.fastapi_url", "http://localhost:8000")
	viper.SetDefault("backend.timeout", "120s")

	viper.SetDefault("redis.mode", "standalone")
	viper.SetDefault("redis.addr", "localhost:6379")
	viper.SetDefault("redis.db", 0)
	viper.SetDefault("redis.pool_size", 100)
	viper.SetDefault("redis.min_idle", 20)

	viper.SetDefault("database.enabled", false)
	viper.SetDefault("database.host", "localhost")
	viper.SetDefault("database.port", 3306)
	viper.SetDefault("database.user", "root")
	viper.SetDefault("database.password", "")
	viper.SetDefault("database.name", "arboris")
	viper.SetDefault("database.writer_max_open", 50)
	viper.SetDefault("database.writer_max_idle", 10)
	viper.SetDefault("database.writer_max_lifetime", "5m")
	viper.SetDefault("database.writer_max_idle_time", "3m")
	viper.SetDefault("database.reader_max_open", 100)
	viper.SetDefault("database.reader_max_idle", 20)
	viper.SetDefault("database.reader_max_lifetime", "5m")
	viper.SetDefault("database.reader_max_idle_time", "3m")
	viper.SetDefault("database.slow_threshold", "200ms")
	viper.SetDefault("database.log_level", "warn")

	viper.SetDefault("payment.enabled", false)
	viper.SetDefault("payment.success_url", "http://localhost:5173/settings?tab=subscription&status=success")
	viper.SetDefault("payment.cancel_url", "http://localhost:5173/settings?tab=subscription&status=cancel")
	viper.SetDefault("payment.webhook_workers", 4)
	viper.SetDefault("payment.webhook_queue_size", 100)

	viper.SetDefault("log.level", "info")
	viper.SetDefault("log.format", "json")
	viper.SetDefault("log.output", "stdout")

	viper.SetDefault("metrics.enabled", true)
	viper.SetDefault("metrics.path", "/metrics")

	// CORS：默认通配，保持既有行为；生产可通过 cors.origins 收紧。
	viper.SetDefault("cors.origins", []string{"*"})

	// 限流默认值（基线取自 gateway/config.yaml）：补全后即便 yaml 漏配某项，
	// 也回退到合理非零值，而非 viper 零值 0——后者会让该桶 count<=0 恒为 false，
	// 把对应流量全部 429 锁死。yaml/env 仍可覆盖。
	viper.SetDefault("rate_limit.default_tpm", 100000)
	viper.SetDefault("rate_limit.default_concurrent", 3)
	viper.SetDefault("rate_limit.default_rpm", 60)
	viper.SetDefault("rate_limit.default_rps", 10)
	viper.SetDefault("rate_limit.premium_tpm", 300000)
	viper.SetDefault("rate_limit.premium_concurrent", 8)
	viper.SetDefault("rate_limit.premium_rpm", 180)
	viper.SetDefault("rate_limit.premium_rps", 30)
	viper.SetDefault("rate_limit.unauth_ip_rpm", 120)

	viper.SetDefault("task_dispatcher.enabled", true)
	viper.SetDefault("task_dispatcher.max_concurrency", 20)
	viper.SetDefault("task_dispatcher.max_per_user", 3)
	viper.SetDefault("task_dispatcher.default_timeout", "10m")
	viper.SetDefault("task_dispatcher.batch_timeout", "60m")
	viper.SetDefault("task_dispatcher.blueprint_timeout", "15m")
	viper.SetDefault("task_dispatcher.max_retries", 3)
	viper.SetDefault("task_dispatcher.retry_delay", "5s")
	viper.SetDefault("task_dispatcher.poll_interval", "100ms")
	viper.SetDefault("task_dispatcher.worker_callback_url", "http://localhost:8000/api/internal/tasks")
	viper.SetDefault("task_dispatcher.worker_grpc_addr", "localhost:50051")
}
