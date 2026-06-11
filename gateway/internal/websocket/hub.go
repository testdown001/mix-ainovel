package websocket

import (
	"context"
	"encoding/json"
	"sync"
	"sync/atomic"
	"time"

	"github.com/arboris-novel/gateway/internal/auth"
	"github.com/arboris-novel/gateway/internal/config"
	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/arboris-novel/gateway/pkg/models"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/websocket/v2"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// Hub WebSocket 连接管理器
type Hub struct {
	// 连接管理
	connections sync.Map // map[string]*Connection (connectionID -> Connection)
	rooms       sync.Map // map[string]*Room (roomID -> Room)

	// Redis 订阅
	redis      *redis.Client
	pubsub     *redis.PubSub
	ctx        context.Context
	cancel     context.CancelFunc

	// 配置
	config *config.WebSocketConfig

	// 统计
	connCount int64
}

// Connection WebSocket 连接
type Connection struct {
	ID        string
	UserID    int
	Username  string
	Conn      *websocket.Conn
	Send      chan []byte
	Hub       *Hub
	Rooms     map[string]bool // 加入的房间
	mu        sync.RWMutex
	closeChan chan struct{}
	closed    bool
}

// Room 房间（用于消息广播）
type Room struct {
	ID          string
	Connections sync.Map // map[string]*Connection
}

// NewHub 创建 WebSocket Hub
func NewHub(redisClient *redis.Client, cfg *config.WebSocketConfig) *Hub {
	ctx, cancel := context.WithCancel(context.Background())

	hub := &Hub{
		redis:  redisClient,
		ctx:    ctx,
		cancel: cancel,
		config: cfg,
	}

	// 订阅 Redis 频道
	hub.pubsub = redisClient.Subscribe(ctx, "ws:broadcast")
	if err := hub.pubsub.PSubscribe(ctx, "arboris:events:user:*"); err != nil {
		logger.Error("订阅任务事件频道失败", zap.Error(err))
	}

	// 启动 Redis 消息监听
	go hub.listenRedis()

	return hub
}

// Upgrade WebSocket 升级处理
func (h *Hub) Upgrade() fiber.Handler {
	return websocket.New(func(c *websocket.Conn) {
		// 从查询参数获取 token
		token := c.Query("token")
		if token == "" {
			c.WriteMessage(websocket.CloseMessage, []byte("Missing token"))
			return
		}

		// 验证 token
		claims, err := auth.ValidateToken(token)
		if err != nil {
			c.WriteMessage(websocket.CloseMessage, []byte("Invalid token"))
			return
		}

		// 创建连接
		conn := h.newConnection(c, claims)

		// 发送欢迎消息
		conn.SendJSON(models.WebSocketMessage{
			Type: "connected",
			Payload: fiber.Map{
				"connection_id": conn.ID,
				"user_id":       conn.UserID,
				"username":      conn.Username,
			},
		})

		// 启动读写协程
		go conn.writePump()
		conn.readPump()
	}, websocket.Config{
		ReadBufferSize:  h.config.ReadBufferSize,
		WriteBufferSize: h.config.WriteBufferSize,
	})
}

// newConnection 创建新连接
func (h *Hub) newConnection(c *websocket.Conn, claims *models.JWTClaims) *Connection {
	conn := &Connection{
		ID:        generateConnectionID(),
		UserID:    claims.UserID,
		Username:  claims.Username,
		Conn:      c,
		Send:      make(chan []byte, 256),
		Hub:       h,
		Rooms:     make(map[string]bool),
		closeChan: make(chan struct{}),
	}

	h.connections.Store(conn.ID, conn)
	atomic.AddInt64(&h.connCount, 1)

	logger.Info("WebSocket connected",
		zap.String("conn_id", conn.ID),
		zap.Int("user_id", conn.UserID),
		zap.String("username", conn.Username),
	)

	return conn
}

// readPump 读取消息
func (c *Connection) readPump() {
	defer func() {
		c.close()
	}()

	c.Conn.SetReadDeadline(time.Now().Add(c.Hub.config.PongTimeout))
	c.Conn.SetPongHandler(func(string) error {
		c.Conn.SetReadDeadline(time.Now().Add(c.Hub.config.PongTimeout))
		return nil
	})

	for {
		_, message, err := c.Conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				logger.Error("WebSocket read error", zap.Error(err))
			}
			break
		}

		// 处理消息
		c.handleMessage(message)
	}
}

// writePump 发送消息
func (c *Connection) writePump() {
	ticker := time.NewTicker(c.Hub.config.PingInterval)
	defer func() {
		ticker.Stop()
		c.close()
	}()

	for {
		select {
		case message, ok := <-c.Send:
			c.Conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				c.Conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			if err := c.Conn.WriteMessage(websocket.TextMessage, message); err != nil {
				return
			}

		case <-ticker.C:
			c.Conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.Conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}

		case <-c.closeChan:
			return
		}
	}
}

// handleMessage 处理接收到的消息
func (c *Connection) handleMessage(message []byte) {
	var msg models.WebSocketMessage
	if err := json.Unmarshal(message, &msg); err != nil {
		logger.Error("Invalid WebSocket message", zap.Error(err))
		return
	}

	switch msg.Type {
	case "join_room":
		if roomID, ok := msg.Payload.(string); ok {
			c.JoinRoom(roomID)
		}
	case "leave_room":
		if roomID, ok := msg.Payload.(string); ok {
			c.LeaveRoom(roomID)
		}
	case "ping":
		c.SendJSON(models.WebSocketMessage{Type: "pong"})
	default:
		logger.Warn("Unknown message type", zap.String("type", msg.Type))
	}
}

