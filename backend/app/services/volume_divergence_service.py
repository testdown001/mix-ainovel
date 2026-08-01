# AIMETA P=卷级N路发散评分收敛|R=据故事实际所处位置发散下一卷方向再评分取Top|NR=不含章节生成_不含自动应用|E=VolumeDivergenceService|X=internal|A=服务类|D=llm,db|S=net,db|RD=./README.ai
"""卷级 N 路发散 + 评分收敛（旗舰档特性）

`ConceptDivergenceService` 在**开书前**对世界观做发散；本服务是它在**连载中**的对应物：
一卷写完后，基于故事**实际所处的位置**（上一卷复盘 + 实际摘要）发散出 N 个彼此迥异的
下一卷走向，评分收敛后返回 Top-K 卡片供作者挑选。

与 `VolumeRetrospectiveService` 的分工：
- 复盘是**自动**的，产出保守的「修订」——顺着既成事实把原规划校准回来；
- 发散是**作者主动触发**的，产出大胆的「另一种可能」——用于作者觉得原方向已经写腻时。

两者落点相同：选中的卡片写进 `volumes[i]["replan"]`，复用复盘那条读侧注入通路
（`build_replan_brief` → `[卷级重规划]` 段），因此发散卡片选完即刻对后续生成生效。

成本约 2 次 LLM 调用（发散 + 评分），故仅旗舰档开放（复用 muse_divergence 能力位）。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from ..utils.json_utils import parse_llm_json
from .llm_service import LLMService
from .volume_retrospective_service import VolumeRetrospectiveService

logger = logging.getLogger(__name__)

_SUMMARY_LIMIT = 3000

# 评分轴：刻意不沿用概念发散的「市场力」——连载中途换方向，读者已在场，
# 真正要权衡的是「够不够意外」与「接不接得住前文」这对矛盾。
_SCORE_AXES = ("surprise", "continuity", "tension")


class VolumeDivergenceService:
    def __init__(self, session):
        self.session = session
        self.llm_service = LLMService(session)

    async def diverge(
        self,
        *,
        project_id: str,
        volume_number: int,
        user_id: int,
        n: int = 5,
        keep: int = 3,
    ) -> List[Dict[str, Any]]:
        """为第 `volume_number` 卷（1-based）发散 N 个走向并收敛到 Top-keep。

        缺数据或 LLM 失败一律返回空列表（调用方按「暂无卡片」处理）。
        """
        n = max(2, min(int(n or 5), 8))
        keep = max(1, min(int(keep or 3), n))

        context = await self._build_context(project_id, volume_number)
        if context is None:
            return []

        cards = await self._generate_cards(context=context, n=n, user_id=user_id)
        if not cards:
            return []
        scored = await self._score_cards(context=context, cards=cards, user_id=user_id)
        scored.sort(key=lambda c: c.get("score", 0), reverse=True)
        return scored[:keep]

    # ------------------------------------------------------------------ 取材
    async def _build_context(self, project_id: str, volume_number: int) -> Optional[Dict[str, Any]]:
        """汇集「故事现在在哪」：目标卷原规划 + 上一卷原规划/复盘/实际摘要。"""
        from ..models.novel import NovelBlueprint

        blueprint = await self.session.get(NovelBlueprint, project_id)
        if blueprint is None:
            return None
        volumes = VolumeRetrospectiveService._parse_volumes(blueprint)
        idx = volume_number - 1
        if idx < 0 or idx >= len(volumes):
            logger.info("卷级发散：卷号 %s 超出分卷范围（共 %d 卷）", volume_number, len(volumes))
            return None

        target = volumes[idx]
        prev = volumes[idx - 1] if idx > 0 else None
        prev_summary = None
        if prev is not None:
            prev_summary = await VolumeRetrospectiveService._load_volume_summary(
                self.session, project_id, prev
            )
        return {
            "target": target,
            "prev": prev,
            "prev_summary": prev_summary,
            "volume_number": volume_number,
        }

    @staticmethod
    def _render_context(context: Dict[str, Any]) -> str:
        target = context["target"]
        prev = context.get("prev")
        lines = [
            f"[待规划的卷] 第{context['volume_number']}卷",
            f"卷名：{target.get('name') or ''}",
            f"章节范围：第{target['start_chapter']}-{target['end_chapter']}章",
            f"原定目标：{target.get('arc_goal') or '（未规划）'}",
            f"原定高潮：{target.get('climax_hint') or '（未规划）'}",
        ]
        if prev is not None:
            lines += [
                "",
                f"[上一卷原规划] {prev.get('name') or ''}",
                f"目标：{prev.get('arc_goal') or '（未规划）'}",
            ]
            retro = prev.get("retrospective")
            if isinstance(retro, dict):
                lines += [
                    "",
                    "[上一卷复盘]",
                    f"实际达成：{retro.get('achieved') or ''}",
                    f"与规划的偏差：{retro.get('drift') or ''}",
                ]
                unresolved = retro.get("unresolved")
                if isinstance(unresolved, list) and unresolved:
                    lines.append("遗留线索：" + "；".join(str(u) for u in unresolved))
        if context.get("prev_summary"):
            lines += ["", "[上一卷实际写成]", str(context["prev_summary"])[:_SUMMARY_LIMIT]]
        return "\n".join(lines)

    # ------------------------------------------------------------------ 发散
    async def _generate_cards(
        self, *, context: Dict[str, Any], n: int, user_id: int
    ) -> List[Dict[str, Any]]:
        system_prompt = (
            f"你是一位擅长中盘变阵的长篇连载主编。请针对「待规划的卷」，一次性发散出 {n} 个"
            "**彼此大相径庭**的走向方案。硬性要求：\n"
            f"1) 恰好 {n} 个，方向必须真不一样（不同的矛盾来源/不同的对手/不同的代价/"
            "不同的情绪基调），严禁同义改写或程度递进；\n"
            "2) 每个方案都必须**接得住上一卷的既成事实**，可以推翻原规划，但不能推翻已经写出来的内容；\n"
            "3) 至少有一个方案要敢于动摇现有格局（换对手、翻立场、让主角付出真实代价），"
            "不要 N 个都是安全牌；\n"
            "4) 章节范围固定，不要提议改章数或合并分卷；\n"
            "5) 只输出 JSON，不要任何解释性文字。\n\n"
            '输出格式：{"cards":[{"title":"一句话方向名","arc_goal":"本卷目标",'
            '"climax_hint":"高潮走向","focus":"最该抓住的一件事","avoid":"要避免的东西",'
            '"hook":"为什么读者会想追这一卷"}]}'
        )
        try:
            raw = await self.llm_service.get_llm_response(
                system_prompt=system_prompt,
                conversation_history=[{"role": "user", "content": self._render_context(context)}],
                temperature=1.0,   # 高温求真发散
                user_id=user_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("卷级发散生成失败: %s", exc)
            return []

        data = parse_llm_json(raw, default={})
        cards = data.get("cards") if isinstance(data, dict) else None
        if not isinstance(cards, list):
            return []
        cleaned: List[Dict[str, Any]] = []
        for item in cards:
            if not isinstance(item, dict):
                continue
            card = {
                key: str(item.get(key) or "").strip()
                for key in ("title", "arc_goal", "climax_hint", "focus", "avoid", "hook")
            }
            # 没有目标的卡片对作者毫无用处，直接丢
            if card["arc_goal"]:
                cleaned.append(card)
        return cleaned

    # ------------------------------------------------------------------ 收敛
    async def _score_cards(
        self, *, context: Dict[str, Any], cards: List[Dict[str, Any]], user_id: int
    ) -> List[Dict[str, Any]]:
        """三轴打分（意外性/承接度/张力）。评分失败则原序返回，不阻断。"""
        system_prompt = (
            "你是严格的长篇连载评审。请给每个下一卷走向方案按三个维度打分（1-10 整数）：\n"
            "- surprise 意外性：多大程度上跳出了读者的预期与本书已用过的套路；\n"
            "- continuity 承接度：多顺畅地接住上一卷的既成事实与遗留线索（**不是**指有多保守）；\n"
            "- tension 张力：矛盾强度与主角要付出的代价是否真的升级。\n"
            "严禁全部给高分，必须拉开差距。只输出 JSON：\n"
            '{"scores":[{"index":0,"surprise":8,"continuity":6,"tension":7,"comment":"一句话点评"}]}'
        )
        payload = json.dumps(
            [{"index": i, **c} for i, c in enumerate(cards)], ensure_ascii=False
        )
        try:
            raw = await self.llm_service.get_llm_response(
                system_prompt=system_prompt,
                conversation_history=[
                    {"role": "user", "content": f"{self._render_context(context)}\n\n[候选方案]\n{payload}"}
                ],
                temperature=0.2,
                user_id=user_id,
            )
            data = parse_llm_json(raw, default={})
            scores = data.get("scores") if isinstance(data, dict) else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("卷级发散评分失败，按原序返回: %s", exc)
            scores = None

        if not isinstance(scores, list):
            return [{**c, "score": 0} for c in cards]

        by_index: Dict[int, Dict[str, Any]] = {}
        for item in scores:
            if not isinstance(item, dict):
                continue
            try:
                by_index[int(item.get("index"))] = item
            except (TypeError, ValueError):
                continue

        result: List[Dict[str, Any]] = []
        for i, card in enumerate(cards):
            item = by_index.get(i) or {}
            axes = {}
            total = 0
            for axis in _SCORE_AXES:
                try:
                    value = max(0, min(int(item.get(axis, 0)), 10))
                except (TypeError, ValueError):
                    value = 0
                axes[axis] = value
                total += value
            result.append({
                **card,
                **axes,
                "score": total,
                "comment": str(item.get("comment") or "").strip(),
            })
        return result

    # ------------------------------------------------------------------ 应用
    async def apply_card(
        self, *, project_id: str, volume_number: int, card: Dict[str, Any]
    ) -> bool:
        """把作者选中的发散卡片写进该卷的 `replan`，复用复盘那条读侧注入通路。

        返回是否写入成功。刻意**不改动**卷的原 arc_goal/climax_hint——
        原规划保留为历史，replan 才是当前生效的方向（与复盘同口径）。
        """
        from ..models.novel import NovelBlueprint

        blueprint = await self.session.get(NovelBlueprint, project_id)
        if blueprint is None:
            return False
        volumes = VolumeRetrospectiveService._parse_volumes(blueprint)
        idx = volume_number - 1
        if idx < 0 or idx >= len(volumes):
            return False

        new_volumes = [dict(v) for v in (blueprint.volumes or [])]
        new_volumes[idx] = {
            **new_volumes[idx],
            "replan": {
                "arc_goal": str(card.get("arc_goal") or "").strip(),
                "climax_hint": str(card.get("climax_hint") or "").strip(),
                "focus": str(card.get("focus") or "").strip(),
                "avoid": str(card.get("avoid") or "").strip(),
                "source": "divergence",   # 区别于复盘自动产出，便于前端标注与追溯
                "title": str(card.get("title") or "").strip(),
                "status": "pending",
            },
        }
        blueprint.volumes = new_volumes
        await self.session.commit()
        logger.info("卷级发散卡片已应用 project=%s 卷#%d", project_id, volume_number)
        return True
