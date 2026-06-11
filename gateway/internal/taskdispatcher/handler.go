package taskdispatcher

import (
	"encoding/json"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
	"github.com/arboris-novel/gateway/internal/auth"
)

// ============================================================
// Task Dispatcher HTTP Handler
//
// 提供任务管理 REST API：
// - POST   /tasks/submit         提交任务
// - GET    /tasks/:id/status     查询任务状态
// - POST   /tasks/:id/cancel     取消任务
// - GET    /tasks/user/:user_id  获取用户任务列表
// - GET    /tasks/stats          获取调度器统计
// - POST   /internal/tasks/:id/progress  Worker 进度回调
// ============================================================

// Handler HTTP 处理器
type Handler struct {
	dispatcher     *Dispatcher
	internalSecret string
}

// NewHandler 创建处理器。internalSecret 为空时不校验内部回调（向后兼容）。
func NewHandler(dispatcher *Dispatcher, internalSecret string) *Handler {
	return &Handler{dispatcher: dispatcher, internalSecret: internalSecret}
}

// RegisterRoutes 注册路由
func (h *Handler) RegisterRoutes(app *fiber.App, authMiddleware fiber.Handler) {
	tasks := app.Group("/tasks", authMiddleware)
	tasks.Post("/submit", h.SubmitTask)
	tasks.Get("/:id/status", h.GetTaskStatus)
	tasks.Post("/:id/cancel", h.CancelTask)
	tasks.Get("/user/:user_id", h.GetUserTasks)
	tasks.Get("/stats", auth.RequireAdmin(), h.GetStats)

	// 内部接口（Worker 回调）
	internal := app.Group("/internal/tasks")
	internal.Post("/:id/progress", h.UpdateProgress)
}

// SubmitTaskRequest 提交任务请求
type SubmitTaskRequest struct {
	Type           string                 `json:"type" validate:"required"` // chapter:generate, chapter:batch_generate
	ProjectID      string                 `json:"project_id" validate:"required"`
	ChapterNumber  int                    `json:"chapter_number,omitempty"`
	ChapterNumbers []int                  `json:"chapter_numbers,omitempty"`
	UserID         int                    `json:"user_id" validate:"required"`
	Priority       int                    `json:"priority"` // 0-3
	Config         map[string]interface{} `json:"config"`
}

// SubmitTaskResponse 提交任务响应
type SubmitTaskResponse struct {
	TaskID    string    `json:"task_id"`
	Status    string    `json:"status"`
	Message   string    `json:"message"`
	CreatedAt time.Time `json:"created_at"`
}

