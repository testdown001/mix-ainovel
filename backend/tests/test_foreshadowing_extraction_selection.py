"""伏笔提取列表挑选：中后期伏笔不再被「只取最早 10 条」截断。

验证 extract_foreshadowings_from_chapter 喂给 LLM 的未回收伏笔列表：
- 上限提到 30，15 个伏笔全量进入（旧代码 [:10] 会截掉第 11-15 个）；
- 超过 30 个且 embedding 不可用时降级为「最早 5 条 + 其余按埋设章节倒序」，不抛异常；
- embedding 可用时语义相关的中后期伏笔优先。
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.models  # noqa: F401  mapper 注册
import app.models.user_quota  # noqa: F401
from app.models.foreshadowing import Foreshadowing
from app.services.foreshadowing_service import ForeshadowingService


async def _seed(session, count, content_fn=None):
    """播种 count 个未回收伏笔，chapter_number = 1..count，content 带 FSMARK 标记。"""
    for i in range(1, count + 1):
        content = content_fn(i) if content_fn else f"FSMARK{i:02d} 第{i}章埋设的伏笔"
        session.add(Foreshadowing(
            project_id="p1",
            chapter_id=1,
            chapter_number=i,
            content=content,
            type="hint",
            status="planted",
            keywords=[],
        ))
    await session.commit()


def _mock_prompt_service():
    return SimpleNamespace(get_prompt=AsyncMock(return_value="伏笔提取提示词"))


async def _run_extract(session, llm, chapter_number):
    service = ForeshadowingService(session)
    stats = await service.extract_foreshadowings_from_chapter(
        project_id="p1",
        chapter_id=999,
        chapter_number=chapter_number,
        chapter_content="本章正文内容",
        llm_service=llm,
        prompt_service=_mock_prompt_service(),
    )
    user_input = llm.get_llm_response.call_args.kwargs["conversation_history"][0]["content"]
    return stats, user_input


@pytest.mark.asyncio
async def test_fifteen_unresolved_all_fed_to_llm(db_session):
    """15 个未回收伏笔 → 喂给 LLM 的列表包含中后期伏笔（旧 [:10] 会截掉）。"""
    await _seed(db_session, 15)
    llm = MagicMock()
    llm.get_llm_response = AsyncMock(return_value='{"foreshadowing_actions": []}')

    stats, user_input = await _run_extract(db_session, llm, chapter_number=16)

    assert stats == {"planted": 0, "developed": 0, "resolved": 0}
    for i in range(1, 16):
        assert f"FSMARK{i:02d}" in user_input


@pytest.mark.asyncio
async def test_over_limit_degrades_to_earliest_plus_recent(db_session):
    """40 个伏笔 + embedding 失败 → 不抛异常，降级为最早 5 条 + 近期优先。"""
    await _seed(db_session, 40)
    llm = MagicMock()
    llm.get_llm_response = AsyncMock(return_value='{"foreshadowing_actions": []}')

    async def _embed_fail(texts):
        raise RuntimeError("embedding 通道不可用")

    llm.get_embeddings_batch = _embed_fail

    _, user_input = await _run_extract(db_session, llm, chapter_number=41)

    # 最早 5 条保底
    for i in range(1, 6):
        assert f"FSMARK{i:02d}" in user_input
    # 近期伏笔（chapter DESC 取 40..16）进入列表
    for i in (40, 30, 16):
        assert f"FSMARK{i:02d}" in user_input
    # 早中段（6..15）被挤出，总量控制在 30
    assert "FSMARK06" not in user_input
    assert "FSMARK15" not in user_input
    listed = user_input.split("[未回收伏笔列表]", 1)[1]
    assert listed.count("FSMARK") == ForeshadowingService.EXTRACTION_UNRESOLVED_LIMIT


@pytest.mark.asyncio
async def test_semantic_relevance_promotes_late_foreshadowing(db_session):
    """embedding 可用时，与本章内容语义相关的中后期伏笔排到最前。"""
    def _content(i):
        if i == 33:
            return f"FSMARK{i:02d} ALPHA 玉佩的秘密"
        return f"FSMARK{i:02d} BETA 普通伏笔"

    await _seed(db_session, 35, content_fn=_content)
    llm = MagicMock()
    llm.get_llm_response = AsyncMock(return_value='{"foreshadowing_actions": []}')

    async def _embed(texts):
        out = []
        for t in texts:
            if "ALPHA" in t:
                out.append([1.0, 0.0])
            else:
                out.append([0.0, 1.0])
        return out

    llm.get_embeddings_batch = _embed

    service = ForeshadowingService(db_session)
    await service.extract_foreshadowings_from_chapter(
        project_id="p1",
        chapter_id=999,
        chapter_number=36,
        chapter_content="ALPHA 玉佩再次浮现",  # query 与第 33 章伏笔语义相关
        llm_service=llm,
        prompt_service=_mock_prompt_service(),
    )
    user_input = llm.get_llm_response.call_args.kwargs["conversation_history"][0]["content"]

    listed = user_input.split("[未回收伏笔列表]", 1)[1]
    first_line = [ln for ln in listed.splitlines() if "FSMARK" in ln][0]
    assert "FSMARK33" in first_line  # 语义相关伏笔排第一
    assert listed.count("FSMARK") == ForeshadowingService.EXTRACTION_UNRESOLVED_LIMIT


def test_select_helper_within_limit_returns_all():
    """未超上限时全量返回，不触发 embedding。"""
    items = [
        SimpleNamespace(id=i, chapter_number=i, content=f"伏笔{i}", name=None)
        for i in range(1, 11)
    ]
    service = ForeshadowingService(session=None)
    selected = asyncio.run(
        service._select_unresolved_for_extraction(items, 11, "正文", llm_service=None)
    )
    assert selected == items
