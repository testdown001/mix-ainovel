package runtime

import (
	"context"
	goruntime "runtime"
	"time"

	"github.com/prometheus/client_golang/prometheus"
)

var (
	GoroutineCount = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "go_goroutine_count",
		Help: "Current number of goroutines",
	})

	HeapAllocBytes = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "go_heap_alloc_bytes",
		Help: "Heap memory allocated in bytes",
	})

	HeapObjectsCount = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "go_heap_objects",
		Help: "Number of allocated heap objects",
	})

	GCPauseTotalMs = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "go_gc_pause_total_ms",
		Help: "Total GC pause time in milliseconds",
	})

	StackInUseBytes = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "go_stack_inuse_bytes",
		Help: "Stack memory in use in bytes",
	})
)

func RegisterMetrics() {
	prometheus.MustRegister(
		GoroutineCount,
		HeapAllocBytes,
		HeapObjectsCount,
		GCPauseTotalMs,
		StackInUseBytes,
	)
}

// CollectMetrics periodically updates Prometheus gauges with runtime stats.
// Run as a goroutine.
func CollectMetrics(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			var m goruntime.MemStats
			goruntime.ReadMemStats(&m)

			GoroutineCount.Set(float64(goruntime.NumGoroutine()))
			HeapAllocBytes.Set(float64(m.HeapAlloc))
			HeapObjectsCount.Set(float64(m.HeapObjects))
			GCPauseTotalMs.Set(float64(m.PauseTotalNs) / 1e6)
			StackInUseBytes.Set(float64(m.StackInuse))
		}
	}
}
