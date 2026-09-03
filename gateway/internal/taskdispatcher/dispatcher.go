package taskdispatcher

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"sync"
	"sync/atomic"
	"time"

	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// ============================================================
// Task Dispatcher 核心
//
// 基于 Redis 的高性能任务调度器，替代 Celery：
// - 优先级队列（critical > high > default > low）
// - 任务状态追踪
// - 并发控制
// - 超时管理
// - 通过 Redis Pub/Sub 推送进度到 WebSocket
// ============================================================

// Priority 任务优先级
type Priority int

const (
	PriorityLow      Priority = 0
	PriorityDefault  Priority = 1
	PriorityHigh     Priority = 2
	PriorityCritical Priority = 3
)

// QueueName 根据优先级返回队列名
func (p Priority) QueueName() string {
	switch p {
	case PriorityCritical:
		return "arboris:tasks:critical"
	case PriorityHigh:
		return "arboris:tasks:high"
	case PriorityDefault:
		return "arboris:tasks:default"
	case PriorityLow:
		return "arboris:tasks:low"
	default:
		return "arboris:tasks:default"
	}
}

// TaskType 任务类型
type TaskType string

// 任务类型是封闭枚举：handler.SubmitTask 的 switch 只认这里列出的类型，
// 新增类型必须同时注册 payload 构造与超时策略，否则提交直接 400。
// （rag:retrieve / chapter:postprocess 曾在此声明但从未有 handler，2026-08-14 清除。）
const (
	TaskGenerateChapter   TaskType = "chapter:generate"
	TaskBatchGenerate     TaskType = "chapter:batch_generate"
	TaskBlueprintGenerate TaskType = "blueprint:generate"
)

// TaskStatus 任务状态
type TaskStatus string

const (
	StatusPending   TaskStatus = "pending"
	StatusQueued    TaskStatus = "queued"
	StatusRunning   TaskStatus = "running"
	StatusCompleted TaskStatus = "completed"
	StatusFailed    TaskStatus = "failed"
	StatusCancelled TaskStatus = "cancelled"
	StatusRetrying  TaskStatus = "retrying"
)

// Task 任务定义
type Task struct {
	ID           string            `json:"id"`
	Type         TaskType          `json:"type"`
	Priority     Priority          `json:"priority"`
	Payload      json.RawMessage   `json:"payload"`
	Status       TaskStatus        `json:"status"`
	Progress     int               `json:"progress"` // 0-100
	Stage        string            `json:"stage"`    // 当前阶段
	Message      string            `json:"message"`  // 状态消息
	UserID       int               `json:"user_id"`
	ProjectID    string            `json:"project_id"`
	MaxRetries   int               `json:"max_retries"`
	RetryCount   int               `json:"retry_count"`
	Timeout      time.Duration     `json:"timeout"`
	CreatedAt    time.Time         `json:"created_at"`
	StartedAt    *time.Time        `json:"started_at,omitempty"`
	CompletedAt  *time.Time        `json:"completed_at,omitempty"`
	Result       json.RawMessage   `json:"result,omitempty"`
	Checkpoint   json.RawMessage   `json:"checkpoint,omitempty"`
	Error        string            `json:"error,omitempty"`
	ParentTaskID string            `json:"parent_task_id,omitempty"`
	Metadata     map[string]string `json:"metadata,omitempty"`
}

const taskRetention = 7 * 24 * time.Hour

// ChapterGeneratePayload 章节生成任务载荷
type ChapterGeneratePayload struct {
	ProjectID      string                 `json:"project_id"`
	ChapterNumber  int                    `json:"chapter_number"`
	UserID         int                    `json:"user_id"`
	Preset         string                 `json:"preset"`
	UseAgentSystem bool                   `json:"use_agent_system"`
	RAGMode        string                 `json:"rag_mode"`
	WritingNotes   string                 `json:"writing_notes,omitempty"`
	Extra          map[string]interface{} `json:"extra,omitempty"`
}

