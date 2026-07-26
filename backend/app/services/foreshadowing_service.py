# AIMETA P=伏笔服务_伏笔管理业务逻辑|R=伏笔CRUD_回收追踪|NR=不含自动分析|E=ForeshadowingService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
"""伏笔管理服务"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.foreshadowing import (
    Foreshadowing,
    ForeshadowingResolution,
    ForeshadowingReminder,
    ForeshadowingAnalysis,
)
from ..models.novel import Chapter, NovelProject

logger = logging.getLogger(__name__)


class ForeshadowingService:
    """伏笔管理服务"""

    _RESOLVED_STATUSES = {"revealed", "resolved", "paid_off", "done", "complete", "completed"}
    _UNRESOLVED_STATUSES = {"planted", "developing", "partial", "open", "pending", "active"}
    
    def __init__(self, session: AsyncSession):
        self.session = session

    def _normalize_status(self, status: Optional[str]) -> str:
        text = (status or "").strip().lower()
        if not text:
            return "planted"
        if text in self._RESOLVED_STATUSES:
            return "revealed"
        if text == "abandoned":
            return "abandoned"
        if text in self._UNRESOLVED_STATUSES:
            return "planted"
        return text

    def _is_resolved(self, status: Optional[str]) -> bool:
        return self._normalize_status(status) == "revealed"

    def _is_unresolved(self, status: Optional[str]) -> bool:
        return self._normalize_status(status) == "planted"
    
    async def create_foreshadowing(
        self,
        project_id: str,
        chapter_id: int,
        chapter_number: int,
        content: str,
        foreshadowing_type: str,
        keywords: Optional[List[str]] = None,
        author_note: Optional[str] = None,
        is_manual: bool = True,
        ai_confidence: Optional[float] = None,
    ) -> Foreshadowing:
        """创建伏笔"""
        foreshadowing = Foreshadowing(
            project_id=project_id,
            chapter_id=chapter_id,
            chapter_number=chapter_number,
            content=content,
            type=foreshadowing_type,
            keywords=keywords or [],
            author_note=author_note,
            is_manual=is_manual,
            ai_confidence=ai_confidence,
        )
        self.session.add(foreshadowing)
        await self.session.flush()
        logger.info(f"创建伏笔: project={project_id}, chapter={chapter_number}, type={foreshadowing_type}")
        return foreshadowing

    async def get_foreshadowing_by_id(
        self,
        project_id: str,
        foreshadowing_id: int,
    ) -> Optional[Foreshadowing]:
        """获取单个伏笔。"""
        result = await self.session.execute(
            select(Foreshadowing).where(
                and_(
                    Foreshadowing.id == foreshadowing_id,
                    Foreshadowing.project_id == project_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_foreshadowing(
        self,
        project_id: str,
        foreshadowing_id: int,
        data: Dict[str, Any],
    ) -> Foreshadowing:
        """更新伏笔。"""
        foreshadowing = await self.get_foreshadowing_by_id(project_id, foreshadowing_id)
        if not foreshadowing:
            raise ValueError(f"伏笔不存在: {foreshadowing_id}")

        editable_fields = {
            "chapter_id",
            "chapter_number",
            "content",
            "type",
            "keywords",
            "author_note",
            "name",
            "target_reveal_chapter",
            "reveal_method",
            "reveal_impact",
            "related_characters",
            "related_plots",
            "related_foreshadowings",
            "importance",
            "urgency",
            "resolved_chapter_id",
            "resolved_chapter_number",
        }

        for key in editable_fields:
            if key in data:
                setattr(foreshadowing, key, data[key])

        if "status" in data:
            normalized = self._normalize_status(data.get("status"))
            if normalized == "revealed":
                foreshadowing.status = "revealed"
            elif normalized == "abandoned":
                foreshadowing.status = "abandoned"
            else:
                foreshadowing.status = "planted"
                # 从“已回收/已放弃”改回未回收时，清理已回收章节信息。
                if "resolved_chapter_id" not in data:
                    foreshadowing.resolved_chapter_id = None
                if "resolved_chapter_number" not in data:
                    foreshadowing.resolved_chapter_number = None

        await self.session.flush()
        logger.info(f"更新伏笔: project={project_id}, id={foreshadowing_id}")
        return foreshadowing

    async def delete_foreshadowing(
        self,
        project_id: str,
        foreshadowing_id: int,
    ) -> bool:
        """删除伏笔。"""
        foreshadowing = await self.get_foreshadowing_by_id(project_id, foreshadowing_id)
        if not foreshadowing:
            return False

        await self.session.delete(foreshadowing)
        await self.session.flush()
        logger.info(f"删除伏笔: project={project_id}, id={foreshadowing_id}")
        return True
    
    async def get_foreshadowings(
        self,
        project_id: str,
        status: Optional[str] = None,
        foreshadowing_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Foreshadowing], int]:
        """获取伏笔列表"""
        query = select(Foreshadowing).where(Foreshadowing.project_id == project_id)
        normalized_status = self._normalize_status(status) if status else None
        
        if normalized_status == "planted":
            query = query.where(Foreshadowing.status.in_(sorted(self._UNRESOLVED_STATUSES)))
        elif normalized_status == "revealed":
            query = query.where(Foreshadowing.status.in_(sorted(self._RESOLVED_STATUSES)))
        elif normalized_status:
            query = query.where(Foreshadowing.status == normalized_status)
        if foreshadowing_type:
            query = query.where(Foreshadowing.type == foreshadowing_type)
        
        # 获取总数
        count_query = select(func.count()).select_from(Foreshadowing).where(Foreshadowing.project_id == project_id)
        if normalized_status == "planted":
            count_query = count_query.where(Foreshadowing.status.in_(sorted(self._UNRESOLVED_STATUSES)))
        elif normalized_status == "revealed":
            count_query = count_query.where(Foreshadowing.status.in_(sorted(self._RESOLVED_STATUSES)))
        elif normalized_status:
            count_query = count_query.where(Foreshadowing.status == normalized_status)
        if foreshadowing_type:
            count_query = count_query.where(Foreshadowing.type == foreshadowing_type)
        
        total = await self.session.scalar(count_query)
        
        # 分页
        query = query.order_by(Foreshadowing.chapter_number).limit(limit).offset(offset)
        result = await self.session.execute(query)
        foreshadowings = result.scalars().all()
        
        return foreshadowings, total
    
    async def resolve_foreshadowing(
        self,
        foreshadowing_id: int,
        resolved_chapter_id: int,
        resolved_chapter_number: int,
        resolution_text: str,
        resolution_type: str = "direct",
        quality_score: Optional[int] = None,
    ) -> ForeshadowingResolution:
        """标记伏笔回收"""
        # 更新伏笔状态
        foreshadowing = await self.session.get(Foreshadowing, foreshadowing_id)
        if not foreshadowing:
            raise ValueError(f"伏笔不存在: {foreshadowing_id}")
        
        foreshadowing.status = "revealed"
        foreshadowing.resolved_chapter_id = resolved_chapter_id
        foreshadowing.resolved_chapter_number = resolved_chapter_number
        
        # 创建回收记录
        resolution = ForeshadowingResolution(
            foreshadowing_id=foreshadowing_id,
            resolved_at_chapter_id=resolved_chapter_id,
            resolved_at_chapter_number=resolved_chapter_number,
            resolution_text=resolution_text,
            resolution_type=resolution_type,
            quality_score=quality_score,
        )
        self.session.add(resolution)
        await self.session.flush()
        
        logger.info(f"标记伏笔回收: foreshadowing={foreshadowing_id}, chapter={resolved_chapter_number}")
        return resolution
    
    async def abandon_foreshadowing(
        self,
        foreshadowing_id: int,
        reason: Optional[str] = None,
    ) -> Foreshadowing:
        """放弃伏笔"""
        foreshadowing = await self.session.get(Foreshadowing, foreshadowing_id)
        if not foreshadowing:
            raise ValueError(f"伏笔不存在: {foreshadowing_id}")
        
        foreshadowing.status = "abandoned"
        if reason:
            foreshadowing.author_note = f"{foreshadowing.author_note or ''}\n[放弃原因]: {reason}".strip()
        
        await self.session.flush()
        logger.info(f"放弃伏笔: foreshadowing={foreshadowing_id}")
        return foreshadowing
    
    async def get_unresolved_foreshadowings(
        self,
        project_id: str,
        current_chapter_number: int,
    ) -> List[Foreshadowing]:
        """获取未回收的伏笔"""
        query = select(Foreshadowing).where(
            and_(
                Foreshadowing.project_id == project_id,
                Foreshadowing.status.in_(sorted(self._UNRESOLVED_STATUSES)),
            )
        ).order_by(Foreshadowing.chapter_number)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def create_reminder(
        self,
        project_id: str,
        foreshadowing_id: int,
        reminder_type: str,
        message: str,
        suggested_chapter_range: Optional[Dict[str, int]] = None,
    ) -> ForeshadowingReminder:
        """创建提醒"""
        reminder = ForeshadowingReminder(
            project_id=project_id,
            foreshadowing_id=foreshadowing_id,
            reminder_type=reminder_type,
            message=message,
            suggested_chapter_range=suggested_chapter_range,
        )
        self.session.add(reminder)
        await self.session.flush()
        logger.info(f"创建提醒: foreshadowing={foreshadowing_id}, type={reminder_type}")
        return reminder
    
    async def get_active_reminders(
        self,
        project_id: str,
        limit: int = 50,
    ) -> List[ForeshadowingReminder]:
        """获取活跃提醒"""
        query = select(ForeshadowingReminder).where(
            and_(
                ForeshadowingReminder.project_id == project_id,
                ForeshadowingReminder.status == "active",
            )
        ).order_by(ForeshadowingReminder.created_at.desc()).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def dismiss_reminder(
        self,
        reminder_id: int,
        reason: Optional[str] = None,
    ) -> ForeshadowingReminder:
        """忽略提醒"""
        reminder = await self.session.get(ForeshadowingReminder, reminder_id)
        if not reminder:
            raise ValueError(f"提醒不存在: {reminder_id}")
        
        reminder.status = "dismissed"
        reminder.dismissed_at = datetime.utcnow()
        reminder.dismissed_reason = reason
        
        await self.session.flush()
        logger.info(f"忽略提醒: reminder={reminder_id}")
        return reminder
    
    async def analyze_foreshadowings(
        self,
        project_id: str,
    ) -> ForeshadowingAnalysis:
        """分析伏笔统计"""
        # 获取所有伏笔
        query = select(Foreshadowing).where(Foreshadowing.project_id == project_id)
        result = await self.session.execute(query)
        foreshadowings = result.scalars().all()
        
        # 统计
        total = len(foreshadowings)
        resolved_count = sum(1 for f in foreshadowings if self._is_resolved(f.status))
        unresolved_count = sum(
            1
            for f in foreshadowings
            if self._is_unresolved(f.status)
        )
        abandoned_count = sum(1 for f in foreshadowings if f.status == "abandoned")
        
        # 计算平均回收距离
        resolution_distances = []
        for f in foreshadowings:
            if self._is_resolved(f.status) and f.resolved_chapter_number:
                distance = f.resolved_chapter_number - f.chapter_number
                resolution_distances.append(distance)
        
        avg_resolution_distance = (
            sum(resolution_distances) / len(resolution_distances)
            if resolution_distances
            else 0
        )
        
        # 计算未回收比例
        unresolved_ratio = unresolved_count / total if total > 0 else 0
        
        # 模式分析
        type_distribution = {}
        for f in foreshadowings:
            type_distribution[f.type] = type_distribution.get(f.type, 0) + 1
        
        # 质量评分
        quality_scores = []
        for f in foreshadowings:
            if f.resolutions:
                for resolution in f.resolutions:
                    if resolution.quality_score:
                        quality_scores.append(resolution.quality_score)
        
        overall_quality_score = (
            sum(quality_scores) / len(quality_scores)
            if quality_scores
            else None
        )
        
        # 生成建议
        recommendations = []
        if unresolved_ratio > 0.3:
            recommendations.append(f"有 {unresolved_count} 个伏笔未回收，建议在后续章节中处理")
        if avg_resolution_distance > 15:
            recommendations.append("伏笔回收距离较长，可能影响读者记忆，建议缩短回收周期")
        if overall_quality_score and overall_quality_score < 6:
            recommendations.append("伏笔回收质量评分较低，建议改进回收方式")
        
        # 更新或创建分析记录
        # 注意: ForeshadowingAnalysis 主键为自增 id, project_id 是 unique 普通列,
        # 不能用 session.get(按主键查), 必须按 project_id 条件查询, 否则恒返回 None
        # 导致第二次调用时 project_id unique 约束冲突。
        analysis_result = await self.session.execute(
            select(ForeshadowingAnalysis).where(
                ForeshadowingAnalysis.project_id == project_id
            )
        )
        analysis = analysis_result.scalar_one_or_none()
        if not analysis:
            analysis = ForeshadowingAnalysis(project_id=project_id)
            self.session.add(analysis)
        
        analysis.total_foreshadowings = total
        analysis.resolved_count = resolved_count
        analysis.unresolved_count = unresolved_count
        analysis.abandoned_count = abandoned_count
        analysis.avg_resolution_distance = avg_resolution_distance
        analysis.unresolved_ratio = unresolved_ratio
        analysis.pattern_analysis = type_distribution
        analysis.overall_quality_score = overall_quality_score
        analysis.recommendations = recommendations
        analysis.analyzed_at = datetime.utcnow()
        
        await self.session.flush()
        logger.info(f"分析伏笔: project={project_id}, total={total}, resolved={resolved_count}")
        return analysis
    
    async def check_and_create_reminders(
        self,
        project_id: str,
        current_chapter_number: int,
        total_chapters: int,
    ) -> List[ForeshadowingReminder]:
        """检查并创建提醒"""
        reminders = []
        
        # 获取未回收的伏笔
        unresolved = await self.get_unresolved_foreshadowings(project_id, current_chapter_number)
        
        for foreshadowing in unresolved:
            # 检查是否已有活跃提醒
            existing_query = select(ForeshadowingReminder).where(
                and_(
                    ForeshadowingReminder.foreshadowing_id == foreshadowing.id,
                    ForeshadowingReminder.status == "active",
                )
            )
            existing = await self.session.scalar(existing_query)
            if existing:
                continue
            
            # 长期未提及提醒
            distance = current_chapter_number - foreshadowing.chapter_number
            if distance > 10:
                reminder = await self.create_reminder(
                    project_id=project_id,
                    foreshadowing_id=foreshadowing.id,
                    reminder_type="long_time_no_mention",
                    message=f"第 {foreshadowing.chapter_number} 章埋下的伏笔已有 {distance} 章未提及，是否打算在后续章节中解答？",
                    suggested_chapter_range={
                        "start": current_chapter_number + 1,
                        "end": min(current_chapter_number + 5, total_chapters),
                    },
                )
                reminders.append(reminder)
            
            # 接近结局提醒
            if current_chapter_number > total_chapters * 0.8:
                reminder = await self.create_reminder(
                    project_id=project_id,
                    foreshadowing_id=foreshadowing.id,
                    reminder_type="unresolved",
                    message=f"小说即将结束，第 {foreshadowing.chapter_number} 章的伏笔仍未回收",
                )
                reminders.append(reminder)
        
        return reminders

    # 喂给提取 LLM 的未回收伏笔上限（每条一行，token 可控）
    EXTRACTION_UNRESOLVED_LIMIT = 30

    async def _select_unresolved_for_extraction(
        self,
        unresolved: List[Foreshadowing],
        chapter_number: int,
        chapter_content: str,
        llm_service,
        limit: int = EXTRACTION_UNRESOLVED_LIMIT,
    ) -> List[Foreshadowing]:
        """挑选喂给提取 LLM 的未回收伏笔（超过 limit 时按优先级取子集）。

        优先复用白金上下文的语义评分能力：与本章内容的语义相关性 +
        紧迫度/逾期启发式加权排序；embedding 不可用时降级为
        「最早 5 条保底 + 其余按埋设章节倒序（近期优先）」，
        避免长篇几十个活跃伏笔时中后期伏笔永远进不了提取列表。
        """
        if len(unresolved) <= limit:
            return list(unresolved)

        semantic_scores: Dict[int, float] = {}
        score_heuristic = None
        try:
            # 懒 import 避免与 platinum_writing_context 的循环依赖
            from .platinum_writing_context import (
                _score_foreshadowing,
                _semantic_foreshadowing_scores,
            )
            score_heuristic = _score_foreshadowing
            semantic_scores = await _semantic_foreshadowing_scores(
                llm_service, (chapter_content or "")[:2000], unresolved
            )
        except Exception:
            semantic_scores = {}

        if semantic_scores and score_heuristic is not None:
            def _priority(item: Foreshadowing) -> float:
                heuristic, _ = score_heuristic(item, chapter_number)
                # 语义相关性加成(0-10)，与紧迫度同量级（对齐白金上下文的权重约定）
                return round(semantic_scores.get(item.id, 0.0) * 10) + heuristic

            return sorted(unresolved, key=_priority, reverse=True)[:limit]

        # 降级：最早 5 条保底 + 其余按埋设章节倒序（近期优先）
        by_chapter = sorted(unresolved, key=lambda f: (f.chapter_number or 0, f.id or 0))
        earliest = by_chapter[:5]
        recent_first = list(reversed(by_chapter[5:]))
        return earliest + recent_first[: limit - len(earliest)]

    async def extract_foreshadowings_from_chapter(
        self,
        *,
        project_id: str,
        chapter_id: int,
        chapter_number: int,
        chapter_content: str,
        llm_service,
        prompt_service,
        user_id: int = 0,
    ) -> Dict[str, Any]:
        """从章节正文中自动提取伏笔操作（plant/develop/resolve）。

        使用LLM分析章节内容，自动：
        - plant类型：创建新伏笔（is_manual=False）
        - develop类型：记录统计
        - resolve类型：标记已回收
        """
        import json
        from ..utils.json_utils import remove_think_tags, unwrap_markdown_json, repair_json

        extraction_prompt = await prompt_service.get_prompt("foreshadowing_extraction")
        if not extraction_prompt:
            logger.warning("未配置 foreshadowing_extraction 提示词，跳过伏笔提取")
            return {"planted": 0, "developed": 0, "resolved": 0}

        # 获取未回收伏笔列表供LLM参考
        unresolved = await self.get_unresolved_foreshadowings(project_id, chapter_number)
        unresolved_text = ""
        if unresolved:
            selected = await self._select_unresolved_for_extraction(
                unresolved, chapter_number, chapter_content, llm_service
            )
            items = []
            for f in selected:
                items.append(f"ID={f.id} | {f.content} | 关键词：{','.join(f.keywords or [])}")
            unresolved_text = "\n".join(items)

        user_input = f"""[章节正文]
{chapter_content[:6000]}

