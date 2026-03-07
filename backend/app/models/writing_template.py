# AIMETA P=写作模板模型_场景化写作指令|R=模板CRUD_参数定义|NR=|E=WritingTemplate|X=internal|A=ORM模型|D=sqlalchemy|S=db|RD=./README.ai
"""写作模板数据模型"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, DateTime, Integer, String, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class WritingTemplate(Base):
    """写作模板 - 场景化的写作指令模板"""

    __tablename__ = "writing_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(20), default="📝")

    # 模板内容
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[Optional[List[dict]]] = mapped_column(JSON, default=list)

    # 使用统计
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "icon": self.icon,
            "prompt_template": self.prompt_template,
            "parameters": self.parameters or [],
            "use_count": self.use_count,
            "is_builtin": self.is_builtin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# 内置模板清单
BUILTIN_TEMPLATES = [
    {
        "name": "高潮对决",
        "category": "高潮",
        "description": "描写关键战斗/冲突场面，情绪达到高潮",
        "icon": "⚔️",
        "prompt_template": """请描写{protagonist}与{antagonist}之间的{duel_type}对决。

背景：{background}
情绪目标：{emotion_target}
目标字数：约{word_count}字

要求：
1. 紧张激烈的对决过程
2. 体现双方实力与智慧
3. 情绪递进，最终达到高潮
4. 使用紧凑短句营造紧张感""",
        "parameters": [
            {"name": "protagonist", "label": "主角", "type": "text", "required": True, "description": "本章主角名称"},
            {"name": "antagonist", "label": "对手", "type": "text", "required": True, "description": "对手/反派名称"},
            {"name": "duel_type", "label": "对决类型", "type": "select", "options": ["武力", "智力", "情感", "综合"], "default": "武力", "description": "对决的主要形式"},
            {"name": "background", "label": "背景设定", "type": "textarea", "required": False, "description": "对决发生的背景"},
            {"name": "emotion_target", "label": "情绪目标", "type": "select", "options": ["紧张", "热血", "悲壮", "感动", "恐惧"], "default": "紧张", "description": "想要达到的情绪效果"},
            {"name": "word_count", "label": "目标字数", "type": "select", "options": ["2000", "3000", "4000", "5000"], "default": "3500", "description": "目标字数"}
        ],
        "is_builtin": True
    },
    {
        "name": "情感推进",
        "category": "情感",
        "description": "角色感情线的发展变化",
        "icon": "💕",
        "prompt_template": """请描写{character_a}对{character_b}感情从{from_stage}到{to_stage}的转变。

触发事件：{trigger_event}
目标字数：约{word_count}字

要求：
1. 细腻的情感变化过程
2. 通过具体事件推动感情发展
3. 符合角色性格
4. 避免突兀的情感转折""",
        "parameters": [
            {"name": "character_a", "label": "主动方", "type": "text", "required": True, "description": "感情变化中的主动方"},
            {"name": "character_b", "label": "被动方", "type": "text", "required": True, "description": "感情变化中的被动方"},
            {"name": "from_stage", "label": "起始阶段", "type": "select", "options": ["陌生", "认识", "好感", "喜欢", "爱慕"], "default": "认识", "description": "起始的感情阶段"},
            {"name": "to_stage", "label": "目标阶段", "type": "select", "options": ["好感", "喜欢", "爱慕", "深爱"], "default": "喜欢", "description": "目标感情阶段"},
            {"name": "trigger_event", "label": "触发事件", "type": "textarea", "required": True, "description": "推动感情变化的关键事件"},
            {"name": "word_count", "label": "目标字数", "type": "select", "options": ["2000", "3000", "4000"], "default": "3000", "description": "目标字数"}
        ],
        "is_builtin": True
    },
    {
        "name": "伏笔回收",
        "category": "悬疑",
        "description": "呼应前文埋下的伏笔",
        "icon": "🔮",
        "prompt_template": """请在本章回收第{chapter}章的伏笔：{foreshadowing_content}

预期揭示方向：{reveal_direction}
目标字数：约{word_count}字

