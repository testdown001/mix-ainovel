# AIMETA P=基准场景夹具|R=场景schema_播种_冻结_清理|NR=不做生成与评分|E=seed_scenario_freeze_project_cleanup_run|X=internal|A=数据夹具|D=novel_service_models|S=none
"""基准场景夹具：加载/播种/冻结/清理。

- BenchScenario：可 JSON 序列化的场景 schema（蓝图 + 大纲 + 先行章 + 目标章）。
- seed_scenario：把场景播种为一个独立的 bench 项目副本（挂在专用 bench 用户下）。
  每个「场景 × 配置」组合必须独立播种一份 —— 生成会写记忆/伏笔/实体等状态，
  配置之间绝不共享项目。
- seed_scenario_vectors：先行章向量入库（best-effort，失败降级返回 False）。
- freeze_project：从既有真实项目冻结出场景夹具（获得真实基准的主路径）。
- cleanup_run / cleanup_all_bench：按 run_tag / 全量删除 bench 项目及其
  项目域数据（含 best-effort 向量清理）。
"""
from __future__ import annotations

import json
import logging
import secrets
import uuid
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.exc import OperationalError, SAWarning
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.security import hash_password
from ...db.base import Base
from ...models.novel import (
    BlueprintCharacter,
    BlueprintRelationship,
    Chapter,
    ChapterOutline,
    ChapterVersion,
    NovelBlueprint,
    NovelProject,
)
from ...models.user import User
from ...schemas.novel import Blueprint, ChapterGenerationStatus
from ..chapter_ingest_service import ChapterIngestionService
from ..llm_service import LLMService
from ..novel_service import NovelService
from ..vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)


class BenchSeedSchemaError(RuntimeError):
    """播种时撞上开发库 schema 落后于 ORM（Unknown column）——环境问题，
    每个 cell 都会失败，应中止整个跑批并提示先启动后端让 init_db() 补列。"""

# 专用 bench 用户：所有 bench 项目都挂在它名下，便于识别与清理
BENCH_USERNAME = "bench@local"

# 夹具 JSON 目录：backend/bench_fixtures/
FIXTURES_DIR = Path(__file__).resolve().parents[3] / "bench_fixtures"

# 蓝图字符列（BlueprintCharacter 的结构化列；其余键进 extra，冻结时原样合回）
_CHARACTER_FIELDS = (
    "name",
    "identity",
    "personality",
    "goals",
    "abilities",
    "relationship_to_protagonist",
)


# ---------------------------------------------------------------------------
# 场景 schema
# ---------------------------------------------------------------------------
@dataclass
class BenchOutline:
    """单条章节大纲。"""

    chapter_number: int
    title: str
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_number": self.chapter_number,
            "title": self.title,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchOutline":
        return cls(
            chapter_number=int(data["chapter_number"]),
            title=str(data.get("title") or ""),
            summary=str(data.get("summary") or ""),
        )


@dataclass
class BenchPriorChapter:
    """先行章：已完成章节的正文与摘要，作为生成目标章的既定前文。"""

    chapter_number: int
    title: str
    content: str
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_number": self.chapter_number,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchPriorChapter":
        return cls(
            chapter_number=int(data["chapter_number"]),
            title=str(data.get("title") or ""),
            content=str(data.get("content") or ""),
            summary=str(data.get("summary") or ""),
        )


@dataclass
class BenchScenario:
    """一个基准场景：固定蓝图 + 大纲 + 先行章，生成 target_chapter 供打分。"""

    scenario_id: str
    description: str
    blueprint: Dict[str, Any]  # 兼容 schemas.novel.Blueprint（含 volumes），不含 chapter_outline
    outlines: List[BenchOutline]
    prior_chapters: List[BenchPriorChapter]
    target_chapter: int
    must_include: List[str] = field(default_factory=list)  # 剧情必含词，供机械评分

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "description": self.description,
            "blueprint": self.blueprint,
            "outlines": [item.to_dict() for item in self.outlines],
            "prior_chapters": [item.to_dict() for item in self.prior_chapters],
            "target_chapter": self.target_chapter,
            "must_include": list(self.must_include),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchScenario":
        return cls(
            scenario_id=str(data["scenario_id"]),
            description=str(data.get("description") or ""),
            blueprint=dict(data.get("blueprint") or {}),
            outlines=[BenchOutline.from_dict(item) for item in (data.get("outlines") or [])],
            prior_chapters=[
                BenchPriorChapter.from_dict(item) for item in (data.get("prior_chapters") or [])
            ],
            target_chapter=int(data["target_chapter"]),
            must_include=[str(term) for term in (data.get("must_include") or [])],
        )


