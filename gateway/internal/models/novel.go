package models

import (
	"database/sql/driver"
	"encoding/json"
	"time"
)

type JSONSlice []interface{}

func (j JSONSlice) Value() (driver.Value, error) {
	if j == nil {
		return nil, nil
	}
	return json.Marshal(j)
}

func (j *JSONSlice) Scan(value interface{}) error {
	if value == nil {
		*j = nil
		return nil
	}
	var b []byte
	switch v := value.(type) {
	case []byte:
		b = v
	case string:
		b = []byte(v)
	}
	return json.Unmarshal(b, j)
}

type NovelProject struct {
	ID               string     `gorm:"primaryKey;size:36" json:"id"`
	UserID           int        `gorm:"index;not null" json:"user_id"`
	Title            string     `gorm:"size:255;not null" json:"title"`
	InitialPrompt    *string    `gorm:"type:text" json:"initial_prompt,omitempty"`
	Status           string     `gorm:"size:32;default:draft" json:"status"`
	IsCompleted      bool       `gorm:"default:false;not null" json:"is_completed"`
	ReferenceNovelIDs JSONSlice `gorm:"type:json" json:"reference_novel_ids,omitempty"`
	FusionDNA        JSONSlice  `gorm:"type:json" json:"fusion_dna,omitempty"`
	CreatedAt        time.Time  `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt        time.Time  `gorm:"autoUpdateTime" json:"updated_at"`

	User *User `gorm:"foreignKey:UserID" json:"-"`
}

func (NovelProject) TableName() string { return "novel_projects" }

type Chapter struct {
	ID                int64      `gorm:"primaryKey;autoIncrement" json:"id"`
	ProjectID         string     `gorm:"size:36;index;not null" json:"project_id"`
	ChapterNumber     int        `gorm:"not null" json:"chapter_number"`
	RealSummary       *string    `gorm:"type:text" json:"real_summary,omitempty"`
	Status            string     `gorm:"size:32;default:not_generated" json:"status"`
	WordCount         int        `gorm:"default:0" json:"word_count"`
	RagIngestHash     *string    `gorm:"size:64" json:"rag_ingest_hash,omitempty"`
	SelectedVersionID *int64     `json:"selected_version_id,omitempty"`
	CreatedAt         time.Time  `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt         time.Time  `gorm:"autoUpdateTime" json:"updated_at"`

	Project         *NovelProject   `gorm:"foreignKey:ProjectID" json:"-"`
	Versions        []ChapterVersion `gorm:"foreignKey:ChapterID" json:"versions,omitempty"`
	SelectedVersion *ChapterVersion `gorm:"foreignKey:ID;references:SelectedVersionID" json:"selected_version,omitempty"`
}

func (Chapter) TableName() string { return "chapters" }

type ChapterVersion struct {
	ID           int64     `gorm:"primaryKey;autoIncrement" json:"id"`
	ChapterID    int64     `gorm:"index;not null" json:"chapter_id"`
	VersionLabel *string   `gorm:"size:64" json:"version_label,omitempty"`
	Provider     *string   `gorm:"size:64" json:"provider,omitempty"`
	Content      string    `gorm:"type:longtext;not null" json:"content"`
	Metadata     JSONSlice `gorm:"type:json" json:"metadata,omitempty"`
	CreatedAt    time.Time `gorm:"autoCreateTime" json:"created_at"`

	Chapter *Chapter `gorm:"foreignKey:ChapterID" json:"-"`
}

func (ChapterVersion) TableName() string { return "chapter_versions" }
