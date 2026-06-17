# AIMETA P=情感曲线偏差比对_预期vs实际|R=规划曲线与实际情绪强度偏差检测+校正提示|NR=不含内容生成|E=EmotionDeviationService|X=internal|A=分析器服务|D=db,compute|S=compute|RD=./README.ai
"""情感曲线偏差比对 (A5)

对比「规划情绪曲线」(PacingController 三幕/英雄之旅等结构推导) 与
「实际情绪强度」(CharacterState 每章情绪快照峰值)，在偏差显著时生成校正提示，
经 TrajectoryAnalysisService 注入后续章节生成 prompt 的 [故事轨迹分析] 段。

设计原则（照 B4 伏笔语义化）：
- 自包含：仅依赖 PacingController(纯规则) + CharacterState(DB)，不触 LLM/embedding；
- 可降级：任意一侧数据缺失或异常一律返回空/None，绝不影响主生成流程；
- 实际曲线取本章 CharacterState.emotion_intensity 的「峰值」(max)，表征本章情绪高点，
  与规划曲线 emotion_intensity(单章整体强度) 同量级 (1-10) 可直接比对。
"""
from __future__ import annotations

import logging
import statistics
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# PacingController 的 narrative_phase 英文枚举 → 中文标签，仅用于提示文案
_NARRATIVE_PHASE_LABELS = {
    "exposition": "铺垫",
    "rising_action": "上升",
    "climax": "高潮",
    "falling_action": "回落",
    "resolution": "收束",
}


