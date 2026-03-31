package repository

import (
	"context"
	"errors"

	"github.com/arboris-novel/gateway/internal/models"
	"gorm.io/gorm"
)

var ErrProjectNotFound = errors.New("project not found")

type ProjectRepository struct {
	db *gorm.DB
}

func NewProjectRepository(db *gorm.DB) *ProjectRepository {
	return &ProjectRepository{db: db}
}

func (r *ProjectRepository) FindByID(ctx context.Context, id string) (*models.NovelProject, error) {
	var project models.NovelProject
	err := r.db.WithContext(ctx).First(&project, "id = ?", id).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, ErrProjectNotFound
	}
	return &project, err
}

func (r *ProjectRepository) ListByUser(ctx context.Context, userID int, limit, offset int) ([]models.NovelProject, int64, error) {
	var projects []models.NovelProject
	var total int64

	query := r.db.WithContext(ctx).Model(&models.NovelProject{}).Where("user_id = ?", userID)
	query.Count(&total)

	err := query.Order("updated_at DESC").Limit(limit).Offset(offset).Find(&projects).Error
	return projects, total, err
}

// --- Chapter queries ---

func (r *ProjectRepository) FindChaptersByProject(ctx context.Context, projectID string) ([]models.Chapter, error) {
	var chapters []models.Chapter
	err := r.db.WithContext(ctx).
		Where("project_id = ?", projectID).
		Order("chapter_number ASC").
		Find(&chapters).Error
	return chapters, err
}

func (r *ProjectRepository) FindChapterByNumber(ctx context.Context, projectID string, chapterNumber int) (*models.Chapter, error) {
	var chapter models.Chapter
	err := r.db.WithContext(ctx).
		Where("project_id = ? AND chapter_number = ?", projectID, chapterNumber).
		First(&chapter).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, nil
	}
	return &chapter, err
}

func (r *ProjectRepository) FindChapterWithVersions(ctx context.Context, projectID string, chapterNumber int) (*models.Chapter, error) {
	var chapter models.Chapter
	err := r.db.WithContext(ctx).
		Preload("Versions").
		Preload("SelectedVersion").
		Where("project_id = ? AND chapter_number = ?", projectID, chapterNumber).
		First(&chapter).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, nil
	}
	return &chapter, err
}

func (r *ProjectRepository) FindVersionsByChapter(ctx context.Context, chapterID int64) ([]models.ChapterVersion, error) {
	var versions []models.ChapterVersion
	err := r.db.WithContext(ctx).
		Where("chapter_id = ?", chapterID).
		Order("created_at DESC").
		Find(&versions).Error
	return versions, err
}

// --- Blueprint / outline queries (used in parallel by errgroup) ---

func (r *ProjectRepository) FindOutlinesByProject(ctx context.Context, projectID string) ([]models.ChapterOutline, error) {
	var outlines []models.ChapterOutline
	err := r.db.WithContext(ctx).
		Where("project_id = ?", projectID).
		Order("chapter_number ASC").
		Find(&outlines).Error
	return outlines, err
}

func (r *ProjectRepository) FindBlueprintByProject(ctx context.Context, projectID string) (*models.NovelBlueprint, error) {
	var bp models.NovelBlueprint
	err := r.db.WithContext(ctx).
		Preload("Characters").
		Preload("Relationships").
		Where("project_id = ?", projectID).
		First(&bp).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, nil
	}
	return &bp, err
}

func (r *ProjectRepository) FindForeshadowingsByProject(ctx context.Context, projectID string) ([]models.Foreshadowing, error) {
	var items []models.Foreshadowing
	err := r.db.WithContext(ctx).
		Where("project_id = ?", projectID).
		Order("chapter_number ASC, id ASC").
		Find(&items).Error
	return items, err
}

func (r *ProjectRepository) FindConversationsByProject(ctx context.Context, projectID string) ([]models.NovelConversation, error) {
	var convs []models.NovelConversation
	err := r.db.WithContext(ctx).
		Where("project_id = ?", projectID).
		Order("seq ASC").
		Find(&convs).Error
	return convs, err
}

func (r *ProjectRepository) GetOrCreateChapter(ctx context.Context, projectID string, chapterNumber int) (*models.Chapter, error) {
	chapter, err := r.FindChapterByNumber(ctx, projectID, chapterNumber)
	if err != nil {
		return nil, err
	}
	if chapter != nil {
		return chapter, nil
	}

	chapter = &models.Chapter{
		ProjectID:     projectID,
		ChapterNumber: chapterNumber,
		Status:        "not_generated",
	}
	if err := r.db.WithContext(ctx).Create(chapter).Error; err != nil {
		return nil, err
	}
	return chapter, nil
}

func (r *ProjectRepository) UpdateChapter(ctx context.Context, chapter *models.Chapter) error {
	return r.db.WithContext(ctx).Save(chapter).Error
}

func (r *ProjectRepository) CreateVersion(ctx context.Context, version *models.ChapterVersion) error {
	return r.db.WithContext(ctx).Create(version).Error
}
