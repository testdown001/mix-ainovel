#!/bin/bash
# Arboris-Novel 快速启动脚本 - 本地开发环境

set -e

echo "🚀 启动 Arboris-Novel 开发环境..."

# 检查 Redis 是否运行
if ! docker ps | grep -q redis; then
    echo "📦 启动 Redis..."
    docker run -d --name arboris-redis -p 6379:6379 redis:7-alpine
    sleep 2
else
    echo "✅ Redis 已运行"
fi

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 激活虚拟环境
source .venv/bin/activate

echo "✅ 虚拟环境已激活"

# 检查依赖
if ! python -c "import celery" 2>/dev/null; then
    echo "📦 安装 Celery 依赖..."
    pip install celery[redis]==5.4.0 flower==2.0.1
fi

echo "✅ 依赖检查完成"

# 创建日志目录
mkdir -p logs

# 启动服务（使用 tmux 或 screen）
if command -v tmux &> /dev/null; then
    echo "🎬 使用 tmux 启动服务..."

    # 创建新的 tmux 会话
    tmux new-session -d -s arboris

    # 窗口 0: FastAPI
    tmux rename-window -t arboris:0 'FastAPI'
    tmux send-keys -t arboris:0 'source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000' C-m

    # 窗口 1: Celery Worker
    tmux new-window -t arboris:1 -n 'Celery-Worker'
    tmux send-keys -t arboris:1 'source .venv/bin/activate && celery -A app.tasks.celery_app worker --loglevel=info -c 4' C-m

    # 窗口 2: Flower 监控
    tmux new-window -t arboris:2 -n 'Flower'
    tmux send-keys -t arboris:2 'source .venv/bin/activate && celery -A app.tasks.celery_app flower --port=5555' C-m

    echo ""
    echo "✅ 服务已启动！"
    echo ""
    echo "📊 访问地址:"
    echo "  - FastAPI:  http://localhost:8000"
    echo "  - API 文档: http://localhost:8000/docs"
    echo "  - Flower:   http://localhost:5555"
    echo ""
    echo "🔧 管理命令:"
    echo "  - 查看所有窗口: tmux attach -t arboris"
    echo "  - 切换窗口: Ctrl+B 然后按数字键 (0/1/2)"
    echo "  - 停止所有服务: tmux kill-session -t arboris"
    echo ""

    # 附加到 tmux 会话
    tmux attach -t arboris

else
    echo "⚠️  未安装 tmux，手动启动服务..."
    echo ""
    echo "请在 3 个终端中分别运行:"
    echo ""
    echo "终端 1 (FastAPI):"
    echo "  source .venv/bin/activate && uvicorn app.main:app --reload"
    echo ""
    echo "终端 2 (Celery Worker):"
    echo "  source .venv/bin/activate && celery -A app.tasks.celery_app worker --loglevel=info -c 4"
    echo ""
    echo "终端 3 (Flower):"
    echo "  source .venv/bin/activate && celery -A app.tasks.celery_app flower --port=5555"
    echo ""
fi