class EmotionDeviationService:
    """规划情绪曲线 vs 实际情绪强度的偏差比对器。"""

    DEFAULT_RECENT_WINDOW = 4   # 仅基于最近若干已完成章节判断趋势，避免远期历史稀释
    DEFAULT_THRESHOLD = 1.5     # 1-10 量级下，均值偏差 >=1.5 视为显著（约 15% 满量程）

    # ------------------------------------------------------------------ 规划侧
    def build_expected_curve(
        self,
        total_chapters: int,
        story_structure: str = "three_act",
    ) -> List[Dict[str, Any]]:
        """用 PacingController 推导整本规划情绪曲线。异常/非法入参 → []。"""
        if not total_chapters or total_chapters < 1:
            return []
        try:
            from .pacing_controller import PacingController

            controller = PacingController(
                total_chapters=int(total_chapters),
                story_structure=story_structure,
            )
            return controller.plan_emotion_curve() or []
        except Exception as exc:  # pragma: no cover - 纯规则极少抛错
            logger.warning("规划情绪曲线生成失败（偏差比对降级）: %s", exc)
            return []

    # ------------------------------------------------------------------ 实际侧
    @staticmethod
    def _aggregate_intensity_by_chapter(rows: Sequence[Any]) -> List[Dict[str, Any]]:
        """把 CharacterState 行按章聚合为单章实际情绪强度（取本章情绪峰值）。"""
        by_chapter: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            chapter_number = getattr(row, "chapter_number", None)
            intensity = getattr(row, "emotion_intensity", None)
            if chapter_number is None or intensity is None:
                continue
            try:
                value = float(intensity)
            except (TypeError, ValueError):
                continue
            # 容错：超出 1-10 的脏数据夹回区间
            value = max(1.0, min(10.0, value))
            current = by_chapter.get(int(chapter_number))
            if current is None or value > current["intensity"]:
                by_chapter[int(chapter_number)] = {
                    "chapter_number": int(chapter_number),
                    "intensity": value,
                    "emotion": getattr(row, "emotion", None) or "",
                }
        return [by_chapter[ch] for ch in sorted(by_chapter)]

    async def build_actual_intensity_curve(
        self,
        project_id: str,
        before_chapter: int,
        *,
        session: Any = None,
    ) -> List[Dict[str, Any]]:
        """读取已完成章节(章号 < before_chapter)的 CharacterState 情绪强度，按章聚合。

        无数据/异常 → []（降级）。仅 enable_memory 档位(精品)会写入 CharacterState，
        其余档位自然返回 []，A5 提示随之静默不出现。
        """
        try:
            from sqlalchemy import select

            from ..models.memory_layer import CharacterState

            async def _run(sess: Any) -> List[Dict[str, Any]]:
                stmt = (
                    select(CharacterState)
                    .where(
                        CharacterState.project_id == project_id,
                        CharacterState.chapter_number < before_chapter,
                        CharacterState.emotion_intensity.isnot(None),
                    )
                    .order_by(CharacterState.chapter_number)
                )
                result = await sess.execute(stmt)
                return self._aggregate_intensity_by_chapter(result.scalars().all())

            if session is not None:
                return await _run(session)

            from ..db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as own_session:
                return await _run(own_session)
        except Exception as exc:
            logger.warning("实际情绪曲线读取失败（偏差比对降级）: %s", exc)
            return []

    # ------------------------------------------------------------------ 比对
    def compute_deviation_brief(
        self,
        expected_curve: Sequence[Dict[str, Any]],
        actual_curve: Sequence[Dict[str, Any]],
        next_chapter: int,
        *,
        recent_window: int = DEFAULT_RECENT_WINDOW,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> Optional[str]:
        """比对近 recent_window 章的实际 vs 规划强度，偏差显著时生成校正提示。

        贴合规划(偏差小)→ None，避免给 prompt 制造噪音。
        """
        if not expected_curve or not actual_curve:
            return None

        expected_map: Dict[int, float] = {}
        expected_phase: Dict[int, Any] = {}
        for point in expected_curve:
            ch = point.get("chapter_number")
            if ch is None:
                continue
            try:
                ch_int = int(ch)
            except (TypeError, ValueError):
                continue
            # 缺失/非数值强度的规划点直接跳过，避免用 0.0 兜底制造虚假偏差
            raw = point.get("emotion_intensity", point.get("intensity"))
            if raw is None:
                continue
            try:
                expected_map[ch_int] = float(raw)
            except (TypeError, ValueError):
                continue
            expected_phase[ch_int] = point.get("narrative_phase")

        # 仅比对「既有规划又有实际」的已完成章节
        matched = []
        for point in actual_curve:
            ch = point.get("chapter_number")
            try:
                ch_int = int(ch)
            except (TypeError, ValueError):
                continue
            if ch_int in expected_map:
                matched.append((ch_int, float(point["intensity"]), expected_map[ch_int]))
        if len(matched) < 2:
            return None

        recent = matched[-recent_window:]
        deltas = [actual - expected for _, actual, expected in recent]
        avg_delta = statistics.mean(deltas)
        worst_ch, worst_actual, worst_expected = max(
            recent, key=lambda t: abs(t[1] - t[2])
        )
        worst_delta = worst_actual - worst_expected

        # 均值贴合且无突兀单章偏差 → 不出提示
        if abs(avg_delta) < threshold and abs(worst_delta) < threshold + 1.0:
            return None

        actual_avg = statistics.mean(a for _, a, _ in recent)
        expected_avg = statistics.mean(e for _, _, e in recent)
        n = len(recent)

        lines = ["### 情感曲线偏差校正 (Emotion Trajectory Correction)"]
        lines.append(
            f"- 近 {n} 章实际情绪强度均值 {actual_avg:.1f}/10，规划均值 "
            f"{expected_avg:.1f}/10（偏差 {avg_delta:+.1f}）。"
        )
        lines.append(
            f"- 偏差最大：第 {worst_ch} 章实际 {worst_actual:.1f} vs 规划 "
            f"{worst_expected:.1f}（{worst_delta:+.1f}）。"
        )

        next_expected = expected_map.get(int(next_chapter))
        next_phase_label = ""
        if next_expected is not None:
            phase = expected_phase.get(int(next_chapter))
            label = _NARRATIVE_PHASE_LABELS.get(phase or "", phase or "")
            if label:
                next_phase_label = f"（阶段：{label}）"

        # 方向判定：均值显著时用均值方向；均值贴合但被「单章大幅偏差」触发时，
        # 由该单章偏差定方向，避免均值近 0 的大幅偏低被误判为偏高。
        effective_delta = avg_delta if abs(avg_delta) >= threshold else worst_delta
        if effective_delta < 0:
            target = (
                f"本章规划强度 {next_expected:.1f}/10{next_phase_label}，"
                if next_expected is not None
                else ""
            )
            lines.append(
                f"- 实际情绪明显低于规划，故事偏平淡。{target}建议强化本章冲突/情绪张力，"
                f"把情绪曲线拉回规划水平。"
            )
        else:
            target = (
                f"本章规划强度仅 {next_expected:.1f}/10{next_phase_label}，"
                if next_expected is not None
                else ""
            )
            lines.append(
                f"- 实际情绪持续高于规划，读者易疲劳。{target}建议本章安排缓冲与情绪沉淀"
                f"（Scene & Sequel），给读者喘息空间。"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------ 入口
    async def build_brief(
        self,
        *,
        project_id: str,
        total_chapters: int,
        next_chapter: int,
        story_structure: str = "three_act",
        session: Any = None,
    ) -> Optional[str]:
        """一站式：读实际曲线 + 推规划曲线 + 比对，输出校正提示或 None。"""
        try:
            actual_curve = await self.build_actual_intensity_curve(
                project_id, next_chapter, session=session
            )
            if len(actual_curve) < 2:
                return None
            expected_curve = self.build_expected_curve(total_chapters, story_structure)
            if not expected_curve:
                return None
            return self.compute_deviation_brief(expected_curve, actual_curve, next_chapter)
        except Exception as exc:  # 双保险：任何异常都不外泄
            logger.warning("情感曲线偏差比对失败（不影响生成）: %s", exc)
            return None