def load_scenario(path: Path | str) -> BenchScenario:
    """从 JSON 文件加载场景夹具。"""
    raw = Path(path).read_text(encoding="utf-8")
    return BenchScenario.from_dict(json.loads(raw))


def save_scenario(scenario: BenchScenario, path: Path | str) -> None:
    """把场景夹具写为 JSON 文件（冻结产物落盘用）。"""
    Path(path).write_text(
        json.dumps(scenario.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# bench 用户
# ---------------------------------------------------------------------------
async def get_or_create_bench_user(session: AsyncSession) -> User:
    """get-or-create 专用 bench 用户（随机密码、不可登录后台，仅作项目属主）。"""
    result = await session.execute(select(User).where(User.username == BENCH_USERNAME))
    user = result.scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        username=BENCH_USERNAME,
        hashed_password=hash_password(secrets.token_urlsafe(24)),
        is_active=True,
        is_admin=False,
    )
    session.add(user)
    await session.flush()
    logger.info("已创建 bench 专用用户 %s (id=%s)", BENCH_USERNAME, user.id)
    return user


def _project_title(scenario: BenchScenario, run_tag: str) -> str:
    return f"[{run_tag}] {scenario.scenario_id}"


# ---------------------------------------------------------------------------
# 播种
# ---------------------------------------------------------------------------
async def seed_scenario(session: AsyncSession, scenario: BenchScenario, run_tag: str) -> str:
    """把场景播种为一个全新的 bench 项目副本，返回 project_id。

    - 蓝图经 NovelService.replace_blueprint 落库（同生产写入路径：角色/关系/大纲/
      伏笔推断/实体/势力同步一致）；scenario.outlines 作为蓝图 chapter_outline 传入。
    - 先行章直接建 Chapter + ChapterVersion，并按生产完成态口径写
      selected_version_id + status=successful + real_summary + word_count
      （novel_service 统计 completed 的条件是 selected_version_id 非空）。
    - 撞上 Unknown column（开发库 schema 落后于 ORM）抛 BenchSeedSchemaError，
      调用方应中止跑批（每个 cell 都会同样失败）。
    """
    try:
        return await _seed_scenario_inner(session, scenario, run_tag)
    except OperationalError as exc:
        if "unknown column" in str(exc).lower():
            raise BenchSeedSchemaError(
                f"播种失败（开发库 schema 落后于 ORM）: {exc}"
            ) from exc
        raise


async def _seed_scenario_inner(
    session: AsyncSession, scenario: BenchScenario, run_tag: str
) -> str:
    user = await get_or_create_bench_user(session)

    project_id = str(uuid.uuid4())
    project = NovelProject(
        id=project_id,
        user_id=user.id,
        title=_project_title(scenario, run_tag),
        initial_prompt=scenario.description,
        status="writing",
    )
    session.add(project)
    await session.flush()

    blueprint_payload = dict(scenario.blueprint)
    blueprint_payload.setdefault("title", scenario.scenario_id)
    # outlines 的单一真相源在 scenario.outlines（蓝图内如带 chapter_outline 一律覆盖）
    blueprint_payload["chapter_outline"] = [item.to_dict() for item in scenario.outlines]
    blueprint = Blueprint.model_validate(blueprint_payload)
    await NovelService(session).replace_blueprint(project_id, blueprint)

    for prior in scenario.prior_chapters:
        # replace_blueprint 的伏笔同步可能已为部分章号预建了占位 Chapter，先查后建
        result = await session.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == prior.chapter_number,
            )
        )
        chapter = result.scalars().first()
        if chapter is None:
            chapter = Chapter(project_id=project_id, chapter_number=prior.chapter_number)
            session.add(chapter)
            await session.flush()
        version = ChapterVersion(
            chapter_id=chapter.id,
            content=prior.content,
            version_label="bench",
            provider="bench",
        )
        session.add(version)
        await session.flush()
        chapter.selected_version_id = version.id
        chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
        chapter.real_summary = prior.summary
        chapter.word_count = len(prior.content or "")

    await session.commit()
    logger.info(
        "已播种 bench 项目 %s（scenario=%s, run_tag=%s, 先行章=%d）",
        project_id, scenario.scenario_id, run_tag, len(scenario.prior_chapters),
    )
    return project_id