// BatchGeneratePayload 批量生成任务载荷
type BatchGeneratePayload struct {
	ProjectID      string                 `json:"project_id"`
	ChapterNumbers []int                  `json:"chapter_numbers"`
	UserID         int                    `json:"user_id"`
	Preset         string                 `json:"preset"`
	UseAgentSystem bool                   `json:"use_agent_system"`
	RAGMode        string                 `json:"rag_mode"`
	WritingNotes   string                 `json:"writing_notes,omitempty"`
	Extra          map[string]interface{} `json:"extra,omitempty"`
}

// BlueprintGeneratePayload 蓝图生成任务载荷（两段式 LLM 生成耗时可达 10 分钟以上，
// 同步 HTTP 会被网关/nginx 超时掐断，故走异步任务路径）
type BlueprintGeneratePayload struct {
	ProjectID string `json:"project_id"`
	UserID    int    `json:"user_id"`
	Depth     string `json:"depth,omitempty"` // fast | deep；缺省 deep（旧网关/旧任务兼容）
}

// TaskResult 任务结果
type TaskResult struct {
	ChapterID     int    `json:"chapter_id,omitempty"`
	ChapterNumber int    `json:"chapter_number,omitempty"`
	VersionsCount int    `json:"versions_count,omitempty"`
	DurationMs    int64  `json:"duration_ms,omitempty"`
	Status        string `json:"status"`
}

// Config 调度器配置
type Config struct {
	// 并发控制
	MaxConcurrency int `mapstructure:"max_concurrency"` // 全局最大并发
	MaxPerUser     int `mapstructure:"max_per_user"`    // 每用户最大并发
	// 超时
	DefaultTimeout   time.Duration `mapstructure:"default_timeout"`   // 默认任务超时
	BatchTimeout     time.Duration `mapstructure:"batch_timeout"`     // 批量任务超时
	BlueprintTimeout time.Duration `mapstructure:"blueprint_timeout"` // 蓝图生成任务超时
	// 重试
	MaxRetries int           `mapstructure:"max_retries"` // 最大重试次数
	RetryDelay time.Duration `mapstructure:"retry_delay"` // 初始重试延迟
	// 轮询
	PollInterval time.Duration `mapstructure:"poll_interval"` // 队列轮询间隔
	// Worker
	WorkerCallbackURL string `mapstructure:"worker_callback_url"` // Python Worker HTTP 回调地址
	WorkerGRPCAddr    string `mapstructure:"worker_grpc_addr"`    // Python Worker gRPC 地址
	// 内部回调共享密钥；为空则不校验（向后兼容）
	InternalCallbackSecret string `mapstructure:"internal_callback_secret"`
}

// DefaultConfig 默认配置
func DefaultConfig() *Config {
	return &Config{
		MaxConcurrency:    20,
		MaxPerUser:        3,
		DefaultTimeout:    10 * time.Minute,
		BatchTimeout:      360 * time.Minute,
		BlueprintTimeout:  15 * time.Minute,
		MaxRetries:        3,
		RetryDelay:        5 * time.Second,
		PollInterval:      100 * time.Millisecond,
		WorkerCallbackURL: "http://localhost:8000/api/internal/tasks",
		WorkerGRPCAddr:    "localhost:50051",
	}
}

// Dispatcher 任务调度器
type Dispatcher struct {
	redis       *redis.Client
	config      *Config
	running     atomic.Bool
	activeCount atomic.Int64 // 当前活跃任务数
	userCounts  sync.Map     // user_id -> *atomic.Int64 (每用户活跃数)
	cancel      context.CancelFunc
	wg          sync.WaitGroup
	workerPool  *WorkerPool // Worker 连接池
}

