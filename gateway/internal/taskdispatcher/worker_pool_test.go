package taskdispatcher

import (
	"testing"
	"time"
)

func TestNewWorkerPoolHTTPTimeoutCoversBatchTasks(t *testing.T) {
	cfg := DefaultConfig()
	cfg.DefaultTimeout = 30 * time.Minute
	cfg.BatchTimeout = 360 * time.Minute
	cfg.BlueprintTimeout = 15 * time.Minute

	pool := NewWorkerPool(cfg)
	t.Cleanup(pool.Close)

	want := cfg.BatchTimeout + 30*time.Second
	if pool.httpClient.Timeout != want {
		t.Fatalf("HTTP client timeout = %s, want %s", pool.httpClient.Timeout, want)
	}
}

func TestNewWorkerPoolHTTPTimeoutStillCoversLongerBlueprint(t *testing.T) {
	cfg := DefaultConfig()
	cfg.DefaultTimeout = 10 * time.Minute
	cfg.BatchTimeout = 5 * time.Minute
	cfg.BlueprintTimeout = 20 * time.Minute

	pool := NewWorkerPool(cfg)
	t.Cleanup(pool.Close)

	want := cfg.BlueprintTimeout + 30*time.Second
	if pool.httpClient.Timeout != want {
		t.Fatalf("HTTP client timeout = %s, want %s", pool.httpClient.Timeout, want)
	}
}