要求：
1. 自然呼应前文
2. 揭示要出人意料又在情理之中
3. 与当前情节有机结合
4. 为后续发展留有悬念""",
        "parameters": [
            {"name": "chapter", "label": "伏笔章节", "type": "number", "required": True, "description": "伏笔所在的章节"},
            {"name": "foreshadowing_content", "label": "伏笔内容", "type": "textarea", "required": True, "description": "前文埋下的伏笔内容"},
            {"name": "reveal_direction", "label": "揭示方向", "type": "select", "options": ["完全揭示", "部分揭示", "反转", "深化"], "default": "完全揭示", "description": "如何处理伏笔的揭示"},
            {"name": "word_count", "label": "目标字数", "type": "select", "options": ["2000", "3000", "4000"], "default": "3000", "description": "目标字数"}
        ],
        "is_builtin": True
    },
    {
        "name": "内心独白",
        "category": "心理",
        "description": "角色内心活动描写",
        "icon": "💭",
        "prompt_template": """以{character}第一人称视角描写{event}后的内心活动。

背景：{background}
情绪：{emotion}
目标字数：约{word_count}字

要求：
1. 真实的心理活动
2. 情绪渲染到位
3. 与角色性格一致
4. 可以使用内心独白、回忆、联想等手法""",
        "parameters": [
            {"name": "character", "label": "角色", "type": "text", "required": True, "description": "进行内心独白的角色"},
            {"name": "event", "label": "触发事件", "type": "textarea", "required": True, "description": "引发内心活动的事件"},
            {"name": "background", "label": "背景", "type": "textarea", "required": False, "description": "相关的背景信息"},
            {"name": "emotion", "label": "情绪", "type": "select", "options": ["悲伤", "喜悦", "愤怒", "恐惧", "迷茫", "坚定", "悔恨", "释然"], "default": "迷茫", "description": "主要情绪"},
            {"name": "word_count", "label": "目标字数", "type": "select", "options": ["1000", "2000", "3000"], "default": "2000", "description": "目标字数"}
        ],
        "is_builtin": True
    },
    {
        "name": "剧情转折",
        "category": "高潮",
        "description": "打破读者预期的转折点",
        "icon": "🎭",
        "prompt_template": """在{location}安排一个{twist_type}转折。

当前情节：{current_plot}
转折内容：{twist_content}
目标字数：约{word_count}字

要求：
1. 出人意料但又在情理之中
2. 改变故事走向
3. 制造强烈的情感冲击
4. 为后续情节埋下伏笔""",
        "parameters": [
            {"name": "location", "label": "转折位置", "type": "select", "options": ["开头", "中段", "结尾"], "default": "中段", "description": "转折发生的位置"},
            {"name": "twist_type", "label": "转折类型", "type": "select", "options": ["身份反转", "关系反转", "局势逆转", "真相揭露", "命运转折"], "default": "真相揭露", "description": "转折的类型"},
            {"name": "current_plot", "label": "当前情节", "type": "textarea", "required": True, "description": "转折前的情节发展"},
            {"name": "twist_content", "label": "转折内容", "type": "textarea", "required": True, "description": "具体的转折内容"},
            {"name": "word_count", "label": "目标字数", "type": "select", "options": ["2000", "3000", "4000", "5000"], "default": "3500", "description": "目标字数"}
        ],
        "is_builtin": True
    },
    {
        "name": "世界观展示",
        "category": "设定",
        "description": "通过场景展示世界观",
        "icon": "🌍",
        "prompt_template": """通过{scene_type}展示{world_aspect}。

世界设定：{world_setting}
展示重点：{focus}
目标字数：约{word_count}字

要求：
1. 世界观自然融入场景
2. 通过人物视角展现
3. 不 exposition（说明）过多
4. 保持故事的吸引力""",
        "parameters": [
            {"name": "scene_type", "label": "场景类型", "type": "select", "options": ["日常", "战斗", "仪式", "交易", "旅行"], "default": "日常", "description": "展示世界观的场景类型"},
            {"name": "world_aspect", "label": "展示方面", "type": "select", "options": ["魔法体系", "社会结构", "种族文化", "历史背景", "地理环境"], "default": "魔法体系", "description": "要展示的世界观方面"},
            {"name": "world_setting", "label": "世界设定", "type": "textarea", "required": True, "description": "相关的世界设定"},
            {"name": "focus", "label": "展示重点", "type": "textarea", "required": False, "description": "希望重点展示的内容"},
            {"name": "word_count", "label": "目标字数", "type": "select", "options": ["2000", "3000", "4000"], "default": "3000", "description": "目标字数"}
        ],
        "is_builtin": True
    },
    {
        "name": "角色登场",
        "category": "人物",
        "description": "新角色的首次亮相",
        "icon": "👤",
        "prompt_template": """描写新角色{character}的首次登场。

