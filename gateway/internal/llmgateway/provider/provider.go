package provider

import (
	"context"
	"time"
)

// Provider LLM Provider 接口
type Provider interface {
	// Name 返回 Provider 名称
	Name() string

	// Generate 生成文本
	Generate(ctx context.Context, req *GenerateRequest) (*GenerateResponse, error)

	// GenerateStream 流式生成文本
	GenerateStream(ctx context.Context, req *GenerateRequest) (<-chan StreamChunk, error)

	// GetModels 获取支持的模型列表
	GetModels() []string

	// HealthCheck 健康检查
	HealthCheck(ctx context.Context) error
}

// GenerateRequest 生成请求
type GenerateRequest struct {
	Model       string                 `json:"model"`
	Messages    []Message              `json:"messages"`
	MaxTokens   int                    `json:"max_tokens,omitempty"`
	Temperature float64                `json:"temperature,omitempty"`
	TopP        float64                `json:"top_p,omitempty"`
	Stream      bool                   `json:"stream,omitempty"`
	Stop        []string               `json:"stop,omitempty"`
	Extra       map[string]interface{} `json:"-"` // Provider 特定参数
}

// Message 消息
type Message struct {
	Role    string `json:"role"`    // system, user, assistant
	Content string `json:"content"`
}

// GenerateResponse 生成响应
type GenerateResponse struct {
	ID      string   `json:"id"`
	Model   string   `json:"model"`
	Content string   `json:"content"`
	Usage   Usage    `json:"usage"`
	Latency Duration `json:"latency"`
}

// StreamChunk 流式响应块
type StreamChunk struct {
	ID      string   `json:"id"`
	Model   string   `json:"model"`
	Delta   string   `json:"delta"`
	Done    bool     `json:"done"`
	Usage   *Usage   `json:"usage,omitempty"`
	Error   error    `json:"-"`
}

// Usage Token 使用情况
type Usage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// Duration 自定义时间类型（用于 JSON 序列化）
type Duration time.Duration

func (d Duration) MarshalJSON() ([]byte, error) {
	return []byte(`"` + time.Duration(d).String() + `"`), nil
}

// ProviderConfig Provider 配置
type ProviderConfig struct {
	Name     string
	APIKey   string
	BaseURL  string
	Timeout  time.Duration
	Models   []string
	MaxTokens int
}

// ProviderError Provider 错误
type ProviderError struct {
	Provider   string
	StatusCode int
	Message    string
	Err        error
}

func (e *ProviderError) Error() string {
	if e.Err != nil {
		return e.Provider + ": " + e.Err.Error()
	}
	return e.Provider + ": " + e.Message
}

func (e *ProviderError) Unwrap() error {
	return e.Err
}
