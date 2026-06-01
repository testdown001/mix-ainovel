# AIMETA P=灵感缪斯_跨界素材发现|R=联网检索冷门真实跨域概念供灵感嫁接|NR=不含对话流程|E=MuseMaterialService|X=internal|A=服务类|D=llm_search|S=net|RD=./README.ai
"""灵感缪斯·跨界素材发现服务。

借鉴 Hermes 模型的 function-calling/联网能力与"敢写/跨界"思路：在概念对话(灵感模式)开场时，
主动联网去找 2-3 个**冷门、真实**的跨领域概念（冷门历史/神话/科学现象/其他行业潜规则），
并给出"如何嫁接进这个故事"的灵感钩子，注入到「文思」的 system prompt 里，
让缪斯能引用大众套路之外的真实素材，显著提升"灵气"。

实现上复用既有的搜索专用 LLM 通道（与 web_search_service 同一机制），不引入新依赖、不跑
重型 agentic loop（对此有界任务属过度设计）。未配置搜索模型时优雅跳过（返回 None）。
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException

from .llm_service import LLMService
from ..utils.json_utils import remove_think_tags

logger = logging.getLogger(__name__)


class MuseMaterialService:
    def __init__(self, session):
        self.session = session
        self.llm_service = LLMService(session)

    async def discover_cross_domain_material(
        self,
        *,
        seed_topic: str,
        user_id: int,
        exclusions: str = "",
    ) -> Optional[str]:
        """针对开场点子，联网发现跨域真实素材。失败/未配置时返回 None（不影响主流程）。"""
        topic = (seed_topic or "").strip()
        if not topic:
            return None

        system_prompt = (
            "你是一位博学的'灵感缪斯'，擅长为小说创作做跨界嫁接。"
            "请优先使用联网搜索，去寻找与给定故事点子相关、但**冷门、真实、可验证**的跨领域素材，"
            "帮作者跳出大众套路。要求：\n"
            "1) 给出 2-3 个素材，每个来自不同领域（冷门历史事件/神话传说/科学现象/某个行业的潜规则/民俗或冷知识等）；\n"
            "2) 每个素材包含：①【领域】一句话概念简介（只写可验证的公开信息，绝不编造）；"
            "②『嫁接钩子』一句话说明它能如何转化成这个故事里新鲜的设定/冲突/世界观细节；\n"
            "3) 越冷门、越能制造'原来还能这样'的惊喜越好；避免人尽皆知的大路货；\n"
            "4) 用简洁中文，总篇幅控制在 500 字内。"
        )
        user_prompt = f"故事点子：{topic}\n"
        if exclusions.strip():
            user_prompt += f"\n（请回避以下方向：{exclusions.strip()}）\n"
        user_prompt += "请给出可嫁接的跨界真实素材。"

        try:
            raw = await self.llm_service.get_search_llm_response(
                system_prompt=system_prompt,
                conversation_history=[{"role": "user", "content": user_prompt}],
                temperature=0.5,
                timeout=180.0,
                max_tokens=1600,
            )
        except HTTPException as exc:
            # 503 = 未配置搜索模型；其余网络/服务异常一并优雅降级
            logger.info("缪斯跨界素材发现跳过(status=%s): %s", exc.status_code, exc.detail)
            return None
        except Exception as exc:  # pragma: no cover - 防御性降级
            logger.warning("缪斯跨界素材发现异常，跳过: %s", exc)
            return None

        material = remove_think_tags(raw or "").strip()
        return material or None
