# AIMETA P=Celery应用_任务队列配置|R=Celery初始化_任务注册|E=celery_app|X=internal|A=Celery|D=celery,redis|S=net
"""
Celery 应用配置 - 异步任务队列

核心功能：
1. 章节生成任务异步化，解耦 HTTP 请求周期
2. 支持任务重试、超时控制
3. Redis 作为 Broker 和 Result Backend
"""
import logging
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
from ..core.config import settings

logger = logging.getLogger(__name__)

# 从 Redis URL 中提取配置
redis_url = settings.redis_url

# 创建 Celery 应用实例
celery_app = Celery(
    "arboris",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.tasks.chapter_tasks",
        "app.tasks.emotion_tasks",
        "app.tasks.foreshadowing_tasks",
    ]
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,

    # 结果过期时间（24小时）
    result_expires=86400,

    # 任务默认配置
    task_acks_late=True,  # 任务执行完成后才确认
    task_reject_on_worker_lost=True,  # Worker 丢失时拒绝任务
    task_track_started=True,  # 跟踪任务开始状态

    # 并发配置
    worker_prefetch_multiplier=1,  # 每个 worker 只预取 1 个任务，避免阻塞
    worker_max_tasks_per_child=50,  # 每个 worker 子进程最多执行 50 个任务后重启

    # 任务路由（可选，用于不同优先级队列）
    task_routes={
        "app.tasks.chapter_tasks.generate_chapter_task": {"queue": "chapter_generation"},
        "app.tasks.chapter_tasks.batch_generate_chapters_task": {"queue": "batch_generation"},
        "app.tasks.emotion_tasks.*": {"queue": "default"},
        "app.tasks.foreshadowing_tasks.*": {"queue": "default"},
    },

    # 队列优先级
    task_queue_max_priority=10,
    task_default_priority=5,
)


@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    """任务开始前的钩子"""
    logger.info(f"Task {task.name} [{task_id}] started")


@task_postrun.connect
def task_postrun_handler(task_id, task, *args, **kwargs):
    """任务完成后的钩子"""
    logger.info(f"Task {task.name} [{task_id}] completed")


@task_failure.connect
def task_failure_handler(task_id, exception, *args, **kwargs):
    """任务失败的钩子"""
    logger.error(f"Task [{task_id}] failed: {exception}")
