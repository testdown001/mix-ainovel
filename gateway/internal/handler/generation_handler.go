package handler

import (
	"bufio"
	"encoding/json"
	"fmt"
	"time"

	"github.com/arboris-novel/gateway/internal/auth"
	"github.com/arboris-novel/gateway/internal/service"
	"github.com/arboris-novel/gateway/pkg/response"
	"github.com/gofiber/fiber/v2"
	"github.com/valyala/fasthttp"
)

type GenerationHandler struct {
	pipeline   *service.GenerationPipeline
	quotaSvc   *service.QuotaService
}

func NewGenerationHandler(pipeline *service.GenerationPipeline, quotaSvc *service.QuotaService) *GenerationHandler {
	return &GenerationHandler{pipeline: pipeline, quotaSvc: quotaSvc}
}

func (h *GenerationHandler) RegisterRoutes(router fiber.Router) {
	writer := router.Group("/writer", auth.JWTMiddleware())
	writer.Post("/generate", h.GenerateChapter)
	writer.Post("/generate/stream", h.GenerateChapterStream)
	writer.Post("/batch-generate", h.BatchGenerate)
}

type generateReq struct {
	ProjectID     string                 `json:"project_id"`
	ChapterNumber int                    `json:"chapter_number"`
	Config        map[string]interface{} `json:"config,omitempty"`
}

func (h *GenerationHandler) GenerateChapter(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)

	var req generateReq
	if err := c.BodyParser(&req); err != nil {
		return response.BadRequest(c, "invalid request body")
	}

	if req.ProjectID == "" || req.ChapterNumber < 1 {
		return response.BadRequest(c, "project_id and chapter_number are required")
	}

	// Quota check
	ok, _ := h.quotaSvc.CheckDailyQuotaRedis(c.Context(), userID, 50)
	if !ok {
		return response.TooManyRequests(c, "daily generation quota exceeded")
	}

	result, err := h.pipeline.Generate(c.Context(), service.GenerateRequest{
		ProjectID:     req.ProjectID,
		ChapterNumber: req.ChapterNumber,
		UserID:        userID,
		Config:        req.Config,
	}, nil)

	if err != nil {
		return response.InternalError(c, err.Error())
	}

	// Consume quota
	_ = h.quotaSvc.ConsumeDailyQuotaRedis(c.Context(), userID, 50)

	return response.OK(c, result)
}

// GenerateChapterStream streams SSE events during generation.
func (h *GenerationHandler) GenerateChapterStream(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)

	var req generateReq
	if err := c.BodyParser(&req); err != nil {
		return response.BadRequest(c, "invalid request body")
	}

	if req.ProjectID == "" || req.ChapterNumber < 1 {
		return response.BadRequest(c, "project_id and chapter_number are required")
	}

	ok, _ := h.quotaSvc.CheckDailyQuotaRedis(c.Context(), userID, 50)
	if !ok {
		return response.TooManyRequests(c, "daily generation quota exceeded")
	}

	events := make(chan service.SSEEvent, 64)

	// Run pipeline in background goroutine
	go func() {
		defer close(events)
		_, _ = h.pipeline.Generate(c.Context(), service.GenerateRequest{
			ProjectID:     req.ProjectID,
			ChapterNumber: req.ChapterNumber,
			UserID:        userID,
			Config:        req.Config,
		}, events)
		_ = h.quotaSvc.ConsumeDailyQuotaRedis(c.Context(), userID, 50)
	}()

	// Stream SSE via fasthttp StreamWriter
	c.Set("Content-Type", "text/event-stream")
	c.Set("Cache-Control", "no-cache")
	c.Set("Connection", "keep-alive")
	c.Set("X-Accel-Buffering", "no")

	c.Status(fiber.StatusOK)
	c.Context().SetBodyStreamWriter(fasthttp.StreamWriter(func(w *bufio.Writer) {
		ticker := time.NewTicker(15 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case evt, ok := <-events:
				if !ok {
					return
				}
				data, _ := json.Marshal(evt.Data)
				fmt.Fprintf(w, "event: %s\ndata: %s\n\n", evt.Event, string(data))
				if err := w.Flush(); err != nil {
					return
				}

			case <-ticker.C:
				fmt.Fprintf(w, ": ping\n\n")
				if err := w.Flush(); err != nil {
					return
				}
			}
		}
	}))

	return nil
}

type batchReq struct {
	ProjectID      string `json:"project_id"`
	ChapterNumbers []int  `json:"chapter_numbers"`
}

func (h *GenerationHandler) BatchGenerate(c *fiber.Ctx) error {
	userID := auth.GetUserID(c)

	var req batchReq
	if err := c.BodyParser(&req); err != nil {
		return response.BadRequest(c, "invalid request body")
	}

	if req.ProjectID == "" || len(req.ChapterNumbers) == 0 {
		return response.BadRequest(c, "project_id and chapter_numbers are required")
	}
	if len(req.ChapterNumbers) > 20 {
		return response.BadRequest(c, "maximum 20 chapters per batch")
	}

	results, err := h.pipeline.BatchGenerate(c.Context(), req.ProjectID, userID, req.ChapterNumbers, nil)
	if err != nil {
		return response.InternalError(c, err.Error())
	}

	return response.OK(c, results)
}

