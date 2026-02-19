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
from ..models import Prompt, SystemConfig, User
from .base import Base
from .system_config_defaults import SYSTEM_CONFIG_DEFAULTS
from .session import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


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

        await session.commit()


async def _ensure_database_exists() -> None:
    """在首次连接前确认数据库存在，针对不同驱动做最小化准备工作。"""
    url = make_url(settings.sqlalchemy_database_uri)

    if url.get_backend_name() == "sqlite":
        # SQLite 采用文件数据库，确保父目录存在即可，无需额外建库语句
        db_path = Path(url.database or "").expanduser()
        if not db_path.is_absolute():
            project_root = Path(__file__).resolve().parents[2]
            db_path = (project_root / db_path).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return

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
    async with engine.begin() as conn:
        def _upgrade(sync_conn):
            inspector = inspect(sync_conn)
            columns = {col["name"] for col in inspector.get_columns("chapter_outlines")}
            if "metadata" not in columns:
                sync_conn.execute(text("ALTER TABLE chapter_outlines ADD COLUMN metadata JSON"))
        await conn.run_sync(_upgrade)


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
            # 仅当 DB 内容仍与“上次同步版本”一致时，才安全覆盖为最新文件内容。
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