// NewDispatcher 创建调度器
func NewDispatcher(redisClient *redis.Client, cfg *Config) *Dispatcher {
	if cfg == nil {
		cfg = DefaultConfig()
	}

	return &Dispatcher{
		redis:  redisClient,
		config: cfg,
	}
}

// Start 启动调度器
func (d *Dispatcher) Start(ctx context.Context) error {
	if d.running.Load() {
		return fmt.Errorf("dispatcher already running")
	}

	ctx, d.cancel = context.WithCancel(ctx)
	d.running.Store(true)

	// Redis 中的任务比网关进程活得更久。服务重启后把中断的任务重新放回队列；
	// 批量正文 worker 会读取已经选版的章节作为检查点，因此不会重复生成已交付正文。
	if err := d.recoverInterruptedTasks(ctx); err != nil {
		logger.Warn("Recover interrupted tasks failed", zap.Error(err))
	}

	// 初始化 Worker 连接池
	d.workerPool = NewWorkerPool(d.config)

	logger.Info("Task dispatcher starting",
		zap.Int("max_concurrency", d.config.MaxConcurrency),
		zap.Int("max_per_user", d.config.MaxPerUser),
		zap.Duration("poll_interval", d.config.PollInterval),
	)

	// 启动调度循环
	d.wg.Add(1)
	go d.dispatchLoop(ctx)

	// 启动超时检查
	d.wg.Add(1)
	go d.timeoutChecker(ctx)

	// 启动失败任务重试
	d.wg.Add(1)
	go d.retryLoop(ctx)

	logger.Info("Task dispatcher started")
	return nil
}

// Stop 停止调度器
func (d *Dispatcher) Stop() {
	if !d.running.Load() {
		return
	}

	logger.Info("Stopping task dispatcher...")
	d.running.Store(false)

	if d.cancel != nil {
		d.cancel()
	}

	d.wg.Wait()

	if d.workerPool != nil {
		d.workerPool.Close()
	}

	logger.Info("Task dispatcher stopped")
}

// Submit 提交任务
func (d *Dispatcher) Submit(ctx context.Context, task *Task) error {
	// 检查用户并发限制
	if !d.checkUserConcurrency(task.UserID) {
		return fmt.Errorf("用户并发达到上限 (%d)", d.config.MaxPerUser)
	}

	// 设置默认值
	if task.Status == "" {
		task.Status = StatusPending
	}
	if task.CreatedAt.IsZero() {
		task.CreatedAt = time.Now()
	}
	if task.MaxRetries == 0 {
		task.MaxRetries = d.config.MaxRetries
	}
	if task.Timeout == 0 {
		task.Timeout = d.config.DefaultTimeout
	}
	if task.Metadata == nil {
		task.Metadata = make(map[string]string)
	}

	// 序列化任务
	data, err := json.Marshal(task)
	if err != nil {
		return fmt.Errorf("序列化任务失败: %w", err)
	}

	pipe := d.redis.Pipeline()

	// 存储任务详情
	taskKey := fmt.Sprintf("arboris:task:%s", task.ID)
	pipe.Set(ctx, taskKey, data, taskRetention)

	// 推入优先级队列
	queueName := task.Priority.QueueName()
	pipe.LPush(ctx, queueName, task.ID)

	// 添加到用户任务集合
	userTasksKey := fmt.Sprintf("arboris:user_tasks:%d", task.UserID)
	pipe.SAdd(ctx, userTasksKey, task.ID)
	pipe.Expire(ctx, userTasksKey, taskRetention)

	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("提交任务失败: %w", err)
	}

	// 发布任务创建事件
	d.publishEvent(ctx, task, "task_created", "任务已提交")

	logger.Info("Task submitted",
		zap.String("task_id", task.ID),
		zap.String("type", string(task.Type)),
		zap.Int("priority", int(task.Priority)),
		zap.Int("user_id", task.UserID),
	)

	return nil
}

