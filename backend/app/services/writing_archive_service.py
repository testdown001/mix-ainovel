# AIMETA P=写作任务档案服务_管理档案生命周期|R=档案创建_查询_统计|NR=不含API路由|E=WritingArchiveService|X=internal|A=Service|D=sqlalchemy|S=db
"""写作任务档案服务 - 管理每个写作任务的完整过程记录（完整版奏折系统）"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.writing_archive import WritingArchive, EdictStatus

logger = logging.getLogger(__name__)


def generate_imperial_edict_id(project_id: str, chapter_number: int) -> str:
    """生成奏折唯一标识

    格式: ed_{日期}_{项目ID前6位}_{章节号}_{随机后缀}
    例如: ed_20240315_a1b2c3_5_f7e2
    """
    date_str = datetime.utcnow().strftime("%Y%m%d")
    project_prefix = project_id[:6] if len(project_id) >= 6 else project_id
    short_uuid = uuid.uuid4().hex[:4]
    return f"ed_{date_str}_{project_prefix}_{chapter_number}_{short_uuid}"


class WritingArchiveService:
    """写作任务档案服务（完整版奏折系统）

    负责记录和管理每次写作任务的完整过程，类似"奏折"系统：
    - 圣旨（用户输入）：记录用户的写作指令和附加说明
    - 时间线：记录任务开始和完成时间，计算耗时
    - 过程数据：记录各 Agent 阶段状态变化和关键日志
    - 产出：记录最终选定的版本和生成版本数量
    - 质量数据：记录审核评分和用户满意度
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_archive(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_command: Optional[str] = None,
        writing_notes: Optional[str] = None,
        chapter_title: Optional[str] = None,
        user_id: Optional[int] = None,
        preset: Optional[str] = None,
    ) -> WritingArchive:
        """创建新的写作任务档案（圣旨下达）

        Args:
            project_id: 项目ID
            chapter_number: 章节编号
            user_command: 用户写作指令（圣旨内容）
            writing_notes: 附加说明（御批）
            chapter_title: 章节标题
            user_id: 用户ID
            preset: 使用的预设配置

        Returns:
            创建的档案对象
        """
        imperial_edict_id = generate_imperial_edict_id(project_id, chapter_number)

        archive = WritingArchive(
            imperial_edict_id=imperial_edict_id,
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            user_command=user_command,
            additional_requirements=writing_notes,
            user_id=user_id,
            preset=preset,
            status=EdictStatus.PENDING,
            started_at=datetime.utcnow(),
            issued_at=datetime.utcnow(),
        )

        self.session.add(archive)
        await self.session.flush()

        logger.info(
            f"创建奏折: imperial_edict_id={imperial_edict_id}, "
            f"project={project_id}, chapter={chapter_number}"
        )

        return archive

    async def start_archive(
        self,
        archive_id: int,
        templates_used: Optional[List[str]] = None,
        skills_enabled: Optional[List[str]] = None,
    ) -> WritingArchive:
        """启动档案（开始处理圣旨）

        Args:
            archive_id: 档案ID
            templates_used: 使用的模板列表
            skills_enabled: 启用的技能列表

        Returns:
            更新后的档案对象
        """
        result = await self.session.execute(
            select(WritingArchive).where(WritingArchive.id == archive_id)
        )
        archive = result.scalars().first()
        if not archive:
            raise ValueError(f"档案不存在: {archive_id}")

        archive.mark_started()

        if templates_used:
            archive.templates_used = templates_used
        if skills_enabled:
            archive.skills_enabled = skills_enabled

        await self.session.flush()
        logger.info(f"启动奏折处理: imperial_edict_id={archive.imperial_edict_id}")

        return archive

    async def add_workflow_stage(
        self,
        archive_id: int,
        stage: str,
        agent: str,
        status: str,
        duration_ms: int,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
    ) -> WritingArchive:
        """添加工作流阶段记录

        Args:
            archive_id: 档案ID
            stage: 阶段名称（如"太子分拣"）
            agent: Agent 标识（如"taizi"）
            status: 状态（pending/completed/failed）
            duration_ms: 耗时（毫秒）
            input_data: 输入数据
            output_data: 输出数据

        Returns:
            更新后的档案对象
        """
        result = await self.session.execute(
            select(WritingArchive).where(WritingArchive.id == archive_id)
        )
        archive = result.scalars().first()
        if not archive:
            raise ValueError(f"档案不存在: {archive_id}")

        archive.add_workflow_stage(
            stage=stage,
            agent=agent,
            status=status,
            duration_ms=duration_ms,
            input_data=input_data,
            output_data=output_data,
        )

        await self.session.flush()
        return archive

    async def update_versions(
        self,
        archive_id: int,
        versions_data: List[Dict[str, Any]],
    ) -> WritingArchive:
        """更新版本数据

        Args:
            archive_id: 档案ID
            versions_data: 版本数据列表

        Returns:
            更新后的档案对象
        """
        result = await self.session.execute(
            select(WritingArchive).where(WritingArchive.id == archive_id)
        )
        archive = result.scalars().first()
        if not archive:
            raise ValueError(f"档案不存在: {archive_id}")

        archive.versions_generated = len(versions_data)
        archive.versions_data = versions_data

        await self.session.flush()
        return archive

    async def update_final_output(
        self,
        archive_id: int,
        selected_version: int,
        word_count: int,
        estimated_reading_time: Optional[str] = None,
    ) -> WritingArchive:
        """更新最终产出

        Args:
            archive_id: 档案ID
            selected_version: 选中的版本号
            word_count: 字数
            estimated_reading_time: 预计阅读时间

        Returns:
            更新后的档案对象
        """
        result = await self.session.execute(
            select(WritingArchive).where(WritingArchive.id == archive_id)
        )
        archive = result.scalars().first()
        if not archive:
            raise ValueError(f"档案不存在: {archive_id}")

        archive.final_output = {
            "selected_version": selected_version,
            "word_count": word_count,
            "estimated_reading_time": estimated_reading_time or f"{max(1, word_count // 300)}分钟",
        }

        await self.session.flush()
        return archive

    async def update_quality_metrics(
        self,
        archive_id: int,
        gatekeeper_score: Optional[float] = None,
        user_rating: Optional[int] = None,
        review_details: Optional[Dict[str, Any]] = None,
    ) -> WritingArchive:
        """更新质量指标

        Args:
            archive_id: 档案ID
            gatekeeper_score: 审核评分
            user_rating: 用户满意度（1-5分）
            review_details: 审核详情

        Returns:
            更新后的档案对象
        """
        result = await self.session.execute(
            select(WritingArchive).where(WritingArchive.id == archive_id)
        )
        archive = result.scalars().first()
        if not archive:
            raise ValueError(f"档案不存在: {archive_id}")

        metrics = archive.quality_metrics or {}

        if gatekeeper_score is not None:
            metrics["gatekeeper_score"] = gatekeeper_score
        if user_rating is not None:
            metrics["user_rating"] = user_rating
        if review_details:
            metrics["review_details"] = review_details

        archive.quality_metrics = metrics

        await self.session.flush()
        return archive

    async def complete_archive(
        self,
        archive_id: int,
        final_version_id: Optional[int] = None,
        version_count: Optional[int] = None,
        gatekeeper_score: Optional[float] = None,
        user_rating: Optional[int] = None,
    ) -> WritingArchive:
        """完成档案记录（奏章批复）

        Args:
            archive_id: 档案ID
            final_version_id: 最终选定的版本ID
            version_count: 生成版本数量
            gatekeeper_score: 审核评分（质量审核评分）
            user_rating: 用户满意度（1-5分）

        Returns:
            更新后的档案对象
        """
        result = await self.session.execute(
            select(WritingArchive).where(WritingArchive.id == archive_id)
        )
        archive = result.scalars().first()
        if not archive:
            raise ValueError(f"档案不存在: {archive_id}")

        archive.mark_completed()

        if final_version_id is not None:
            archive.final_output = archive.final_output or {}
            archive.final_output["selected_version"] = final_version_id

        if version_count is not None:
            archive.versions_generated = version_count
        if gatekeeper_score is not None:
            if archive.quality_metrics is None:
                archive.quality_metrics = {}
            archive.quality_metrics["gatekeeper_score"] = gatekeeper_score
        if user_rating is not None:
            if archive.quality_metrics is None:
                archive.quality_metrics = {}
            archive.quality_metrics["user_rating"] = user_rating

        await self.session.flush()

        logger.info(
            f"完成奏折: imperial_edict_id={archive.imperial_edict_id}, "
            f"duration={archive.duration_ms}ms, score={gatekeeper_score}"
        )

        return archive

    async def fail_archive(
        self,
        archive_id: int,
        error_message: str,
    ) -> WritingArchive:
        """标记档案失败

        Args:
            archive_id: 档案ID
            error_message: 错误信息

        Returns:
            更新后的档案对象
        """
        result = await self.session.execute(
            select(WritingArchive).where(WritingArchive.id == archive_id)
        )
        archive = result.scalars().first()
        if not archive:
            raise ValueError(f"档案不存在: {archive_id}")

        archive.mark_failed(error_message)

        await self.session.flush()

        logger.error(
            f"奏折失败: imperial_edict_id={archive.imperial_edict_id}, error={error_message}"
        )

        return archive

    async def get_archive(self, archive_id: int) -> Optional[WritingArchive]:
        """获取单个档案

        Args:
            archive_id: 档案ID

        Returns:
            档案对象，如果不存在则返回 None
        """
        result = await self.session.execute(
            select(WritingArchive).where(WritingArchive.id == archive_id)
        )
        return result.scalars().first()

    async def get_archive_by_edict_id(self, imperial_edict_id: str) -> Optional[WritingArchive]:
        """通过奏折ID获取档案

        Args:
            imperial_edict_id: 奏折唯一标识

        Returns:
            档案对象，如果不存在则返回 None
        """
        result = await self.session.execute(
            select(WritingArchive).where(WritingArchive.imperial_edict_id == imperial_edict_id)
        )
        return result.scalars().first()

    async def get_archives_by_project(
        self,
        project_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WritingArchive]:
        """获取项目的所有档案

        Args:
            project_id: 项目ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            档案列表（按创建时间倒序）
        """
        result = await self.session.execute(
            select(WritingArchive)
            .where(WritingArchive.project_id == project_id)
            .order_by(desc(WritingArchive.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_archives_by_chapter(
        self,
        project_id: str,
        chapter_number: int,
    ) -> List[WritingArchive]:
        """获取指定章节的所有档案

        Args:
            project_id: 项目ID
            chapter_number: 章节编号

        Returns:
            档案列表（按创建时间倒序）
        """
        result = await self.session.execute(
            select(WritingArchive)
            .where(WritingArchive.project_id == project_id)
            .where(WritingArchive.chapter_number == chapter_number)
            .order_by(desc(WritingArchive.created_at))
        )
        return list(result.scalars().all())

    async def get_latest_archive(
        self,
        project_id: str,
        chapter_number: int,
    ) -> Optional[WritingArchive]:
        """获取指定章节的最新档案

        Args:
            project_id: 项目ID
            chapter_number: 章节编号

        Returns:
            最新的档案对象，如果不存在则返回 None
        """
        result = await self.session.execute(
            select(WritingArchive)
            .where(WritingArchive.project_id == project_id)
            .where(WritingArchive.chapter_number == chapter_number)
            .order_by(desc(WritingArchive.created_at))
            .limit(1)
        )
        return result.scalars().first()

    async def update_user_rating(
        self,
        archive_id: int,
        user_rating: int,
    ) -> WritingArchive:
        """更新用户满意度评分

        Args:
            archive_id: 档案ID
            user_rating: 用户满意度（1-5分）

        Returns:
            更新后的档案对象
        """
        result = await self.session.execute(
            select(WritingArchive).where(WritingArchive.id == archive_id)
        )
        archive = result.scalars().first()
        if not archive:
            raise ValueError(f"档案不存在: {archive_id}")

        if archive.quality_metrics is None:
            archive.quality_metrics = {}
        archive.quality_metrics["user_rating"] = user_rating

        await self.session.flush()
        return archive

    async def get_project_stats(
        self,
        project_id: str,
    ) -> Dict[str, Any]:
        """获取项目的写作统计信息

        Args:
            project_id: 项目ID

        Returns:
            统计信息字典
        """
        # 总任务数
        total_result = await self.session.execute(
            select(func.count(WritingArchive.id)).where(
                WritingArchive.project_id == project_id
            )
        )
        total_count = total_result.scalar() or 0

        # 已完成任务数
        completed_result = await self.session.execute(
            select(func.count(WritingArchive.id)).where(
                WritingArchive.project_id == project_id,
                WritingArchive.status == EdictStatus.COMPLETED,
            )
        )
        completed_count = completed_result.scalar() or 0

        # 失败任务数
        failed_result = await self.session.execute(
            select(func.count(WritingArchive.id)).where(
                WritingArchive.project_id == project_id,
                WritingArchive.status == EdictStatus.FAILED,
            )
        )
        failed_count = failed_result.scalar() or 0

        # 平均评分
        avg_score_result = await self.session.execute(
            select(func.avg(
                WritingArchive.quality_metrics["gatekeeper_score"]
            )).where(
                WritingArchive.project_id == project_id,
            )
        )
        avg_score = avg_score_result.scalar()

        # 平均耗时（毫秒）
        avg_duration_result = await self.session.execute(
            select(func.avg(WritingArchive.duration_ms)).where(
                WritingArchive.project_id == project_id,
                WritingArchive.duration_ms.isnot(None),
            )
        )
        avg_duration = avg_duration_result.scalar()

        # 总生成版本数
        total_versions_result = await self.session.execute(
            select(func.sum(WritingArchive.versions_generated)).where(
                WritingArchive.project_id == project_id,
                WritingArchive.versions_generated.isnot(None),
            )
        )
        total_versions = total_versions_result.scalar() or 0

        return {
            "total_tasks": total_count,
            "completed_tasks": completed_count,
            "failed_tasks": failed_count,
            "avg_gatekeeper_score": round(float(avg_score), 2) if avg_score else None,
            "avg_duration_ms": round(float(avg_duration), 0) if avg_duration else None,
            "total_versions_generated": total_versions,
        }

    async def delete_archive(self, archive_id: int) -> bool:
        """删除档案

        Args:
            archive_id: 档案ID

        Returns:
            是否删除成功
        """
        result = await self.session.execute(
            select(WritingArchive).where(WritingArchive.id == archive_id)
        )
        archive = result.scalars().first()
        if not archive:
            return False

        await self.session.delete(archive)
        await self.session.flush()
        logger.info(f"删除奏折: archive_id={archive_id}")
        return True


# 全局服务实例
writing_archive_service = WritingArchiveService
