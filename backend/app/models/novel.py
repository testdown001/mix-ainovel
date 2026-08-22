# AIMETA P=小说模型_项目和章节定义|R=小说表_章节表_版本表|NR=不含业务逻辑|E=Novel_Chapter_ChapterVersion|X=internal|A=ORM模型|D=sqlalchemy|S=none|RD=./README.ai
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

# 自定义列类型：MySQL 专用
BIGINT_PK_TYPE = BigInteger().with_variant(Integer, "sqlite")  # SQLite 需 INTEGER 才能自增
LONG_TEXT_TYPE = Text().with_variant(LONGTEXT, "mysql")


class _MetadataAccessor:
    """Descriptor 用于将 `metadata` 访问重定向到 `metadata_`，且保持 Base.metadata 可用。"""

    def __get__(self, instance, owner):
        if instance is None:
            return Base.metadata
        return instance.metadata_

    def __set__(self, instance, value):
        instance.metadata_ = value


class NovelProject(Base):
    """小说项目主表，仅存放轻量级元数据。"""

    __tablename__ = "novel_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    initial_prompt: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    # 公开分享令牌：NULL = 未分享；非空 = 凭 /share/{token} 免登录可读已完稿章节。
    # 关闭分享置 NULL、再开启生成新 token——旧链接即作废，无需单独的「重新生成」入口。
    share_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship("User", back_populates="novel_projects")
    blueprint: Mapped[Optional["NovelBlueprint"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    conversations: Mapped[list["NovelConversation"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="NovelConversation.seq"
    )
    characters: Mapped[list["BlueprintCharacter"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="BlueprintCharacter.position"
    )
    relationships_: Mapped[list["BlueprintRelationship"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="BlueprintRelationship.position"
    )
    outlines: Mapped[list["ChapterOutline"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by=lambda: (ChapterOutline.sort_key, ChapterOutline.chapter_number),
    )
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by=lambda: (Chapter.sort_key, Chapter.chapter_number),
    )
    # M1：分卷从 blueprint JSON 演进为一等实体；JSON 仅保留为旧生成链路的兼容投影。
    volumes: Mapped[list["Volume"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Volume.position"
    )
    reference_novel_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, default=list)
    fusion_dna: Mapped[Optional[dict]] = mapped_column(JSON)
    # 故事立项书（结构化前提产物）：{"dossier": {...ConceptDossier}, "stress_report": {...}, ...}
    # 灵感对话 is_complete 后蒸馏生成；蓝图 Stage A 以它为最高优先级设定锚点。NULL = 未蒸馏。
    concept_dossier: Mapped[Optional[dict]] = mapped_column(JSON)
    # 创作禁区（用户在灵感模式划定的红线文本）：持久化后贯穿概念对话/蓝图生成/宪法播种。
    exclusions: Mapped[Optional[str]] = mapped_column(Text)
    # 任一章走过模型起草/选区改写后为 True；纯手打且从未跑模型保持 False。
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    # AI 封面元数据；图片二进制保存在共享 storage 卷，避免 JSON/base64 膨胀数据库。
    cover_image: Mapped[Optional[dict]] = mapped_column(JSON, default=None)


class NovelConversation(Base):
    """对话记录表，存储概念阶段的连续对话。"""

    __tablename__ = "novel_conversations"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(LONG_TEXT_TYPE, nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON)
    metadata = _MetadataAccessor()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[NovelProject] = relationship(back_populates="conversations")


class NovelBlueprint(Base):
    """蓝图主体信息（标题、风格等）。"""

    __tablename__ = "novel_blueprints"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), primary_key=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255))
    target_audience: Mapped[Optional[str]] = mapped_column(String(255))
    genre: Mapped[Optional[str]] = mapped_column(String(128))
    style: Mapped[Optional[str]] = mapped_column(String(128))
    tone: Mapped[Optional[str]] = mapped_column(String(128))
    one_sentence_summary: Mapped[Optional[str]] = mapped_column(Text)
    full_synopsis: Mapped[Optional[str]] = mapped_column(LONG_TEXT_TYPE)
    world_setting: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    golden_finger: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    volumes: Mapped[Optional[list]] = mapped_column(JSON, default=None)
    # 蓝图审稿门产物（商业量表评分+问题清单）：NULL = 未审（旧蓝图/审稿降级跳过）。
    review_report: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project: Mapped[NovelProject] = relationship(back_populates="blueprint")


class Volume(Base):
    """作品的一等分卷实体（M1）。

    ``NovelBlueprint.volumes`` 在过渡期仍保留为面向旧生成/复盘代码的 JSON 投影；
    该表才是编辑、排序、导出边界和章节归属的长期事实来源。
    """

    __tablename__ = "volumes"
    __table_args__ = (
        UniqueConstraint("project_id", "position", name="uq_volumes_project_position"),
        Index("ix_volumes_project_range", "project_id", "start_chapter", "end_chapter"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # position 从 1 开始，是对外稳定卷号；不要依赖数据库自增 id 表达显示顺序。
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    start_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    end_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    arc_goal: Mapped[Optional[str]] = mapped_column(Text)
    climax_hint: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned", server_default="planned")
    retrospective: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    replan: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    # 保存旧 JSON 中的未知扩展字段，防止 M1 迁移吞掉既有功能数据。
    extra: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project: Mapped[NovelProject] = relationship(back_populates="volumes")
    outlines: Mapped[list["ChapterOutline"]] = relationship(back_populates="volume")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="volume")


class BlueprintCharacter(Base):
    """蓝图角色信息。"""

    __tablename__ = "blueprint_characters"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    identity: Mapped[Optional[str]] = mapped_column(String(255))
    personality: Mapped[Optional[str]] = mapped_column(Text)
    goals: Mapped[Optional[str]] = mapped_column(Text)
    abilities: Mapped[Optional[str]] = mapped_column(Text)
    relationship_to_protagonist: Mapped[Optional[str]] = mapped_column(Text)
    extra: Mapped[Optional[dict]] = mapped_column(JSON)
    position: Mapped[int] = mapped_column(Integer, default=0)

    # 力量体系关联 (基于 MuMuAINovel 的职业等级约束)
    power_system_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("power_systems.id", ondelete="SET NULL"), nullable=True, comment="角色绑定的体系"
    )
    current_power_level_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("power_levels.id", ondelete="SET NULL"), nullable=True, comment="角色当前所处境界/等级"
    )

    project: Mapped[NovelProject] = relationship(back_populates="characters")


class BlueprintRelationship(Base):
    """角色之间的关系。"""

    __tablename__ = "blueprint_relationships"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    character_from: Mapped[str] = mapped_column(String(255), nullable=False)
    character_to: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped[NovelProject] = relationship(back_populates="relationships_")


class ChapterOutline(Base):
    """章节纲要，支持 metadata 存储导演脚本/节拍状态等信息。"""

    __tablename__ = "chapter_outlines"
    __table_args__ = (
        Index("ix_chapter_outlines_project_chapter", "project_id", "chapter_number"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    volume_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("volumes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # M1：排序与显示章号解耦。旧数据回填为 chapter_number * 1000，便于未来插章。
    sort_key: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON)  # 存储导演脚本/节拍状态
    metadata = _MetadataAccessor()

    project: Mapped[NovelProject] = relationship(back_populates="outlines")
    volume: Mapped[Optional[Volume]] = relationship(back_populates="outlines")


class Chapter(Base):
    """章节正文状态，指向选中的版本。"""

    __tablename__ = "chapters"
    __table_args__ = (
        Index("ix_chapters_project_chapter", "project_id", "chapter_number"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    volume_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("volumes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_key: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    real_summary: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="not_generated")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    # M2：正文保存的乐观锁基线。每次改变当前选中正文都递增 revision_id，
    # content_hash 与实际选中文本对应，避免不同浏览器静默互相覆盖。
    revision_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rag_ingest_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
    selected_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapter_versions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project: Mapped[NovelProject] = relationship(back_populates="chapters")
    volume: Mapped[Optional[Volume]] = relationship(back_populates="chapters")
    versions: Mapped[list["ChapterVersion"]] = relationship(
        "ChapterVersion",
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="ChapterVersion.created_at",
        primaryjoin="Chapter.id == ChapterVersion.chapter_id",
        foreign_keys="[ChapterVersion.chapter_id]",
    )
    selected_version: Mapped[Optional["ChapterVersion"]] = relationship(
        "ChapterVersion",
        foreign_keys=[selected_version_id],
        primaryjoin="Chapter.selected_version_id == ChapterVersion.id",
        post_update=True,
    )
    evaluations: Mapped[list["ChapterEvaluation"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan", order_by="ChapterEvaluation.created_at"
    )
    world_state_snapshots: Mapped[list["ChapterWorldState"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan", order_by="ChapterWorldState.created_at"
    )


class ChapterVersion(Base):
    """章节的不可变正文快照。

    ``Chapter.selected_version_id`` 只标记当前采用的快照；任何保存、AI 采纳或
    恢复历史都必须新增本表记录，绝不能修改已有 ``content``。
    """

    __tablename__ = "chapter_versions"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    version_label: Mapped[Optional[str]] = mapped_column(String(64))
    provider: Mapped[Optional[str]] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(LONG_TEXT_TYPE, nullable=False)
    # M3：可追溯修订链。旧记录由迁移标为 legacy，后续写入一律携带来源和正文哈希。
    parent_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapter_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="legacy", server_default="legacy", index=True
    )
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    change_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON)
    metadata = _MetadataAccessor()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chapter: Mapped[Chapter] = relationship(
        "Chapter",
        back_populates="versions",
        foreign_keys=[chapter_id],
    )
    parent_version: Mapped[Optional["ChapterVersion"]] = relationship(
        "ChapterVersion",
        remote_side="ChapterVersion.id",
        foreign_keys=[parent_version_id],
        back_populates="child_versions",
    )
    child_versions: Mapped[list["ChapterVersion"]] = relationship(
        "ChapterVersion",
        foreign_keys="[ChapterVersion.parent_version_id]",
        back_populates="parent_version",
    )
    evaluations: Mapped[list["ChapterEvaluation"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    world_state_snapshots: Mapped[list["ChapterWorldState"]] = relationship(
        back_populates="source_version", foreign_keys="[ChapterWorldState.source_version_id]"
    )


class ChapterWorldState(Base):
    """章节版本级世界状态切片（M1）。

    仅保存已确认的事实切片与来源证据；自动抽取、冲突诊断及下一章增量继承由 M5
    接入。每次写入都新增记录，避免把新的推测覆盖旧版本事实。
    """

    __tablename__ = "chapter_world_states"
    __table_args__ = (
        Index("ix_world_states_project_chapter", "project_id", "chapter_number"),
        Index("ix_world_states_source_version", "source_version_id"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=True, index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapter_versions.id", ondelete="SET NULL"), nullable=True
    )
    parent_snapshot_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chapter_world_states.id", ondelete="SET NULL"), nullable=True
    )
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", server_default="manual")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chapter: Mapped[Optional[Chapter]] = relationship(back_populates="world_state_snapshots")
    source_version: Mapped[Optional[ChapterVersion]] = relationship(
        back_populates="world_state_snapshots", foreign_keys=[source_version_id]
    )


class ChapterEvaluation(Base):
    """章节评估记录。"""

    __tablename__ = "chapter_evaluations"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapter_versions.id", ondelete="CASCADE"))
    decision: Mapped[Optional[str]] = mapped_column(String(32))
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    score: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chapter: Mapped[Chapter] = relationship(back_populates="evaluations")
    version: Mapped[Optional[ChapterVersion]] = relationship(back_populates="evaluations")
