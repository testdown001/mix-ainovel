package taskdispatcher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"

	"github.com/arboris-novel/gateway/internal/logger"
	"go.uber.org/zap"
)

// ============================================================
// Worker Pool
//
// 管理与 Python AI Worker 之间的通信：
// - HTTP 方式：通过 HTTP POST 回调 Python Worker
// - 连接池复用，减少连接开销
// - 支持进度回调
// ============================================================

// WorkerPool Worker 连接池
type WorkerPool struct {
	config     *Config
	httpClient *http.Client
	mu         sync.RWMutex
	workers    []*WorkerInfo
}

// WorkerInfo Worker 信息
type WorkerInfo struct {
	ID         string    `json:"id"`
	BaseURL    string    `json:"base_url"`
	Healthy    bool      `json:"healthy"`
	ActiveJobs int       `json:"active_jobs"`
	MaxJobs    int       `json:"max_jobs"`
	LastPing   time.Time `json:"last_ping"`
}

// NewWorkerPool 创建 Worker Pool
func NewWorkerPool(cfg *Config) *WorkerPool {
	pool := &WorkerPool{
		config: cfg,
		httpClient: &http.Client{
			Timeout: cfg.DefaultTimeout + 30*time.Second, // 超时留余量
			Transport: &http.Transport{
				MaxIdleConns:        100,
				MaxConnsPerHost:     50,
				MaxIdleConnsPerHost: 20,
				IdleConnTimeout:     90 * time.Second,
			},
		},
		workers: make([]*WorkerInfo, 0),
	}

	// 注册默认 Worker（Python FastAPI）
	pool.RegisterWorker(&WorkerInfo{
		ID:      "python-worker-1",
		BaseURL: cfg.WorkerCallbackURL,
		Healthy: true,
		MaxJobs: 10,
	})

	return pool
}

// RegisterWorker 注册 Worker
func (p *WorkerPool) RegisterWorker(worker *WorkerInfo) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.workers = append(p.workers, worker)
	logger.Info("Worker registered", zap.String("id", worker.ID), zap.String("url", worker.BaseURL))
}

// Execute 执行任务（选择最佳 Worker 发送）
func (p *WorkerPool) Execute(ctx context.Context, task *Task) (json.RawMessage, error) {
	worker := p.selectWorker()
	if worker == nil {
		return nil, fmt.Errorf("没有可用的 Worker")
	}

	worker.ActiveJobs++
	defer func() { worker.ActiveJobs-- }()

	switch task.Type {
	case TaskGenerateChapter:
		return p.executeChapterGenerate(ctx, worker, task)
	case TaskBatchGenerate:
		return p.executeBatchGenerate(ctx, worker, task)
	default:
		return nil, fmt.Errorf("未知任务类型: %s", task.Type)
	}
}

// Close 关闭连接池
func (p *WorkerPool) Close() {
	p.httpClient.CloseIdleConnections()
}

// GetWorkers 获取 Worker 列表
func (p *WorkerPool) GetWorkers() []*WorkerInfo {
	p.mu.RLock()
	defer p.mu.RUnlock()
	result := make([]*WorkerInfo, len(p.workers))
	copy(result, p.workers)
	return result
}

// ============================================================
// 内部方法
// ============================================================

// selectWorker 选择最佳 Worker（最少活跃任务）
func (p *WorkerPool) selectWorker() *WorkerInfo {
	p.mu.RLock()
	defer p.mu.RUnlock()

	var best *WorkerInfo
	for _, w := range p.workers {
		if !w.Healthy || w.ActiveJobs >= w.MaxJobs {
			continue
		}
		if best == nil || w.ActiveJobs < best.ActiveJobs {
			best = w
		}
	}
	return best
}

// WorkerTaskRequest 发送给 Python Worker 的任务请求
type WorkerTaskRequest struct {
	TaskID         string          `json:"task_id"`
	TaskType       string          `json:"task_type"`
	ProjectID      string          `json:"project_id"`
	ChapterNumber  int             `json:"chapter_number,omitempty"`
	ChapterNumbers []int           `json:"chapter_numbers,omitempty"`
	UserID         int             `json:"user_id"`
	Config         json.RawMessage `json:"config"`
	CallbackURL    string          `json:"callback_url"` // 进度回调地址
}

