package provider

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/arboris-novel/gateway/internal/logger"
	"go.uber.org/zap"
)

// OpenAIProvider OpenAI Provider
type OpenAIProvider struct {
	config *ProviderConfig
	client *http.Client
}

// NewOpenAIProvider 创建 OpenAI Provider
func NewOpenAIProvider(config *ProviderConfig, client *http.Client) *OpenAIProvider {
	return &OpenAIProvider{
		config: config,
		client: client,
	}
}

// Name 返回 Provider 名称
func (p *OpenAIProvider) Name() string {
	return p.config.Name
}

// Generate 生成文本
func (p *OpenAIProvider) Generate(ctx context.Context, req *GenerateRequest) (*GenerateResponse, error) {
	start := time.Now()

	// 构建请求
	body := map[string]interface{}{
		"model":    req.Model,
		"messages": req.Messages,
		"stream":   false,
	}

	if req.MaxTokens > 0 {
		body["max_tokens"] = req.MaxTokens
	}
	if req.Temperature > 0 {
		body["temperature"] = req.Temperature
	}
	if req.TopP > 0 {
		body["top_p"] = req.TopP
	}
	if len(req.Stop) > 0 {
		body["stop"] = req.Stop
	}

	// 发送请求
	respData, err := p.doRequest(ctx, "/chat/completions", body)
	if err != nil {
		return nil, err
	}

	// 解析响应
	var openaiResp struct {
		ID      string `json:"id"`
		Model   string `json:"model"`
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
		Usage struct {
			PromptTokens     int `json:"prompt_tokens"`
			CompletionTokens int `json:"completion_tokens"`
			TotalTokens      int `json:"total_tokens"`
		} `json:"usage"`
	}

	if err := json.Unmarshal(respData, &openaiResp); err != nil {
		return nil, &ProviderError{
			Provider: p.Name(),
			Message:  "failed to parse response",
			Err:      err,
		}
	}

	if len(openaiResp.Choices) == 0 {
		return nil, &ProviderError{
			Provider: p.Name(),
			Message:  "no choices in response",
		}
	}

	return &GenerateResponse{
		ID:      openaiResp.ID,
		Model:   openaiResp.Model,
		Content: openaiResp.Choices[0].Message.Content,
		Usage: Usage{
			PromptTokens:     openaiResp.Usage.PromptTokens,
			CompletionTokens: openaiResp.Usage.CompletionTokens,
			TotalTokens:      openaiResp.Usage.TotalTokens,
		},
		Latency: Duration(time.Since(start)),
	}, nil
}

// GenerateStream 流式生成文本
func (p *OpenAIProvider) GenerateStream(ctx context.Context, req *GenerateRequest) (<-chan StreamChunk, error) {
	// 构建请求
	body := map[string]interface{}{
		"model":    req.Model,
		"messages": req.Messages,
		"stream":   true,
	}

	if req.MaxTokens > 0 {
		body["max_tokens"] = req.MaxTokens
	}
	if req.Temperature > 0 {
		body["temperature"] = req.Temperature
	}

	bodyBytes, _ := json.Marshal(body)

	// 创建 HTTP 请求
	httpReq, err := http.NewRequestWithContext(ctx, "POST", p.config.BaseURL+"/chat/completions", bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, err
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+p.config.APIKey)

	// 发送请求
	resp, err := p.client.Do(httpReq)
	if err != nil {
		return nil, &ProviderError{
			Provider: p.Name(),
			Message:  "request failed",
			Err:      err,
		}
	}

	if resp.StatusCode != http.StatusOK {
		resp.Body.Close()
		return nil, &ProviderError{
			Provider:   p.Name(),
			StatusCode: resp.StatusCode,
			Message:    "unexpected status code",
		}
	}

	// 创建流式响应通道
	ch := make(chan StreamChunk, 64)

	go func() {
		defer close(ch)
		defer resp.Body.Close()

		scanner := bufio.NewScanner(resp.Body)
		scanner.Buffer(make([]byte, 64*1024), 1024*1024) // 1MB buffer

		for scanner.Scan() {
			line := scanner.Text()

			// SSE 格式: data: {...}
			if len(line) < 6 || line[:6] != "data: " {
				continue
			}

			data := line[6:]

			// 结束标记
			if data == "[DONE]" {
				ch <- StreamChunk{Done: true}
				return
			}

			// 解析 JSON
			var chunk struct {
				ID      string `json:"id"`
				Model   string `json:"model"`
				Choices []struct {
					Delta struct {
						Content string `json:"content"`
					} `json:"delta"`
				} `json:"choices"`
			}

			if err := json.Unmarshal([]byte(data), &chunk); err != nil {
				logger.Warn("Failed to parse stream chunk", zap.Error(err))
				continue
			}

			if len(chunk.Choices) > 0 {
				ch <- StreamChunk{
					ID:    chunk.ID,
					Model: chunk.Model,
					Delta: chunk.Choices[0].Delta.Content,
					Done:  false,
				}
			}
		}

		if err := scanner.Err(); err != nil {
			ch <- StreamChunk{
				Error: &ProviderError{
					Provider: p.Name(),
					Message:  "stream read error",
					Err:      err,
				},
			}
		}
	}()

	return ch, nil
}

// GetModels 获取支持的模型列表
func (p *OpenAIProvider) GetModels() []string {
	return p.config.Models
}

// HealthCheck 健康检查
func (p *OpenAIProvider) HealthCheck(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, "GET", p.config.BaseURL+"/models", nil)
	if err != nil {
		return err
	}

	req.Header.Set("Authorization", "Bearer "+p.config.APIKey)

	resp, err := p.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return &ProviderError{
			Provider:   p.Name(),
			StatusCode: resp.StatusCode,
			Message:    "health check failed",
		}
	}

	return nil
}

// doRequest 发送 HTTP 请求
func (p *OpenAIProvider) doRequest(ctx context.Context, path string, body interface{}) ([]byte, error) {
	bodyBytes, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, "POST", p.config.BaseURL+path, bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+p.config.APIKey)

	resp, err := p.client.Do(req)
	if err != nil {
		return nil, &ProviderError{
			Provider: p.Name(),
			Message:  "request failed",
			Err:      err,
		}
	}
	defer resp.Body.Close()

	respData, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, &ProviderError{
			Provider: p.Name(),
			Message:  "failed to read response",
			Err:      err,
		}
	}

	if resp.StatusCode != http.StatusOK {
		return nil, &ProviderError{
			Provider:   p.Name(),
			StatusCode: resp.StatusCode,
			Message:    fmt.Sprintf("unexpected status code: %s", string(respData)),
		}
	}

	return respData, nil
}