角色设定：{character_profile}
登场场景：{scene}
目标字数：约{word_count}字

要求：
1. 出场方式有特色
2. 初步展现角色性格
3. 给读者留下深刻印象
4. 与情节自然衔接""",
        "parameters": [
            {"name": "character", "label": "角色名", "type": "text", "required": True, "description": "新角色的名称"},
            {"name": "character_profile", "label": "角色设定", "type": "textarea", "required": True, "description": "角色的基本设定"},
            {"name": "scene", "label": "登场场景", "type": "textarea", "required": True, "description": "角色在什么场景登场"},
            {"name": "word_count", "label": "目标字数", "type": "select", "options": ["1500", "2500", "3500"], "default": "2500", "description": "目标字数"}
        ],
        "is_builtin": True
    },
    {
        "name": "悬念结尾",
        "category": "悬疑",
        "description": "以悬念结束章节",
        "icon": "🎬",
        "prompt_template": """以悬念结尾本章。

本章情节：{plot_summary}
悬念类型：{cliffhanger_type}
目标字数：约{word_count}字

要求：
1. 制造强烈的悬念
2. 吸引读者继续阅读
3. 悬念要合理
4. 与本章主题相关""",
        "parameters": [
            {"name": "plot_summary", "label": "本章情节", "type": "textarea", "required": True, "description": "本章的主要情节"},
            {"name": "cliffhanger_type", "label": "悬念类型", "type": "select", "options": ["问题", "危机", "秘密", "反转", "死亡"], "default": "危机", "description": "悬念的类型"},
            {"name": "word_count", "label": "目标字数", "type": "select", "options": ["500", "1000", "1500"], "default": "1000", "description": "结尾字数"}
        ],
        "is_builtin": True
    },
    {
        "name": "时间跳跃",
        "category": "过渡",
        "description": "跨越时间的场景转换",
        "icon": "⏰",
        "prompt_template": """从{from_time}跳跃到{to_time}。

跳跃前：{before_moment}
跳跃后：{after_moment}
目标字数：约{word_count}字

要求：
1. 过渡自然流畅
2. 交代时间变化
3. 保持情节连贯
4. 可以使用时间标记""",
        "parameters": [
            {"name": "from_time", "label": "起始时间", "type": "text", "required": True, "description": "跳跃前的时间点"},
            {"name": "to_time", "label": "目标时间", "type": "text", "required": True, "description": "跳跃后的时间点"},
            {"name": "before_moment", "label": "跳跃前情景", "type": "textarea", "required": True, "description": "时间跳跃前的情节"},
            {"name": "after_moment", "label": "跳跃后情景", "type": "textarea", "required": True, "description": "时间跳跃后的情节"},
            {"name": "word_count", "label": "目标字数", "type": "select", "options": ["1000", "2000", "3000"], "default": "2000", "description": "目标字数"}
        ],
        "is_builtin": True
    },
    {
        "name": "暴风雨前的宁静",
        "category": "节奏",
        "description": "紧张前的平静铺垫",
        "icon": "🌤️",
        "prompt_template": """描写{upcoming_event}之前的宁静时刻。

即将发生：{upcoming_event}
宁静氛围：{atmosphere}
目标字数：约{word_count}字

要求：
1. 对比要强烈
2. 暗示即将到来的风暴
3. 渲染情绪
4. 为高潮做铺垫""",
        "parameters": [
            {"name": "upcoming_event", "label": "即将发生", "type": "textarea", "required": True, "description": "即将发生的紧张事件"},
            {"name": "atmosphere", "label": "氛围", "type": "select", "options": ["平和", "温馨", "诡异", "平静"], "default": "平和", "description": "宁静的氛围"},
            {"name": "word_count", "label": "目标字数", "type": "select", "options": ["1500", "2500", "3500"], "default": "2500", "description": "目标字数"}
        ],
        "is_builtin": True
    }
]
