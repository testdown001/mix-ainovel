.PHONY: build run test clean docker-build docker-run

# 变量
BINARY_NAME=arboris-gateway
DOCKER_IMAGE=arboris-gateway:latest

# 构建
build:
	go build -o $(BINARY_NAME) cmd/gateway/main.go

# 运行
run:
	go run cmd/gateway/main.go

# 测试
test:
	go test -v ./...

# 测试覆盖率
test-coverage:
	go test -cover ./...

# 清理
clean:
	rm -f $(BINARY_NAME)
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
