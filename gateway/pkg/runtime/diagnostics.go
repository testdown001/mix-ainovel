package runtime

import (
	"context"
	"runtime"
	"runtime/debug"
	"sync/atomic"
	"time"

	"github.com/arboris-novel/gateway/internal/logger"
	"go.uber.org/zap"
)

// GoroutineLeakDetector monitors goroutine count and alerts on unexpected growth.
type GoroutineLeakDetector struct {
	baseline     int64
	threshold    int64
	checkInterval time.Duration
	alertFn      func(current, baseline int64)
}

type LeakDetectorOption func(*GoroutineLeakDetector)

func WithThreshold(n int64) LeakDetectorOption {
	return func(d *GoroutineLeakDetector) { d.threshold = n }
}

func WithCheckInterval(dur time.Duration) LeakDetectorOption {
	return func(d *GoroutineLeakDetector) { d.checkInterval = dur }
}

func WithAlertFunc(fn func(current, baseline int64)) LeakDetectorOption {
	return func(d *GoroutineLeakDetector) { d.alertFn = fn }
}

func NewGoroutineLeakDetector(opts ...LeakDetectorOption) *GoroutineLeakDetector {
	d := &GoroutineLeakDetector{
		baseline:      int64(runtime.NumGoroutine()),
		threshold:     500,
		checkInterval: 30 * time.Second,
		alertFn: func(current, baseline int64) {
			logger.Warn("goroutine count exceeds threshold",
				zap.Int64("current", current),
				zap.Int64("baseline", baseline),
				zap.Int64("delta", current-baseline),
			)
		},
	}
	for _, opt := range opts {
		opt(d)
	}
	return d
}

// Start begins periodic goroutine count monitoring. Run as a goroutine.
func (d *GoroutineLeakDetector) Start(ctx context.Context) {
	ticker := time.NewTicker(d.checkInterval)
	defer ticker.Stop()

	var prevCount int64
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			current := int64(runtime.NumGoroutine())

			if current > d.baseline+d.threshold {
				d.alertFn(current, d.baseline)
			}

			if prevCount > 0 && current > prevCount*2 && current > 100 {
				logger.Warn("goroutine count doubled since last check",
					zap.Int64("current", current),
					zap.Int64("previous", prevCount),
				)
			}

			prevCount = current
		}
	}
}

// UpdateBaseline resets the baseline to the current goroutine count.
func (d *GoroutineLeakDetector) UpdateBaseline() {
	atomic.StoreInt64(&d.baseline, int64(runtime.NumGoroutine()))
}

// RuntimeStats returns a snapshot of Go runtime statistics.
type RuntimeStats struct {
	NumGoroutine int                `json:"num_goroutine"`
	NumCPU       int                `json:"num_cpu"`
	GOMAXPROCS   int                `json:"gomaxprocs"`
	GoVersion    string             `json:"go_version"`
	Memory       MemoryStats        `json:"memory"`
	GC           GCStats            `json:"gc"`
	BuildInfo    *debug.BuildInfo   `json:"build_info,omitempty"`
}

type MemoryStats struct {
	AllocMB       float64 `json:"alloc_mb"`
	TotalAllocMB  float64 `json:"total_alloc_mb"`
	SysMB         float64 `json:"sys_mb"`
	HeapAllocMB   float64 `json:"heap_alloc_mb"`
	HeapInUseMB   float64 `json:"heap_inuse_mb"`
	HeapIdleMB    float64 `json:"heap_idle_mb"`
	HeapReleasedMB float64 `json:"heap_released_mb"`
	HeapObjects   uint64  `json:"heap_objects"`
	StackInUseMB  float64 `json:"stack_inuse_mb"`
}

type GCStats struct {
	NumGC        uint32  `json:"num_gc"`
	PauseTotalMs float64 `json:"pause_total_ms"`
	LastPauseMs  float64 `json:"last_pause_ms"`
	GCCPUPercent float64 `json:"gc_cpu_percent"`
	NextGCMB     float64 `json:"next_gc_mb"`
}

func GetRuntimeStats() RuntimeStats {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	bi, _ := debug.ReadBuildInfo()

	var lastPause float64
	if m.NumGC > 0 {
		lastPause = float64(m.PauseNs[(m.NumGC+255)%256]) / 1e6
	}

	return RuntimeStats{
		NumGoroutine: runtime.NumGoroutine(),
		NumCPU:       runtime.NumCPU(),
		GOMAXPROCS:   runtime.GOMAXPROCS(0),
		GoVersion:    runtime.Version(),
		Memory: MemoryStats{
			AllocMB:       float64(m.Alloc) / 1024 / 1024,
			TotalAllocMB:  float64(m.TotalAlloc) / 1024 / 1024,
			SysMB:         float64(m.Sys) / 1024 / 1024,
			HeapAllocMB:   float64(m.HeapAlloc) / 1024 / 1024,
			HeapInUseMB:   float64(m.HeapInuse) / 1024 / 1024,
			HeapIdleMB:    float64(m.HeapIdle) / 1024 / 1024,
			HeapReleasedMB: float64(m.HeapReleased) / 1024 / 1024,
			HeapObjects:   m.HeapObjects,
			StackInUseMB:  float64(m.StackInuse) / 1024 / 1024,
		},
		GC: GCStats{
			NumGC:        m.NumGC,
			PauseTotalMs: float64(m.PauseTotalNs) / 1e6,
			LastPauseMs:  lastPause,
			GCCPUPercent: m.GCCPUFraction * 100,
			NextGCMB:     float64(m.NextGC) / 1024 / 1024,
		},
		BuildInfo: bi,
	}
}

// TuneGC sets GOGC and memory limit for production workloads.
func TuneGC(gogcPercent int, memLimitMB int64) {
	if gogcPercent > 0 {
		old := debug.SetGCPercent(gogcPercent)
		logger.Info("GOGC tuned", zap.Int("old", old), zap.Int("new", gogcPercent))
	}
	if memLimitMB > 0 {
		limit := memLimitMB * 1024 * 1024
		debug.SetMemoryLimit(limit)
		logger.Info("memory limit set", zap.Int64("limit_mb", memLimitMB))
	}
}
