package repository

import (
	"context"
	"errors"
	"time"

	"github.com/arboris-novel/gateway/internal/models"
	"gorm.io/gorm"
)

type QuotaRepository struct {
	db *gorm.DB
}

func NewQuotaRepository(db *gorm.DB) *QuotaRepository {
	return &QuotaRepository{db: db}
}

func (r *QuotaRepository) GetOrCreate(ctx context.Context, userID int) (*models.UserQuota, error) {
	var quota models.UserQuota
	err := r.db.WithContext(ctx).Where("user_id = ?", userID).First(&quota).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		now := time.Now().UTC()
		quota = models.UserQuota{
			UserID:         userID,
			DailyResetAt:   now,
			MonthlyResetAt: now,
		}
		if createErr := r.db.WithContext(ctx).Create(&quota).Error; createErr != nil {
			return nil, createErr
		}
		return &quota, nil
	}
	return &quota, err
}

func (r *QuotaRepository) Update(ctx context.Context, quota *models.UserQuota) error {
	return r.db.WithContext(ctx).Save(quota).Error
}
