package models

import "time"

type PaymentOrder struct {
	ID              uint64     `gorm:"primaryKey;autoIncrement" json:"id"`
	UserID          int        `gorm:"index;not null" json:"user_id"`
	PlanID          int        `gorm:"index;not null" json:"plan_id"`
	IdempotencyKey  string     `gorm:"uniqueIndex;size:64;not null" json:"idempotency_key"`
	Amount          int64      `gorm:"not null" json:"amount"`
	Currency        string     `gorm:"size:3;default:cny;not null" json:"currency"`
	Status          string     `gorm:"size:20;index;not null" json:"status"`
	Channel         string     `gorm:"size:20;not null" json:"channel"`
	ExternalID      *string    `gorm:"index;size:128" json:"external_id,omitempty"`
	ExternalEventID *string    `gorm:"uniqueIndex;size:128" json:"external_event_id,omitempty"`
	PaidAt          *time.Time `json:"paid_at,omitempty"`
	RefundedAt      *time.Time `json:"refunded_at,omitempty"`
	Metadata        JSONSlice  `gorm:"type:json" json:"metadata,omitempty"`
	CreatedAt       time.Time  `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt       time.Time  `gorm:"autoUpdateTime" json:"updated_at"`

	User *User `gorm:"foreignKey:UserID" json:"-"`
	Plan *Plan `gorm:"foreignKey:PlanID" json:"-"`
}

func (PaymentOrder) TableName() string { return "payment_orders" }

const (
	OrderStatusPending   = "pending"
	OrderStatusPaid      = "paid"
	OrderStatusRefunded  = "refunded"
	OrderStatusCancelled = "cancelled"

	ChannelStripe = "stripe"
	ChannelAlipay = "alipay"
	ChannelWechat = "wechat"
)

type Subscription struct {
	ID                 uint64     `gorm:"primaryKey;autoIncrement" json:"id"`
	UserID             int        `gorm:"uniqueIndex;not null" json:"user_id"`
	PlanID             int        `gorm:"index;not null" json:"plan_id"`
	Status             string     `gorm:"size:20;index" json:"status"`
	CurrentPeriodStart time.Time  `json:"current_period_start"`
	CurrentPeriodEnd   time.Time  `json:"current_period_end"`
	CancelledAt        *time.Time `json:"cancelled_at,omitempty"`
	ExternalSubID      *string    `gorm:"index;size:128" json:"external_sub_id,omitempty"`
	CreatedAt          time.Time  `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt          time.Time  `gorm:"autoUpdateTime" json:"updated_at"`

	User *User `gorm:"foreignKey:UserID" json:"-"`
	Plan *Plan `gorm:"foreignKey:PlanID" json:"-"`
}

func (Subscription) TableName() string { return "subscriptions" }

const (
	SubStatusActive    = "active"
	SubStatusCancelled = "cancelled"
	SubStatusExpired   = "expired"
	SubStatusPastDue   = "past_due"
)
