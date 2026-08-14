# AIMETA P=参考小说模式_序列化数据|R=参考小说请求响应|NR=不含业务逻辑|E=ReferenceNovelSchema|X=internal|A=Pydantic模型|D=pydantic|S=none|RD=./README.ai
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MemoryCard(BaseModel):
    model_config = ConfigDict(extra="ignore")

    genre: str = Field(default="", description="题材定位")
    core_selling_point: str = Field(default="", description="核心卖点")
    target_audience: str = Field(default="", description="目标人群")
    cool_point_patterns: List[str] = Field(default_factory=list)
    pacing_traits: str = Field(default="", description="节奏特点")
    world_type: str = Field(default="", description="世界类型")
    main_conflict_pattern: str = Field(default="", description="主线冲突模版")
    narrative_pov: str = Field(default="", description="叙述视角")
    foreshadowing_techniques: List[str] = Field(default_factory=list)
    suspense_techniques: List[str] = Field(default_factory=list)
    dialogue_style: str = Field(default="", description="对话风格")
    scene_transition_style: str = Field(default="", description="场景切换方式")
    emotion_control_pattern: str = Field(default="", description="情绪控制节奏")
    commercial_data: Dict[str, str] = Field(default_factory=dict)
    takeaways: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class ReferenceBeat(BaseModel):
    """单条桥段：一个「情境 → 手法」的可复用映射。

    这是「剧情思考」的最小单元。MemoryCard 只有全书级形容词（节奏快、爽点密），
    写到具体章节时给不出任何可操作的东西；桥段回答的是：什么局面、怎么铺垫、
    靠什么转折、情绪在哪兑现、照搬会怎么翻车。situation 是检索键——生成第 N 章时
    按本章情境找最相似的桥段注入。
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="", description="桥段名，如「当众打脸·实力悬殊反转」")
    situation: str = Field(default="", description="适用情境（检索键）：什么局面下用")
    tags: List[str] = Field(default_factory=list, description="情境标签，如 打脸/逆袭/公开场合")
    setup: str = Field(default="", description="铺垫怎么做：前置章节埋了什么")
    turn: str = Field(default="", description="转折靠什么触发：伏笔回收/信息差/外力")
    payoff: str = Field(default="", description="情绪兑现点在哪、读者情绪曲线")
    pitfalls: str = Field(default="", description="照搬的翻车点")


class BeatStructure(BaseModel):
    """全书级结构手法：给蓝图章纲阶段用的「排章思路」。"""

    model_config = ConfigDict(extra="ignore")

    volume_rhythm: str = Field(default="", description="分卷节奏：每卷怎么排大小高潮")
    conflict_escalation: str = Field(default="", description="冲突升级路径")
    hook_pattern: str = Field(default="", description="章末钩子的常用形态")


class BeatLibrary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    beats: List[ReferenceBeat] = Field(default_factory=list)
    structure: BeatStructure = Field(default_factory=BeatStructure)


class ReferenceNovelBase(BaseModel):
    title: str
    outline_content: Optional[str] = None
    style_samples_content: Optional[str] = None
    memory_card: Optional[MemoryCard] = None
    genre: Optional[str] = None
    author: Optional[str] = None
    source_url: Optional[str] = None


class ReferenceNovelCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    author: Optional[str] = Field(default=None, max_length=100)
    genre: Optional[str] = Field(default=None, max_length=50)


class ReferenceNovelUpdate(BaseModel):
    outline_content: Optional[str] = None
    style_samples_content: Optional[str] = None
    memory_card: Optional[MemoryCard] = None
    beat_library: Optional[BeatLibrary] = None
    genre: Optional[str] = None
    author: Optional[str] = None
    source_url: Optional[str] = None
    status: Optional[str] = None
    error_message: Optional[str] = None


class ReferenceNovelSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    genre: Optional[str] = None
    author: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class ReferenceNovelDetail(ReferenceNovelSummary):
    outline_content: Optional[str] = None
    style_samples_content: Optional[str] = None
    memory_card: Optional[MemoryCard] = None
    beat_library: Optional[BeatLibrary] = None
    source_url: Optional[str] = None
    error_message: Optional[str] = None


class ReferenceNovelSelectRequest(BaseModel):
    reference_novel_ids: List[int] = Field(default_factory=list, max_items=3)