// SubmitTask 提交任务
func (h *Handler) SubmitTask(c *fiber.Ctx) error {
	var req SubmitTaskRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "请求格式错误: " + err.Error()})
	}

	// user_id 一律以网关校验后的身份为准，忽略请求体自带值（防止冒用他人身份提交任务）
	userID := auth.GetUserID(c)
	if userID == 0 {
		return c.Status(401).JSON(fiber.Map{"error": "未授权"})
	}
	req.UserID = userID

	if req.Type == "" || req.ProjectID == "" {
		return c.Status(400).JSON(fiber.Map{"error": "缺少必填字段: type, project_id"})
	}

	// 构造任务载荷
	var payload interface{}
	taskType := TaskType(req.Type)

	switch taskType {
	case TaskGenerateChapter:
		payload = ChapterGeneratePayload{
			ProjectID:      req.ProjectID,
			ChapterNumber:  req.ChapterNumber,
			UserID:         req.UserID,
			Preset:         getStringConfig(req.Config, "preset", "fast"),
			UseAgentSystem: getBoolConfig(req.Config, "use_agent_system", false),
			RAGMode:        getStringConfig(req.Config, "rag_mode", "simple"),
			WritingNotes:   getStringConfig(req.Config, "writing_notes", ""),
			Extra:          getExtraConfig(req.Config),
		}
	case TaskBatchGenerate:
		if len(req.ChapterNumbers) == 0 {
			return c.Status(400).JSON(fiber.Map{"error": "批量生成需要 chapter_numbers"})
		}
		payload = BatchGeneratePayload{
			ProjectID:      req.ProjectID,
			ChapterNumbers: req.ChapterNumbers,
			UserID:         req.UserID,
			Preset:         getStringConfig(req.Config, "preset", "fast"),
			UseAgentSystem: getBoolConfig(req.Config, "use_agent_system", false),
			RAGMode:        getStringConfig(req.Config, "rag_mode", "simple"),
			Extra:          getExtraConfig(req.Config),
		}
	default:
		return c.Status(400).JSON(fiber.Map{"error": "不支持的任务类型: " + req.Type})
	}

	payloadJSON, err := json.Marshal(payload)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": "序列化载荷失败"})
	}

	// 确定超时
	timeout := h.dispatcher.config.DefaultTimeout
	if taskType == TaskBatchGenerate {
		timeout = h.dispatcher.config.BatchTimeout
	}

	task := &Task{
		ID:        uuid.New().String(),
		Type:      taskType,
		Priority:  Priority(req.Priority),
		Payload:   payloadJSON,
		UserID:    req.UserID,
		ProjectID: req.ProjectID,
		Timeout:   timeout,
	}

	if err := h.dispatcher.Submit(c.Context(), task); err != nil {
		return c.Status(429).JSON(fiber.Map{"error": err.Error()})
	}

	return c.Status(201).JSON(SubmitTaskResponse{
		TaskID:    task.ID,
		Status:    string(task.Status),
		Message:   "任务已提交",
		CreatedAt: task.CreatedAt,
	})
}

// TaskStatusResponse 任务状态响应
type TaskStatusResponse struct {
	TaskID      string          `json:"task_id"`
	Type        string          `json:"type"`
	Status      string          `json:"status"`
	Progress    int             `json:"progress"`
	Stage       string          `json:"stage,omitempty"`
	Message     string          `json:"message,omitempty"`
	Error       string          `json:"error,omitempty"`
	Result      json.RawMessage `json:"result,omitempty"`
	CreatedAt   time.Time       `json:"created_at"`
	StartedAt   *time.Time      `json:"started_at,omitempty"`
	CompletedAt *time.Time      `json:"completed_at,omitempty"`
	RetryCount  int             `json:"retry_count"`
}

// GetTaskStatus 查询任务状态
func (h *Handler) GetTaskStatus(c *fiber.Ctx) error {
	taskID := c.Params("id")

	task, err := h.dispatcher.GetTask(c.Context(), taskID)
	if err != nil {
		return c.Status(404).JSON(fiber.Map{"error": err.Error()})
	}

	// 归属校验：仅任务所有者或管理员可见
	if task.UserID != auth.GetUserID(c) && !auth.IsAdmin(c) {
		return c.Status(403).JSON(fiber.Map{"error": "无权访问该任务"})
	}

	return c.JSON(TaskStatusResponse{
		TaskID:      task.ID,
		Type:        string(task.Type),
		Status:      string(task.Status),
		Progress:    task.Progress,
		Stage:       task.Stage,
		Message:     task.Message,
		Error:       task.Error,
		Result:      task.Result,
		CreatedAt:   task.CreatedAt,
		StartedAt:   task.StartedAt,
		CompletedAt: task.CompletedAt,
		RetryCount:  task.RetryCount,
	})
}

// CancelTask 取消任务
func (h *Handler) CancelTask(c *fiber.Ctx) error {
	taskID := c.Params("id")

	// 归属校验：仅任务所有者或管理员可取消
	task, err := h.dispatcher.GetTask(c.Context(), taskID)
	if err != nil {
		return c.Status(404).JSON(fiber.Map{"error": err.Error()})
	}
	if task.UserID != auth.GetUserID(c) && !auth.IsAdmin(c) {
		return c.Status(403).JSON(fiber.Map{"error": "无权取消该任务"})
	}

	if err := h.dispatcher.CancelTask(c.Context(), taskID); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": err.Error()})
	}

	return c.JSON(fiber.Map{
		"task_id": taskID,
		"status":  "cancelled",
		"message": "任务已取消",
	})
}