[未回收伏笔列表]
{unresolved_text or "暂无已记录的伏笔"}
"""
        try:
            response = await llm_service.get_llm_response(
                system_prompt=extraction_prompt,
                conversation_history=[{"role": "user", "content": user_input}],
                temperature=0.2,
                user_id=user_id,
                timeout=60.0,
            )
            cleaned = remove_think_tags(response)
            if not cleaned:
                cleaned = response
            normalized = unwrap_markdown_json(cleaned)
            if not normalized:
                logger.warning("伏笔提取JSON为空")
                return {"planted": 0, "developed": 0, "resolved": 0}
            try:
                result = json.loads(normalized)
            except json.JSONDecodeError:
                repaired = repair_json(normalized)
                result = json.loads(repaired)

            actions = result.get("foreshadowing_actions", [])
            stats = {"planted": 0, "developed": 0, "resolved": 0}

            for action_item in actions:
                action_type = action_item.get("action", "")

                if action_type == "plant":
                    try:
                        await self.create_foreshadowing(
                            project_id=project_id,
                            chapter_id=chapter_id,
                            chapter_number=chapter_number,
                            content=action_item.get("content", ""),
                            foreshadowing_type=action_item.get("foreshadowing_type", "hint"),
                            keywords=action_item.get("keywords", []),
                            is_manual=False,
                            ai_confidence=0.7,
                        )
                        stats["planted"] += 1
                    except Exception as e:
                        logger.warning("自动创建伏笔失败: %s", e)

                elif action_type == "resolve":
                    matched_id = action_item.get("matched_existing_id")
                    if matched_id:
                        try:
                            await self.resolve_foreshadowing(
                                foreshadowing_id=int(matched_id),
                                resolved_chapter_id=chapter_id,
                                resolved_chapter_number=chapter_number,
                            )
                            stats["resolved"] += 1
                        except Exception as e:
                            logger.warning("自动回收伏笔失败: %s", e)

                elif action_type == "develop":
                    stats["developed"] += 1

            logger.info(
                "伏笔提取完成: planted=%d, developed=%d, resolved=%d",
                stats["planted"], stats["developed"], stats["resolved"],
            )
            return stats

        except Exception as e:
            logger.warning("伏笔提取失败: %s", e)
            return {"planted": 0, "developed": 0, "resolved": 0}
