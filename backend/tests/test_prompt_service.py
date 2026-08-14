import time

import pytest
from fastapi import HTTPException

from app.models import Prompt
from app.schemas.prompt import PromptUpdate
from app.services import prompt_service as ps_module
from app.services.prompt_service import PromptService


@pytest.fixture(autouse=True)
def _clear_prompt_cache():
    ps_module._CACHE.clear()
    yield
    ps_module._CACHE.clear()


def test_render_prompt_replaces_named_fields_and_preserves_json_braces():
    template = """novel_title: {novel_title}
search_results: {search_results}
```json
{
  "genre": "都市异能",
  "commercial_data": { "word_count": "300万字" }
}
```
{{already_escaped}}
"""

    rendered = PromptService.render_prompt(
        template,
        novel_title="测试小说",
        search_results="一段搜索结果",
    )

    assert "测试小说" in rendered
    assert "一段搜索结果" in rendered
    assert '"genre": "都市异能"' in rendered
    assert '{ "word_count": "300万字" }' in rendered
    assert '{already_escaped}' in rendered


def test_extract_placeholders_ignores_escaped_braces():
    text = "标题 {novel_title}，转义 {{json_example}}，非法 {不是标识符}，{outline}"
    assert ps_module._extract_placeholders(text) == {"novel_title", "outline"}


@pytest.mark.asyncio
async def test_get_prompt_ttl_expiry_resources_from_db(db_session):
    """TTL 过期后回源 DB：模拟另一副本改了内容，本副本最迟 60 秒看到新值。"""
    prompt = Prompt(name="ttl_case", content="v1")
    db_session.add(prompt)
    await db_session.commit()

    service = PromptService(db_session)
    assert await service.get_prompt("ttl_case") == "v1"

    # 模拟其他副本的修改（不经过本副本的写穿路径）
    prompt.content = "v2"
    await db_session.commit()

    # TTL 内仍返回缓存旧值
    assert await service.get_prompt("ttl_case") == "v1"

    # 人为把缓存条目置为过期
    cached, _ = ps_module._CACHE["ttl_case"]
    ps_module._CACHE["ttl_case"] = (cached, time.monotonic() - ps_module._CACHE_TTL_SEC - 1)

    assert await service.get_prompt("ttl_case") == "v2"


@pytest.mark.asyncio
async def test_update_prompt_writes_through_cache(db_session):
    prompt = Prompt(name="write_through_case", content="old")
    db_session.add(prompt)
    await db_session.commit()

    service = PromptService(db_session)
    assert await service.get_prompt("write_through_case") == "old"

    updated = await service.update_prompt(prompt.id, PromptUpdate(content="new"))
    assert updated is not None
    # 不等 TTL，立即生效
    assert await service.get_prompt("write_through_case") == "new"


@pytest.mark.asyncio
async def test_get_prompt_miss_not_cached(db_session):
    service = PromptService(db_session)
    assert await service.get_prompt("nonexistent_case") is None
    assert "nonexistent_case" not in ps_module._CACHE


@pytest.mark.asyncio
async def test_update_prompt_rejects_missing_placeholders(db_session, tmp_path, monkeypatch):
    """占位符护栏：新内容缺失文件版模板的必需占位符 → 400。"""
    (tmp_path / "guarded.md").write_text(
        "标题：{novel_title}\n大纲：{outline}\n转义示例 {{not_required}}",
        encoding="utf-8",
    )
    monkeypatch.setattr(ps_module, "_PROMPTS_DIR", tmp_path)

    prompt = Prompt(name="guarded", content="占位")
    db_session.add(prompt)
    await db_session.commit()

    service = PromptService(db_session)

    with pytest.raises(HTTPException) as excinfo:
        await service.update_prompt(prompt.id, PromptUpdate(content="只有 {outline}，标题没了"))
    assert excinfo.value.status_code == 400
    assert "{novel_title}" in excinfo.value.detail

    # 占位符齐全则通过（{{}} 转义不算必需项）
    updated = await service.update_prompt(
        prompt.id, PromptUpdate(content="改写：{novel_title} / {outline}")
    )
    assert updated is not None


@pytest.mark.asyncio
async def test_update_prompt_without_template_file_skips_validation(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(ps_module, "_PROMPTS_DIR", tmp_path)

    prompt = Prompt(name="admin_custom", content="自建模板 {anything}")
    db_session.add(prompt)
    await db_session.commit()

    service = PromptService(db_session)
    updated = await service.update_prompt(prompt.id, PromptUpdate(content="随便改，无文件对照"))
    assert updated is not None
