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
from .foreshadowing import router as foreshadowing_router
from .power_system import router as power_system_router
from .admin import router as admin_router
from .updates import router as updates_router
from .analytics import router as analytics_router
from .writing_preferences import router as writing_preferences_router
from .review import router as review_router
from .writing_template import router as writing_template_router
from .writer_progress import router as writer_progress_router
from .skill import router as skill_router
from .task_worker import router as task_worker_router
from .quota import router as quota_router
from .plans import router as plans_router
from .model_catalog import router as model_catalog_router
from .api_usage import router as api_usage_router
from .payment import router as payment_router
from .public_share import router as public_share_router
from .creative_memory import router as creative_memory_router


api_router = APIRouter()

# 认证 - auth.py 已经定义了 prefix="/api/auth"
api_router.include_router(auth_router, tags=["Auth"])

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

# 伏笔系统 - foreshadowing.py 已经定义了 prefix
api_router.include_router(foreshadowing_router, tags=["Foreshadowing"])

# 战力系统 - power_system.py 没有定义 prefix，保持原样或检查是否需要添加
api_router.include_router(power_system_router, prefix="/power-system", tags=["PowerSystem"])

# 管理员 - admin.py 已经定义了 prefix
api_router.include_router(admin_router, tags=["Admin"])

# 更新日志 - updates.py 已经定义了 prefix
api_router.include_router(updates_router, tags=["Updates"])

# 数据分析 - analytics.py 已经定义了 prefix
api_router.include_router(analytics_router, tags=["Analytics"])

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
# 模型目录（前台可选模型 + 后台 CRUD）- 已定义 prefix
api_router.include_router(model_catalog_router, tags=["ModelCatalog"])

# API 用量统计 - api_usage.py 已经定义了 prefix
api_router.include_router(api_usage_router, tags=["ApiUsage"])

# 支付 - payment.py 已经定义了 prefix="/api/payment"
api_router.include_router(payment_router, tags=["Payment"])

# 作品公开分享（免登录只读）- public_share.py 已经定义了 prefix="/api/public/shared"
api_router.include_router(public_share_router, tags=["PublicShare"])

# 创作记忆 - 候选偏好确认、分级规则和生成使用回执
api_router.include_router(creative_memory_router, tags=["CreativeMemories"])
