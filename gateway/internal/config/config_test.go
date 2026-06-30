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

func TestUnauthIPRPMDefaultsTo120(t *testing.T) {
	cfg, err := Load(writeMinimalConfig(t, ""))
	if err != nil {
		t.Fatalf("load config: %v", err)
	}
	if cfg.RateLimit.UnauthIPRPM != 120 {
		t.Fatalf("expected default unauth_ip_rpm=120, got %d", cfg.RateLimit.UnauthIPRPM)
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
