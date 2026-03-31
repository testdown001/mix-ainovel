package service

import (
	"context"
	"sync"
	"sync/atomic"
	"time"

	"github.com/arboris-novel/gateway/internal/logger"
	"github.com/arboris-novel/gateway/internal/metrics"
	"go.uber.org/zap"
)

// WebhookTask represents a unit of webhook processing work.
type WebhookTask struct {
	EventID   string
	Payload   []byte
	Signature string
	Received  time.Time
}

// WebhookWorkerPool is a bounded goroutine pool with a channel-based task queue.
// It provides backpressure when the queue is full — Submit blocks until a slot opens.
type WebhookWorkerPool struct {
	workers    int
	taskQueue  chan WebhookTask
	handler    func(ctx context.Context, task WebhookTask) error
	wg         sync.WaitGroup
	ctx        context.Context
	cancel     context.CancelFunc

	// Metrics
	processed  atomic.Int64
	failed     atomic.Int64
	queueDepth atomic.Int64
}

func NewWebhookWorkerPool(workers, queueSize int, handler func(ctx context.Context, task WebhookTask) error) *WebhookWorkerPool {
	ctx, cancel := context.WithCancel(context.Background())
	return &WebhookWorkerPool{
		workers:   workers,
		taskQueue: make(chan WebhookTask, queueSize),
		handler:   handler,
		ctx:       ctx,
		cancel:    cancel,
	}
}

// Start launches worker goroutines. Call from a go statement.
func (p *WebhookWorkerPool) Start(parentCtx context.Context) {
	// Replace context with one derived from parent
	p.ctx, p.cancel = context.WithCancel(parentCtx)

	for i := 0; i < p.workers; i++ {
		p.wg.Add(1)
		go p.worker(i)
	}

	logger.Info("webhook worker pool started",
		zap.Int("workers", p.workers),
		zap.Int("queue_size", cap(p.taskQueue)),
	)
}

func (p *WebhookWorkerPool) worker(id int) {
	defer p.wg.Done()

	for {
		select {
		case task, ok := <-p.taskQueue:
			if !ok {
				return // queue closed
			}
			p.queueDepth.Add(-1)

			start := time.Now()
			if err := p.handler(p.ctx, task); err != nil {
				p.failed.Add(1)
				metrics.WebhookFailed.Inc()
				logger.Error("webhook processing failed",
					zap.Int("worker", id),
					zap.String("event_id", task.EventID),
					zap.Duration("elapsed", time.Since(start)),
					zap.Error(err),
				)
			} else {
				p.processed.Add(1)
				metrics.WebhookProcessed.Inc()
			}
			metrics.WebhookProcessingDuration.Observe(time.Since(start).Seconds())
			metrics.WebhookQueueDepth.Set(float64(p.queueDepth.Load()))

		case <-p.ctx.Done():
			return
		}
	}
}

// Submit enqueues a webhook task. Blocks if the queue is full (backpressure).
// Returns false if the pool is shutting down.
func (p *WebhookWorkerPool) Submit(task WebhookTask) bool {
	select {
	case p.taskQueue <- task:
		p.queueDepth.Add(1)
		return true
	case <-p.ctx.Done():
		return false
	}
}

// TrySubmit attempts to enqueue without blocking. Returns false if queue is full.
func (p *WebhookWorkerPool) TrySubmit(task WebhookTask) bool {
	select {
	case p.taskQueue <- task:
		p.queueDepth.Add(1)
		return true
	default:
		return false
	}
}

// Shutdown closes the queue and waits for all workers to finish.
func (p *WebhookWorkerPool) Shutdown() {
	close(p.taskQueue)
	p.wg.Wait()
	logger.Info("webhook worker pool stopped",
		zap.Int64("processed", p.processed.Load()),
		zap.Int64("failed", p.failed.Load()),
	)
}

// Stats returns pool statistics.
func (p *WebhookWorkerPool) Stats() map[string]interface{} {
	return map[string]interface{}{
		"workers":     p.workers,
		"queue_depth": p.queueDepth.Load(),
		"queue_cap":   cap(p.taskQueue),
		"processed":   p.processed.Load(),
		"failed":      p.failed.Load(),
	}
}