// GetTask 获取任务状态
func (d *Dispatcher) GetTask(ctx context.Context, taskID string) (*Task, error) {
	taskKey := fmt.Sprintf("arboris:task:%s", taskID)
	data, err := d.redis.Get(ctx, taskKey).Bytes()
	if err != nil {
		if err == redis.Nil {
			return nil, fmt.Errorf("任务不存在: %s", taskID)
		}
		return nil, fmt.Errorf("获取任务失败: %w", err)
	}

	var task Task
	if err := json.Unmarshal(data, &task); err != nil {
		return nil, fmt.Errorf("反序列化任务失败: %w", err)
	}

	return &task, nil
}

// CancelTask 取消任务
func (d *Dispatcher) CancelTask(ctx context.Context, taskID string) error {
	task, err := d.GetTask(ctx, taskID)
	if err != nil {
		return err
	}

	if task.Status == StatusCompleted || task.Status == StatusFailed || task.Status == StatusCancelled {
		return fmt.Errorf("任务已终结，无法取消: %s", task.Status)
	}

	task.Status = StatusCancelled
	now := time.Now()
	task.CompletedAt = &now

	return d.updateTask(ctx, task)
}

// GetUserTasks 获取用户的所有任务
func (d *Dispatcher) GetUserTasks(ctx context.Context, userID int) ([]*Task, error) {
	userTasksKey := fmt.Sprintf("arboris:user_tasks:%d", userID)
	taskIDs, err := d.redis.SMembers(ctx, userTasksKey).Result()
	if err != nil {
		return nil, err
	}

	tasks := make([]*Task, 0, len(taskIDs))
	for _, id := range taskIDs {
		task, err := d.GetTask(ctx, id)
		if err != nil {
			continue
		}
		tasks = append(tasks, task)
	}
	sort.Slice(tasks, func(i, j int) bool {
		return tasks[i].CreatedAt.After(tasks[j].CreatedAt)
	})

	return tasks, nil
}

// recoverInterruptedTasks 让重启前处于队列、运行或退避中的任务恢复执行。
// 先从所有队列移除旧副本再入队，避免 queued 任务因重启被重复消费。
func (d *Dispatcher) recoverInterruptedTasks(ctx context.Context) error {
	var cursor uint64
	for {
		keys, next, err := d.redis.Scan(ctx, cursor, "arboris:task:*", 100).Result()
		if err != nil {
			return err
		}
		for _, key := range keys {
			data, err := d.redis.Get(ctx, key).Bytes()
			if err != nil {
				continue
			}
			var task Task
			if json.Unmarshal(data, &task) != nil {
				continue
			}
			if task.Status != StatusPending && task.Status != StatusQueued &&
				task.Status != StatusRunning && task.Status != StatusRetrying {
				continue
			}

			task.Status = StatusQueued
			task.Stage = "recovered"
			task.Message = "服务已恢复，正在从最近检查点继续"
			task.ensureMetadata()
			task.Metadata["recovered_at"] = time.Now().UTC().Format(time.RFC3339)
			if err := d.updateTask(ctx, &task); err != nil {
				continue
			}
			for _, priority := range []Priority{PriorityCritical, PriorityHigh, PriorityDefault, PriorityLow} {
				d.redis.LRem(ctx, priority.QueueName(), 0, task.ID)
			}
			d.redis.ZRem(ctx, "arboris:tasks:retry", task.ID)
			d.redis.LPush(ctx, task.Priority.QueueName(), task.ID)
		}
		cursor = next
		if cursor == 0 {
			break
		}
	}
	return nil
}

// GetStats 获取调度器统计
func (d *Dispatcher) GetStats(ctx context.Context) *DispatcherStats {
	stats := &DispatcherStats{
		ActiveTasks:    int(d.activeCount.Load()),
		MaxConcurrency: d.config.MaxConcurrency,
		Running:        d.running.Load(),
	}

	// 各队列长度
	for _, p := range []Priority{PriorityCritical, PriorityHigh, PriorityDefault, PriorityLow} {
		length, _ := d.redis.LLen(ctx, p.QueueName()).Result()
		stats.QueueLengths = append(stats.QueueLengths, QueueLength{
			Name:     p.QueueName(),
			Priority: int(p),
			Length:   length,
		})
	}

	return stats
}

