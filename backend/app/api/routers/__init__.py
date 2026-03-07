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


api_router = APIRouter()

# 认证
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])

# 项目与小说
api_router.include_router(projects_router, prefix="/projects", tags=["Projects"])
api_router.include_router(novels_router, prefix="/novels", tags=["Novels"])

# 写作
api_router.include_router(writer_router, prefix="/writer", tags=["Writer"])
api_router.include_router(optimizer_router, prefix="/optimizer", tags=["Optimizer"])

# 参考小说库
api_router.include_router(reference_novels_router, prefix="/reference-novels", tags=["ReferenceNovels"])

# LLM 配置
api_router.include_router(llm_config_router, prefix="/llm-config", tags=["LLMConfig"])

# 伏笔系统
api_router.include_router(foreshadowing_router, prefix="/foreshadowing", tags=["Foreshadowing"])

# 战力系统
api_router.include_router(power_system_router, prefix="/power-system", tags=["PowerSystem"])

# 管理员
api_router.include_router(admin_router, prefix="/admin", tags=["Admin"])

# 更新日志
api_router.include_router(updates_router, prefix="/updates", tags=["Updates"])

# 数据分析
api_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(analytics_enhanced_router, prefix="/analytics-enhanced", tags=["AnalyticsEnhanced"])

# 写作偏好
api_router.include_router(writing_preferences_router, prefix="/writing-preferences", tags=["WritingPreferences"])

# 章节审核
api_router.include_router(review_router, prefix="/review", tags=["Review"])

# 写作模板
api_router.include_router(writing_template_router, prefix="/writing-templates", tags=["WritingTemplates"])

# 写作进度
api_router.include_router(writer_progress_router, prefix="/writer-progress", tags=["WriterProgress"])

# 技能系统
api_router.include_router(skill_router, prefix="/skills", tags=["Skills"])