async def seed_scenario_vectors(
    session: AsyncSession, scenario: BenchScenario, project_id: str
) -> bool:
    """把先行章正文/摘要向量入库（best-effort），供目标章生成时 RAG 检索。

    走生产同款 ChapterIngestionService.ingest_chapter（切分→embedding→Qdrant）。
    Qdrant 未配置 / embedding 通道不可用 / 任一环节异常时返回 False——播种照常
    成立，但报告会标注「本 run 向量层不可用，RAG 相关配置差异无效」。
    """
    if not scenario.prior_chapters:
        return True
    if not settings.vector_store_enabled:
        logger.warning("向量库未配置（QDRANT_HOST 为空），跳过先行章向量播种: %s", project_id)
        return False
    try:
        llm_service = LLMService(session)
        # 探针：embedding 出口失败静默返回 []（不抛异常），先探测一次判定可用性
        probe = await llm_service.get_embedding(scenario.prior_chapters[0].content[:200])
        if not probe:
            logger.warning("embedding 通道不可用，跳过先行章向量播种: %s", project_id)
            return False
        ingestion = ChapterIngestionService(llm_service=llm_service)
        for prior in scenario.prior_chapters:
            await ingestion.ingest_chapter(
                project_id=project_id,
                chapter_number=prior.chapter_number,
                title=prior.title,
                content=prior.content,
                summary=prior.summary or None,
            )
    except Exception as exc:  # noqa: BLE001 - 向量播种绝不阻断跑批
        logger.warning("先行章向量播种失败（降级继续）: project=%s error=%s", project_id, exc)
        return False
    logger.info(
        "先行章向量播种完成: project=%s chapters=%d", project_id, len(scenario.prior_chapters)
    )
    return True


