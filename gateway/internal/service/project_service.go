package service

import (
	"context"
	"fmt"
	"time"

	"github.com/arboris-novel/gateway/internal/cache"
	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/arboris-novel/gateway/internal/models"
	"github.com/arboris-novel/gateway/internal/repository"
	"go.uber.org/zap"
	"golang.org/x/sync/errgroup"
)

type ProjectService struct {
	repo  *repository.ProjectRepository
	cache *cache.Cache
}

func NewProjectService(repo *repository.ProjectRepository, cache *cache.Cache) *ProjectService {
	return &ProjectService{repo: repo, cache: cache}
}

// --- Serialized project response (mirrors Python NovelProjectSchema) ---

type ProjectResponse struct {
	ID            string                  `json:"id"`
	UserID        int                     `json:"user_id"`
	Title         string                  `json:"title"`
	InitialPrompt *string                 `json:"initial_prompt,omitempty"`
	IsCompleted   bool                    `json:"is_completed"`
	Blueprint     *BlueprintResponse      `json:"blueprint,omitempty"`
	Chapters      []ChapterResponse       `json:"chapters"`
	Conversations []ConversationResponse  `json:"conversation_history,omitempty"`
	CreatedAt     time.Time               `json:"created_at"`
	UpdatedAt     time.Time               `json:"updated_at"`
}

type BlueprintResponse struct {
	ProjectID        string                       `json:"project_id"`
	Title            *string                      `json:"title,omitempty"`
	Genre            *string                      `json:"genre,omitempty"`
	Style            *string                      `json:"style,omitempty"`
	Tone             *string                      `json:"tone,omitempty"`
	TargetAudience   *string                      `json:"target_audience,omitempty"`
	OneSentenceSummary *string                    `json:"one_sentence_summary,omitempty"`
	FullSynopsis     *string                      `json:"full_synopsis,omitempty"`
	WorldSetting     models.JSONMap               `json:"world_setting,omitempty"`
	GoldenFinger     models.JSONMap               `json:"golden_finger,omitempty"`
	Characters       []BlueprintCharacterResponse `json:"characters,omitempty"`
	Relationships    []BlueprintRelResponse       `json:"relationships,omitempty"`
	ChapterOutline   []OutlineResponse            `json:"chapter_outline,omitempty"`
	Foreshadowings   []ForeshadowingResponse      `json:"foreshadowings,omitempty"`
}

type BlueprintCharacterResponse struct {
	ID                        int64          `json:"id"`
	Name                      string         `json:"name"`
	Identity                  *string        `json:"identity,omitempty"`
	Personality               *string        `json:"personality,omitempty"`
	Goals                     *string        `json:"goals,omitempty"`
	Abilities                 *string        `json:"abilities,omitempty"`
	RelationshipToProtagonist *string        `json:"relationship_to_protagonist,omitempty"`
	Extra                     models.JSONMap `json:"extra,omitempty"`
	Position                  int            `json:"position"`
}

type BlueprintRelResponse struct {
	ID            int64   `json:"id"`
	CharacterFrom string  `json:"character_from"`
	CharacterTo   string  `json:"character_to"`
	Description   *string `json:"description,omitempty"`
}

type OutlineResponse struct {
	ChapterNumber int            `json:"chapter_number"`
	Title         string         `json:"title"`
	Summary       *string        `json:"summary,omitempty"`
	Metadata      models.JSONMap `json:"metadata,omitempty"`
}

type ForeshadowingResponse struct {
	ID                    int64              `json:"id"`
	Name                  *string            `json:"name,omitempty"`
	ChapterNumber         int                `json:"chapter_number"`
	Content               string             `json:"content"`
	Type                  string             `json:"type"`
	Status                string             `json:"status"`
	TargetRevealChapter   *int               `json:"target_reveal_chapter,omitempty"`
	RevealMethod          *string            `json:"reveal_method,omitempty"`
	RelatedCharacters     models.JSONSlice   `json:"related_characters,omitempty"`
	RelatedPlots          models.JSONSlice   `json:"related_plots,omitempty"`
	Importance            *string            `json:"importance,omitempty"`
}

type ChapterResponse struct {
	ChapterNumber int                `json:"chapter_number"`
	OutlineTitle  *string            `json:"outline_title,omitempty"`
	OutlineSummary *string           `json:"outline_summary,omitempty"`
	RealSummary   *string            `json:"real_summary,omitempty"`
	Content       *string            `json:"content,omitempty"`
	Status        string             `json:"status"`
	WordCount     int                `json:"word_count"`
	Versions      []VersionResponse  `json:"versions,omitempty"`
}

