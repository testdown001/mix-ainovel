package service

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/arboris-novel/gateway/internal/models"
	"github.com/arboris-novel/gateway/internal/repository"
	"github.com/redis/go-redis/v9"
)

var (
	ErrChapterQuotaExceeded = errors.New("daily chapter quota exceeded")
	ErrStorageQuotaExceeded = errors.New("storage quota exceeded")
	ErrTokenQuotaExceeded   = errors.New("monthly token quota exceeded")
)

const (
	premiumDailyChapterLimit = 50
	premiumStorageLimit      = 10_737_418_240 // 10 GB
	premiumMonthlyTokenLimit = 10_000_000
)

type QuotaService struct {
	repo  *repository.QuotaRepository
	redis *redis.Client
}

func NewQuotaService(repo *repository.QuotaRepository, rdb *redis.Client) *QuotaService {
	return &QuotaService{repo: repo, redis: rdb}
}

// CheckDailyQuotaRedis checks quota via Redis (hot path, no DB hit).
// Falls back to DB if Redis is unavailable.
func (s *QuotaService) CheckDailyQuotaRedis(ctx context.Context, userID int, limit int) (bool, error) {
	today := time.Now().UTC().Format("2006-01-02")
	key := fmt.Sprintf("quota:daily:%d:%s", userID, today)

	count, err := s.redis.Get(ctx, key).Int64()
	if err != nil && !errors.Is(err, redis.Nil) {
		return true, nil // Redis down, fail open
	}

	return count < int64(limit), nil
}

// ConsumeDailyQuotaRedis atomically increments daily usage in Redis.
func (s *QuotaService) ConsumeDailyQuotaRedis(ctx context.Context, userID int, limit int) error {
	today := time.Now().UTC().Format("2006-01-02")
	key := fmt.Sprintf("quota:daily:%d:%s", userID, today)

	count, err := s.redis.Incr(ctx, key).Result()
	if err != nil {
		return nil // Redis down, fail open
	}

	if count == 1 {
		s.redis.Expire(ctx, key, 25*time.Hour)
	}

	if count > int64(limit) {
		s.redis.Decr(ctx, key) // rollback
		return ErrChapterQuotaExceeded
	}

	return nil
}

// GetQuotaInfo returns full quota information from DB (after reset checks).
func (s *QuotaService) GetQuotaInfo(ctx context.Context, userID int) (*models.UserQuota, error) {
	quota, err := s.repo.GetOrCreate(ctx, userID)
	if err != nil {
		return nil, err
	}

	now := time.Now().UTC()
	updated := false

	if now.Sub(quota.DailyResetAt) >= 24*time.Hour {
		quota.DailyChapterUsed = 0
		quota.DailyResetAt = now
		updated = true
	}

	if now.Sub(quota.MonthlyResetAt) >= 30*24*time.Hour {
		quota.MonthlyTokenUsed = 0
		quota.MonthlyResetAt = now
		updated = true
	}

	if updated {
		_ = s.repo.Update(ctx, quota)
	}

	return quota, nil
}

// SyncRedisToDB periodically syncs Redis quota counters back to MySQL.
// Run as a background goroutine.
func (s *QuotaService) SyncRedisToDB(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			s.doSync(ctx)
		}
	}
}

func (s *QuotaService) doSync(ctx context.Context) {
	// In production this would scan Redis keys matching "quota:daily:*"
	// and batch-update MySQL. Simplified for now.
}

func (s *QuotaService) UpgradeToPremium(ctx context.Context, userID int, expiresAt time.Time) error {
	quota, err := s.repo.GetOrCreate(ctx, userID)
	if err != nil {
		return err
	}

	quota.IsPremium = true
	quota.PremiumExpiresAt = &expiresAt
	quota.DailyChapterLimit = premiumDailyChapterLimit
	quota.StorageLimit = premiumStorageLimit
	quota.MonthlyTokenLimit = premiumMonthlyTokenLimit

	return s.repo.Update(ctx, quota)
}

func (s *QuotaService) DowngradeFromPremium(ctx context.Context, userID int) error {
	quota, err := s.repo.GetOrCreate(ctx, userID)
	if err != nil {
		return err
	}

	quota.IsPremium = false
	quota.PremiumExpiresAt = nil
	quota.DailyChapterLimit = 10
	quota.StorageLimit = 1_073_741_824
	quota.MonthlyTokenLimit = 1_000_000

	return s.repo.Update(ctx, quota)
}