// GetUserTasks 获取用户任务列表
func (h *Handler) GetUserTasks(c *fiber.Ctx) error {
	userID, err := c.ParamsInt("user_id")
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "无效的 user_id"})
	}

	tasks, err := h.dispatcher.GetUserTasks(c.Context(), userID)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}

	responses := make([]TaskStatusResponse, 0, len(tasks))
	for _, t := range tasks {
		responses = append(responses, TaskStatusResponse{
			TaskID:      t.ID,
			Type:        string(t.Type),
			Status:      string(t.Status),
			Progress:    t.Progress,
			Stage:       t.Stage,
			Message:     t.Message,
			Error:       t.Error,
			CreatedAt:   t.CreatedAt,
			StartedAt:   t.StartedAt,
			CompletedAt: t.CompletedAt,
			RetryCount:  t.RetryCount,
		})
	}

	return c.JSON(fiber.Map{
		"user_id": userID,
		"tasks":   responses,
		"count":   len(responses),
	})
}

// GetStats 获取调度器统计
func (h *Handler) GetStats(c *fiber.Ctx) error {
	stats := h.dispatcher.GetStats(c.Context())

	return c.JSON(fiber.Map{
		"dispatcher": stats,
		"workers":    h.dispatcher.workerPool.GetWorkers(),
	})
}

// UpdateProgressRequest Worker 进度回调请求
type UpdateProgressRequest struct {
	Progress int    `json:"progress"` // 0-100
	Stage    string `json:"stage"`    // 当前阶段
	Message  string `json:"message"`
}

// UpdateProgress Worker 进度回调
func (h *Handler) UpdateProgress(c *fiber.Ctx) error {
	// 内部回调鉴权：仅当配置了密钥时校验（向后兼容）
	if h.internalSecret != "" && c.Get("X-Internal-Secret") != h.internalSecret {
		return c.Status(401).JSON(fiber.Map{"error": "未授权的内部回调"})
	}

	taskID := c.Params("id")

	var req UpdateProgressRequest
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "请求格式错误"})
	}

	task, err := h.dispatcher.GetTask(c.Context(), taskID)
	if err != nil {
		return c.Status(404).JSON(fiber.Map{"error": err.Error()})
	}

	task.Progress = req.Progress
	task.Stage = req.Stage
	task.Message = req.Message

	if err := h.dispatcher.updateTask(c.Context(), task); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": "更新进度失败"})
	}

	// 发布进度事件到 WebSocket
	h.dispatcher.publishEvent(c.Context(), task, "progress", req.Message)

	return c.JSON(fiber.Map{"status": "ok"})
}

// ============================================================
// 辅助函数
// ============================================================

func getStringConfig(config map[string]interface{}, key string, defaultVal string) string {
	if config == nil {
		return defaultVal
	}
	if v, ok := config[key]; ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return defaultVal
}

func getBoolConfig(config map[string]interface{}, key string, defaultVal bool) bool {
	if config == nil {
		return defaultVal
	}
	if v, ok := config[key]; ok {
		if b, ok := v.(bool); ok {
			return b
		}
	}
	return defaultVal
}

func getExtraConfig(config map[string]interface{}) map[string]interface{} {
	if config == nil {
		return nil
	}

	extra := make(map[string]interface{})
	for key, value := range config {
		switch key {
		case "preset", "use_agent_system", "rag_mode", "writing_notes":
			continue
		default:
			extra[key] = value
		}
	}

	if len(extra) == 0 {
		return nil
	}
	return extra
}
