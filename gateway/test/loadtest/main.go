package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"sync"
	"sync/atomic"
	"time"
)

type Config struct {
	BaseURL     string
	Token       string
	Concurrency int
	Duration    time.Duration
	Scenario    string
}

type Stats struct {
	TotalRequests  atomic.Int64
	SuccessCount   atomic.Int64
	FailureCount   atomic.Int64
	TotalLatencyMs atomic.Int64
	MaxLatencyMs   atomic.Int64
	MinLatencyMs   atomic.Int64

	StatusCodes sync.Map // map[int]*int64
}

func main() {
	cfg := Config{}
	flag.StringVar(&cfg.BaseURL, "url", "http://localhost:3000", "API base URL")
	flag.StringVar(&cfg.Token, "token", "", "JWT token for authenticated endpoints")
	flag.IntVar(&cfg.Concurrency, "c", 100, "number of concurrent workers")
	flag.DurationVar(&cfg.Duration, "d", 30*time.Second, "test duration")
	flag.StringVar(&cfg.Scenario, "scenario", "health", "test scenario: health|plans|projects|mixed")
	flag.Parse()

	fmt.Printf("=== Arboris Load Test ===\n")
	fmt.Printf("URL:         %s\n", cfg.BaseURL)
	fmt.Printf("Concurrency: %d\n", cfg.Concurrency)
	fmt.Printf("Duration:    %s\n", cfg.Duration)
	fmt.Printf("Scenario:    %s\n\n", cfg.Scenario)

	stats := &Stats{}
	stats.MinLatencyMs.Store(999999)

	ctx, cancel := context.WithTimeout(context.Background(), cfg.Duration)
	defer cancel()

	start := time.Now()
	var wg sync.WaitGroup

	for i := 0; i < cfg.Concurrency; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			worker(ctx, workerID, cfg, stats)
		}(i)
	}

	// Progress reporter
	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				elapsed := time.Since(start).Seconds()
				total := stats.TotalRequests.Load()
				rps := float64(total) / elapsed
				fmt.Printf("[%6.1fs] requests=%d  rps=%.1f  success=%d  fail=%d\n",
					elapsed, total, rps,
					stats.SuccessCount.Load(), stats.FailureCount.Load())
			}
		}
	}()

	wg.Wait()
	elapsed := time.Since(start)

	printReport(stats, elapsed, cfg)
}

func worker(ctx context.Context, id int, cfg Config, stats *Stats) {
	client := &http.Client{Timeout: 30 * time.Second}

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		req := buildRequest(cfg, id)
		if req == nil {
			continue
		}
		req = req.WithContext(ctx)

		start := time.Now()
		resp, err := client.Do(req)
		latency := time.Since(start).Milliseconds()

		stats.TotalRequests.Add(1)
		stats.TotalLatencyMs.Add(latency)

		// Update min/max
		for {
			old := stats.MaxLatencyMs.Load()
			if latency <= old || stats.MaxLatencyMs.CompareAndSwap(old, latency) {
				break
			}
		}
		for {
			old := stats.MinLatencyMs.Load()
			if latency >= old || stats.MinLatencyMs.CompareAndSwap(old, latency) {
				break
			}
		}

		if err != nil {
			stats.FailureCount.Add(1)
			continue
		}

		io.Copy(io.Discard, resp.Body)
		resp.Body.Close()

		// Track status codes
		key := resp.StatusCode
		if v, loaded := stats.StatusCodes.LoadOrStore(key, new(int64)); loaded {
			atomic.AddInt64(v.(*int64), 1)
		} else {
			atomic.StoreInt64(v.(*int64), 1)
		}

		if resp.StatusCode >= 200 && resp.StatusCode < 400 {
			stats.SuccessCount.Add(1)
		} else {
			stats.FailureCount.Add(1)
		}
	}
}

func buildRequest(cfg Config, workerID int) *http.Request {
	var req *http.Request
	var err error

	switch cfg.Scenario {
	case "health":
		req, err = http.NewRequest("GET", cfg.BaseURL+"/health", nil)

	case "plans":
		req, err = http.NewRequest("GET", cfg.BaseURL+"/api/v2/plans/public", nil)

	case "projects":
		req, err = http.NewRequest("GET", cfg.BaseURL+"/api/v2/novels?page=1&page_size=10", nil)
		if req != nil && cfg.Token != "" {
			req.Header.Set("Authorization", "Bearer "+cfg.Token)
		}

	case "create_order":
		body, _ := json.Marshal(map[string]interface{}{
			"plan_id":         2,
			"channel":         "stripe",
			"idempotency_key": fmt.Sprintf("loadtest-%d-%d", workerID, time.Now().UnixNano()),
		})
		req, err = http.NewRequest("POST", cfg.BaseURL+"/api/v2/payment/orders", bytes.NewReader(body))
		if req != nil {
			req.Header.Set("Content-Type", "application/json")
			if cfg.Token != "" {
				req.Header.Set("Authorization", "Bearer "+cfg.Token)
			}
		}

	case "mixed":
		scenarios := []string{"health", "plans", "projects"}
		idx := int(time.Now().UnixNano()) % len(scenarios)
		cfg2 := cfg
		cfg2.Scenario = scenarios[idx]
		return buildRequest(cfg2, workerID)

	default:
		req, err = http.NewRequest("GET", cfg.BaseURL+"/health", nil)
	}

	if err != nil {
		return nil
	}
	return req
}

func printReport(stats *Stats, elapsed time.Duration, cfg Config) {
	total := stats.TotalRequests.Load()
	success := stats.SuccessCount.Load()
	failure := stats.FailureCount.Load()
	avgLatency := float64(0)
	if total > 0 {
		avgLatency = float64(stats.TotalLatencyMs.Load()) / float64(total)
	}
	rps := float64(total) / elapsed.Seconds()

	fmt.Println("\n=== Results ===")
	fmt.Printf("Duration:       %s\n", elapsed.Round(time.Millisecond))
	fmt.Printf("Concurrency:    %d\n", cfg.Concurrency)
	fmt.Printf("Total Requests: %d\n", total)
	fmt.Printf("Success:        %d (%.1f%%)\n", success, float64(success)/float64(max(total, 1))*100)
	fmt.Printf("Failure:        %d (%.1f%%)\n", failure, float64(failure)/float64(max(total, 1))*100)
	fmt.Printf("RPS:            %.1f\n", rps)
	fmt.Printf("Avg Latency:    %.1f ms\n", avgLatency)
	fmt.Printf("Min Latency:    %d ms\n", stats.MinLatencyMs.Load())
	fmt.Printf("Max Latency:    %d ms\n", stats.MaxLatencyMs.Load())

	fmt.Println("\nStatus Codes:")
	stats.StatusCodes.Range(func(key, value interface{}) bool {
		code := key.(int)
		count := atomic.LoadInt64(value.(*int64))
		fmt.Printf("  %d: %d\n", code, count)
		return true
	})

	if rps >= 10000 {
		fmt.Println("\n✓ 10K+ RPS achieved!")
	} else if rps >= 5000 {
		fmt.Println("\n~ 5K+ RPS - good, but below 10K target")
	} else {
		fmt.Printf("\n✗ %.0f RPS - below target. Consider tuning GOMAXPROCS, pool sizes, or adding read replicas.\n", rps)
	}
}

func max(a, b int64) int64 {
	if a > b {
		return a
	}
	return b
}

func init() {
	_ = os.Stdout // avoid unused import
}
