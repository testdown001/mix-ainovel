# AIMETA P=模型包初始化_导出所有模型类|R=包标识_模型导出|NR=不含模型实现|E=-|X=internal|A=-|D=none|S=none|RD=./README.ai
"""集中导出 ORM 模型，确保 SQLAlchemy 元数据在初始化时被正确加载。"""

from .admin_setting import AdminSetting
from .llm_config import LLMConfig
from .novel import (
    BlueprintCharacter,
    BlueprintRelationship,
    Chapter,
    ChapterEvaluation,
    ChapterOutline,
    ChapterVersion,
    NovelBlueprint,
    NovelConversation,
    NovelProject,
)
from .prompt import Prompt
from .update_log import UpdateLog
from .usage_metric import UsageMetric
from .user import User
from .user_daily_request import UserDailyRequest
from .user_writing_preference import UserWritingPreference
from .system_config import SystemConfig
from .reference_novel import ReferenceNovel

# 新增：项目记忆模型
from .project_memory import ProjectMemory, ChapterSnapshot, VolumeSummary

# 新增：章节蓝图模型
from .chapter_blueprint import (
    ChapterBlueprint,
    BlueprintTemplate,
    SuspenseDensity,
    ForeshadowingOp,
    ChapterFunction,
)

# 新增：记忆层模型
from .memory_layer import (
    CharacterState,
    CharacterStateType,
    TimelineEvent,
    CausalChain,
    StoryTimeTracker,
)

# 新增：伏笔模型
from .foreshadowing import (
    Foreshadowing,
    ForeshadowingResolution,
    ForeshadowingReminder,
    ForeshadowingStatusHistory,
    ForeshadowingAnalysis,
)

# 新增：实体注册表模型
from .entity_registry import EntityRegistry, EntityAlias

# 新增：力量体系模型
from .power_system import PowerSystem, PowerLevel

# 新增：写作模板模型
from .writing_template import WritingTemplate

# 新增：章节审核模型（门下省机制）
from .chapter_review import ChapterReview

# 新增：写作任务档案模型
from .writing_archive import WritingArchive, EdictStatus
from .plan import Plan

__all__ = [
    # 基础模型
    "AdminSetting",
    "LLMConfig",
    "NovelConversation",
    "NovelBlueprint",
    "BlueprintCharacter",
    "BlueprintRelationship",
    "ChapterOutline",
    "Chapter",
    "ChapterVersion",
    "ChapterEvaluation",
    "NovelProject",
    "Prompt",
    "UpdateLog",
    "UsageMetric",
    "User",
    "UserDailyRequest",
    "UserWritingPreference",
    "SystemConfig",
    "ReferenceNovel",
    # 项目记忆模型
    "ProjectMemory",
    "ChapterSnapshot",
    "VolumeSummary",
    # 章节蓝图模型
    "ChapterBlueprint",
    "BlueprintTemplate",
    "SuspenseDensity",
    "ForeshadowingOp",
    "ChapterFunction",
    # 记忆层模块
    "CharacterState",
    "CharacterStateType",
    "TimelineEvent",
    "CausalChain",
    "StoryTimeTracker",
    # 伏笔模型
    "Foreshadowing",
    "ForeshadowingResolution",
    "ForeshadowingReminder",
    "ForeshadowingStatusHistory",
    "ForeshadowingAnalysis",
    # 实体注册表模型
    "EntityRegistry",
    "EntityAlias",
    # 力量体系模型
    "PowerSystem",
    "PowerLevel",
    # 写作模板模型
    "WritingTemplate",
    # 章节审核模型（门下省机制）
    "ChapterReview",
    # 写作任务档案模型
    "WritingArchive",
    "EdictStatus",
    "Plan",
]