type VersionResponse struct {
	ID           int64          `json:"id"`
	VersionLabel *string        `json:"version_label,omitempty"`
	Provider     *string        `json:"provider,omitempty"`
	Content      string         `json:"content"`
	Metadata     models.JSONSlice `json:"metadata,omitempty"`
	CreatedAt    time.Time      `json:"created_at"`
}

type ConversationResponse struct {
	Seq     int            `json:"seq"`
	Role    string         `json:"role"`
	Content string         `json:"content"`
	Metadata models.JSONMap `json:"metadata,omitempty"`
}

// --- Get project with errgroup parallel queries ---

func (s *ProjectService) GetProject(ctx context.Context, projectID string, userID int, includeContent bool) (*ProjectResponse, error) {
	cacheKey := fmt.Sprintf("project:%s:full:%v", projectID, includeContent)

	// Try cache first (singleflight prevents stampede)
	var resp ProjectResponse
	if s.cache.GetJSON(ctx, cacheKey, &resp) {
		if resp.UserID != userID {
			return nil, ErrProjectNotFound
		}
		return &resp, nil
	}

	// Load project record
	project, err := s.repo.FindByID(ctx, projectID)
	if err != nil {
		return nil, err
	}
	if project.UserID != userID {
		return nil, ErrProjectNotFound
	}

	// Parallel queries via errgroup
	g, gctx := errgroup.WithContext(ctx)

	var (
		blueprint      *models.NovelBlueprint
		chapters       []models.Chapter
		outlines       []models.ChapterOutline
		foreshadowings []models.Foreshadowing
		conversations  []models.NovelConversation
	)

	g.Go(func() error {
		var e error
		blueprint, e = s.repo.FindBlueprintByProject(gctx, projectID)
		return e
	})

	g.Go(func() error {
		var e error
		chapters, e = s.repo.FindChaptersByProject(gctx, projectID)
		return e
	})

	g.Go(func() error {
		var e error
		outlines, e = s.repo.FindOutlinesByProject(gctx, projectID)
		return e
	})

	g.Go(func() error {
		var e error
		foreshadowings, e = s.repo.FindForeshadowingsByProject(gctx, projectID)
		return e
	})

	g.Go(func() error {
		var e error
		conversations, e = s.repo.FindConversationsByProject(gctx, projectID)
		return e
	})

	if err := g.Wait(); err != nil {
		return nil, fmt.Errorf("parallel project load failed: %w", err)
	}

	// Assemble response
	resp = s.buildProjectResponse(project, blueprint, chapters, outlines, foreshadowings, conversations, includeContent)

	// Cache result (30 min TTL)
	if err := s.cache.SetJSON(ctx, cacheKey, &resp); err != nil {
		logger.Warn("failed to cache project", zap.String("project_id", projectID), zap.Error(err))
	}

	return &resp, nil
}

// --- Section queries (partial project data) ---

type SectionName string

const (
	SectionOverview       SectionName = "overview"
	SectionWorldSetting   SectionName = "world_setting"
	SectionCharacters     SectionName = "characters"
	SectionRelationships  SectionName = "relationships"
	SectionChapterOutline SectionName = "chapter_outline"
	SectionChapters       SectionName = "chapters"
)

func (s *ProjectService) GetSection(ctx context.Context, projectID string, userID int, section SectionName) (interface{}, error) {
	project, err := s.repo.FindByID(ctx, projectID)
	if err != nil {
		return nil, err
	}
	if project.UserID != userID {
		return nil, ErrProjectNotFound
	}

	switch section {
	case SectionOverview:
		return map[string]interface{}{
			"id":             project.ID,
			"title":          project.Title,
			"initial_prompt": project.InitialPrompt,
			"is_completed":   project.IsCompleted,
			"created_at":     project.CreatedAt,
			"updated_at":     project.UpdatedAt,
		}, nil

	case SectionWorldSetting:
		bp, _ := s.repo.FindBlueprintByProject(ctx, projectID)
		if bp == nil {
			return nil, nil
		}
		return bp.WorldSetting, nil

	case SectionCharacters:
		bp, _ := s.repo.FindBlueprintByProject(ctx, projectID)
		if bp == nil {
			return []BlueprintCharacterResponse{}, nil
		}
		return s.buildCharacters(bp.Characters), nil

	case SectionRelationships:
		bp, _ := s.repo.FindBlueprintByProject(ctx, projectID)
		if bp == nil {
			return []BlueprintRelResponse{}, nil
		}
		return s.buildRelationships(bp.Relationships), nil

	case SectionChapterOutline:
		outlines, _ := s.repo.FindOutlinesByProject(ctx, projectID)
		return s.buildOutlines(outlines), nil

	case SectionChapters:
		g, gctx := errgroup.WithContext(ctx)
		var chapters []models.Chapter
		var outlines []models.ChapterOutline

		g.Go(func() error {
			var e error
			chapters, e = s.repo.FindChaptersByProject(gctx, projectID)
			return e
		})
		g.Go(func() error {
			var e error
			outlines, e = s.repo.FindOutlinesByProject(gctx, projectID)
			return e
		})
		if err := g.Wait(); err != nil {
			return nil, err
		}
		return s.buildChapters(chapters, outlines, false), nil
	}

	return nil, fmt.Errorf("unknown section: %s", section)
}

