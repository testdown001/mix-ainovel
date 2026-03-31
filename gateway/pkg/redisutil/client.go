package redisutil

import (
	"context"
	"fmt"

	"github.com/arboris-novel/gateway/internal/config"
	"github.com/redis/go-redis/v9"
)

// NewClient creates a Redis client based on config mode (standalone / sentinel / cluster).
// Returns redis.UniversalClient which works for all three modes.
func NewClient(cfg config.RedisConfig) (redis.UniversalClient, error) {
	var client redis.UniversalClient

	switch cfg.Mode {
	case "sentinel":
		if cfg.MasterName == "" {
			return nil, fmt.Errorf("redis sentinel mode requires master_name")
		}
		addrs := cfg.SentinelAddrs
		if len(addrs) == 0 {
			addrs = []string{cfg.Addr}
		}
		client = redis.NewFailoverClient(&redis.FailoverOptions{
			MasterName:    cfg.MasterName,
			SentinelAddrs: addrs,
			Password:      cfg.Password,
			DB:            cfg.DB,
			PoolSize:      cfg.PoolSize,
			MinIdleConns:  cfg.MinIdle,
		})

	case "cluster":
		addrs := cfg.Addrs
		if len(addrs) == 0 {
			addrs = []string{cfg.Addr}
		}
		client = redis.NewClusterClient(&redis.ClusterOptions{
			Addrs:        addrs,
			Password:     cfg.Password,
			PoolSize:     cfg.PoolSize,
			MinIdleConns: cfg.MinIdle,
		})

	default: // standalone
		client = redis.NewClient(&redis.Options{
			Addr:         cfg.Addr,
			Password:     cfg.Password,
			DB:           cfg.DB,
			PoolSize:     cfg.PoolSize,
			MinIdleConns: cfg.MinIdle,
		})
	}

	if err := client.Ping(context.Background()).Err(); err != nil {
		return nil, fmt.Errorf("redis ping failed (%s mode): %w", cfg.Mode, err)
	}

	return client, nil
}

// PoolStats returns connection pool statistics for the client.
func PoolStats(client redis.UniversalClient) map[string]interface{} {
	stats := client.PoolStats()
	return map[string]interface{}{
		"hits":       stats.Hits,
		"misses":     stats.Misses,
		"timeouts":   stats.Timeouts,
		"total_conns": stats.TotalConns,
		"idle_conns":  stats.IdleConns,
		"stale_conns": stats.StaleConns,
	}
}
