package models

import "time"

type Plan struct {
	ID                int       `gorm:"primaryKey;autoIncrement" json:"id"`
	Name              string    `gorm:"size:64;not null" json:"name"`
	Description       *string   `gorm:"size:255" json:"description,omitempty"`
	Price             float64   `gorm:"default:0;not null" json:"price"`
	Period            string    `gorm:"size:32;default:monthly;not null" json:"period"`
	DailyChapterLimit int       `gorm:"default:0;not null" json:"daily_chapter_limit"`
	MaxNovels         int       `gorm:"default:0;not null" json:"max_novels"`
	Features          *string   `gorm:"type:text" json:"features,omitempty"`
	IsRecommended     bool      `gorm:"default:false;not null" json:"is_recommended"`
	IsActive          bool      `gorm:"default:true;not null" json:"is_active"`
	SortOrder         int       `gorm:"default:0;not null" json:"sort_order"`
	CreatedAt         time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt         time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (Plan) TableName() string { return "plans" }
