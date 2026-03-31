package repository

import (
	"context"
	"errors"

	"github.com/arboris-novel/gateway/internal/models"
	"gorm.io/gorm"
)

var (
	ErrOrderNotFound = errors.New("payment order not found")
	ErrSubNotFound   = errors.New("subscription not found")
)

type PaymentRepository struct {
	db *gorm.DB
}

func NewPaymentRepository(db *gorm.DB) *PaymentRepository {
	return &PaymentRepository{db: db}
}

// --- PaymentOrder ---

func (r *PaymentRepository) CreateOrder(ctx context.Context, order *models.PaymentOrder) error {
	return r.db.WithContext(ctx).Create(order).Error
}

func (r *PaymentRepository) FindOrderByID(ctx context.Context, id uint64) (*models.PaymentOrder, error) {
	var order models.PaymentOrder
	err := r.db.WithContext(ctx).First(&order, id).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrOrderNotFound
	}
	return &order, err
}

func (r *PaymentRepository) FindOrderByIdempotencyKey(ctx context.Context, key string) (*models.PaymentOrder, error) {
	var order models.PaymentOrder
	err := r.db.WithContext(ctx).Where("idempotency_key = ?", key).First(&order).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, nil
	}
	return &order, err
}

func (r *PaymentRepository) FindOrderByExternalID(ctx context.Context, externalID string) (*models.PaymentOrder, error) {
	var order models.PaymentOrder
	err := r.db.WithContext(ctx).Where("external_id = ?", externalID).First(&order).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, nil
	}
	return &order, err
}

func (r *PaymentRepository) ExistsByExternalEventID(ctx context.Context, eventID string) (bool, error) {
	var count int64
	err := r.db.WithContext(ctx).Model(&models.PaymentOrder{}).
		Where("external_event_id = ?", eventID).Count(&count).Error
	return count > 0, err
}

func (r *PaymentRepository) UpdateOrder(ctx context.Context, order *models.PaymentOrder) error {
	return r.db.WithContext(ctx).Save(order).Error
}

func (r *PaymentRepository) ListOrdersByUser(ctx context.Context, userID int, limit, offset int) ([]models.PaymentOrder, int64, error) {
	var orders []models.PaymentOrder
	var total int64

	query := r.db.WithContext(ctx).Model(&models.PaymentOrder{}).Where("user_id = ?", userID)
	query.Count(&total)

	err := query.Order("created_at DESC").Limit(limit).Offset(offset).Find(&orders).Error
	return orders, total, err
}

// --- Subscription ---

func (r *PaymentRepository) CreateSubscription(ctx context.Context, sub *models.Subscription) error {
	return r.db.WithContext(ctx).Create(sub).Error
}

func (r *PaymentRepository) FindSubscriptionByUser(ctx context.Context, userID int) (*models.Subscription, error) {
	var sub models.Subscription
	err := r.db.WithContext(ctx).Where("user_id = ?", userID).First(&sub).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, nil
	}
	return &sub, err
}

func (r *PaymentRepository) FindSubscriptionByExternalID(ctx context.Context, externalSubID string) (*models.Subscription, error) {
	var sub models.Subscription
	err := r.db.WithContext(ctx).Where("external_sub_id = ?", externalSubID).First(&sub).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, nil
	}
	return &sub, err
}

func (r *PaymentRepository) UpdateSubscription(ctx context.Context, sub *models.Subscription) error {
	return r.db.WithContext(ctx).Save(sub).Error
}

// --- Plan ---

func (r *PaymentRepository) ListActivePlans(ctx context.Context) ([]models.Plan, error) {
	var plans []models.Plan
	err := r.db.WithContext(ctx).Where("is_active = ?", true).
		Order("sort_order ASC").Find(&plans).Error
	return plans, err
}

func (r *PaymentRepository) FindPlanByID(ctx context.Context, id int) (*models.Plan, error) {
	var plan models.Plan
	err := r.db.WithContext(ctx).First(&plan, id).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, errors.New("plan not found")
	}
	return &plan, err
}

// Transaction executes fn within a database transaction.
func (r *PaymentRepository) Transaction(fn func(tx *gorm.DB) error) error {
	return r.db.Transaction(fn)
}