# ---------------------------------------------------------------------------
# 冻结
# ---------------------------------------------------------------------------
async def freeze_project(
    session: AsyncSession,
    project_id: str,
    upto_chapter: int,
    target_chapter: int,
    *,
    scenario_id: Optional[str] = None,
    description: Optional[str] = None,
    must_include: Optional[List[str]] = None,
) -> BenchScenario:
    """从既有真实项目冻结场景夹具（获得真实基准的主路径）。

    读蓝图/全部大纲/前 upto_chapter 个已完成章（selected_version_id 非空）的正文与摘要。
    must_include 无法从项目推断，由调用方指定（默认空，冻结后人工补）。
    """
    project = await session.get(NovelProject, project_id)
    if project is None:
        raise ValueError(f"项目不存在: {project_id}")
    record = await session.get(NovelBlueprint, project_id)
    if record is None:
        raise ValueError(f"项目缺少蓝图，无法冻结: {project_id}")

    characters_result = await session.execute(
        select(BlueprintCharacter)
        .where(BlueprintCharacter.project_id == project_id)
        .order_by(BlueprintCharacter.position)
    )
    characters: List[Dict[str, Any]] = []
    for row in characters_result.scalars().all():
        data: Dict[str, Any] = {}
        for key in _CHARACTER_FIELDS:
            value = getattr(row, key)
            if value is not None:
                data[key] = value
        data.update(row.extra or {})
        characters.append(data)

    relationships_result = await session.execute(
        select(BlueprintRelationship)
        .where(BlueprintRelationship.project_id == project_id)
        .order_by(BlueprintRelationship.position)
    )
    relationships = [
        {
            "character_from": row.character_from,
            "character_to": row.character_to,
            "description": row.description or "",
        }
        for row in relationships_result.scalars().all()
    ]

    blueprint: Dict[str, Any] = {
        "title": record.title or project.title,
        "target_audience": record.target_audience or "",
        "genre": record.genre or "",
        "style": record.style or "",
        "tone": record.tone or "",
        "one_sentence_summary": record.one_sentence_summary or "",
        "full_synopsis": record.full_synopsis or "",
        "world_setting": record.world_setting or {},
        "volumes": record.volumes or [],
        "characters": characters,
        "relationships": relationships,
    }
    if record.golden_finger is not None:
        blueprint["golden_finger"] = record.golden_finger

    outlines_result = await session.execute(
        select(ChapterOutline)
        .where(ChapterOutline.project_id == project_id)
        .order_by(ChapterOutline.chapter_number)
    )
    outlines = [
        BenchOutline(chapter_number=row.chapter_number, title=row.title, summary=row.summary or "")
        for row in outlines_result.scalars().all()
    ]
    outline_titles = {item.chapter_number: item.title for item in outlines}

    chapters_result = await session.execute(
        select(Chapter)
        .where(
            Chapter.project_id == project_id,
            Chapter.chapter_number <= upto_chapter,
            Chapter.selected_version_id.is_not(None),
        )
        .order_by(Chapter.chapter_number)
    )
    prior_chapters: List[BenchPriorChapter] = []
    for chapter in chapters_result.scalars().all():
        version = await session.get(ChapterVersion, chapter.selected_version_id)
        if version is None or not (version.content or "").strip():
            continue
        prior_chapters.append(
            BenchPriorChapter(
                chapter_number=chapter.chapter_number,
                title=outline_titles.get(chapter.chapter_number, f"第{chapter.chapter_number}章"),
                content=version.content,
                summary=chapter.real_summary or "",
            )
        )

    return BenchScenario(
        scenario_id=scenario_id or f"frozen-{project_id[:8]}-ch{target_chapter}",
        description=description or f"冻结自项目 {project_id}（前 {upto_chapter} 章，目标第 {target_chapter} 章）",
        blueprint=blueprint,
        outlines=outlines,
        prior_chapters=prior_chapters,
        target_chapter=target_chapter,
        must_include=list(must_include or []),
    )


# ---------------------------------------------------------------------------
# 清理
# ---------------------------------------------------------------------------
async def cleanup_run(session: AsyncSession, run_tag: str) -> int:
    """删除该 run_tag 批次的全部 bench 项目及其项目域数据，返回删除的项目数。"""
    user = await _get_bench_user(session)
    if user is None:
        return 0
    ids_result = await session.execute(
        select(NovelProject.id).where(
            NovelProject.user_id == user.id,
            NovelProject.title.like(f"[{run_tag}] %"),
        )
    )
    return await _cleanup_projects(session, [row[0] for row in ids_result])


async def cleanup_all_bench(session: AsyncSession) -> int:
    """删除 bench 用户名下**全部**项目（不看 run_tag），返回删除的项目数。

    供 `run_bench.py cleanup --all-bench` 使用——多次跑批遗留的孤儿项目一把清。
    """
    user = await _get_bench_user(session)
    if user is None:
        return 0
    ids_result = await session.execute(
        select(NovelProject.id).where(NovelProject.user_id == user.id)
    )
    return await _cleanup_projects(session, [row[0] for row in ids_result])


async def _get_bench_user(session: AsyncSession) -> Optional[User]:
    result = await session.execute(select(User).where(User.username == BENCH_USERNAME))
    return result.scalar_one_or_none()