// --- List projects ---

func (s *ProjectService) ListProjects(ctx context.Context, userID, page, pageSize int) ([]ProjectSummary, int64, error) {
	offset := (page - 1) * pageSize
	projects, total, err := s.repo.ListByUser(ctx, userID, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}

	summaries := make([]ProjectSummary, len(projects))
	for i, p := range projects {
		summaries[i] = ProjectSummary{
			ID:          p.ID,
			Title:       p.Title,
			Status:      p.Status,
			IsCompleted: p.IsCompleted,
			CreatedAt:   p.CreatedAt,
			UpdatedAt:   p.UpdatedAt,
		}
	}
	return summaries, total, nil
}

type ProjectSummary struct {
	ID          string    `json:"id"`
	Title       string    `json:"title"`
	Status      string    `json:"status"`
	IsCompleted bool      `json:"is_completed"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// --- Get single chapter ---

func (s *ProjectService) GetChapter(ctx context.Context, projectID string, userID int, chapterNumber int) (*ChapterResponse, error) {
	project, err := s.repo.FindByID(ctx, projectID)
	if err != nil {
		return nil, err
	}
	if project.UserID != userID {
		return nil, ErrProjectNotFound
	}

	g, gctx := errgroup.WithContext(ctx)
	var chapter *models.Chapter
	var outline *models.ChapterOutline

	g.Go(func() error {
		var e error
		chapter, e = s.repo.FindChapterWithVersions(gctx, projectID, chapterNumber)
		return e
	})
	g.Go(func() error {
		outlines, e := s.repo.FindOutlinesByProject(gctx, projectID)
		if e != nil {
			return e
		}
		for i := range outlines {
			if outlines[i].ChapterNumber == chapterNumber {
				outline = &outlines[i]
				break
			}
		}
		return nil
	})

	if err := g.Wait(); err != nil {
		return nil, err
	}

	if chapter == nil {
		resp := &ChapterResponse{
			ChapterNumber: chapterNumber,
			Status:        "not_generated",
		}
		if outline != nil {
			resp.OutlineTitle = &outline.Title
			resp.OutlineSummary = outline.Summary
		}
		return resp, nil
	}

	resp := &ChapterResponse{
		ChapterNumber: chapterNumber,
		RealSummary:   chapter.RealSummary,
		Status:        chapter.Status,
		WordCount:     chapter.WordCount,
	}

	if outline != nil {
		resp.OutlineTitle = &outline.Title
		resp.OutlineSummary = outline.Summary
	}

	if chapter.SelectedVersion != nil {
		resp.Content = &chapter.SelectedVersion.Content
	}

	resp.Versions = make([]VersionResponse, len(chapter.Versions))
	for i, v := range chapter.Versions {
		resp.Versions[i] = VersionResponse{
			ID:           v.ID,
			VersionLabel: v.VersionLabel,
			Provider:     v.Provider,
			Content:      v.Content,
			Metadata:     v.Metadata,
			CreatedAt:    v.CreatedAt,
		}
	}

	return resp, nil
}

// --- Builders ---

func (s *ProjectService) buildProjectResponse(
	project *models.NovelProject,
	blueprint *models.NovelBlueprint,
	chapters []models.Chapter,
	outlines []models.ChapterOutline,
	foreshadowings []models.Foreshadowing,
	conversations []models.NovelConversation,
	includeContent bool,
) ProjectResponse {
	resp := ProjectResponse{
		ID:            project.ID,
		UserID:        project.UserID,
		Title:         project.Title,
		InitialPrompt: project.InitialPrompt,
		IsCompleted:   project.IsCompleted,
		CreatedAt:     project.CreatedAt,
		UpdatedAt:     project.UpdatedAt,
	}

	if blueprint != nil {
		bp := &BlueprintResponse{
			ProjectID:        blueprint.ProjectID,
			Title:            blueprint.Title,
			Genre:            blueprint.Genre,
			Style:            blueprint.Style,
			Tone:             blueprint.Tone,
			TargetAudience:   blueprint.TargetAudience,
			OneSentenceSummary: blueprint.OneSentenceSummary,
			FullSynopsis:     blueprint.FullSynopsis,
			WorldSetting:     blueprint.WorldSetting,
			GoldenFinger:     blueprint.GoldenFinger,
			Characters:       s.buildCharacters(blueprint.Characters),
			Relationships:    s.buildRelationships(blueprint.Relationships),
			ChapterOutline:   s.buildOutlines(outlines),
			Foreshadowings:   s.buildForeshadowings(foreshadowings),
		}
		resp.Blueprint = bp
	}

	resp.Chapters = s.buildChapters(chapters, outlines, includeContent)

	if len(conversations) > 0 {
		resp.Conversations = make([]ConversationResponse, len(conversations))
		for i, c := range conversations {
			resp.Conversations[i] = ConversationResponse{
				Seq:     c.Seq,
				Role:    c.Role,
				Content: c.Content,
				Metadata: c.Metadata,
			}
		}
	}

	return resp
}

func (s *ProjectService) buildCharacters(chars []models.BlueprintCharacter) []BlueprintCharacterResponse {
	result := make([]BlueprintCharacterResponse, len(chars))
	for i, c := range chars {
		result[i] = BlueprintCharacterResponse{
			ID:                        c.ID,
			Name:                      c.Name,
			Identity:                  c.Identity,
			Personality:               c.Personality,
			Goals:                     c.Goals,
			Abilities:                 c.Abilities,
			RelationshipToProtagonist: c.RelationshipToProtagonist,
			Extra:                     c.Extra,
			Position:                  c.Position,
		}
	}
	return result
}

func (s *ProjectService) buildRelationships(rels []models.BlueprintRelationship) []BlueprintRelResponse {
	result := make([]BlueprintRelResponse, len(rels))
	for i, r := range rels {
		result[i] = BlueprintRelResponse{
			ID:            r.ID,
			CharacterFrom: r.CharacterFrom,
			CharacterTo:   r.CharacterTo,
			Description:   r.Description,
		}
	}
	return result
}

func (s *ProjectService) buildOutlines(outlines []models.ChapterOutline) []OutlineResponse {
	result := make([]OutlineResponse, len(outlines))
	for i, o := range outlines {
		result[i] = OutlineResponse{
			ChapterNumber: o.ChapterNumber,
			Title:         o.Title,
			Summary:       o.Summary,
			Metadata:      o.Metadata,
		}
	}
	return result
}

func (s *ProjectService) buildForeshadowings(items []models.Foreshadowing) []ForeshadowingResponse {
	result := make([]ForeshadowingResponse, len(items))
	for i, f := range items {
		result[i] = ForeshadowingResponse{
			ID:                  f.ID,
			Name:                f.Name,
			ChapterNumber:       f.ChapterNumber,
			Content:             f.Content,
			Type:                f.Type,
			Status:              f.Status,
			TargetRevealChapter: f.TargetRevealChapter,
			RevealMethod:        f.RevealMethod,
			RelatedCharacters:   f.RelatedCharacters,
			RelatedPlots:        f.RelatedPlots,
			Importance:          f.Importance,
		}
	}
	return result
}

func (s *ProjectService) buildChapters(chapters []models.Chapter, outlines []models.ChapterOutline, includeContent bool) []ChapterResponse {
	outlineMap := make(map[int]*models.ChapterOutline, len(outlines))
	for i := range outlines {
		outlineMap[outlines[i].ChapterNumber] = &outlines[i]
	}

	chapterMap := make(map[int]*models.Chapter, len(chapters))
	allNumbers := make(map[int]bool)
	for i := range chapters {
		chapterMap[chapters[i].ChapterNumber] = &chapters[i]
		allNumbers[chapters[i].ChapterNumber] = true
	}
	for _, o := range outlines {
		allNumbers[o.ChapterNumber] = true
	}

	sorted := make([]int, 0, len(allNumbers))
	for n := range allNumbers {
		sorted = append(sorted, n)
	}
	sortInts(sorted)

	result := make([]ChapterResponse, 0, len(sorted))
	for _, num := range sorted {
		cr := ChapterResponse{
			ChapterNumber: num,
			Status:        "not_generated",
		}

		if o, ok := outlineMap[num]; ok {
			cr.OutlineTitle = &o.Title
			cr.OutlineSummary = o.Summary
		}

		if ch, ok := chapterMap[num]; ok {
			cr.Status = ch.Status
			cr.WordCount = ch.WordCount
			cr.RealSummary = ch.RealSummary

			if includeContent && ch.SelectedVersion != nil {
				cr.Content = &ch.SelectedVersion.Content
			}
		}

		result = append(result, cr)
	}

	return result
}

func sortInts(a []int) {
	for i := 1; i < len(a); i++ {
		for j := i; j > 0 && a[j-1] > a[j]; j-- {
			a[j-1], a[j] = a[j], a[j-1]
		}
	}
}

// ErrProjectNotFound re-exported for handler use
var ErrProjectNotFound = repository.ErrProjectNotFound
