package dbutil

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/arboris-novel/gateway/internal/logger"
	"go.uber.org/zap"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	gormlogger "gorm.io/gorm/logger"
	"gorm.io/plugin/dbresolver"
)

type DBConfig struct {
	WriteDSN string
	ReadDSNs []string

	Writer PoolConfig
	Reader PoolConfig

	SlowThreshold time.Duration
	LogLevel      string
}

type PoolConfig struct {
	MaxOpen     int
	MaxIdle     int
	MaxLifetime time.Duration
	MaxIdleTime time.Duration
}

func DefaultDBConfig() DBConfig {
	return DBConfig{
		Writer: PoolConfig{
			MaxOpen:     50,
			MaxIdle:     10,
			MaxLifetime: 5 * time.Minute,
			MaxIdleTime: 3 * time.Minute,
		},
		Reader: PoolConfig{
			MaxOpen:     100,
			MaxIdle:     20,
			MaxLifetime: 5 * time.Minute,
			MaxIdleTime: 3 * time.Minute,
		},
		SlowThreshold: 200 * time.Millisecond,
		LogLevel:      "warn",
	}
}

func NewDB(cfg DBConfig) (*gorm.DB, error) {
	logLevel := gormlogger.Warn
	switch cfg.LogLevel {
	case "silent":
		logLevel = gormlogger.Silent
	case "error":
		logLevel = gormlogger.Error
	case "info":
		logLevel = gormlogger.Info
	}

	db, err := gorm.Open(mysql.Open(cfg.WriteDSN), &gorm.Config{
		Logger: gormlogger.Default.LogMode(logLevel),
	})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to write database: %w", err)
	}

	writerDB, err := db.DB()
	if err != nil {
		return nil, fmt.Errorf("failed to get underlying write db: %w", err)
	}
	applyPoolConfig(writerDB, cfg.Writer)

	if len(cfg.ReadDSNs) > 0 {
		replicas := make([]gorm.Dialector, len(cfg.ReadDSNs))
		for i, dsn := range cfg.ReadDSNs {
			replicas[i] = mysql.Open(dsn)
		}

		err = db.Use(dbresolver.Register(dbresolver.Config{
			Replicas: replicas,
			Policy:   dbresolver.RandomPolicy{},
		}).SetMaxOpenConns(cfg.Reader.MaxOpen).
			SetMaxIdleConns(cfg.Reader.MaxIdle).
			SetConnMaxLifetime(cfg.Reader.MaxLifetime).
			SetConnMaxIdleTime(cfg.Reader.MaxIdleTime))
		if err != nil {
			return nil, fmt.Errorf("failed to register read replicas: %w", err)
		}
	}

	logger.Info("database initialized",
		zap.Int("writer_max_open", cfg.Writer.MaxOpen),
		zap.Int("reader_replicas", len(cfg.ReadDSNs)),
		zap.Int("reader_max_open", cfg.Reader.MaxOpen),
	)

	return db, nil
}

func applyPoolConfig(db *sql.DB, cfg PoolConfig) {
	db.SetMaxOpenConns(cfg.MaxOpen)
	db.SetMaxIdleConns(cfg.MaxIdle)
	db.SetConnMaxLifetime(cfg.MaxLifetime)
	db.SetConnMaxIdleTime(cfg.MaxIdleTime)
}

type PoolStats struct {
	OpenConnections int     `json:"open_connections"`
	InUse           int     `json:"in_use"`
	Idle            int     `json:"idle"`
	WaitCount       int64   `json:"wait_count"`
	WaitDuration    float64 `json:"wait_duration_ms"`
	MaxOpen         int     `json:"max_open"`
}

func GetPoolStats(db *gorm.DB) (*PoolStats, error) {
	sqlDB, err := db.DB()
	if err != nil {
		return nil, err
	}
	stats := sqlDB.Stats()
	return &PoolStats{
		OpenConnections: stats.OpenConnections,
		InUse:           stats.InUse,
		Idle:            stats.Idle,
		WaitCount:       stats.WaitCount,
		WaitDuration:    float64(stats.WaitDuration.Milliseconds()),
		MaxOpen:         stats.MaxOpenConnections,
	}, nil
}

func HealthCheck(ctx context.Context, db *gorm.DB) error {
	sqlDB, err := db.DB()
	if err != nil {
		return err
	}
	return sqlDB.PingContext(ctx)
}

func BuildMySQLDSN(user, password, host string, port int, database string) string {
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=True&loc=Local",
		user, password, host, port, database)
}