// DispatcherStats 调度器统计
type DispatcherStats struct {
	ActiveTasks    int           `json:"active_tasks"`
	MaxConcurrency int           `json:"max_concurrency"`
	Running        bool          `json:"running"`
	QueueLengths   []QueueLength `json:"queue_lengths"`
}

// QueueLength 队列长度
type QueueLength struct {
	Name     string `json:"name"`
	Priority int    `json:"priority"`
	Length   int64  `json:"length"`
}

// ============================================================
// 内部方法
// ============================================================

// dispatchLoop 调度主循环，按优先级轮询队列
func (d *Dispatcher) dispatchLoop(ctx context.Context) {
	defer d.wg.Done()

	// 按优先级从高到低的队列列表
	queues := []string{
		PriorityCritical.QueueName(),
		PriorityHigh.QueueName(),
		PriorityDefault.QueueName(),
		PriorityLow.QueueName(),
	}

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		// 检查是否达到全局并发上限
		if d.activeCount.Load() >= int64(d.config.MaxConcurrency) {
			time.Sleep(d.config.PollInterval)
			continue
		}

		// 按优先级从高到低取任务
		dispatched := false
		for _, queue := range queues {
			taskID, err := d.redis.RPop(ctx, queue).Result()
			if err == redis.Nil {
				continue
			}
			if err != nil {
				logger.Error("从队列取任务失败", zap.String("queue", queue), zap.Error(err))
				continue
			}

			// 获取任务详情
			task, err := d.GetTask(ctx, taskID)
			if err != nil {
				logger.Error("获取任务详情失败", zap.String("task_id", taskID), zap.Error(err))
				continue
			}

			// 跳过已取消的任务
			if task.Status == StatusCancelled {
				continue
			}

			// 检查用户并发
			if !d.acquireUserSlot(task.UserID) {
				// 放回队列
				d.redis.LPush(ctx, queue, taskID)
				continue
			}

			// 执行任务
			d.activeCount.Add(1)
			d.wg.Add(1)
			go d.executeTask(ctx, task)

			dispatched = true
			break // 调度一个就跳出，下次循环再检查高优先级
		}

		if !dispatched {
			time.Sleep(d.config.PollInterval)
		}
	}
}

// executeTask 执行单个任务
func (d *Dispatcher) executeTask(ctx context.Context, task *Task) {
	defer d.wg.Done()
	defer d.activeCount.Add(-1)
	defer d.releaseUserSlot(task.UserID)

	// 更新状态为运行中
	now := time.Now()
	task.Status = StatusRunning
	task.StartedAt = &now
	if err := d.updateTask(ctx, task); err != nil {
		logger.Error("更新任务状态失败", zap.String("task_id", task.ID), zap.Error(err))
		return
	}

	d.publishEvent(ctx, task, "task_started", "任务开始执行")

	// 添加超时控制
	taskCtx, taskCancel := context.WithTimeout(ctx, task.Timeout)
	defer taskCancel()

	// 通过 Worker Pool 调用 Python Worker
	startTime := time.Now()
	result, err := d.workerPool.Execute(taskCtx, task)
	duration := time.Since(startTime)

	if err != nil {
		d.handleTaskFailure(ctx, task, err, duration)
		return
	}

	d.handleTaskSuccess(ctx, task, result, duration)
}

