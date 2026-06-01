# AIMETA P=太子省Agent|R=需求分拣|NR=解析用户指令并转发给中书省|E=TaiziAgent|X=internal|A=Agent实现|D=asyncio
"""太子省 Agent - 需求分拣"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .base import BaseAgent
from .message import AgentContext, AgentMessageType, AgentResult


class TaiziAgent(BaseAgent):
    """
    太子 Agent - 需求分拣

    职责：
    1. 解析用户写作指令
    2. 识别章节类型和情绪目标
    3. 提取关键写作要求
    4. 转发给中书省
    """

    AGENT_NAME = "taizi"

    async def process(self, context: AgentContext) -> AgentResult:
        await self.emit_stage("agent:taizi:start", "开始解析用户写作指令")

        # 1. 解析用户指令
        parsed = await self._parse_command(context.user_input or "")

        # 2. 识别章节类型
        chapter_type = await self._identify_chapter_type(
            parsed,
            context.blueprint
        )

        # 3. 提取情绪目标
        emotion_target = await self._extract_emotion_target(
            parsed,
            context.blueprint
        )

        # 4. 提取写作偏好
        writing_preferences = await self._extract_writing_preferences(parsed)

        await self.emit_stage("agent:taizi:done", f"指令解析完成，识别为【{chapter_type}】")

        # 收敛说明：原通过 send_message 转发给中书省，现主流程直接读取
        # 本方法的返回值驱动下一阶段，转发调用已移除。
        return AgentResult(
            status="delegated",
            output={
                "chapter_type": chapter_type,
                "parsed_command": parsed,
                "emotion_target": emotion_target,
                "writing_preferences": writing_preferences,
            },
            next_agent="zhongshu"
        )

    async def _parse_command(self, user_input: str) -> Dict[str, Any]:
        """解析用户指令"""
        if not user_input:
            return self._empty_parse()

        prompt = f"""请解析用户的写作指令，提取以下信息：
用户输入：{user_input}
请返回 JSON 格式：
{{
    "action": "写作动作，如'继续写作'、'修改章节'、'生成新章节'",
    "target": "目标章节或内容",
    "requirements": "具体要求列表",
    "style": "风格偏好",
    "pacing": "节奏偏好"
}}
"""
        try:
            result = await self.llm_service.generate(
                prompt,
                max_tokens=500,
                temperature=0.3,
            )
            parsed = json.loads(result)
            return parsed
        except (json.JSONDecodeError, Exception):
            return self._empty_parse()

    def _empty_parse(self) -> Dict[str, Any]:
        """空解析结果"""
        return {
            "action": "generate",
            "target": "",
            "requirements": [],
            "style": "default",
            "pacing": "balanced"
        }

    async def _identify_chapter_type(
        self,
        parsed: Dict[str, Any],
        blueprint: Optional[Dict[str, Any]]
    ) -> str:
        """识别章节类型"""
        # 类型：铺垫章/高潮章/转折章/过渡章/结局章
        if blueprint and blueprint.get("chapter_outline"):
            outline = blueprint.get("chapter_outline", {})
            position = outline.get("position", "middle")
            if position == "opening":
                return "铺垫章"
            elif position == "climax":
                return "高潮章"
            elif position == "turning":
                return "转折章"
            elif position == "ending":
                return "结局章"

        return parsed.get("chapter_type", "普通章")

    async def _extract_emotion_target(
        self,
        parsed: Dict[str, Any],
        blueprint: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """提取情绪目标"""
        return {
            "primary_emotion": parsed.get("emotion", "平稳"),
            "intensity": parsed.get("intensity", 5),
            "target_feeling": parsed.get("target_feeling", ""),
        }

    async def _extract_writing_preferences(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """提取写作偏好"""
        return {
            "style": parsed.get("style", "default"),
            "pacing": parsed.get("pacing", "balanced"),
            "dialogue_ratio": parsed.get("dialogue_ratio", 0.3),
            "description_style": parsed.get("description_style", "immersive"),
        }
