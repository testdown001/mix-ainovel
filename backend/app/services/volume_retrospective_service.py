# AIMETA P=卷级复盘与重规划|R=卷末对比计划与实际+改写下一卷规划+读侧注入|NR=不含章节生成_不含卷摘要生成|E=VolumeRetrospectiveService|X=internal|A=分析器服务|D=db,llm|S=db,net|RD=./README.ai
"""卷级复盘正式重规划

针对「开环规划」这一核心缺陷：`NovelBlueprint.volumes` 的分卷规划（arc_goal / climax_hint）
在蓝图阶段写死一次，此后**永不复盘**。故事实际写成什么样（VolumeSummary）与当初的规划
之间的落差无人过问，下一卷仍按早已过时的假设推进，偏差逐卷累积。

A1（OutlineRevisionService）在**章**这一层闭了环；本服务是它在**卷**这一层的同构体：

- 写侧 `review_volume`：某卷最后一章定稿后，把「本卷原规划」与「本卷实际摘要」并排送评，
  产出结构化复盘 + 对**下一卷**规划的修订，写回 `NovelBlueprint.volumes` 的 JSON：
    volumes[i]["retrospective"]  本卷复盘（达成/漂移/遗留）
    volumes[i+1]["replan"]       下一卷的修订规划（pending）
- 读侧 `build_replan_brief`：生成某章时，若其所属卷带 pending replan，格式化为
  `[卷级重规划]` 段注入 prompt。

设计原则（照 A1）：
- 自包含：仅依赖 NovelBlueprint.volumes + VolumeSummary(DB) + 一次 LLM 调用；
- 可降级：任意环节缺数据/异常一律返回空/None，绝不影响主生成；
- **只写规划、绝不自动改写已有章纲**：建议是给作者与下一批大纲生成用的，作者终审；
- flagship 独占 + env 灰度开关，经 preset=premium 入口门控 transitively 实现（同 A1）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_SUMMARY_LIMIT = 4000  # 送评的卷摘要截断长度


class VolumeReplan(BaseModel):
    """对下一卷规划的修订（LLM 结构化输出）。"""

    arc_goal: str = ""
    climax_hint: str = ""
    focus: str = ""          # 下一卷最该抓住的一件事
    avoid: str = ""          # 明确要避免的重复/坑


class VolumeRetrospectiveResult(BaseModel):
    achieved: str = ""       # 本卷实际达成了什么
    drift: str = ""          # 与原规划的偏差
    unresolved: List[str] = Field(default_factory=list)  # 遗留待处理的线索
    next_volume: Optional[VolumeReplan] = None


class VolumeRetrospectiveService:
    """卷级复盘：写侧评审本卷 + 重规划下一卷，读侧注入重规划提示。"""

    # ------------------------------------------------------------------ 通用
    @staticmethod
    def _parse_volumes(blueprint: Any) -> List[Dict[str, Any]]:
        """读出结构合法的分卷列表（口径与 writer._build_volume_context 一致）。

        注意 volumes 挂在 **NovelBlueprint**（主键即 project_id）上，不是 NovelProject。
        """
        raw = getattr(blueprint, "volumes", None)
        if not isinstance(raw, list):
            return []
        parsed: List[Dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                start = int(item.get("start_chapter", 0))
                end = int(item.get("end_chapter", 0))
            except (TypeError, ValueError):
                continue
            if start <= 0 or end < start:
                continue
            parsed.append(item)
        return parsed

    @staticmethod
    def _index_of_chapter(volumes: List[Dict[str, Any]], chapter_number: int) -> Optional[int]:
        for idx, vol in enumerate(volumes):
            if int(vol["start_chapter"]) <= chapter_number <= int(vol["end_chapter"]):
                return idx
        return None

    # ------------------------------------------------------------------ 写侧
    async def review_volume(
        self,
        *,
        project_id: str,
        finalized_chapter_number: int,
        session: Any,
        llm_service: Any,
        prompt_service: Any,
        user_id: int = 0,
    ) -> Dict[str, Any]:
        """某章定稿后，若它是所属卷的最后一章则复盘该卷并重规划下一卷。

        返回统计字典；任何前置条件不满足都以 `{"skipped": 原因}` 返回，不抛异常。
        """
        stats: Dict[str, Any] = {"reviewed": False}

        from ..models.novel import NovelBlueprint

        blueprint = await session.get(NovelBlueprint, project_id)
        if blueprint is None:
            return {"skipped": "blueprint_missing"}

        volumes = self._parse_volumes(blueprint)
        if not volumes:
            return {"skipped": "no_volumes"}

        idx = self._index_of_chapter(volumes, finalized_chapter_number)
        if idx is None:
            return {"skipped": "chapter_outside_volumes"}
        current = volumes[idx]
        # 只在卷末触发：卷内每章都复盘既贵又没有新信息
        if int(current["end_chapter"]) != finalized_chapter_number:
            return {"skipped": "not_volume_end"}
        if idx + 1 >= len(volumes):
            return {"skipped": "last_volume"}  # 没有下一卷可重规划

        volume_summary = await self._load_volume_summary(session, project_id, current)
        if not volume_summary:
            # 卷摘要尚未生成（卷内仍有章节缺 real_summary）——没有「实际」就无从对比
            return {"skipped": "no_volume_summary"}

        result = await self._ask_llm(
            current=current,
            next_volume=volumes[idx + 1],
            volume_summary=volume_summary,
            llm_service=llm_service,
            prompt_service=prompt_service,
            user_id=user_id,
        )
        if result is None:
            return {"skipped": "llm_failed"}

        # 先读后并整体重赋值：JSON 列必须换新对象才触发 SQLAlchemy 变更检测
        new_volumes = [dict(v) for v in (blueprint.volumes or [])]
        new_volumes[idx] = {
            **new_volumes[idx],
            "retrospective": {
                "achieved": result.achieved,
                "drift": result.drift,
                "unresolved": result.unresolved,
                "source_chapter": finalized_chapter_number,
            },
        }
        if result.next_volume is not None:
            new_volumes[idx + 1] = {
                **new_volumes[idx + 1],
                "replan": {
                    "arc_goal": result.next_volume.arc_goal,
                    "climax_hint": result.next_volume.climax_hint,
                    "focus": result.next_volume.focus,
                    "avoid": result.next_volume.avoid,
                    "source_volume": idx + 1,
                    "status": "pending",
                },
            }
            stats["replanned_volume"] = idx + 2  # 1-based 卷号，便于日志对照
        blueprint.volumes = new_volumes
        await session.commit()

        stats["reviewed"] = True
        logger.info(
            "卷级复盘完成 project=%s 卷#%d(至第%d章) stats=%s",
            project_id, idx + 1, finalized_chapter_number, stats,
        )
        return stats

    @staticmethod
    async def _load_volume_summary(
        session: Any, project_id: str, volume: Dict[str, Any]
    ) -> Optional[str]:
        """按章节区间取该卷的实际摘要。"""
        from sqlalchemy import select

        from ..models.project_memory import VolumeSummary

        rows = await session.execute(
            select(VolumeSummary.summary).where(
                VolumeSummary.project_id == project_id,
                VolumeSummary.chapter_start == int(volume["start_chapter"]),
                VolumeSummary.chapter_end == int(volume["end_chapter"]),
            )
        )
        summary = rows.scalars().first()
        return (summary or "").strip() or None

    async def _ask_llm(
        self,
        *,
        current: Dict[str, Any],
        next_volume: Dict[str, Any],
        volume_summary: str,
        llm_service: Any,
        prompt_service: Any,
        user_id: int,
    ) -> Optional[VolumeRetrospectiveResult]:
        try:
            system_prompt = await prompt_service.get_prompt("volume_retrospective")
            if not system_prompt:
                logger.warning("缺少 volume_retrospective 提示词，跳过卷级复盘")
                return None
            user_input = (
                "[本卷原规划]\n"
                f"卷名：{current.get('name') or ''}\n"
                f"章节范围：第{current['start_chapter']}-{current['end_chapter']}章\n"
                f"本卷目标：{current.get('arc_goal') or '（未规划）'}\n"
                f"高潮设想：{current.get('climax_hint') or '（未规划）'}\n\n"
                "[本卷实际写成]\n"
                f"{volume_summary[:_SUMMARY_LIMIT]}\n\n"
                "[下一卷原规划]\n"
                f"卷名：{next_volume.get('name') or ''}\n"
                f"章节范围：第{next_volume['start_chapter']}-{next_volume['end_chapter']}章\n"
                f"本卷目标：{next_volume.get('arc_goal') or '（未规划）'}\n"
                f"高潮设想：{next_volume.get('climax_hint') or '（未规划）'}\n"
            )
            result = await llm_service.generate_structured(
                prompt=user_input,
                schema=VolumeRetrospectiveResult,
                system_prompt=system_prompt,
                temperature=0.2,
                user_id=user_id,
                default=None,
            )
            # default=None 时校验彻底失败会返回 None，调用方按「跳过」处理
            return result
        except Exception as exc:  # noqa: BLE001 - 复盘失败不得影响主流程
            logger.warning("卷级复盘 LLM 调用失败（已降级跳过）: %s", exc)
            return None

    # ------------------------------------------------------------------ 读侧
    async def build_replan_brief(
        self,
        *,
        project_id: str,
        chapter_number: int,
        session: Any = None,
    ) -> Optional[str]:
        """读本章所属卷的 replan(pending)，格式化为 [卷级重规划] 段文本。

        无分卷/不在任何卷内/无 replan/异常 → None（不注入）。仅 DB 读，无 LLM。
        """
        try:
            async def _run(sess: Any) -> Optional[str]:
                from ..models.novel import NovelBlueprint

                blueprint = await sess.get(NovelBlueprint, project_id)
                if blueprint is None:
                    return None
                volumes = self._parse_volumes(blueprint)
                idx = self._index_of_chapter(volumes, chapter_number)
                if idx is None:
                    return None
                replan = volumes[idx].get("replan")
                if not isinstance(replan, dict) or replan.get("status") != "pending":
                    return None
                return self._format_brief(replan)

            if session is not None:
                return await _run(session)

            from ..db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as own_session:
                return await _run(own_session)
        except Exception as exc:
            logger.warning("卷级重规划读取失败（不影响生成）: %s", exc)
            return None

    @staticmethod
    def _format_brief(replan: Dict[str, Any]) -> Optional[str]:
        lines: List[str] = []
        if replan.get("arc_goal"):
            lines.append(f"- 本卷修订后的目标：{replan['arc_goal']}")
        if replan.get("climax_hint"):
            lines.append(f"- 本卷高潮走向：{replan['climax_hint']}")
        if replan.get("focus"):
            lines.append(f"- 本卷最该抓住的：{replan['focus']}")
        if replan.get("avoid"):
            lines.append(f"- 明确要避免：{replan['avoid']}")
        if not lines:
            return None
        header = "### 卷级重规划（基于上一卷实际走向的复盘结论）"
        return "\n".join([header, *lines])