async def _delete_project_vectors(session: AsyncSession, project_ids: List[str]) -> None:
    """best-effort 删除各项目在 Qdrant 里的章节向量（含播种与生成写入的）。

    VectorStoreService 无按 project 整删接口（实证），用 delete_by_chapters
    按项目现存章号删；失败仅 warning，不阻断行级清理。"""
    if not settings.vector_store_enabled:
        return
    try:
        rows = await session.execute(
            select(Chapter.project_id, Chapter.chapter_number).where(
                Chapter.project_id.in_(project_ids)
            )
        )
        chapters_by_project: Dict[str, List[int]] = {}
        for pid, number in rows:
            chapters_by_project.setdefault(pid, []).append(number)
        vector_store = VectorStoreService()
        for pid, numbers in chapters_by_project.items():
            await vector_store.delete_by_chapters(pid, numbers)
    except Exception as exc:  # noqa: BLE001 - 向量清理绝不阻断行级清理
        logger.warning("bench 向量清理失败（降级继续）: %s", exc)


async def _cleanup_projects(session: AsyncSession, project_ids: List[str]) -> int:
    """删除给定 bench 项目及其项目域数据（行级 + best-effort 向量）。

    级联实证：novel_projects 的下游外键均为 ondelete=CASCADE，但
    ① chapter_reviews / writing_archives 的 project_id 没有外键约束，数据库级联管不到；
    ② SQLite 测试引擎不开 FK pragma，数据库级联根本不会执行；
    ③ ORM 级联只覆盖 NovelProject 上映射的 6 个 relationship。
    故这里不依赖任何级联，按反向拓扑序逐表显式删除：
    - 含 project_id 列的表直接按 project_id 删（天然覆盖无外键的两张表）；
    - 不含 project_id 的孙表（chapter_versions/entity_alias/power_levels/
      faction_relationship_history/foreshadowing_* 等）经由指向含 project_id
      父表的外键做子查询删除（父表行此时尚未删除，反向拓扑序保证）。
    """
    if not project_ids:
        return 0

    # 向量先删（章号还查得到）；Qdrant 挂了只 warning
    await _delete_project_vectors(session, project_ids)

    # 先解除 chapters -> chapter_versions 的选中引用，避免删除版本行时的悬挂外键
    await session.execute(
        update(Chapter)
        .where(Chapter.project_id.in_(project_ids))
        .values(selected_version_id=None)
    )

    # chapters ↔ chapter_versions 存在环形外键（selected_version_id / chapter_id），
    # 拓扑序无法保证先后，孙表子查询可能在父行删除后落空 —— 先物化 chapter_ids
    # 显式删掉章节子表，再走通用循环（通用循环里对它们跳过）。
    chapter_ids = [
        row[0]
        for row in await session.execute(
            select(Chapter.id).where(Chapter.project_id.in_(project_ids))
        )
    ]
    handled_tables = set()
    if chapter_ids:
        from ...models.novel import ChapterEvaluation  # 局部导入避免顶部堆积

        await session.execute(
            delete(ChapterEvaluation).where(ChapterEvaluation.chapter_id.in_(chapter_ids))
        )
        await session.execute(
            delete(ChapterVersion).where(ChapterVersion.chapter_id.in_(chapter_ids))
        )
        handled_tables = {ChapterEvaluation.__tablename__, ChapterVersion.__tablename__}

    try:
        with warnings.catch_warnings():
            # chapters ↔ chapter_versions 的环已在上方显式处理，
            # 压掉 sorted_tables 对该环的 SAWarning
            warnings.simplefilter("ignore", SAWarning)
            ordered_tables = list(reversed(Base.metadata.sorted_tables))
    except Exception:  # pragma: no cover - 环形外键导致拓扑排序失败时的兜底
        ordered_tables = list(Base.metadata.tables.values())

    for table in ordered_tables:
        if table.name == NovelProject.__tablename__ or table.name in handled_tables:
            continue
        if "project_id" in table.c:
            await session.execute(table.delete().where(table.c.project_id.in_(project_ids)))
            continue
        for fk in table.foreign_keys:
            parent = fk.column.table
            if parent.name == table.name or "project_id" not in parent.c:
                continue
            subquery = select(fk.column).where(parent.c.project_id.in_(project_ids))
            await session.execute(table.delete().where(fk.parent.in_(subquery)))

    await session.execute(delete(NovelProject).where(NovelProject.id.in_(project_ids)))
    await session.commit()
    session.expire_all()
    logger.info("bench 清理: 已删除 %d 个 bench 项目", len(project_ids))
    return len(project_ids)
