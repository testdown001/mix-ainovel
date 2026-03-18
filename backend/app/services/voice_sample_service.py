from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..db.session import AsyncSessionLocal
from .llm_service import LLMService
from ..utils.json_utils import remove_think_tags

logger = logging.getLogger(__name__)


class VoiceSampleService:
    """为章节生成角色声纹样本。"""

    async def generate_voice_samples(
        self,
        *,
        characters: List[Dict[str, Any]],
        outline_summary: str,
        chapter_mission: Optional[dict],
        user_id: int,
    ) -> str:
        if not characters or len(characters) < 2:
            return ""

        char_list = []
        for character in characters[:6]:
            name = character.get("name", "")
            personality = character.get("personality", "")
            role = character.get("role", "")
            if name:
                char_list.append(f"- {name}：{role}，{personality}")

        if not char_list:
            return ""

        prompt = (
            f"以下角色将在本章出场。为每个角色写2句对话样本，展示他们的说话方式。\n"
            f"要求：遮住名字能认出是谁。对话要口语化、有性格差异。\n\n"
            f"角色：\n{''.join(char_list)}\n\n"
            f"当前情境：{outline_summary[:200]}\n\n"
            f"格式：每个角色名后跟2句示例台词，简短即可。"
        )

        try:
            async with AsyncSessionLocal() as session:
                llm_service = LLMService(session)
                response = await llm_service.get_llm_response(
                    system_prompt="你是一个角色对话设计师。为每个角色写出有辨识度的对话样本。",
                    conversation_history=[{"role": "user", "content": prompt}],
                    temperature=0.8,
                    user_id=user_id,
                    timeout=30.0,
                )
            result = (remove_think_tags(response) or response).strip()
            return f"[角色声纹参考——遮住名字要能认出谁在说话]\n{result}" if result else ""
        except Exception as exc:
            logger.warning("声纹样本生成失败（不影响生成）: %s", exc)
            return ""
