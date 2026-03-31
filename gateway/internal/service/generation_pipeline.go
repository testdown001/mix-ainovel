package service

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/arboris-novel/gateway/internal/cache"
	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/arboris-novel/gateway/internal/models"
	"github.com/arboris-novel/gateway/internal/repository"
	"go.uber.org/zap"
	"golang.org/x/sync/semaphore"
)

// WritingStage mirrors Python WritingStage constants
type WritingStage string

const (
	StageInit        WritingStage = "init"
	StageParse       WritingStage = "parse"
	StagePlan        WritingStage = "plan"
	StagePreview     WritingStage = "preview"
	StageWriting     WritingStage = "writing"
	StagePostProcess WritingStage = "post_process"
	StageReview      WritingStage = "review"
	StageFinalize    WritingStage = "finalize"
)

// SSEEvent is a Server-Sent Event emitted during generation.
type SSEEvent struct {
	Event string      `json:"event"`
	Data  interface{} `json:"data,omitempty"`
}

// PipelineConfig holds generation pipeline settings.
type PipelineConfig struct {
	MaxLLMConcurrency int64
	DefaultTimeout    time.Duration
	BatchTimeout      time.Duration
	FastAPIBaseURL    string
}

// GenerationPipeline orchestrates chapter generation with channel-based stages.
type GenerationPipeline struct {
	repo     *repository.ProjectRepository
	cache    *cache.Cache
	llmSem   *semaphore.Weighted // bounds concurrent LLM calls
	config   PipelineConfig
}

func NewGenerationPipeline(repo *repository.ProjectRepository, cache *cache.Cache, cfg PipelineConfig) *GenerationPipeline {
	if cfg.MaxLLMConcurrency <= 0 {
		cfg.MaxLLMConcurrency = 5
	}
	if cfg.DefaultTimeout <= 0 {
		cfg.DefaultTimeout = 10 * time.Minute
	}
	return &GenerationPipeline{
		repo:   repo,
		cache:  cache,
		llmSem: semaphore.NewWeighted(cfg.MaxLLMConcurrency),
		config: cfg,
	}
}

// GenerateRequest is the input to the pipeline.
type GenerateRequest struct {
	ProjectID     string `json:"project_id"`
	ChapterNumber int    `json:"chapter_number"`
	UserID        int    `json:"user_id"`
	Config        map[string]interface{} `json:"config,omitempty"`
}

// GenerateResult is the output of the pipeline.
type GenerateResult struct {
	ChapterNumber int               `json:"chapter_number"`
	Versions      []VersionResponse `json:"versions,omitempty"`
	Status        string            `json:"status"`
	Error         string            `json:"error,omitempty"`
}

// Generate runs the full chapter generation pipeline.
// events channel receives SSE events for real-time streaming. Can be nil for non-streaming.
func (p *GenerationPipeline) Generate(ctx context.Context, req GenerateRequest, events chan<- SSEEvent) (*GenerateResult, error) {
	ctx, cancel := context.WithTimeout(ctx, p.config.DefaultTimeout)
	defer cancel()

	emit := func(event string, data interface{}) {
		if events != nil {
			select {
			case events <- SSEEvent{Event: event, Data: data}:
			case <-ctx.Done():
			}
		}
	}

	emit("started", map[string]interface{}{
		"project_id":     req.ProjectID,
		"chapter_number": req.ChapterNumber,
		"timestamp":      time.Now().UTC(),
	})

	// Stage 1: Init — validate and prepare
	emit("stage", map[string]interface{}{"stage": StageInit, "status": "running"})

	chapter, err := p.repo.GetOrCreateChapter(ctx, req.ProjectID, req.ChapterNumber)
	if err != nil {
		emit("error", map[string]string{"message": err.Error()})
		return nil, err
	}

	chapter.Status = "generating"
	if err := p.repo.UpdateChapter(ctx, chapter); err != nil {
		return nil, err
	}

	// Stage 2: Plan — load context (outline, blueprint, previous chapters)
	emit("stage", map[string]interface{}{"stage": StagePlan, "status": "running"})

	contextData, err := p.loadGenerationContext(ctx, req.ProjectID, req.ChapterNumber)
	if err != nil {
		p.markFailed(ctx, chapter)
		emit("error", map[string]string{"message": "failed to load context"})
		return nil, err
	}

	emit("stage", map[string]interface{}{"stage": StagePlan, "status": "completed", "context_keys": len(contextData)})

	// Stage 3: Writing — acquire semaphore, call LLM
	emit("stage", map[string]interface{}{"stage": StageWriting, "status": "running"})

	if err := p.llmSem.Acquire(ctx, 1); err != nil {
		p.markFailed(ctx, chapter)
		emit("error", map[string]string{"message": "LLM concurrency limit reached"})
		return nil, fmt.Errorf("LLM semaphore: %w", err)
	}

	content, err := p.callLLMGeneration(ctx, req, contextData, emit)
	p.llmSem.Release(1)

	if err != nil {
		p.markFailed(ctx, chapter)
		emit("error", map[string]string{"message": err.Error()})
		return nil, err
	}

	// Stage 4: Post-process — create version, update chapter
	emit("stage", map[string]interface{}{"stage": StagePostProcess, "status": "running"})

	version := &models.ChapterVersion{
		ChapterID:    chapter.ID,
		VersionLabel: strPtr("v1"),
		Content:      content,
	}
	if err := p.repo.CreateVersion(ctx, version); err != nil {
		p.markFailed(ctx, chapter)
		return nil, err
	}

	chapter.Status = "generated"
	chapter.WordCount = countWords(content)
	chapter.SelectedVersionID = &version.ID
	if err := p.repo.UpdateChapter(ctx, chapter); err != nil {
		return nil, err
	}

	// Invalidate project cache
	p.cache.InvalidateProject(ctx, req.ProjectID)

	emit("stage", map[string]interface{}{"stage": StageFinalize, "status": "completed"})
	emit("completed", map[string]interface{}{
		"chapter_number": req.ChapterNumber,
		"word_count":     chapter.WordCount,
		"version_id":     version.ID,
	})

	return &GenerateResult{
		ChapterNumber: req.ChapterNumber,
		Versions: []VersionResponse{{
			ID:           version.ID,
			VersionLabel: version.VersionLabel,
			Content:      content,
			CreatedAt:    version.CreatedAt,
		}},
		Status: "generated",
	}, nil
}

