#!/bin/bash
# 停止 Arboris-Novel 开发环境

echo "🛑 停止 Arboris-Novel 开发环境..."

# 停止 tmux 会话
if tmux has-session -t arboris 2>/dev/null; then
    echo "📦 停止 tmux 会话..."
    tmux kill-session -t arboris
    echo "✅ tmux 会话已停止"
fi

# 停止 Redis 容器
if docker ps | grep -q arboris-redis; then
    echo "📦 停止 Redis 容器..."
    docker stop arboris-redis
    docker rm arboris-redis
    echo "✅ Redis 容器已停止"
fi

echo "✅ 所有服务已停止"