// SendJSON 发送 JSON 消息
func (c *Connection) SendJSON(msg models.WebSocketMessage) error {
	data, err := json.Marshal(msg)
	if err != nil {
		return err
	}
	c.sendRaw(data)
	return nil
}

// sendRaw 向连接发送原始字节（非阻塞）：连接已关闭或缓冲满则丢弃。
// close() 不再关闭 Send channel，仅靠 closeChan 退出 writePump，
// 因此这里向 Send 写入永不会 panic。
func (c *Connection) sendRaw(data []byte) {
	select {
	case c.Send <- data:
	case <-c.closeChan:
	default:
		logger.Warn("Send buffer full, dropping message", zap.String("conn_id", c.ID))
	}
}

// JoinRoom 加入房间
func (c *Connection) JoinRoom(roomID string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.Rooms[roomID] {
		return
	}

	// 获取或创建房间
	val, _ := c.Hub.rooms.LoadOrStore(roomID, &Room{
		ID: roomID,
	})
	room := val.(*Room)

	// 加入房间
	room.Connections.Store(c.ID, c)
	c.Rooms[roomID] = true

	logger.Info("Joined room",
		zap.String("conn_id", c.ID),
		zap.String("room_id", roomID),
	)
}

// LeaveRoom 离开房间
func (c *Connection) LeaveRoom(roomID string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if !c.Rooms[roomID] {
		return
	}

	if val, ok := c.Hub.rooms.Load(roomID); ok {
		room := val.(*Room)
		room.Connections.Delete(c.ID)
		delete(c.Rooms, roomID)
	}
}

// close 关闭连接
func (c *Connection) close() {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.closed {
		return
	}
	c.closed = true

	// 从所有房间移除
	for roomID := range c.Rooms {
		if val, ok := c.Hub.rooms.Load(roomID); ok {
			room := val.(*Room)
			room.Connections.Delete(c.ID)
		}
	}

	// 从 Hub 移除
	c.Hub.connections.Delete(c.ID)
	atomic.AddInt64(&c.Hub.connCount, -1)

	// 仅关闭 closeChan 作为唯一停止信号（writePump 据此退出）；
	// 不关闭 Send —— 否则 listenRedis/BroadcastToRoom 并发写入会向已关闭 channel 发送而 panic。
	close(c.closeChan)
	c.Conn.Close()

	logger.Info("WebSocket disconnected",
		zap.String("conn_id", c.ID),
		zap.Int("user_id", c.UserID),
	)
}

// BroadcastToRoom 向房间广播消息
func (h *Hub) BroadcastToRoom(roomID string, msg models.WebSocketMessage) {
	if val, ok := h.rooms.Load(roomID); ok {
		room := val.(*Room)
		data, _ := json.Marshal(msg)

		room.Connections.Range(func(key, value interface{}) bool {
			conn := value.(*Connection)
			select {
			case conn.Send <- data:
			default:
				// 缓冲区满，跳过
			}
			return true
		})
	}
}

// listenRedis 监听 Redis 消息
func (h *Hub) listenRedis() {
	ch := h.pubsub.Channel()

	for {
		select {
		case msg := <-ch:
			// 任务调度器按用户推送的进度事件：原样转发给该用户的所有连接
			if msg.Pattern == "arboris:events:user:*" {
				h.dispatchUserEvent(msg.Payload)
				continue
			}

			// ws:broadcast：全局广播
			var wsMsg models.WebSocketMessage
			if err := json.Unmarshal([]byte(msg.Payload), &wsMsg); err != nil {
				logger.Error("Invalid Redis message", zap.Error(err))
				continue
			}
			h.connections.Range(func(key, value interface{}) bool {
				conn := value.(*Connection)
				conn.SendJSON(wsMsg)
				return true
			})

		case <-h.ctx.Done():
			return
		}
	}
}

// dispatchUserEvent 把任务进度事件原样转发给目标用户的所有连接。
// payload 即 dispatcher.publishEvent 发布的事件 JSON（含 task_id/event_type/user_id 等），
// 前端 useWebSocket 直接按顶层字段解析，故此处不二次包装。
func (h *Hub) dispatchUserEvent(payload string) {
	var meta struct {
		UserID int `json:"user_id"`
	}
	if err := json.Unmarshal([]byte(payload), &meta); err != nil {
		logger.Error("Invalid task event", zap.Error(err))
		return
	}

	data := []byte(payload)
	h.connections.Range(func(key, value interface{}) bool {
		conn := value.(*Connection)
		if conn.UserID == meta.UserID {
			conn.sendRaw(data)
		}
		return true
	})
}

// Close 关闭 Hub
func (h *Hub) Close() {
	h.cancel()
	h.pubsub.Close()

	// 关闭所有连接
	h.connections.Range(func(key, value interface{}) bool {
		conn := value.(*Connection)
		conn.close()
		return true
	})
}

// generateConnectionID 生成连接 ID
func generateConnectionID() string {
	return time.Now().Format("20060102150405") + "-" + randomString(8)
}

func randomString(n int) string {
	const letters = "abcdefghijklmnopqrstuvwxyz0123456789"
	b := make([]byte, n)
	for i := range b {
		b[i] = letters[time.Now().UnixNano()%int64(len(letters))]
	}
	return string(b)
}
