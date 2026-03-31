package models

import "time"

type User struct {
	ID             int        `gorm:"primaryKey;autoIncrement" json:"id"`
	Username       string     `gorm:"size:64;uniqueIndex;not null" json:"username"`
	Email          *string    `gorm:"size:128;uniqueIndex" json:"email,omitempty"`
	HashedPassword string     `gorm:"size:255;not null" json:"-"`
	ExternalID     *string    `gorm:"size:255;uniqueIndex" json:"external_id,omitempty"`
	IsAdmin        bool       `gorm:"default:false" json:"is_admin"`
	IsActive       bool       `gorm:"default:true" json:"is_active"`
	CreatedAt      time.Time  `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt      time.Time  `gorm:"autoUpdateTime" json:"updated_at"`

	Quota *UserQuota `gorm:"foreignKey:UserID" json:"quota,omitempty"`
}

func (User) TableName() string { return "users" }

type UserQuota struct {
	ID                     int        `gorm:"primaryKey;autoIncrement" json:"id"`
	UserID                 int        `gorm:"uniqueIndex;not null" json:"user_id"`
	DailyChapterLimit      int        `gorm:"default:10;not null" json:"daily_chapter_limit"`
	DailyChapterUsed       int        `gorm:"default:0;not null" json:"daily_chapter_used"`
	TotalChaptersGenerated int        `gorm:"default:0;not null" json:"total_chapters_generated"`
	StorageLimit           int64      `gorm:"default:1073741824;not null" json:"storage_limit"`
	StorageUsed            int64      `gorm:"default:0;not null" json:"storage_used"`
	MonthlyTokenLimit      int        `gorm:"default:1000000;not null" json:"monthly_token_limit"`
	MonthlyTokenUsed       int        `gorm:"default:0;not null" json:"monthly_token_used"`
	IsPremium              bool       `gorm:"default:false;not null" json:"is_premium"`
	PremiumExpiresAt       *time.Time `json:"premium_expires_at,omitempty"`
	DailyResetAt           time.Time  `gorm:"not null" json:"daily_reset_at"`
	MonthlyResetAt         time.Time  `gorm:"not null" json:"monthly_reset_at"`
	CreatedAt              time.Time  `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt              time.Time  `gorm:"autoUpdateTime" json:"updated_at"`

	User *User `gorm:"foreignKey:UserID" json:"-"`
}

func (UserQuota) TableName() string { return "user_quotas" }
