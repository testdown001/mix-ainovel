#!/usr/bin/env python3
"""
Celery Beat 启动脚本（定时任务调度器）

用法:
    python celery_beat.py

或使用 Celery CLI:
    celery -A app.tasks.celery_app beat --loglevel=info
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.tasks.celery_app import celery_app

if __name__ == "__main__":
    celery_app.worker_main([
        "beat",
        "--loglevel=info",
    ])
