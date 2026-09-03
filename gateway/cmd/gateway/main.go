package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/arboris-novel/gateway/internal/auth"
	"github.com/arboris-novel/gateway/internal/config"
	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/arboris-novel/gateway/internal/metrics"
	"github.com/arboris-novel/gateway/internal/middleware"
	"github.com/arboris-novel/gateway/internal/proxy"
	"github.com/arboris-novel/gateway/internal/ratelimit"
	"github.com/arboris-novel/gateway/internal/taskdispatcher"
	"github.com/arboris-novel/gateway/internal/websocket"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	configPath := "config.yaml"
	if envPath := os.Getenv("CONFIG_PATH"); envPath != "" {
		configPath = envPath
	}
	cfg, err := config.Load(configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to load config: %v\n", err)
		os.Exit(1)
	}

	if err := logger.Init(cfg.Log.Level, cfg.Log.Format, cfg.Log.Output, cfg.Log.FilePath); err != nil {
		fmt.Fprintf(os.Stderr, "failed to init logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()

	metrics.Init()

	rdb := redis.NewClient(&redis.Options{
		Addr:         cfg.Redis.Addr,
		Password:     cfg.Redis.Password,
		DB:           cfg.Redis.DB,
		PoolSize:     cfg.Redis.PoolSize,
		MinIdleConns: cfg.Redis.MinIdle,
	})
	if err := rdb.Ping(ctx).Err(); err != nil {
		logger.Fatal("failed to connect to Redis", zap.Error(err))
	}
	logger.Info("redis connected", zap.String("addr", cfg.Redis.Addr))

	limiter := ratelimit.NewLimiter(rdb, &cfg.RateLimit)

	app := fiber.New(fiber.Config{
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
		Prefork:      cfg.Server.Prefork,
	})

	app.Use(middleware.Recovery())
	app.Use(middleware.CORSWithOrigins(cfg.CORS.Origins))
	app.Use(middleware.RequestLogger())

	app.Get("/health", proxy.HealthCheck())

	if cfg.Metrics.Enabled {
		app.Get(cfg.Metrics.Path, metrics.Handler())
	}

	// WebSocket — Hub starts Redis listener goroutine internally via NewHub
	wsHub := websocket.NewHub(rdb, &cfg.WebSocket)
	app.Get("/ws", wsHub.Upgrade())

	// Task dispatcher
	var dispatcher *taskdispatcher.Dispatcher
	if cfg.TaskDispatcher.Enabled {
		dispatcherCfg := &taskdispatcher.Config{
			MaxConcurrency:         cfg.TaskDispatcher.MaxConcurrency,
			MaxPerUser:             cfg.TaskDispatcher.MaxPerUser,
			DefaultTimeout:         cfg.TaskDispatcher.DefaultTimeout,
			BatchTimeout:           cfg.TaskDispatcher.BatchTimeout,
			BlueprintTimeout:       cfg.TaskDispatcher.BlueprintTimeout,
			MaxRetries:             cfg.TaskDispatcher.MaxRetries,
			RetryDelay:             cfg.TaskDispatcher.RetryDelay,
			PollInterval:           cfg.TaskDispatcher.PollInterval,
			LeaseDuration:          cfg.TaskDispatcher.LeaseDuration,
			WorkerCallbackURL:      cfg.TaskDispatcher.WorkerCallbackURL,
			WorkerGRPCAddr:         cfg.TaskDispatcher.WorkerGRPCAddr,
			InternalCallbackSecret: cfg.TaskDispatcher.InternalCallbackSecret,
		}
		dispatcher = taskdispatcher.NewDispatcher(rdb, dispatcherCfg)
		go func() {
			if err := dispatcher.Start(ctx); err != nil {
				logger.Error("dispatcher start error", zap.Error(err))
			}
		}()
		handler := taskdispatcher.NewHandler(dispatcher, cfg.TaskDispatcher.InternalCallbackSecret)
		handler.RegisterRoutes(app, auth.JWTMiddleware())
	}

	// 支付回调：不需要 JWT 也不需要限流，签名验证在 Python 端完成
	app.Post("/api/payment/alipay/notify", proxy.ReverseProxy())
	app.Post("/api/payment/wechat/notify", proxy.ReverseProxy())

	// API reverse proxy to FastAPI with optional JWT + rate limiting
	api := app.Group("/api")
	api.Use(auth.OptionalJWTMiddleware())
	api.Use(limiter.Middleware())
	api.All("/*", proxy.ReverseProxy())

	addr := fmt.Sprintf("%s:%d", cfg.Server.Host, cfg.Server.Port)
	go func() {
		logger.Info("gateway starting", zap.String("addr", addr))
		if err := app.Listen(addr); err != nil {
			logger.Error("gateway listen error", zap.Error(err))
		}
	}()

	<-ctx.Done()
	logger.Info("shutdown signal received, stopping gateway...")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if dispatcher != nil {
		dispatcher.Stop()
	}
	wsHub.Close()

	if err := app.ShutdownWithContext(shutdownCtx); err != nil {
		logger.Error("gateway shutdown error", zap.Error(err))
	}

	rdb.Close()
	logger.Info("gateway stopped")
}
