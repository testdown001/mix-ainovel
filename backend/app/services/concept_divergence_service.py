# AIMETA P=概念N路发散评分收敛|R=一次生成N个迥异世界观种子再评分取Top|NR=不含对话流程|E=ConceptDivergenceService|X=internal|A=服务类|D=llm|S=net|RD=./README.ai
"""概念 N 路发散 + 评分收敛（divergent → convergent，旗舰档特性）。

借鉴"多假设并行发散→自我批判收敛"：高温一次性生成 N 个**彼此迥异**的世界观/冲突种子，
再用一轮低温评分（新颖度/市场力/可写性）打分去重，返回 Top-K 卡片供用户挑选。
成本约 2 次 LLM 调用（生成 + 评分），属高耗 token 特性，故仅旗舰档开放。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .llm_service import LLMService
from ..utils.json_utils import parse_llm_json

logger = logging.getLogger(__name__)


class ConceptDivergenceService:
    def __init__(self, session):
        self.session = session
        self.llm_service = LLMService(session)

    async def diverge(
        self,
        *,
        seed_topic: str,
        user_id: int,
        exclusions: str = "",
        n: int = 5,
        keep: int = 3,
    ) -> List[Dict[str, Any]]:
        """生成 N 个迥异种子并评分收敛到 Top-keep。失败返回空列表。"""
        topic = (seed_topic or "").strip()
        if not topic:
            return []
        n = max(2, min(int(n or 5), 8))
        keep = max(1, min(int(keep or 3), n))

        seeds = await self._generate_seeds(topic=topic, exclusions=exclusions, n=n, user_id=user_id)
        if not seeds:
            return []
        scored = await self._score_seeds(topic=topic, seeds=seeds, user_id=user_id)
        # 按总分降序，取 Top-keep
        scored.sort(key=lambda s: s.get("score", 0), reverse=True)
        return scored[:keep]

    async def _generate_seeds(
        self, *, topic: str, exclusions: str, n: int, user_id: int
    ) -> List[Dict[str, Any]]:
        system_prompt = (
            f"你是一位脑洞惊人的小说概念缪斯。请针对用户点子，一次性发散出 {n} 个**彼此大相径庭**的世界观/故事种子。"
            "硬性要求：\n"
            f"1) 恰好 {n} 个，方向必须真不一样（不同切入角度/基调/世界观假设/主角处境），严禁同义改写；\n"
            "2) 每个种子要敢想、跳出俗套，可大胆触碰暗黑/灰度/反常设定（合规边界内）；\n"
            "3) 只输出一个 JSON 数组，每个元素字段："
            "{\"title\":一句话工作标题, \"logline\":一句话故事梗概, "
            "\"hook\":开场最抓人的反常钩子, \"world\":世界观一句话, "
            "\"tone\":基调, \"twist\":一个反直觉的点, \"emotional_hook\":读者会牵挂的具体人物或关系选择}\n"
            "4) 不要输出 JSON 以外任何文字、不要 Markdown 围栏。"
        )
        user_prompt = f"用户点子：{topic}\n"
        if exclusions.strip():
            user_prompt += f"请回避：{exclusions.strip()}\n"
        user_prompt += f"请给出 {n} 个迥异种子的 JSON 数组。"

        try:
            raw = await self.llm_service.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=1.0,  # 高温促发散
                user_id=user_id,
                max_tokens=2600,
                response_format="json_object",
            )
        except Exception as exc:
            logger.warning("N路发散生成失败: %s", exc)
            return []

        data = parse_llm_json(raw, default=None)
        seeds = self._coerce_seed_list(data)
        # 截断到 n，并补 id
        out: List[Dict[str, Any]] = []
        for idx, s in enumerate(seeds[:n]):
            if not isinstance(s, dict):
                continue
            out.append({
                "id": idx,
                "title": str(s.get("title", "") or "").strip(),
                "logline": str(s.get("logline", "") or "").strip(),
                "hook": str(s.get("hook", "") or "").strip(),
                "world": str(s.get("world", "") or "").strip(),
                "tone": str(s.get("tone", "") or "").strip(),
                "twist": str(s.get("twist", "") or "").strip(),
                "emotional_hook": str(s.get("emotional_hook", "") or "").strip(),
            })
        return [s for s in out if s["logline"] or s["title"]]

    @staticmethod
    def _coerce_seed_list(data: Any) -> List[Any]:
        """LLM 可能返回数组，也可能返回 {"seeds":[...]} / {"items":[...]} 包裹。"""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("seeds", "items", "results", "data"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    async def _score_seeds(
        self, *, topic: str, seeds: List[Dict[str, Any]], user_id: int
    ) -> List[Dict[str, Any]]:
        system_prompt = (
            "你是资深网文主编。请给每个候选种子按五维打分（各 0-10）："
            "novelty(新颖/不落俗套)、marketability(market 抓力/可连载性)、coherence(可写性/逻辑自洽)，"
            "attachment(人物是否让读者想继续了解)、relationship_potential(关系能否持续产生有代价的选择)。"
            "不因悲惨身世或爱情本身加分，依据具体行为与牵挂。并给一句 verdict。只输出 JSON 数组，元素："
            "{\"id\":候选id, \"novelty\":int, \"marketability\":int, \"coherence\":int, "
            "\"attachment\":int, \"relationship_potential\":int, \"verdict\":一句话点评}。"
            "不要输出 JSON 以外内容。"
        )
        compact = [
            {"id": s["id"], "title": s["title"], "logline": s["logline"], "hook": s["hook"],
             "twist": s["twist"], "emotional_hook": s.get("emotional_hook", "")}
            for s in seeds
        ]
        user_prompt = (
            f"用户点子：{topic}\n候选种子（JSON）：\n{json.dumps(compact, ensure_ascii=False)}\n请打分。"
        )
        score_map: Dict[int, Dict[str, Any]] = {}
        try:
            raw = await self.llm_service.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,  # 低温稳定评分
                user_id=user_id,
                max_tokens=1500,
                response_format="json_object",
            )
            parsed = self._coerce_seed_list(parse_llm_json(raw, default=None))
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                try:
                    sid = int(item.get("id"))
                except (TypeError, ValueError):
                    continue
                nv = _clamp_score(item.get("novelty"))
                mk = _clamp_score(item.get("marketability"))
                ch = _clamp_score(item.get("coherence"))
                attachment = _clamp_score(item.get("attachment"))
                relationship = _clamp_score(item.get("relationship_potential"))
                score_map[sid] = {
                    "novelty": nv, "marketability": mk, "coherence": ch,
                    "attachment": attachment, "relationship_potential": relationship,
                    "score": nv + mk + ch + attachment + relationship, "score_max": 50,
                    "verdict": str(item.get("verdict", "") or "").strip(),
                }
        except Exception as exc:
            logger.warning("N路发散评分失败，按原序返回: %s", exc)

        # 合并分数；评分缺失的种子给中性分，保证不丢
        merged: List[Dict[str, Any]] = []
        for s in seeds:
            sc = score_map.get(s["id"], {"novelty": 5, "marketability": 5, "coherence": 5,
                                       "attachment": 5, "relationship_potential": 5,
                                       "score": 25, "score_max": 50, "verdict": ""})
            merged.append({**s, **sc})
        return merged


def _clamp_score(value: Any) -> int:
    try:
        return max(0, min(10, int(round(float(value)))))
    except (TypeError, ValueError):
        return 5
