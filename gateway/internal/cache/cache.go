package cache

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
	"golang.org/x/sync/singleflight"
)

// Cache provides a two-level cache: L1 (in-process map) + L2 (Redis).
// singleflight prevents cache stampedes on hot keys.
type Cache struct {
	rdb        *redis.Client
	defaultTTL time.Duration
	sfg        singleflight.Group

	// L1 in-process cache
	l1    sync.Map
	l1TTL time.Duration
}

type l1Entry struct {
	data      []byte
	expiresAt time.Time
}

func New(rdb *redis.Client, defaultTTL time.Duration) *Cache {
	c := &Cache{
		rdb:        rdb,
		defaultTTL: defaultTTL,
		l1TTL:      5 * time.Second,
	}
	go c.l1Cleanup(30 * time.Second)
	return c
}

// Get retrieves a value by key. Checks L1 first, then L2 (Redis).
func (c *Cache) Get(ctx context.Context, key string) ([]byte, bool) {
	// L1
	if v, ok := c.l1.Load(key); ok {
		entry := v.(*l1Entry)
		if time.Now().Before(entry.expiresAt) {
			return entry.data, true
		}
		c.l1.Delete(key)
	}

	// L2 (Redis)
	data, err := c.rdb.Get(ctx, key).Bytes()
	if err != nil {
		return nil, false
	}

	// Backfill L1
	c.l1.Store(key, &l1Entry{data: data, expiresAt: time.Now().Add(c.l1TTL)})
	return data, true
}

// Set stores a value in both L1 and L2.
func (c *Cache) Set(ctx context.Context, key string, data []byte, ttl ...time.Duration) error {
	t := c.defaultTTL
	if len(ttl) > 0 && ttl[0] > 0 {
		t = ttl[0]
	}

	c.l1.Store(key, &l1Entry{data: data, expiresAt: time.Now().Add(c.l1TTL)})

	return c.rdb.Set(ctx, key, data, t).Err()
}

// Delete removes a key from both levels.
func (c *Cache) Delete(ctx context.Context, key string) error {
	c.l1.Delete(key)
	return c.rdb.Del(ctx, key).Err()
}

// GetJSON unmarshals a cached value into dest.
func (c *Cache) GetJSON(ctx context.Context, key string, dest interface{}) bool {
	data, ok := c.Get(ctx, key)
	if !ok {
		return false
	}
	return json.Unmarshal(data, dest) == nil
}

// SetJSON marshals value and stores it.
func (c *Cache) SetJSON(ctx context.Context, key string, value interface{}, ttl ...time.Duration) error {
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return c.Set(ctx, key, data, ttl...)
}

// GetOrLoad uses singleflight to prevent stampedes.
// If the key is not cached, loader is called exactly once (even under concurrent access)
// and the result is cached.
func (c *Cache) GetOrLoad(ctx context.Context, key string, loader func() (interface{}, error), ttl ...time.Duration) ([]byte, error) {
	if data, ok := c.Get(ctx, key); ok {
		return data, nil
	}

	v, err, _ := c.sfg.Do(key, func() (interface{}, error) {
		result, err := loader()
		if err != nil {
			return nil, err
		}

		data, err := json.Marshal(result)
		if err != nil {
			return nil, err
		}

		if setErr := c.Set(ctx, key, data, ttl...); setErr != nil {
			logger.Warn("cache set failed after load", zap.String("key", key), zap.Error(setErr))
		}

		return data, nil
	})

	if err != nil {
		return nil, err
	}
	return v.([]byte), nil
}

// InvalidatePattern deletes all keys matching a pattern via SCAN.
func (c *Cache) InvalidatePattern(ctx context.Context, pattern string) error {
	var cursor uint64
	for {
		keys, nextCursor, err := c.rdb.Scan(ctx, cursor, pattern, 100).Result()
		if err != nil {
			return err
		}
		if len(keys) > 0 {
			c.rdb.Del(ctx, keys...)
			for _, k := range keys {
				c.l1.Delete(k)
			}
		}
		cursor = nextCursor
		if cursor == 0 {
			break
		}
	}
	return nil
}

// InvalidateProject removes all cached data for a project.
func (c *Cache) InvalidateProject(ctx context.Context, projectID string) error {
	return c.InvalidatePattern(ctx, fmt.Sprintf("project:%s:*", projectID))
}

// StartInvalidationListener subscribes to Redis Pub/Sub for cache invalidation broadcasts.
// Run as a goroutine.
func (c *Cache) StartInvalidationListener(ctx context.Context) {
	pubsub := c.rdb.Subscribe(ctx, "cache:invalidate")
	defer pubsub.Close()

	ch := pubsub.Channel()
	for {
		select {
		case msg, ok := <-ch:
			if !ok {
				return
			}
			c.l1.Delete(msg.Payload)
			logger.Debug("L1 cache invalidated via pub/sub", zap.String("key", msg.Payload))
		case <-ctx.Done():
			return
		}
	}
}

func (c *Cache) l1Cleanup(interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for range ticker.C {
		now := time.Now()
		c.l1.Range(func(key, value interface{}) bool {
			entry := value.(*l1Entry)
			if now.After(entry.expiresAt) {
				c.l1.Delete(key)
			}
			return true
		})
	}
}
