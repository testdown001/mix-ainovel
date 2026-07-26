# AIMETA P=数据库初始化_创建表和默认数据|R=创建表_初始化管理员|NR=不含业务逻辑|E=init_db|X=internal|A=初始化函数|D=sqlalchemy|S=db|RD=./README.ai
import logging
import hashlib

from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ..core.config import settings
from ..core.security import hash_password
from ..models import Plan, Prompt, SystemConfig, User, WritingTemplate
from .base import Base
from .system_config_defaults import SYSTEM_CONFIG_DEFAULTS
from .session import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)

_SCHEMA_MISMATCH_MARKERS = (
    "Unknown column 'chapter_outlines.metadata'",
    "Unknown column 'writer_personas.physiological_reactions'",
    "Unknown column 'writer_personas.benchmark_texts'",
    "Unknown column 'novel_blueprints.golden_finger'",
    "Unknown column 'blueprint_characters.power_system_id'",
    "Unknown column 'blueprint_characters.current_power_level_id'",
    "Unknown column 'novel_projects.reference_novel_ids'",
    "Unknown column 'novel_projects.fusion_dna'",
    "Unknown column 'chapter_blueprints.strand_type'",
    "Unknown column 'chapter_blueprints.strand_weight'",
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def is_schema_mismatch_error(exc: BaseException) -> bool:
    message = str(getattr(exc, "orig", exc) or exc)
    return any(marker in message for marker in _SCHEMA_MISMATCH_MARKERS)


async def repair_schema_if_needed(exc: BaseException) -> bool:
    if not is_schema_mismatch_error(exc):
        return False

    logger.warning("检测到旧版数据库缺列，尝试自动补齐: %s", exc)
    await _ensure_schema_updates()
    return True


async def init_db() -> None:
    """初始化数据库结构并确保默认管理员存在。"""

    await _ensure_database_exists()

    # ---- 第一步：创建所有表结构 ----
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表结构已初始化")
    await _ensure_schema_updates()

    # ---- 第二步：确保管理员账号至少存在一个 ----
    async with AsyncSessionLocal() as session:
        admin_exists = await session.execute(select(User).where(User.is_admin.is_(True)))
        if not admin_exists.scalars().first():
            logger.warning("未检测到管理员账号，正在创建默认管理员 ...")
            admin_user = User(
                username=settings.admin_default_username,
                email=settings.admin_default_email,
                hashed_password=hash_password(settings.admin_default_password),
                is_admin=True,
            )

            session.add(admin_user)
            try:
                await session.commit()
                logger.info("默认管理员创建完成：%s", settings.admin_default_username)
            except IntegrityError:
                await session.rollback()
                logger.exception("默认管理员创建失败，可能是并发启动导致，请检查数据库状态")

        # ---- 第三步：同步系统配置到数据库 ----
        for entry in SYSTEM_CONFIG_DEFAULTS:
            value = entry.value_getter(settings)
            if value is None:
                continue
            existing = await session.get(SystemConfig, entry.key)
            if existing:
                if entry.description and existing.description != entry.description:
                    existing.description = entry.description
                continue
            session.add(
                SystemConfig(
                    key=entry.key,
                    value=value,
                    description=entry.description,
                )
            )

        await _ensure_default_prompts(session)

        await _ensure_default_plans(session)

        await _ensure_default_models(session)

        await session.commit()


async def _ensure_database_exists() -> None:
    """在首次连接前确认 MySQL 数据库存在。SQLite/PostgreSQL 时跳过。"""
    if settings.db_provider == "sqlite":
        return
    if settings.database_url and ("postgresql" in settings.database_url or "postgres" in settings.database_url):
        return

    url = make_url(settings.sqlalchemy_database_uri)

    database = (url.database or "").strip("/")
    if not database:
        return

    admin_url = URL.create(
        drivername=url.drivername,
        username=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        database=None,
        query=url.query,
    )

    admin_engine = create_async_engine(
        admin_url.render_as_string(hide_password=False),
        isolation_level="AUTOCOMMIT",
    )
    async with admin_engine.begin() as conn:
        await conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{database}`"))
    await admin_engine.dispose()


async def _ensure_schema_updates() -> None:
    """补齐历史版本缺失的列，避免旧库在新版本报错。"""
    db_uri = settings.sqlalchemy_database_uri
    if settings.db_provider == "sqlite" or "postgresql" in db_uri or "postgres" in db_uri:
        # SQLite/PostgreSQL: Base.metadata.create_all already created all columns, skip ALTER TABLE
        return

    async with engine.begin() as conn:
        def _upgrade(sync_conn):
            inspector = inspect(sync_conn)

            def _ensure_columns(table_name: str, column_sql: dict[str, str]) -> None:
                if not inspector.has_table(table_name):
                    return
                existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
                for column_name, ddl in column_sql.items():
                    if column_name in existing_columns:
                        continue
                    sync_conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))

            def _ensure_index(table_name: str, index_name: str, columns: list[str]) -> None:
                """为既有库补建缺失的复合索引（幂等）。"""
                if not inspector.has_table(table_name):
                    return
                existing = {idx["name"] for idx in inspector.get_indexes(table_name)}
                if index_name in existing:
                    return
                cols = ", ".join(columns)
                sync_conn.execute(
                    text(f"CREATE INDEX {index_name} ON {table_name} ({cols})")
                )

            _ensure_columns(
                "chapter_outlines",
                {
                    "metadata": "metadata JSON",
                },
            )

            _ensure_columns(
                "writer_personas",
                {
                    "physiological_reactions": "physiological_reactions JSON",
                    "benchmark_texts": "benchmark_texts JSON",
                },
            )

            _ensure_columns(
                "novel_blueprints",
                {
                    "golden_finger": "golden_finger JSON",
                    "volumes": "volumes JSON",
                },
            )

            _ensure_columns(
                "blueprint_characters",
                {
                    "power_system_id": "power_system_id BIGINT NULL",
                    "current_power_level_id": "current_power_level_id BIGINT NULL",
                },
            )
            _ensure_columns(
                "novel_projects",
                {
                    "reference_novel_ids": "reference_novel_ids JSON",
                    "fusion_dna": "fusion_dna JSON",
                    "is_completed": "is_completed TINYINT(1) NOT NULL DEFAULT 0",
                },
            )

            _ensure_columns(
                "chapter_blueprints",
                {
                    "strand_type": "strand_type VARCHAR(32) NULL",
                    "strand_weight": "strand_weight FLOAT NULL",
                },
            )
            _ensure_columns(
                "project_memories",
                {
                    "book_summary": "book_summary LONGTEXT NULL",
                },
            )
            _ensure_columns(
                "user_quotas",
                {
                    "plan_tier": "plan_tier VARCHAR(32) NOT NULL DEFAULT 'free'",
                    "credit_balance": "credit_balance INT NOT NULL DEFAULT 0",
                    "monthly_credit_grant": "monthly_credit_grant INT NOT NULL DEFAULT 0",
                    "credit_carryover": "credit_carryover TINYINT(1) NOT NULL DEFAULT 0",
                    "credit_reset_at": "credit_reset_at DATETIME NULL",
                },
            )
            _ensure_columns(
                "plans",
                {
                    "tier": "tier VARCHAR(32) NOT NULL DEFAULT 'free'",
                    "monthly_credits": "monthly_credits INT NOT NULL DEFAULT 0",
                },
            )
            _ensure_columns(
                "users",
                {
                    "phone": "phone VARCHAR(32) NULL",
                },
            )
            _ensure_index("users", "ix_users_phone", ["phone"])

            # 热点联合过滤补复合索引（与模型 __table_args__ 对齐，覆盖既有库）
            _ensure_index("chapters", "ix_chapters_project_chapter",
                          ["project_id", "chapter_number"])
            _ensure_index("chapter_outlines", "ix_chapter_outlines_project_chapter",
                          ["project_id", "chapter_number"])
        await conn.run_sync(_upgrade)


async def _ensure_default_plans(session: AsyncSession) -> None:
    """套餐表为空时落库三档默认套餐（free/creator/flagship）。

    DEFAULT_PLANS 此前仅作接口的展示兜底（其 id 为字符串档位名），不是真实数据行，
    导致后台「会员套餐」的编辑/上下架/删除（按数字主键 PUT /api/plans/{int} 操作）必然
    422。首次启动落库一次使其成为可编辑的真实行；已存在任何套餐则不动（幂等）。
    """
    import json

    from ..api.routers.plans import DEFAULT_PLANS

    existing = await session.execute(select(Plan).limit(1))
    if existing.scalars().first():
        return

    for item in DEFAULT_PLANS:
        session.add(
            Plan(
                name=item["name"],
                description=item.get("description"),
                price=item["price"],
                period=item["period"],
                daily_chapter_limit=item["daily_chapter_limit"],
                max_novels=item["max_novels"],
                monthly_credits=item.get("monthly_credits", 0),
                tier=item["tier"],
                features=json.dumps(item.get("features") or [], ensure_ascii=False),
                is_recommended=item.get("is_recommended", False),
                is_active=item.get("is_active", True),
                sort_order=item.get("sort_order", 0),
            )
        )
    logger.info("套餐表为空，已落库 %d 个默认会员套餐", len(DEFAULT_PLANS))


async def _ensure_default_models(session: AsyncSession) -> None:
    """模型目录为空时落库占位模型（章鱼1.0/2.0/3.0）。通道五键留空 → 生成时回退 llm.* 默认模型，
    上线后在后台「模型目录」配真实大模型。已存在任何模型则不动（幂等）。"""
    from ..api.routers.model_catalog import DEFAULT_MODELS
    from ..models.model_catalog import ModelCatalog

    existing = await session.execute(select(ModelCatalog).limit(1))
    if existing.scalars().first():
        return
    for item in DEFAULT_MODELS:
        session.add(
            ModelCatalog(
                code=item["code"],
                display_name=item["display_name"],
                description=item.get("description"),
                credit_price=item["credit_price"],
                min_tier=item["min_tier"],
                is_active=item.get("is_active", True),
                sort_order=item.get("sort_order", 0),
            )
        )
    logger.info("模型目录为空，已落库 %d 个占位模型（通道留空回退 llm.*）", len(DEFAULT_MODELS))


async def _ensure_default_prompts(session: AsyncSession) -> None:
    prompts_dir = Path(__file__).resolve().parents[2] / "prompts"
    if not prompts_dir.is_dir():
        return

    prompts_result = await session.execute(select(Prompt))
    existing_prompts = {prompt.name: prompt for prompt in prompts_result.scalars().all()}

    checksum_result = await session.execute(
        select(SystemConfig).where(SystemConfig.key.like("prompt.checksum.%"))
    )
    checksum_records = {
        config.key: config
        for config in checksum_result.scalars().all()
    }

    for prompt_file in sorted(prompts_dir.glob("*.md")):
        name = prompt_file.stem
        content = prompt_file.read_text(encoding="utf-8")
        file_hash = _sha256_text(content)
        checksum_key = f"prompt.checksum.{name}"
        checksum_desc = f"Prompt checksum for auto sync: {name}"

        prompt = existing_prompts.get(name)
        checksum = checksum_records.get(checksum_key)
        stored_hash = checksum.value if checksum and checksum.value else None

        if not prompt:
            prompt = Prompt(name=name, content=content)
            session.add(prompt)
            existing_prompts[name] = prompt
            final_hash = file_hash
        else:
            db_hash = _sha256_text(prompt.content or "")
            # 仅当 DB 内容仍与"上次同步版本"一致时，才安全覆盖为最新文件内容。
            if stored_hash and stored_hash == db_hash and db_hash != file_hash:
                prompt.content = content
                final_hash = file_hash
            else:
                final_hash = db_hash

        if checksum:
            checksum.value = final_hash
            checksum.description = checksum_desc
        else:
            checksum = SystemConfig(
                key=checksum_key,
                value=final_hash,
                description=checksum_desc,
            )
            session.add(checksum)
            checksum_records[checksum_key] = checksum
