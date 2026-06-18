FROM golang:1.22-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
# 默认走七牛 Go 模块代理（,direct 回退保证私有/未代理模块仍可直连），与本项目 pip(清华)/npm(淘宝) 国内源一致。
# 海外构建可 docker build --build-arg GOPROXY=direct 覆盖。
ARG GOPROXY=https://goproxy.cn,direct
ENV GOPROXY=${GOPROXY}
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o gateway cmd/gateway/main.go

FROM alpine:latest

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /root/

COPY --from=builder /app/gateway .
COPY --from=builder /app/config.yaml .

RUN mkdir -p logs

EXPOSE 3000

# 唯一生产入口：cmd/gateway。原 cmd/api（与 FastAPI 重复的 Go 领域逻辑双二进制）已移除。
CMD ["./gateway"]
