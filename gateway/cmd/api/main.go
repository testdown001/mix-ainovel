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

	"github.com/arboris-novel/gateway/internal/cache"
	"github.com/arboris-novel/gateway/internal/config"
	"github.com/arboris-novel/gateway/internal/handler"
	"github.com/arboris-novel/gateway/internal/lock"
	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/arboris-novel/gateway/internal/metrics"
	"github.com/arboris-novel/gateway/internal/middleware"
	"github.com/arboris-novel/gateway/internal/models"
	"github.com/arboris-novel/gateway/internal/mq"
	"github.com/arboris-novel/gateway/internal/repository"
	"github.com/arboris-novel/gateway/internal/service"
	"github.com/arboris-novel/gateway/pkg/dbutil"
	"github.com/arboris-novel/gateway/pkg/response"
	pkgrt "github.com/arboris-novel/gateway/pkg/runtime"
	"gorm.io/gorm"
)

func main() {
	// Global context with graceful shutdown signal propagation
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	// Load config
	configPath := "config.yaml"
	if envPath := os.Getenv("CONFIG_PATH"); envPath != "" {
		configPath = envPath
	}
	cfg, err := config.Load(configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to load config: %v\n", err)
		os.Exit(1)
	}

	// Init logger
	if err := logger.Init(cfg.Log.Level, cfg.Log.Format, cfg.Log.Output, cfg.Log.FilePath); err != nil {
		fmt.Fprintf(os.Stderr, "failed to init logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()

	// Init Prometheus metrics
	metrics.Init()
	pkgrt.RegisterMetrics()

	// GC tuning for production workloads
	pkgrt.TuneGC(100, 0) // GOGC=100 (default), no hard memory limit

	// Goroutine leak detector
	leakDetector := pkgrt.NewGoroutineLeakDetector(
		pkgrt.WithThreshold(500),
		pkgrt.WithCheckInterval(30*time.Second),
	)
	go leakDetector.Start(ctx)

	// Runtime metrics collector
	go pkgrt.CollectMetrics(ctx, 15*time.Second)

	// Init Redis
	rdb := redis.NewClient(&redis.Options{
		Addr:     cfg.Redis.Addr,
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
		PoolSize: cfg.Redis.PoolSize,
		MinIdleConns: cfg.Redis.MinIdle,
	})
	if err := rdb.Ping(ctx).Err(); err != nil {
		logger.Fatal("failed to connect to Redis", zap.Error(err))
	}
	logger.Info("redis connected", zap.String("addr", cfg.Redis.Addr))

	// Init distributed lock manager
	lockMgr := lock.NewManager(rdb)

	// Init cache
	appCache := cache.New(rdb, 30*time.Minute)

	// Init database (optional — only if configured)
	var db *gorm.DB
	if cfg.Database.Enabled {
		writeDSN := dbutil.BuildMySQLDSN(
			cfg.Database.User, cfg.Database.Password,
			cfg.Database.Host, cfg.Database.Port, cfg.Database.Name,
		)

		dbCfg := dbutil.DefaultDBConfig()
		dbCfg.WriteDSN = writeDSN
		dbCfg.Writer.MaxOpen = cfg.Database.WriterMaxOpen
		dbCfg.Writer.MaxIdle = cfg.Database.WriterMaxIdle
		dbCfg.Writer.MaxLifetime = cfg.Database.WriterMaxLifetime
		dbCfg.Writer.MaxIdleTime = cfg.Database.WriterMaxIdleTime
		dbCfg.Reader.MaxOpen = cfg.Database.ReaderMaxOpen
		dbCfg.Reader.MaxIdle = cfg.Database.ReaderMaxIdle
		dbCfg.Reader.MaxLifetime = cfg.Database.ReaderMaxLifetime
		dbCfg.Reader.MaxIdleTime = cfg.Database.ReaderMaxIdleTime
		dbCfg.SlowThreshold = cfg.Database.SlowThreshold
		dbCfg.LogLevel = cfg.Database.LogLevel

		for _, host := range cfg.Database.ReadHosts {
			dbCfg.ReadDSNs = append(dbCfg.ReadDSNs, dbutil.BuildMySQLDSN(
				cfg.Database.User, cfg.Database.Password,
				host, cfg.Database.Port, cfg.Database.Name,
			))
		}

		db, err = dbutil.NewDB(dbCfg)
		if err != nil {
			logger.Fatal("failed to initialize database", zap.Error(err))
		}

		if err := db.AutoMigrate(
			&models.PaymentOrder{},
			&models.Subscription{},
		); err != nil {
			logger.Fatal("failed to auto-migrate payment tables", zap.Error(err))
		}

		logger.Info("database initialized",
			zap.String("host", cfg.Database.Host),
			zap.String("name", cfg.Database.Name),
		)

		// Start DB pool metrics collector goroutine
		go collectDBMetrics(ctx, db)
	}

	// Create Fiber app
	app := fiber.New(fiber.Config{
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
		Prefork:      cfg.Server.Prefork,
		ErrorHandler: func(c *fiber.Ctx, err error) error {
			code := fiber.StatusInternalServerError
			if e, ok := err.(*fiber.Error); ok {
				code = e.Code
			}
			return response.Fail(c, code, "ERROR", err.Error())
		},
	})

	// Global middleware
	app.Use(middleware.Recovery())
	app.Use(middleware.CORS())
	app.Use(middleware.RequestLogger())

	// Health check
	app.Get("/health", func(c *fiber.Ctx) error {
		health := fiber.Map{
			"status": "ok",
			"time":   time.Now().UTC().Format(time.RFC3339),
		}

		if err := rdb.Ping(c.Context()).Err(); err != nil {
			health["redis"] = "down"
			health["status"] = "degraded"
		} else {
			health["redis"] = "ok"
		}

		if db != nil {
			if err := dbutil.HealthCheck(c.Context(), db); err != nil {
				health["database"] = "down"
				health["status"] = "degraded"
			} else {
				health["database"] = "ok"
			}
		}

		return response.OK(c, health)
	})

	// DB pool stats endpoint
	app.Get("/debug/db-pool", func(c *fiber.Ctx) error {
		if db == nil {
			return response.BadRequest(c, "database not enabled")
		}
		stats, err := dbutil.GetPoolStats(db)
		if err != nil {
			return response.InternalError(c, err.Error())
		}
		return response.OK(c, stats)
	})

	// Runtime diagnostics endpoint
	app.Get("/debug/runtime", func(c *fiber.Ctx) error {
		return response.OK(c, pkgrt.GetRuntimeStats())
	})

	// Redis pool stats endpoint
	app.Get("/debug/redis-pool", func(c *fiber.Ctx) error {
		stats := rdb.PoolStats()
		return response.OK(c, fiber.Map{
			"mode":        cfg.Redis.Mode,
			"hits":        stats.Hits,
			"misses":      stats.Misses,
			"timeouts":    stats.Timeouts,
			"total_conns": stats.TotalConns,
			"idle_conns":  stats.IdleConns,
			"stale_conns": stats.StaleConns,
		})
	})

	// Prometheus metrics
	app.Get(cfg.Metrics.Path, metrics.Handler())

	// API routes
	api := app.Group("/api/v2")

	// Webhook worker pool (started even if payment disabled, for graceful lifecycle)
	var webhookPool *service.WebhookWorkerPool

	// Wire up services when DB is available
	if db != nil {
		userRepo := repository.NewUserRepository(db)
		quotaRepo := repository.NewQuotaRepository(db)
		paymentRepo := repository.NewPaymentRepository(db)

		authSvc := service.NewAuthService(userRepo, quotaRepo, cfg)
		quotaSvc := service.NewQuotaService(quotaRepo, rdb)

		authHandler := handler.NewAuthHandler(authSvc, quotaSvc)
		authHandler.RegisterRoutes(api)

		// Background goroutine: sync Redis quota counters back to MySQL
		go quotaSvc.SyncRedisToDB(ctx, 5*time.Minute)

		// Payment service (Phase 2)
		if cfg.Payment.Enabled {
			paymentSvc := service.NewPaymentService(
				paymentRepo, quotaSvc, lockMgr, rdb,
				service.PaymentConfig{
					StripeSecretKey:     cfg.Payment.StripeSecretKey,
					StripeWebhookSecret: cfg.Payment.StripeWebhookSecret,
					SuccessURL:          cfg.Payment.SuccessURL,
					CancelURL:           cfg.Payment.CancelURL,
				},
			)

			// Webhook Worker Pool: bounded goroutine pool + channel queue
			webhookPool = service.NewWebhookWorkerPool(
				cfg.Payment.WebhookWorkers,
				cfg.Payment.WebhookQueueSize,
				func(workerCtx context.Context, task service.WebhookTask) error {
					return paymentSvc.HandleStripeWebhook(workerCtx, task.Payload, task.Signature)
				},
			)
			webhookPool.Start(ctx)

			paymentHandler := handler.NewPaymentHandler(paymentSvc, webhookPool)
			paymentHandler.RegisterRoutes(api)

			logger.Info("payment service initialized",
				zap.Int("webhook_workers", cfg.Payment.WebhookWorkers),
			)
		}
	}

	// Webhook worker pool stats
	app.Get("/debug/webhook-pool", func(c *fiber.Ctx) error {
		if webhookPool == nil {
			return response.OK(c, fiber.Map{"enabled": false})
		}
		stats := webhookPool.Stats()
		stats["enabled"] = true
		return response.OK(c, stats)
	})

	// Phase 3: Project + Generation services
	if db != nil {
		projectRepo := repository.NewProjectRepository(db)
		projectSvc := service.NewProjectService(projectRepo, appCache)
		projectHandler := handler.NewProjectHandler(projectSvc)
		projectHandler.RegisterRoutes(api)

		genPipeline := service.NewGenerationPipeline(projectRepo, appCache, service.PipelineConfig{
			MaxLLMConcurrency: 5,
			DefaultTimeout:    10 * time.Minute,
			BatchTimeout:      60 * time.Minute,
			FastAPIBaseURL:    cfg.Backend.FastAPIURL,
		})

		if db != nil {
			quotaRepo := repository.NewQuotaRepository(db)
			quotaSvcForGen := service.NewQuotaService(quotaRepo, rdb)
			genHandler := handler.NewGenerationHandler(genPipeline, quotaSvcForGen)
			genHandler.RegisterRoutes(api)
		}

		logger.Info("project & generation services initialized")
	}

	// Start cache invalidation listener (Pub/Sub goroutine)
	go appCache.StartInvalidationListener(ctx)

	// Message queue (Redis Streams)
	hostname, _ := os.Hostname()
	mqClient := mq.NewRedisStreamMQ(rdb, "arboris-api", fmt.Sprintf("api-%s-%d", hostname, os.Getpid()))
	_ = mqClient.HealthCheck(ctx)
	logger.Info("message queue initialized (Redis Streams)")

	// Start server in a goroutine
	addr := fmt.Sprintf("%s:%d", cfg.Server.Host, cfg.Server.Port)
	go func() {
		logger.Info("API server starting", zap.String("addr", addr))
		if err := app.Listen(addr); err != nil {
			logger.Error("server listen error", zap.Error(err))
		}
	}()

	// Wait for shutdown signal — context.Done() propagates to all child goroutines
	<-ctx.Done()
	logger.Info("shutdown signal received, gracefully stopping...")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := app.ShutdownWithContext(shutdownCtx); err != nil {
		logger.Error("server shutdown error", zap.Error(err))
	}

	// Drain webhook worker pool before closing connections
	if webhookPool != nil {
		webhookPool.Shutdown()
	}

	if err := rdb.Close(); err != nil {
		logger.Error("redis close error", zap.Error(err))
	}

	if db != nil {
		sqlDB, _ := db.DB()
		if sqlDB != nil {
			sqlDB.Close()
		}
	}

	logger.Info("server stopped gracefully")
}

// collectDBMetrics periodically pushes DB connection pool stats to Prometheus.
func collectDBMetrics(ctx context.Context, db *gorm.DB) {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			stats, err := dbutil.GetPoolStats(db)
			if err != nil {
				continue
			}
			metrics.DBPoolOpenConnections.WithLabelValues("writer").Set(float64(stats.OpenConnections))
			metrics.DBPoolIdleConnections.WithLabelValues("writer").Set(float64(stats.Idle))
		}
	}
}