// ensureMetadata 重建 nil 的 Metadata map。
// Task.Metadata 带 json:"metadata,omitempty"：提交时初始化的空 map 经 Redis(JSON) 往返后，
// omitempty 使该字段被省略、反序列化回 nil。任何"写 Metadata"前必须调用本方法，否则向
// nil map 赋值会 panic("assignment to entry in nil map")→收尾 goroutine 崩溃→任务结果
// 永不回报→前端干等到 10 分钟超时。
func (t *Task) ensureMetadata() {
	if t.Metadata == nil {
		t.Metadata = make(map[string]string)
	}
}

// handleTaskSuccess 处理任务成功
func (d *Dispatcher) handleTaskSuccess(ctx context.Context, task *Task, result json.RawMessage, duration time.Duration) {
	now := time.Now()
	task.Status = StatusCompleted
	task.CompletedAt = &now
	task.Progress = 100
	task.Result = result
	// 任务可能在一次可恢复的传输错误后重试成功；成功终态不能继续携带旧错误，
	// 否则状态接口会同时返回 completed 与 error，前端无从判断真实结果。
	task.Error = ""
	task.ensureMetadata()
	task.Metadata["duration_ms"] = fmt.Sprintf("%d", duration.Milliseconds())

	if err := d.updateTask(ctx, task); err != nil {
		logger.Error("更新任务结果失败", zap.String("task_id", task.ID), zap.Error(err))
	}

	d.publishEvent(ctx, task, "task_completed", "任务完成")

	logger.Info("Task completed",
		zap.String("task_id", task.ID),
		zap.Duration("duration", duration),
	)
}

// handleTaskFailure 处理任务失败
func (d *Dispatcher) handleTaskFailure(ctx context.Context, task *Task, err error, duration time.Duration) {
	task.Error = err.Error()
	task.ensureMetadata()
	task.Metadata["duration_ms"] = fmt.Sprintf("%d", duration.Milliseconds())

	// 确定性失败（如档位门控拒绝）：重试窗口内结果不会改变，直接终态
	var permErr *PermanentTaskError
	isPermanent := errors.As(err, &permErr)

	// 检查是否可以重试
	if !isPermanent && task.RetryCount < task.MaxRetries {
		task.Status = StatusRetrying
		task.RetryCount++
		if updateErr := d.updateTask(ctx, task); updateErr != nil {
			logger.Error("更新重试状态失败", zap.String("task_id", task.ID), zap.Error(updateErr))
		}

		// 推入重试队列（延迟执行）
		retryDelay := d.config.RetryDelay * time.Duration(1<<uint(task.RetryCount-1)) // 指数退避
		retryKey := "arboris:tasks:retry"
		retryAt := time.Now().Add(retryDelay).UnixMilli()
		d.redis.ZAdd(ctx, retryKey, redis.Z{
			Score:  float64(retryAt),
			Member: task.ID,
		})

		d.publishEvent(ctx, task, "task_retrying",
			fmt.Sprintf("任务将在 %s 后重试 (%d/%d)", retryDelay, task.RetryCount, task.MaxRetries))

		logger.Warn("Task will retry",
			zap.String("task_id", task.ID),
			zap.Int("retry_count", task.RetryCount),
			zap.Duration("retry_delay", retryDelay),
			zap.Error(err),
		)
		return
	}

	// 超过重试次数，标记失败
	now := time.Now()
	task.Status = StatusFailed
	task.CompletedAt = &now
	if updateErr := d.updateTask(ctx, task); updateErr != nil {
		logger.Error("更新失败状态失败", zap.String("task_id", task.ID), zap.Error(updateErr))
	}

	d.publishEvent(ctx, task, "task_failed", fmt.Sprintf("任务失败: %s", err.Error()))

	logger.Error("Task failed",
		zap.String("task_id", task.ID),
		zap.Int("retries", task.RetryCount),
		zap.Error(err),
	)
}