// WorkerTaskResponse Python Worker 返回的结果
type WorkerTaskResponse struct {
	Status   string          `json:"status"` // completed, failed
	Result   json.RawMessage `json:"result,omitempty"`
	Error    string          `json:"error,omitempty"`
	Duration int64           `json:"duration_ms,omitempty"`
}

// executeChapterGenerate 执行章节生成
func (p *WorkerPool) executeChapterGenerate(ctx context.Context, worker *WorkerInfo, task *Task) (json.RawMessage, error) {
	var payload ChapterGeneratePayload
	if err := json.Unmarshal(task.Payload, &payload); err != nil {
		return nil, fmt.Errorf("解析任务载荷失败: %w", err)
	}

	// 构造发送给 Python Worker 的请求
	configData, _ := json.Marshal(map[string]interface{}{
		"preset":           payload.Preset,
		"use_agent_system": payload.UseAgentSystem,
		"rag_mode":         payload.RAGMode,
		"writing_notes":    payload.WritingNotes,
		"extra":            payload.Extra,
	})

	workerReq := &WorkerTaskRequest{
		TaskID:        task.ID,
		TaskType:      string(task.Type),
		ProjectID:     payload.ProjectID,
		ChapterNumber: payload.ChapterNumber,
		UserID:        payload.UserID,
		Config:        configData,
		CallbackURL:   fmt.Sprintf("http://gateway:3000/internal/tasks/%s/progress", task.ID),
	}

	return p.callWorker(ctx, worker, "/execute", workerReq)
}

// executeBatchGenerate 执行批量生成
func (p *WorkerPool) executeBatchGenerate(ctx context.Context, worker *WorkerInfo, task *Task) (json.RawMessage, error) {
	var payload BatchGeneratePayload
	if err := json.Unmarshal(task.Payload, &payload); err != nil {
		return nil, fmt.Errorf("解析任务载荷失败: %w", err)
	}

	configData, _ := json.Marshal(map[string]interface{}{
		"preset":           payload.Preset,
		"use_agent_system": payload.UseAgentSystem,
		"rag_mode":         payload.RAGMode,
		"extra":            payload.Extra,
	})

	workerReq := &WorkerTaskRequest{
		TaskID:         task.ID,
		TaskType:       string(task.Type),
		ProjectID:      payload.ProjectID,
		ChapterNumbers: payload.ChapterNumbers,
		UserID:         payload.UserID,
		Config:         configData,
		CallbackURL:    fmt.Sprintf("http://gateway:3000/internal/tasks/%s/progress", task.ID),
	}

	return p.callWorker(ctx, worker, "/execute", workerReq)
}

// callWorker 调用 Python Worker
func (p *WorkerPool) callWorker(ctx context.Context, worker *WorkerInfo, path string, req *WorkerTaskRequest) (json.RawMessage, error) {
	url := worker.BaseURL + path

	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("序列化请求失败: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("创建请求失败: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("X-Task-ID", req.TaskID)

	logger.Debug("Calling Python Worker",
		zap.String("url", url),
		zap.String("task_id", req.TaskID),
	)

	resp, err := p.httpClient.Do(httpReq)
	if err != nil {
		// 标记 Worker 不健康
		worker.Healthy = false
		return nil, fmt.Errorf("调用 Worker 失败: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("读取响应失败: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Worker 返回错误 (HTTP %d): %s", resp.StatusCode, string(respBody))
	}

	var workerResp WorkerTaskResponse
	if err := json.Unmarshal(respBody, &workerResp); err != nil {
		return nil, fmt.Errorf("解析响应失败: %w", err)
	}

	if workerResp.Status == "failed" {
		return nil, fmt.Errorf("Worker 执行失败: %s", workerResp.Error)
	}

	return workerResp.Result, nil
}
