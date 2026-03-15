package models

import "time"

// User 用户信息
type User struct {
	ID        int       `json:"id"`
	Username  string    `json:"username"`
	Email     string    `json:"email"`
	IsPremium bool      `json:"is_premium"`
	IsAdmin   bool      `json:"is_admin"`
	CreatedAt time.Time `json:"created_at"`
}

// JWTClaims JWT 声明
type JWTClaims struct {
	UserID    int    `json:"user_id"`
	Username  string `json:"username"`
	IsPremium bool   `json:"is_premium"`
	IsAdmin   bool   `json:"is_admin"`
	Issuer    string `json:"iss"`
	Audience  string `json:"aud"`
	ExpiresAt int64  `json:"exp"`
	IssuedAt  int64  `json:"iat"`
}

// RateLimitInfo 限流信息
type RateLimitInfo struct {
	TPM        int // Tokens Per Minute
	Concurrent int // 并发槽数量
	RPM        int // Requests Per Minute
	RPS        int // Requests Per Second
}

// WebSocketMessage WebSocket 消息
type WebSocketMessage struct {
	Type    string      `json:"type"`
	Payload interface{} `json:"payload"`
}

// TaskProgress 任务进度
type TaskProgress struct {
	TaskID      string  `json:"task_id"`
	Status      string  `json:"status"`
	Progress    float64 `json:"progress"`
	Message     string  `json:"message"`
	CurrentStep string  `json:"current_step,omitempty"`
}