// retryLoop 重试循环：扫描需要重试的任务
func (d *Dispatcher) retryLoop(ctx context.Context) {
	defer d.wg.Done()
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()

	retryKey := "arboris:tasks:retry"

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}

		now := float64(time.Now().UnixMilli())
		taskIDs, err := d.redis.ZRangeByScore(ctx, retryKey, &redis.ZRangeBy{
			Min: "-inf",
			Max: fmt.Sprintf("%f", now),
		}).Result()

		if err != nil || len(taskIDs) == 0 {
			continue
		}

		for _, taskID := range taskIDs {
			// 移除重试队列
			d.redis.ZRem(ctx, retryKey, taskID)

			// 重新入队
			task, err := d.GetTask(ctx, taskID)
			if err != nil {
				continue
			}
			if task.Status == StatusCancelled {
				continue
			}

			task.Status = StatusQueued
			d.updateTask(ctx, task)

			queueName := task.Priority.QueueName()
			d.redis.LPush(ctx, queueName, task.ID)

			logger.Info("Task re-queued for retry",
				zap.String("task_id", taskID),
				zap.Int("retry_count", task.RetryCount),
			)
		}
	}
}

// timeoutChecker 超时检查
func (d *Dispatcher) timeoutChecker(ctx context.Context) {
	defer d.wg.Done()
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}

		// 扫描运行中的任务检查超时
		// 这里通过 Redis SCAN 查找 arboris:task:* 状态为 running 的任务
		// 简化实现：依赖 context timeout，此处仅记录日志
	}
}

// updateTask 更新任务到 Redis
func (d *Dispatcher) updateTask(ctx context.Context, task *Task) error {
	data, err := json.Marshal(task)
	if err != nil {
		return err
	}
	taskKey := fmt.Sprintf("arboris:task:%s", task.ID)
	return d.redis.Set(ctx, taskKey, data, taskRetention).Err()
}

// publishEvent 通过 Redis Pub/Sub 发布事件（推送到 WebSocket）
func (d *Dispatcher) publishEvent(ctx context.Context, task *Task, eventType string, message string) {
	event := map[string]interface{}{
		"task_id":    task.ID,
		"event_type": eventType,
		"progress":   task.Progress,
		"stage":      task.Stage,
		"message":    message,
		"user_id":    task.UserID,
		"project_id": task.ProjectID,
		"timestamp":  time.Now().UnixMilli(),
	}
	if len(task.Checkpoint) > 0 && string(task.Checkpoint) != "null" {
		var checkpoint interface{}
		if json.Unmarshal(task.Checkpoint, &checkpoint) == nil {
			event["checkpoint"] = checkpoint
		}
	}

	data, err := json.Marshal(event)
	if err != nil {
		return
	}

	// 发布到用户专属频道
	channel := fmt.Sprintf("arboris:events:user:%d", task.UserID)
	d.redis.Publish(ctx, channel, data)

	// 同时发布到项目频道
	projectChannel := fmt.Sprintf("arboris:events:project:%s", task.ProjectID)
	d.redis.Publish(ctx, projectChannel, data)
}

// checkUserConcurrency 检查用户并发是否达到上限（不消耗名额）
func (d *Dispatcher) checkUserConcurrency(userID int) bool {
	val, _ := d.userCounts.LoadOrStore(userID, &atomic.Int64{})
	counter := val.(*atomic.Int64)
	return counter.Load() < int64(d.config.MaxPerUser)
}

// acquireUserSlot 获取用户并发名额
func (d *Dispatcher) acquireUserSlot(userID int) bool {
	val, _ := d.userCounts.LoadOrStore(userID, &atomic.Int64{})
	counter := val.(*atomic.Int64)
	for {
		current := counter.Load()
		if current >= int64(d.config.MaxPerUser) {
			return false
		}
		if counter.CompareAndSwap(current, current+1) {
			return true
		}
	}
}

// releaseUserSlot 释放用户并发名额
func (d *Dispatcher) releaseUserSlot(userID int) {
	val, ok := d.userCounts.Load(userID)
	if !ok {
		return
	}
	counter := val.(*atomic.Int64)
	counter.Add(-1)
}
