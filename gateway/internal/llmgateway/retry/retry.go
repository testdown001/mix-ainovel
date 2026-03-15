package retry

import (
	"context"
	"errors"
	"math"
	"time"

	"github.com/arboris-novel/gateway/internal/logger"
	"go.uber.org/zap"
)

// Strategy 重试策略
type Strategy struct {
	MaxAttempts  int
	InitialDelay time.Duration
	MaxDelay     time.Duration
	Multiplier   float64
}

// DefaultStrategy 默认重试策略
var DefaultStrategy = Strategy{
	MaxAttempts:  3,
	InitialDelay: 100 * time.Millisecond,
	MaxDelay:     5 * time.Second,
	Multiplier:   2.0,
}

// Do 执行带重试的操作
func (s *Strategy) Do(ctx context.Context, operation func() error) error {
	var lastErr error

	for attempt := 0; attempt < s.MaxAttempts; attempt++ {
		// 执行操作
		err := operation()
		if err == nil {
			return nil
		}

		lastErr = err

		// 检查是否可重试
		if !isRetryable(err) {
			logger.Warn("Non-retryable error",
				zap.Error(err),
				zap.Int("attempt", attempt+1),
			)
			return err
		}

		// 最后一次尝试，不再等待
		if attempt == s.MaxAttempts-1 {
			break
		}

		// 计算延迟（指数退避）
		delay := s.calculateDelay(attempt)

		logger.Info("Retrying after error",
			zap.Error(err),
			zap.Int("attempt", attempt+1),
			zap.Duration("delay", delay),
		)

		// 等待
		select {
		case <-time.After(delay):
			// 继续重试
		case <-ctx.Done():
			return ctx.Err()
		}
	}

	return lastErr
}

// DoWithResult 执行带重试的操作（带返回值）
func DoWithResult[T any](ctx context.Context, s *Strategy, operation func() (T, error)) (T, error) {
	var result T
	var lastErr error

	for attempt := 0; attempt < s.MaxAttempts; attempt++ {
		// 执行操作
		res, err := operation()
		if err == nil {
			return res, nil
		}

		lastErr = err

		// 检查是否可重试
		if !isRetryable(err) {
			return result, err
		}

		// 最后一次尝试
		if attempt == s.MaxAttempts-1 {
			break
		}

		// 计算延迟
		delay := s.calculateDelay(attempt)

		logger.Info("Retrying after error",
			zap.Error(err),
			zap.Int("attempt", attempt+1),
			zap.Duration("delay", delay),
		)

		// 等待
		select {
		case <-time.After(delay):
		case <-ctx.Done():
			return result, ctx.Err()
		}
	}

	return result, lastErr
}

// calculateDelay 计算延迟（指数退避）
func (s *Strategy) calculateDelay(attempt int) time.Duration {
	delay := float64(s.InitialDelay) * math.Pow(s.Multiplier, float64(attempt))

	if delay > float64(s.MaxDelay) {
		delay = float64(s.MaxDelay)
	}

	// 添加随机抖动（±10%）
	jitter := delay * 0.1 * (2*float64(time.Now().UnixNano()%100)/100 - 1)
	delay += jitter

	return time.Duration(delay)
}

// isRetryable 判断错误是否可重试
func isRetryable(err error) bool {
	if err == nil {
		return false
	}

	// 上下文错误不可重试
	if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
		return false
	}

	// 检查是否是 RetryableError
	var retryableErr *RetryableError
	if errors.As(err, &retryableErr) {
		return retryableErr.Retryable
	}

	// 默认可重试（网络错误、超时等）
	return true
}

// RetryableError 可重试错误
type RetryableError struct {
	Err       error
	Retryable bool
}

func (e *RetryableError) Error() string {
	return e.Err.Error()
}

func (e *RetryableError) Unwrap() error {
	return e.Err
}

// NewRetryableError 创建可重试错误
func NewRetryableError(err error, retryable bool) error {
	return &RetryableError{
		Err:       err,
		Retryable: retryable,
	}
}

// Metrics 重试指标
type Metrics struct {
	TotalAttempts   int64
	SuccessAttempts int64
	FailedAttempts  int64
	RetryCount      int64
}

// Tracker 重试追踪器
type Tracker struct {
	metrics Metrics
}

// NewTracker 创建追踪器
func NewTracker() *Tracker {
	return &Tracker{}
}

// RecordAttempt 记录尝试
func (t *Tracker) RecordAttempt(success bool, retryCount int) {
	t.metrics.TotalAttempts++
	t.metrics.RetryCount += int64(retryCount)

	if success {
		t.metrics.SuccessAttempts++
	} else {
		t.metrics.FailedAttempts++
	}
}

// GetMetrics 获取指标
func (t *Tracker) GetMetrics() Metrics {
	return t.metrics
}
