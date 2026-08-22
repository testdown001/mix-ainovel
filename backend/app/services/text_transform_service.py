# AIMETA P=选区文本手术刀|R=扩写改写去AI味_只处理选区|NR=不含整章生成|E=transform_selection|X=internal|A=选区变换|D=llm,humanize|S=llm
"""段落级扩写 / 改写 / 去 AI 味。只把选区送给模型，禁止整章重跑。

付费必交付：产出不是正文、或与原文一字不差，都算没兑现（delivered=False），
调用方据此退款——退回原文本身不是交付。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from .humanization_service import HumanizationService
from .llm_service import LLMService
from ..utils.json_utils import is_probable_chapter_plain_text, sanitize_chapter_plain_text

logger = logging.getLogger(__name__)

TransformAction = Literal["expand", "rewrite", "de_ai"]


@dataclass(frozen=True)
class TransformOutcome:
    """选区变换结果。delivered=False 时 text 即原选区，调用方须退款。"""

    text: str
    delivered: bool
    note: str = ""


def _settle(original: str, result: str) -> TransformOutcome:
    """一字未改 = 没兑现。规则修复无命中、模型原样回抄都落在这里。"""
    if result.strip() == original.strip():
        return TransformOutcome(original, False, "这次没能改出不一样的写法")
    return TransformOutcome(result, True)

_ACTION_PROMPTS = {
    "expand": "把下面这段网文扩写得更具体，增加动作、对白或感官，不要另起新情节，不要解释，只输出扩写后的正文。",
    "rewrite": "改写下面这段网文，保持情节与信息不变，让句子更利落、更像人写的。不要解释，只输出改写后的正文。",
}


async def transform_selection(
    session: AsyncSession,
    *,
    action: TransformAction,
    selected_text: str,
    instruction: str = "",
    context_before: str = "",
    context_after: str = "",
    user_id: int,
) -> TransformOutcome:
    text = (selected_text or "").strip()
    if not text:
        raise ValueError("请先选中要改的段落")
    if action == "de_ai":
        return _settle(text, await _de_ai(session, text, user_id))
    prompt = _ACTION_PROMPTS[action]
    if instruction.strip():
        prompt += f"\n作者额外要求：{instruction.strip()[:400]}"
    ctx = ""
    if context_before or context_after:
        ctx = f"\n前文（仅供衔接，勿改写）：{context_before[-200:]}\n后文（仅供衔接，勿改写）：{context_after[:200]}\n"
    llm = LLMService(session)
    raw = await llm.get_llm_response(
        system_prompt="你是网文作者的段落助手。只改用户圈出的那段，输出纯正文。",
        conversation_history=[{"role": "user", "content": f"{prompt}{ctx}\n【选区】\n{text}"}],
        temperature=0.7,
        user_id=user_id,
        timeout=120.0,
        response_format=None,
        max_tokens=min(4096, max(512, int(len(text) * 2.5))),
    )
    result = sanitize_chapter_plain_text((raw or "").strip())
    if not result or not is_probable_chapter_plain_text(result):
        logger.warning("选区变换产出不是正文，退回原文 action=%s", action)
        return TransformOutcome(text, False, "模型这次没返回可用的正文")
    return _settle(text, result)


async def _de_ai(session: AsyncSession, text: str, user_id: int) -> str:
    svc = HumanizationService(session, LLMService(session))
    report = svc.scan(text)
    fixed = svc.apply_rule_fixes(text, report)
    if report.score >= 92:
        return fixed
    return await svc.humanize(fixed, svc.scan(fixed), user_id=user_id)
