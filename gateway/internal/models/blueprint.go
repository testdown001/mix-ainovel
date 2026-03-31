package models

import (
	"database/sql/driver"
	"encoding/json"
	"time"
)

// JSONMap handles MySQL JSON columns as map[string]interface{}.
type JSONMap map[string]interface{}

func (j JSONMap) Value() (driver.Value, error) {
	if j == nil {
		return nil, nil
	}
	return json.Marshal(j)
}

func (j *JSONMap) Scan(value interface{}) error {
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

type NovelBlueprint struct {
	ProjectID        string    `gorm:"primaryKey;size:36" json:"project_id"`
	Title            *string   `gorm:"size:255" json:"title,omitempty"`
	TargetAudience   *string   `gorm:"size:255" json:"target_audience,omitempty"`
	Genre            *string   `gorm:"size:128" json:"genre,omitempty"`
	Style            *string   `gorm:"size:128" json:"style,omitempty"`
	Tone             *string   `gorm:"size:128" json:"tone,omitempty"`
	OneSentenceSummary *string `gorm:"type:text" json:"one_sentence_summary,omitempty"`
	FullSynopsis     *string   `gorm:"type:longtext" json:"full_synopsis,omitempty"`
	WorldSetting     JSONMap   `gorm:"type:json" json:"world_setting,omitempty"`
	GoldenFinger     JSONMap   `gorm:"type:json" json:"golden_finger,omitempty"`
	CreatedAt        time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt        time.Time `gorm:"autoUpdateTime" json:"updated_at"`

	Characters    []BlueprintCharacter    `gorm:"foreignKey:ProjectID;references:ProjectID" json:"characters,omitempty"`
	Relationships []BlueprintRelationship `gorm:"foreignKey:ProjectID;references:ProjectID" json:"relationships,omitempty"`
}

func (NovelBlueprint) TableName() string { return "novel_blueprints" }

type BlueprintCharacter struct {
	ID                        int64   `gorm:"primaryKey;autoIncrement" json:"id"`
	ProjectID                 string  `gorm:"size:36;index;not null" json:"project_id"`
	Name                      string  `gorm:"size:255" json:"name"`
	Identity                  *string `gorm:"size:255" json:"identity,omitempty"`
	Personality               *string `gorm:"type:text" json:"personality,omitempty"`
	Goals                     *string `gorm:"type:text" json:"goals,omitempty"`
	Abilities                 *string `gorm:"type:text" json:"abilities,omitempty"`
	RelationshipToProtagonist *string `gorm:"type:text" json:"relationship_to_protagonist,omitempty"`
	Extra                     JSONMap `gorm:"type:json" json:"extra,omitempty"`
	Position                  int     `gorm:"default:0" json:"position"`
	PowerSystemID             *int    `json:"power_system_id,omitempty"`
	CurrentPowerLevelID       *int    `json:"current_power_level_id,omitempty"`
}

func (BlueprintCharacter) TableName() string { return "blueprint_characters" }

type BlueprintRelationship struct {
	ID            int64   `gorm:"primaryKey;autoIncrement" json:"id"`
	ProjectID     string  `gorm:"size:36;index;not null" json:"project_id"`
	CharacterFrom string  `gorm:"size:255" json:"character_from"`
	CharacterTo   string  `gorm:"size:255" json:"character_to"`
	Description   *string `gorm:"type:text" json:"description,omitempty"`
	Position      int     `gorm:"default:0" json:"position"`
}

func (BlueprintRelationship) TableName() string { return "blueprint_relationships" }

type ChapterOutline struct {
	ID            int64     `gorm:"primaryKey;autoIncrement" json:"id"`
	ProjectID     string    `gorm:"size:36;index;not null" json:"project_id"`
	ChapterNumber int       `gorm:"not null" json:"chapter_number"`
	Title         string    `gorm:"size:255" json:"title"`
	Summary       *string   `gorm:"type:text" json:"summary,omitempty"`
	Metadata      JSONMap   `gorm:"column:metadata;type:json" json:"metadata,omitempty"`
}

func (ChapterOutline) TableName() string { return "chapter_outlines" }

type Foreshadowing struct {
	ID                     int64      `gorm:"primaryKey;autoIncrement" json:"id"`
	ProjectID              string     `gorm:"size:36;index;not null" json:"project_id"`
	ChapterID              *int64     `json:"chapter_id,omitempty"`
	ChapterNumber          int        `json:"chapter_number"`
	Content                string     `gorm:"type:longtext" json:"content"`
	Type                   string     `gorm:"size:32" json:"type"`
	Keywords               JSONSlice  `gorm:"type:json" json:"keywords,omitempty"`
	Status                 string     `gorm:"size:32;index;default:planted" json:"status"`
	ResolvedChapterID      *int64     `json:"resolved_chapter_id,omitempty"`
	ResolvedChapterNumber  *int       `json:"resolved_chapter_number,omitempty"`
	Name                   *string    `gorm:"size:255" json:"name,omitempty"`
	TargetRevealChapter    *int       `json:"target_reveal_chapter,omitempty"`
	RevealMethod           *string    `gorm:"type:text" json:"reveal_method,omitempty"`
	RevealImpact           *string    `gorm:"type:text" json:"reveal_impact,omitempty"`
	RelatedCharacters      JSONSlice  `gorm:"type:json" json:"related_characters,omitempty"`
	RelatedPlots           JSONSlice  `gorm:"type:json" json:"related_plots,omitempty"`
	RelatedForeshadowings  JSONSlice  `gorm:"type:json" json:"related_foreshadowings,omitempty"`
	Importance             *string    `gorm:"size:32" json:"importance,omitempty"`
	Urgency                *int       `json:"urgency,omitempty"`
	IsManual               bool       `gorm:"default:false" json:"is_manual"`
	AIConfidence           *float64   `json:"ai_confidence,omitempty"`
	AuthorNote             *string    `gorm:"type:text" json:"author_note,omitempty"`
	CreatedAt              time.Time  `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt              time.Time  `gorm:"autoUpdateTime" json:"updated_at"`
}

func (Foreshadowing) TableName() string { return "foreshadowings" }

type NovelConversation struct {
	ID        int64     `gorm:"primaryKey;autoIncrement" json:"id"`
	ProjectID string    `gorm:"size:36;index;not null" json:"project_id"`
	Seq       int       `json:"seq"`
	Role      string    `gorm:"size:32" json:"role"`
	Content   string    `gorm:"type:longtext" json:"content"`
	Metadata  JSONMap   `gorm:"column:metadata;type:json" json:"metadata,omitempty"`
	CreatedAt time.Time `gorm:"autoCreateTime" json:"created_at"`
}

func (NovelConversation) TableName() string { return "novel_conversations" }