// BatchGenerate uses fan-out/fan-in to generate multiple chapters concurrently.
func (p *GenerationPipeline) BatchGenerate(ctx context.Context, projectID string, userID int, chapterNumbers []int, events chan<- SSEEvent) ([]GenerateResult, error) {
	ctx, cancel := context.WithTimeout(ctx, p.config.BatchTimeout)
	defer cancel()

	results := make([]GenerateResult, len(chapterNumbers))
	var mu sync.Mutex
	var wg sync.WaitGroup

	for i, num := range chapterNumbers {
		wg.Add(1)
		go func(idx, chNum int) {
			defer wg.Done()

			req := GenerateRequest{
				ProjectID:     projectID,
				ChapterNumber: chNum,
				UserID:        userID,
			}

			result, err := p.Generate(ctx, req, events)
			mu.Lock()
			defer mu.Unlock()

			if err != nil {
				results[idx] = GenerateResult{
					ChapterNumber: chNum,
					Status:        "failed",
					Error:         err.Error(),
				}
			} else {
				results[idx] = *result
			}
		}(i, num)
	}

	wg.Wait()
	return results, nil
}

// --- Internal helpers ---

func (p *GenerationPipeline) loadGenerationContext(ctx context.Context, projectID string, chapterNumber int) (map[string]interface{}, error) {
	contextData := make(map[string]interface{})

	outline, err := p.repo.FindOutlinesByProject(ctx, projectID)
	if err != nil {
		return nil, err
	}

	for _, o := range outline {
		if o.ChapterNumber == chapterNumber {
			contextData["current_outline"] = map[string]interface{}{
				"title":   o.Title,
				"summary": o.Summary,
			}
			break
		}
	}

	bp, _ := p.repo.FindBlueprintByProject(ctx, projectID)
	if bp != nil {
		contextData["blueprint"] = map[string]interface{}{
			"genre":        bp.Genre,
			"style":        bp.Style,
			"world_setting": bp.WorldSetting,
		}
		contextData["characters_count"] = len(bp.Characters)
	}

	contextData["chapter_number"] = chapterNumber
	return contextData, nil
}

// callLLMGeneration delegates actual LLM call to the Python backend
// (via HTTP to FastAPI) since LLM orchestration remains in Python for now.
// The semaphore ensures bounded concurrency regardless of Python backend behavior.
func (p *GenerationPipeline) callLLMGeneration(ctx context.Context, req GenerateRequest, contextData map[string]interface{}, emit func(string, interface{})) (string, error) {
	emit("stage", map[string]interface{}{
		"stage":  StageWriting,
		"detail": "delegating to Python LLM orchestrator",
	})

	payload := map[string]interface{}{
		"project_id":     req.ProjectID,
		"chapter_number": req.ChapterNumber,
		"user_id":        req.UserID,
		"context":        contextData,
		"config":         req.Config,
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}

	_ = body // will be used with http.Post to FastAPI

	// Placeholder: in production, HTTP POST to FastAPI /api/internal/generate
	// and stream text_delta events back through the SSE channel.
	// For now, return a stub indicating delegation.
	logger.Info("LLM generation delegated to Python backend",
		zap.String("project_id", req.ProjectID),
		zap.Int("chapter", req.ChapterNumber),
	)

	return fmt.Sprintf("[Generation delegated to Python backend for chapter %d]", req.ChapterNumber), nil
}

func (p *GenerationPipeline) markFailed(ctx context.Context, chapter *models.Chapter) {
	chapter.Status = "generation_failed"
	_ = p.repo.UpdateChapter(ctx, chapter)
}

func strPtr(s string) *string { return &s }

func countWords(content string) int {
	count := 0
	for _, r := range content {
		if r > 127 {
			count++ // CJK character
		}
	}
	if count == 0 {
		// ASCII word count fallback
		inWord := false
		for _, r := range content {
			if r == ' ' || r == '\n' || r == '\t' {
				inWord = false
			} else if !inWord {
				inWord = true
				count++
			}
		}
	}
	return count
}
