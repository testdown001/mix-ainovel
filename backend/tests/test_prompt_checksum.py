"""提示词启动同步的 checksum 语义回归。

checksum（SystemConfig prompt.checksum.{name}）=「上次与 .md 文件同步时的内容哈希」：
- stored == db 哈希 → 未被接管，跟随文件更新；
- stored != db 哈希 → 管理员接管，永不自动覆盖，直到显式恢复默认。

历史 bug：「保留 DB」分支把 checksum 回写成 DB 内容哈希，伪造出「已同步」状态，
第二次重启即满足覆盖条件、把管理员改动抹掉。本文件锁死该行为。
"""
import hashlib

import pytest
from sqlalchemy import select

from app.db.init_db import _ensure_default_prompts
from app.models import Prompt, SystemConfig
from app.services import prompt_service as ps_module
from app.services.prompt_service import PromptService


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture(autouse=True)
def _clear_prompt_cache():
    ps_module._CACHE.clear()
    yield
    ps_module._CACHE.clear()


async def _get_prompt_row(session, name: str) -> Prompt:
    result = await session.execute(select(Prompt).where(Prompt.name == name))
    return result.scalars().first()


async def _get_checksum(session, name: str) -> str | None:
    result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == f"prompt.checksum.{name}")
    )
    record = result.scalars().first()
    return record.value if record else None


@pytest.mark.asyncio
async def test_admin_edit_survives_repeated_restarts(db_session, tmp_path):
    """管理员改动跨多次启动同步不被 .md 覆盖（复现旧 bug 的双重启场景）。"""
    (tmp_path / "concept.md").write_text("file-v1 {foo}", encoding="utf-8")

    # 首次启动：从文件建库
    await _ensure_default_prompts(db_session, prompts_dir=tmp_path)
    await db_session.commit()
    prompt = await _get_prompt_row(db_session, "concept")
    assert prompt.content == "file-v1 {foo}"
    assert await _get_checksum(db_session, "concept") == _sha("file-v1 {foo}")

    # 管理员在后台接管
    prompt.content = "admin took over {foo}"
    await db_session.commit()

    # 之后发布了新文件版本，连续重启两次
    (tmp_path / "concept.md").write_text("file-v2 {foo}", encoding="utf-8")
    for _ in range(2):
        await _ensure_default_prompts(db_session, prompts_dir=tmp_path)
        await db_session.commit()
        prompt = await _get_prompt_row(db_session, "concept")
        assert prompt.content == "admin took over {foo}"
        # checksum 保持「上次同步」的 v1 哈希，不得被回写成 DB 哈希
        assert await _get_checksum(db_session, "concept") == _sha("file-v1 {foo}")


@pytest.mark.asyncio
async def test_untouched_prompt_follows_file_updates(db_session, tmp_path):
    (tmp_path / "outline.md").write_text("file-v1", encoding="utf-8")
    await _ensure_default_prompts(db_session, prompts_dir=tmp_path)
    await db_session.commit()

    (tmp_path / "outline.md").write_text("file-v2", encoding="utf-8")
    await _ensure_default_prompts(db_session, prompts_dir=tmp_path)
    await db_session.commit()

    prompt = await _get_prompt_row(db_session, "outline")
    assert prompt.content == "file-v2"
    assert await _get_checksum(db_session, "outline") == _sha("file-v2")


@pytest.mark.asyncio
async def test_reset_to_default_restores_file_following(db_session, tmp_path, monkeypatch):
    """恢复默认后：内容回到文件版，且重新跟随后续文件更新。"""
    (tmp_path / "concept.md").write_text("file-v1", encoding="utf-8")
    await _ensure_default_prompts(db_session, prompts_dir=tmp_path)
    await db_session.commit()

    prompt = await _get_prompt_row(db_session, "concept")
    prompt.content = "admin content"
    await db_session.commit()

    monkeypatch.setattr(ps_module, "_PROMPTS_DIR", tmp_path)
    service = PromptService(db_session)
    restored = await service.reset_prompt_to_default(prompt.id)
    assert restored is not None
    assert restored.content == "file-v1"
    assert await _get_checksum(db_session, "concept") == _sha("file-v1")

    # 恢复默认后文件再更新 → 重新自动跟随
    (tmp_path / "concept.md").write_text("file-v2", encoding="utf-8")
    await _ensure_default_prompts(db_session, prompts_dir=tmp_path)
    await db_session.commit()
    prompt = await _get_prompt_row(db_session, "concept")
    assert prompt.content == "file-v2"


@pytest.mark.asyncio
async def test_reset_to_default_returns_none_without_file(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(ps_module, "_PROMPTS_DIR", tmp_path)
    prompt = Prompt(name="admin_only", content="自建")
    db_session.add(prompt)
    await db_session.commit()

    service = PromptService(db_session)
    assert await service.reset_prompt_to_default(prompt.id) is None


@pytest.mark.asyncio
async def test_legacy_row_without_checksum_is_protected(db_session, tmp_path):
    """旧库升级（有行无 checksum）且 DB != 文件：按接管处理，不覆盖。"""
    db_session.add(Prompt(name="legacy", content="old db content"))
    await db_session.commit()

    (tmp_path / "legacy.md").write_text("new file content", encoding="utf-8")
    for _ in range(2):
        await _ensure_default_prompts(db_session, prompts_dir=tmp_path)
        await db_session.commit()
        prompt = await _get_prompt_row(db_session, "legacy")
        assert prompt.content == "old db content"

    # checksum 登记为文件哈希（≠ DB 哈希 → 永久接管态）
    assert await _get_checksum(db_session, "legacy") == _sha("new file content")
