FROM golang:1.22-alpine AS builder

WORKDIR /app

# 复制 go.mod 和 go.sum
COPY go.mod go.sum ./
RUN go mod download

# 复制源代码
COPY . .

# 编译
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o gateway cmd/gateway/main.go

# 运行阶段
FROM alpine:latest

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /root/

# 从构建阶段复制二进制文件
COPY --from=builder /app/gateway .
COPY --from=builder /app/config.yaml .

# 创建日志目录
RUN mkdir -p logs

EXPOSE 3000

CMD ["./gateway"]
