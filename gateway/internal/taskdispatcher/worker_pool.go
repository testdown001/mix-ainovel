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

// workerRecoveryCooldown 一个 Worker 因传输错误被标记不健康后的冷却期；
// 冷却期过后 selectWorker 会乐观地再次尝试它，避免一次网络抖动让 Worker 永久下线。
const workerRecoveryCooldown = 30 * time.Second

// WorkerPool Worker 连接池
type WorkerPool struct {
	config     *Config
	httpClient *http.Client
	mu         sync.RWMutex
	workers    []*WorkerInfo
}

// WorkerInfo Worker 信息
type WorkerInfo struct {
	ID          string    `json:"id"`
	BaseURL     string    `json:"base_url"`
	Healthy     bool      `json:"healthy"`
	ActiveJobs  int       `json:"active_jobs"`
	MaxJobs     int       `json:"max_jobs"`
	LastPing    time.Time `json:"last_ping"`
	LastFailure time.Time `json:"last_failure,omitempty"`
}

// NewWorkerPool 创建 Worker Pool
func NewWorkerPool(cfg *Config) *WorkerPool {
	// HTTP 客户端超时是全局上限（逐任务超时由 dispatcher 的 per-task context 约束），
	// 须覆盖耗时最长的单次 /execute 调用：蓝图任务超时可能大于默认任务超时。
	clientTimeout := cfg.DefaultTimeout
	if cfg.BlueprintTimeout > clientTimeout {
		clientTimeout = cfg.BlueprintTimeout
	}
	pool := &WorkerPool{
		config: cfg,
		httpClient: &http.Client{
			Timeout: clientTimeout + 30*time.Second, // 超时留余量
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

	p.mu.Lock()
	worker.ActiveJobs++
	p.mu.Unlock()
	defer func() {
		p.mu.Lock()
		worker.ActiveJobs--
		p.mu.Unlock()
	}()

	switch task.Type {
	case TaskGenerateChapter:
		return p.executeChapterGenerate(ctx, worker, task)
	case TaskBatchGenerate:
		return p.executeBatchGenerate(ctx, worker, task)
	case TaskBlueprintGenerate:
		return p.executeBlueprintGenerate(ctx, worker, task)
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
		// 不健康且仍在冷却期内才跳过；冷却期过后乐观重试（自愈）
		if !w.Healthy && time.Since(w.LastFailure) < workerRecoveryCooldown {
			continue
		}
		if w.ActiveJobs >= w.MaxJobs {
			continue
		}
		if best == nil || w.ActiveJobs < best.ActiveJobs {
			best = w
		}
	}
	return best
}

// markWorkerUnhealthy 标记 Worker 不健康并记录失败时刻（进入冷却期）
func (p *WorkerPool) markWorkerUnhealthy(w *WorkerInfo) {
	p.mu.Lock()
	w.Healthy = false
	w.LastFailure = time.Now()
	p.mu.Unlock()
}

// markWorkerHealthy 传输成功即视为 Worker 可达，恢复健康
func (p *WorkerPool) markWorkerHealthy(w *WorkerInfo) {
	p.mu.Lock()
	w.Healthy = true
	w.LastPing = time.Now()
	p.mu.Unlock()
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
	Status    string          `json:"status"` // completed, failed
	Result    json.RawMessage `json:"result,omitempty"`
	Error     string          `json:"error,omitempty"`
	Duration  int64           `json:"duration_ms,omitempty"`
	Permanent bool            `json:"permanent,omitempty"` // true=确定性失败（如档位门控 403），重试无意义
}

// PermanentTaskError 确定性任务失败：dispatcher 不应对其重试
type PermanentTaskError struct {
	msg string
}

func (e *PermanentTaskError) Error() string { return e.msg }

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

// executeBlueprintGenerate 执行蓝图生成
func (p *WorkerPool) executeBlueprintGenerate(ctx context.Context, worker *WorkerInfo, task *Task) (json.RawMessage, error) {
	var payload BlueprintGeneratePayload
	if err := json.Unmarshal(task.Payload, &payload); err != nil {
		return nil, fmt.Errorf("解析任务载荷失败: %w", err)
	}

	depth := payload.Depth
	if depth == "" {
		depth = "deep" // 旧任务载荷无 depth 字段，行为与现网一致
	}
	configJSON, err := json.Marshal(map[string]string{"depth": depth})
	if err != nil {
		return nil, fmt.Errorf("序列化蓝图配置失败: %w", err)
	}

	workerReq := &WorkerTaskRequest{
		TaskID:    task.ID,
		TaskType:  string(task.Type),
		ProjectID: payload.ProjectID,
		UserID:    payload.UserID,
		Config:      json.RawMessage(configJSON),
		CallbackURL: fmt.Sprintf("http://gateway:3000/internal/tasks/%s/progress", task.ID),
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
	// 内部调用鉴权：FastAPI /api/internal/tasks/execute 入站强制校验该密钥
	if p.config != nil && p.config.InternalCallbackSecret != "" {
		httpReq.Header.Set("X-Internal-Secret", p.config.InternalCallbackSecret)
	}

	logger.Debug("Calling Python Worker",
		zap.String("url", url),
		zap.String("task_id", req.TaskID),
	)

	resp, err := p.httpClient.Do(httpReq)
	if err != nil {
		// 传输错误：进入冷却期，避免一次抖动让 Worker 永久下线
		p.markWorkerUnhealthy(worker)
		return nil, fmt.Errorf("调用 Worker 失败: %w", err)
	}
	// 传输成功，Worker 可达
	p.markWorkerHealthy(worker)
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
		if workerResp.Permanent {
			return nil, &PermanentTaskError{msg: fmt.Sprintf("Worker 执行失败(不可重试): %s", workerResp.Error)}
		}
		return nil, fmt.Errorf("Worker 执行失败: %s", workerResp.Error)
	}

	return workerResp.Result, nil
}
