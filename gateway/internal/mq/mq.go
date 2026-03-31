package mq

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// Message represents a message from a stream/queue.
type Message struct {
	ID      string
	Stream  string
	Payload map[string]interface{}
}

// Handler processes a message. Return nil to ACK, error to NACK/retry.
type Handler func(ctx context.Context, msg Message) error

// RedisStreamMQ implements a message queue on top of Redis Streams.
// Consumer groups provide at-least-once delivery with manual ACK.
type RedisStreamMQ struct {
	rdb       *redis.Client
	group     string
	consumer  string
	blockTime time.Duration
}

func NewRedisStreamMQ(rdb *redis.Client, group, consumer string) *RedisStreamMQ {
	return &RedisStreamMQ{
		rdb:       rdb,
		group:     group,
		consumer:  consumer,
		blockTime: 5 * time.Second,
	}
}

// EnsureStream creates the stream and consumer group if they don't exist.
func (q *RedisStreamMQ) EnsureStream(ctx context.Context, stream string) error {
	err := q.rdb.XGroupCreateMkStream(ctx, stream, q.group, "0").Err()
	if err != nil && err.Error() != "BUSYGROUP Consumer Group name already exists" {
		return err
	}
	return nil
}

// Publish pushes a message to a Redis Stream.
func (q *RedisStreamMQ) Publish(ctx context.Context, stream string, payload interface{}) (string, error) {
	data, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}

	id, err := q.rdb.XAdd(ctx, &redis.XAddArgs{
		Stream: stream,
		Values: map[string]interface{}{"data": string(data)},
	}).Result()
	if err != nil {
		return "", err
	}

	logger.Debug("message published", zap.String("stream", stream), zap.String("id", id))
	return id, nil
}

// Subscribe starts consuming messages from a stream. Runs until ctx is cancelled.
// handler is called for each message. ACK is sent on success.
func (q *RedisStreamMQ) Subscribe(ctx context.Context, stream string, handler Handler) {
	if err := q.EnsureStream(ctx, stream); err != nil {
		logger.Error("failed to ensure stream", zap.String("stream", stream), zap.Error(err))
		return
	}

	// First, claim pending messages that weren't ACKed
	q.reclaimPending(ctx, stream, handler)

	// Then consume new messages
	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		streams, err := q.rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group:    q.group,
			Consumer: q.consumer,
			Streams:  []string{stream, ">"},
			Count:    10,
			Block:    q.blockTime,
		}).Result()

		if err != nil {
			if err == redis.Nil || ctx.Err() != nil {
				continue
			}
			logger.Error("XReadGroup error", zap.String("stream", stream), zap.Error(err))
			time.Sleep(time.Second)
			continue
		}

		for _, s := range streams {
			for _, rawMsg := range s.Messages {
				msg := q.parseMessage(s.Stream, rawMsg)
				if err := handler(ctx, msg); err != nil {
					logger.Error("message processing failed",
						zap.String("stream", stream),
						zap.String("id", msg.ID),
						zap.Error(err),
					)
					continue // don't ACK — will be reclaimed later
				}

				q.rdb.XAck(ctx, stream, q.group, msg.ID)
			}
		}
	}
}

func (q *RedisStreamMQ) reclaimPending(ctx context.Context, stream string, handler Handler) {
	pending, err := q.rdb.XPendingExt(ctx, &redis.XPendingExtArgs{
		Stream: stream,
		Group:  q.group,
		Start:  "-",
		End:    "+",
		Count:  100,
	}).Result()
	if err != nil {
		return
	}

	for _, p := range pending {
		if p.Idle < 30*time.Second {
			continue // recently delivered, skip
		}

		claimed, err := q.rdb.XClaim(ctx, &redis.XClaimArgs{
			Stream:   stream,
			Group:    q.group,
			Consumer: q.consumer,
			MinIdle:  30 * time.Second,
			Messages: []string{p.ID},
		}).Result()
		if err != nil || len(claimed) == 0 {
			continue
		}

		for _, rawMsg := range claimed {
			msg := q.parseMessage(stream, rawMsg)
			if err := handler(ctx, msg); err != nil {
				logger.Warn("reclaimed message failed", zap.String("id", msg.ID), zap.Error(err))
				continue
			}
			q.rdb.XAck(ctx, stream, q.group, msg.ID)
		}
	}
}

func (q *RedisStreamMQ) parseMessage(stream string, raw redis.XMessage) Message {
	payload := make(map[string]interface{})
	if dataStr, ok := raw.Values["data"].(string); ok {
		_ = json.Unmarshal([]byte(dataStr), &payload)
	}
	return Message{
		ID:      raw.ID,
		Stream:  stream,
		Payload: payload,
	}
}

// --- Stream names ---

const (
	StreamChapterGeneration = "mq:chapter:generate"
	StreamCacheInvalidation = "mq:cache:invalidate"
	StreamQuotaSync         = "mq:quota:sync"
)

// PublishGenerationTask publishes a chapter generation request to the queue.
func (q *RedisStreamMQ) PublishGenerationTask(ctx context.Context, projectID string, chapterNumber, userID int) (string, error) {
	return q.Publish(ctx, StreamChapterGeneration, map[string]interface{}{
		"project_id":     projectID,
		"chapter_number": chapterNumber,
		"user_id":        userID,
		"queued_at":      time.Now().UTC().Format(time.RFC3339),
	})
}

// PublishCacheInvalidation broadcasts a cache invalidation message.
func (q *RedisStreamMQ) PublishCacheInvalidation(ctx context.Context, key string) (string, error) {
	return q.Publish(ctx, StreamCacheInvalidation, map[string]interface{}{
		"key":       key,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

// StartGenerationConsumer starts a consumer goroutine that processes generation tasks.
func (q *RedisStreamMQ) StartGenerationConsumer(ctx context.Context, handler func(ctx context.Context, projectID string, chapterNumber, userID int) error) {
	q.Subscribe(ctx, StreamChapterGeneration, func(ctx context.Context, msg Message) error {
		projectID, _ := msg.Payload["project_id"].(string)
		chapterNumber := int(msg.Payload["chapter_number"].(float64))
		userID := int(msg.Payload["user_id"].(float64))

		logger.Info("processing generation task from queue",
			zap.String("project_id", projectID),
			zap.Int("chapter", chapterNumber),
			zap.String("msg_id", msg.ID),
		)

		return handler(ctx, projectID, chapterNumber, userID)
	})
}

// HealthCheck verifies the Redis Stream is accessible.
func (q *RedisStreamMQ) HealthCheck(ctx context.Context) error {
	_, err := q.rdb.XInfoStream(ctx, StreamChapterGeneration).Result()
	if err != nil {
		// Stream might not exist yet — create it
		return q.EnsureStream(ctx, StreamChapterGeneration)
	}
	return nil
}

func StreamName(prefix string, suffix string) string {
	return fmt.Sprintf("mq:%s:%s", prefix, suffix)
}
