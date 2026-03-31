.PHONY: build build-api run run-api test clean docker-build docker-run

# 变量
BINARY_GATEWAY=arboris-gateway
BINARY_API=arboris-api
DOCKER_IMAGE=arboris-gateway:latest

# 构建
build:
	go build -o $(BINARY_GATEWAY) cmd/gateway/main.go

build-api:
	go build -o $(BINARY_API) cmd/api/main.go

build-all: build build-api

# 运行
run:
	go run cmd/gateway/main.go

run-api:
	go run cmd/api/main.go

# 测试
test:
	go test -v ./...

# 测试覆盖率
test-coverage:
	go test -cover ./...

# 清理
clean:
	rm -f $(BINARY_GATEWAY) $(BINARY_API)
	rm -rf logs/

# Docker 构建
docker-build:
	docker build -t $(DOCKER_IMAGE) .

# Docker 运行
docker-run:
	docker run -p 3000:3000 --env-file .env $(DOCKER_IMAGE)

# 格式化代码
fmt:
	go fmt ./...

# 代码检查
lint:
	golangci-lint run

# 安装依赖
deps:
	go mod download
	go mod tidy

# 生成 go.sum
mod-verify:
	go mod verify

# 压测
LOADTEST_BINARY=loadtest
build-loadtest:
	go build -o $(LOADTEST_BINARY) test/loadtest/main.go

loadtest-health: build-loadtest
	./$(LOADTEST_BINARY) -url http://localhost:3000 -c 1000 -d 30s -scenario health

loadtest-mixed: build-loadtest
	./$(LOADTEST_BINARY) -url http://localhost:3000 -c 500 -d 60s -scenario mixed

loadtest-10k: build-loadtest
	./$(LOADTEST_BINARY) -url http://localhost:3000 -c 10000 -d 30s -scenario health

# 运行时诊断
debug-runtime:
	@curl -s http://localhost:3000/debug/runtime | python3 -m json.tool 2>/dev/null || curl -s http://localhost:3000/debug/runtime

debug-db-pool:
	@curl -s http://localhost:3000/debug/db-pool | python3 -m json.tool 2>/dev/null || curl -s http://localhost:3000/debug/db-pool

debug-redis-pool:
	@curl -s http://localhost:3000/debug/redis-pool | python3 -m json.tool 2>/dev/null || curl -s http://localhost:3000/debug/redis-pool

debug-webhook-pool:
	@curl -s http://localhost:3000/debug/webhook-pool | python3 -m json.tool 2>/dev/null || curl -s http://localhost:3000/debug/webhook-pool
