package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadAllowsGatewayEnvOverrides(t *testing.T) {
	t.Setenv("GATEWAY_BACKEND_FASTAPI_URL", "http://env-app:8000")
	t.Setenv("GATEWAY_JWT_SECRET", "env-secret")
	t.Setenv("GATEWAY_TASK_DISPATCHER_INTERNAL_CALLBACK_SECRET", "env-callback-secret")
	t.Setenv("GATEWAY_REDIS_ADDR", "env-redis:6379")
	t.Setenv("GATEWAY_TASK_DISPATCHER_MAX_CONCURRENCY", "4")
	t.Setenv("GATEWAY_TASK_DISPATCHER_LEASE_DURATION", "45s")

	configPath := filepath.Join(t.TempDir(), "config.yaml")
	err := os.WriteFile(configPath, []byte(`
server:
  port: 3001
backend:
  fastapi_url: "http://yaml-app:8000"
jwt:
  secret: "yaml-secret"
redis:
  addr: "yaml-redis:6379"
task_dispatcher:
  internal_callback_secret: "yaml-callback-secret"
`), 0o600)
	if err != nil {
		t.Fatalf("write config: %v", err)
	}

	cfg, err := Load(configPath)
	if err != nil {
		t.Fatalf("load config: %v", err)
	}

	if cfg.Server.Port != 3001 {
		t.Fatalf("expected YAML server port to remain 3001, got %d", cfg.Server.Port)
	}
	if cfg.Backend.FastAPIURL != "http://env-app:8000" {
		t.Fatalf("backend fastapi_url was not overridden: %q", cfg.Backend.FastAPIURL)
	}
	if cfg.JWT.Secret != "env-secret" {
		t.Fatalf("jwt secret was not overridden: %q", cfg.JWT.Secret)
	}
	if cfg.Redis.Addr != "env-redis:6379" {
		t.Fatalf("redis addr was not overridden: %q", cfg.Redis.Addr)
	}
	if cfg.TaskDispatcher.InternalCallbackSecret != "env-callback-secret" {
		t.Fatalf(
			"internal callback secret was not overridden: %q",
			cfg.TaskDispatcher.InternalCallbackSecret,
		)
	}
	if cfg.TaskDispatcher.MaxConcurrency != 4 {
		t.Fatalf("task dispatcher capacity was not overridden: %d", cfg.TaskDispatcher.MaxConcurrency)
	}
	if cfg.TaskDispatcher.LeaseDuration.String() != "45s" {
		t.Fatalf("task dispatcher lease duration was not overridden: %s", cfg.TaskDispatcher.LeaseDuration)
	}
}

func writeMinimalConfig(t *testing.T, extra string) string {
	t.Helper()
	configPath := filepath.Join(t.TempDir(), "config.yaml")
	body := `
jwt:
  secret: "yaml-secret"
task_dispatcher:
  internal_callback_secret: "yaml-callback-secret"
` + extra
	if err := os.WriteFile(configPath, []byte(body), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}
	return configPath
}

func TestRateLimitDefaultsWhenYAMLOmitsSection(t *testing.T) {
	// yaml 完全不含 rate_limit 段：所有项都应回退到非零默认，杜绝 0=拒所有。
	cfg, err := Load(writeMinimalConfig(t, ""))
	if err != nil {
		t.Fatalf("load config: %v", err)
	}
	rl := cfg.RateLimit
	checks := map[string]int{
		"default_tpm":        rl.DefaultTPM,
		"default_concurrent": rl.DefaultConcurrent,
		"default_rpm":        rl.DefaultRPM,
		"default_rps":        rl.DefaultRPS,
		"premium_tpm":        rl.PremiumTPM,
		"premium_concurrent": rl.PremiumConcurrent,
		"premium_rpm":        rl.PremiumRPM,
		"premium_rps":        rl.PremiumRPS,
		"unauth_ip_rpm":      rl.UnauthIPRPM,
	}
	for name, val := range checks {
		if val <= 0 {
			t.Fatalf("rate_limit.%s 应有非零默认，实得 %d", name, val)
		}
	}
	if rl.UnauthIPRPM != 120 {
		t.Fatalf("expected default unauth_ip_rpm=120, got %d", rl.UnauthIPRPM)
	}
	if rl.DefaultRPM != 60 {
		t.Fatalf("expected default default_rpm=60, got %d", rl.DefaultRPM)
	}
}

func TestTaskDispatcherDefaultsMatchApplicationCapacity(t *testing.T) {
	cfg, err := Load(writeMinimalConfig(t, ""))
	if err != nil {
		t.Fatalf("load config: %v", err)
	}
	if cfg.TaskDispatcher.MaxConcurrency != 3 {
		t.Fatalf("expected global task capacity 3, got %d", cfg.TaskDispatcher.MaxConcurrency)
	}
	if cfg.TaskDispatcher.LeaseDuration.String() != "30s" {
		t.Fatalf("expected lease duration 30s, got %s", cfg.TaskDispatcher.LeaseDuration)
	}
}

func TestUnauthIPRPMEnvOverride(t *testing.T) {
	t.Setenv("GATEWAY_RATE_LIMIT_UNAUTH_IP_RPM", "300")
	cfg, err := Load(writeMinimalConfig(t, "rate_limit:\n  unauth_ip_rpm: 90\n"))
	if err != nil {
		t.Fatalf("load config: %v", err)
	}
	if cfg.RateLimit.UnauthIPRPM != 300 {
		t.Fatalf("expected env override unauth_ip_rpm=300, got %d", cfg.RateLimit.UnauthIPRPM)
	}
}
