package lock

import (
	"context"
	"errors"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"

	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/arboris-novel/gateway/internal/metrics"
)

var (
	ErrLockNotAcquired = errors.New("failed to acquire lock")
	ErrLockNotHeld     = errors.New("lock not held by this owner")
)

// Lua script: atomically release only if we own the lock
var releaseLuaScript = redis.NewScript(`
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
`)

// Lua script: atomically extend TTL only if we own the lock
var renewLuaScript = redis.NewScript(`
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
`)

type Option func(*lockOptions)

type lockOptions struct {
	ttl           time.Duration
	retryCount    int
	retryInterval time.Duration
	watchdog      bool
}

func defaultOptions() lockOptions {
	return lockOptions{
		ttl:           30 * time.Second,
		retryCount:    0,
		retryInterval: 100 * time.Millisecond,
		watchdog:      false,
	}
}

func WithTTL(d time.Duration) Option {
	return func(o *lockOptions) { o.ttl = d }
}

func WithRetry(count int, interval time.Duration) Option {
	return func(o *lockOptions) {
		o.retryCount = count
		o.retryInterval = interval
	}
}

func WithWatchdog() Option {
	return func(o *lockOptions) { o.watchdog = true }
}

type Manager struct {
	client *redis.Client
}

func NewManager(client *redis.Client) *Manager {
	return &Manager{client: client}
}

func (m *Manager) NewLock(key string, opts ...Option) *Lock {
	o := defaultOptions()
	for _, fn := range opts {
		fn(&o)
	}
	return &Lock{
		client:  m.client,
		key:     key,
		value:   uuid.New().String(),
		options: o,
	}
}

type Lock struct {
	client    *redis.Client
	key       string
	value     string
	options   lockOptions
	cancelWD  context.CancelFunc
}

func (l *Lock) Acquire(ctx context.Context) error {
	start := time.Now()
	attempts := l.options.retryCount + 1

	for i := 0; i < attempts; i++ {
		ok, err := l.client.SetNX(ctx, l.key, l.value, l.options.ttl).Result()
		if err != nil {
			metrics.LockErrors.WithLabelValues(l.key, "acquire").Inc()
			return err
		}
		if ok {
			metrics.LockAcquired.WithLabelValues(l.key).Inc()
			metrics.LockWaitDuration.WithLabelValues(l.key).Observe(time.Since(start).Seconds())

			if l.options.watchdog {
				l.startWatchdog(ctx)
			}
			return nil
		}

		if i < attempts-1 {
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(l.options.retryInterval):
			}
		}
	}

	metrics.LockTimeouts.WithLabelValues(l.key).Inc()
	return ErrLockNotAcquired
}

func (l *Lock) Release(ctx context.Context) error {
	if l.cancelWD != nil {
		l.cancelWD()
	}

	result, err := releaseLuaScript.Run(ctx, l.client, []string{l.key}, l.value).Int64()
	if err != nil {
		metrics.LockErrors.WithLabelValues(l.key, "release").Inc()
		return err
	}
	if result == 0 {
		return ErrLockNotHeld
	}
	metrics.LockReleased.WithLabelValues(l.key).Inc()
	return nil
}

func (l *Lock) startWatchdog(parentCtx context.Context) {
	ctx, cancel := context.WithCancel(parentCtx)
	l.cancelWD = cancel

	interval := l.options.ttl / 3
	go func() {
		ticker := time.NewTicker(interval)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				ttlMs := l.options.ttl.Milliseconds()
				result, err := renewLuaScript.Run(ctx, l.client, []string{l.key}, l.value, ttlMs).Int64()
				if err != nil || result == 0 {
					logger.Warn("lock watchdog: failed to renew",
						zap.String("key", l.key),
						zap.Error(err),
					)
					return
				}
			}
		}
	}()
}
