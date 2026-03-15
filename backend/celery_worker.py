#!/usr/bin/env python3
"""
Celery Worker 启动脚本

用法:
    python celery_worker.py

或使用 Celery CLI:
    celery -A app.tasks.celery_app worker --loglevel=info -c 4
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.tasks.celery_app import celery_app

if __name__ == "__main__":
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--concurrency=4",
        "--max-tasks-per-child=50",
        "--time-limit=660",
        "--soft-time-limit=600",
    ])
