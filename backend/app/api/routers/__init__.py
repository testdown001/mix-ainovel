# AIMETA P=API路由汇总|R=所有API路由统一注册|NR=|E=api_router|X=internal|A=路由系统|D=py|S=net
"""
API 路由汇总

所有 API 路由的统一入口。
"""
from fastapi import APIRouter

from .auth import router as auth_router
from .novels import router as novels_router
from .projects import router as projects_router
from .writer import router as writer_router
from .optimizer import router as optimizer_router
from .reference_novels import router as reference_novels_router
from .llm_config import router as llm_config_router
from .foreshadowing import router as foreshadowing_router
from .power_system import router as power_system_router
from .admin import router as admin_router
from .updates import router as updates_router
from .analytics import router as analytics_router
from .analytics_enhanced import router as analytics_enhanced_router
from .writing_preferences import router as writing_preferences_router
from .review import router as review_router
from .writing_template import router as writing_template_router
from .writer_progress import router as writer_progress_router
from .skill import router as skill_router
from .task_worker import router as task_worker_router
from .tasks import router as tasks_router
from .quota import router as quota_router
from .plans import router as plans_router


api_router = APIRouter()

# 认证 - auth.py 已经定义了 prefix="/api/auth"
api_router.include_router(auth_router, tags=["Auth"])

# 任务管理 - tasks.py 已经定义了 prefix="/api/tasks"
api_router.include_router(tasks_router, tags=["Tasks"])

# 配额管理 - quota.py 已经定义了 prefix="/api/quota"
api_router.include_router(quota_router, tags=["Quota"])

# 项目与小说 - novels.py 和 projects.py 已经定义了 prefix
api_router.include_router(projects_router, tags=["Projects"])
api_router.include_router(novels_router, tags=["Novels"])

# 写作 - writer.py 和 optimizer.py 已经定义了 prefix
api_router.include_router(writer_router, tags=["Writer"])
api_router.include_router(optimizer_router, tags=["Optimizer"])

# 参考小说库 - reference_novels.py 已经定义了 prefix
api_router.include_router(reference_novels_router, tags=["ReferenceNovels"])

# LLM 配置 - llm_config.py 已经定义了 prefix
api_router.include_router(llm_config_router, tags=["LLMConfig"])

# 伏笔系统 - foreshadowing.py 已经定义了 prefix
api_router.include_router(foreshadowing_router, tags=["Foreshadowing"])

# 战力系统 - power_system.py 没有定义 prefix，保持原样或检查是否需要添加
api_router.include_router(power_system_router, prefix="/power-system", tags=["PowerSystem"])

# 管理员 - admin.py 已经定义了 prefix
api_router.include_router(admin_router, tags=["Admin"])

# 更新日志 - updates.py 已经定义了 prefix
api_router.include_router(updates_router, tags=["Updates"])

# 数据分析 - analytics.py 和 analytics_enhanced.py 已经定义了 prefix
api_router.include_router(analytics_router, tags=["Analytics"])
api_router.include_router(analytics_enhanced_router, tags=["AnalyticsEnhanced"])

# 写作偏好 - writing_preferences.py 已经定义了 prefix
api_router.include_router(writing_preferences_router, tags=["WritingPreferences"])

# 章节审核 - review.py 已经定义了 prefix
api_router.include_router(review_router, tags=["Review"])

# 写作模板 - writing_template.py 已经定义了 prefix
api_router.include_router(writing_template_router, tags=["WritingTemplates"])

# 写作进度 - writer_progress.py 已经定义了 prefix
api_router.include_router(writer_progress_router, tags=["WriterProgress"])

# 技能系统 - skill.py 已经定义了 prefix
api_router.include_router(skill_router, tags=["Skills"])

# Go Task Dispatcher Worker 适配器 - 内部接口，由 Go Gateway 调用
api_router.include_router(task_worker_router, tags=["Internal"])

# 套餐管理 - plans.py 已经定义了 prefix
api_router.include_router(plans_router, tags=["Plans"])
