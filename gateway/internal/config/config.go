package config

import (
	"time"

	"github.com/spf13/viper"
)

// Config 全局配置
type Config struct {
	Server         ServerConfig         `mapstructure:"server"`
	Backend        BackendConfig        `mapstructure:"backend"`
	JWT            JWTConfig            `mapstructure:"jwt"`
	Redis          RedisConfig          `mapstructure:"redis"`
	RateLimit      RateLimitConfig      `mapstructure:"rate_limit"`
	WebSocket      WebSocketConfig      `mapstructure:"websocket"`
	TaskDispatcher TaskDispatcherConfig `mapstructure:"task_dispatcher"`
	Log            LogConfig            `mapstructure:"log"`
	Metrics        MetricsConfig        `mapstructure:"metrics"`
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
	Addr     string `mapstructure:"addr"`
	Password string `mapstructure:"password"`
	DB       int    `mapstructure:"db"`
	PoolSize int    `mapstructure:"pool_size"`
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
	MaxRetries        int           `mapstructure:"max_retries"`
	RetryDelay        time.Duration `mapstructure:"retry_delay"`
	PollInterval      time.Duration `mapstructure:"poll_interval"`
	WorkerCallbackURL string        `mapstructure:"worker_callback_url"`
	WorkerGRPCAddr    string        `mapstructure:"worker_grpc_addr"`
}

var globalConfig *Config

// Load 加载配置文件
func Load(configPath string) (*Config, error) {
	viper.SetConfigFile(configPath)
	viper.SetConfigType("yaml")

	// 设置默认值
	setDefaults()

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

func setDefaults() {
	viper.SetDefault("server.host", "0.0.0.0")
	viper.SetDefault("server.port", 3000)
	viper.SetDefault("server.read_timeout", "10s")
	viper.SetDefault("server.write_timeout", "120s")
	viper.SetDefault("server.prefork", false)

	viper.SetDefault("backend.fastapi_url", "http://localhost:8000")
	viper.SetDefault("backend.timeout", "120s")

	viper.SetDefault("redis.addr", "localhost:6379")
	viper.SetDefault("redis.db", 0)
	viper.SetDefault("redis.pool_size", 50)

	viper.SetDefault("log.level", "info")
	viper.SetDefault("log.format", "json")
	viper.SetDefault("log.output", "stdout")

	viper.SetDefault("metrics.enabled", true)
	viper.SetDefault("metrics.path", "/metrics")

	viper.SetDefault("task_dispatcher.enabled", true)
	viper.SetDefault("task_dispatcher.max_concurrency", 20)
	viper.SetDefault("task_dispatcher.max_per_user", 3)
	viper.SetDefault("task_dispatcher.default_timeout", "10m")
	viper.SetDefault("task_dispatcher.batch_timeout", "60m")
	viper.SetDefault("task_dispatcher.max_retries", 3)
	viper.SetDefault("task_dispatcher.retry_delay", "5s")
	viper.SetDefault("task_dispatcher.poll_interval", "100ms")
	viper.SetDefault("task_dispatcher.worker_callback_url", "http://localhost:8000/api/internal/tasks")
	viper.SetDefault("task_dispatcher.worker_grpc_addr", "localhost:50051")
}
