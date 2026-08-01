"""编辑章节后刷新滚动细纲修订（7 月整改遗留 #33 的实质缺口，2026-08-01 补）。

后续章节的 `revision_hint` 是按「本章实际内容」算出来的。章节被手工编辑后：
- 伏笔**会**重新提取（`_background_chapter_post_process` 的 edit 分支早已有这一步）；
- 大纲修订**不会** → 后续章节继续注入基于编辑前旧文本算出的陈旧建议。

两者本是对称的一对（写侧同挂在生成收尾的 schedule_followups 上），edit 路径漏了一半。

注：审计原记的另外两条经复核不成立，故未改——
- 「触发点在写侧任务而非 finalize」：`generation_write_task_service` 只是实现所在模块，
  真正触发点是 `generation_finalize_service.schedule_followups:117`，与伏笔提取并列；
- 「缺 consumed 标记」：hint 描述的是「前章既成事实 vs 本章未改大纲」的**持续性**矛盾，
  在大纲被改写前一直成立（改写时已由 update_or_create_outline 清除）。若在定稿时标
  consumed，重生成该章将拿不到这条仍然有效的指导，是净损失。
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import app.models  # noqa: F401  触发 mapper 注册
import app.models.user_quota  # noqa: F401  防 mapper KeyError


def _patch_env(monkeypatch, enabled: bool):
    from app.core.config import settings
    monkeypatch.setattr(settings, "outline_revision_enabled", enabled, raising=False)


@pytest.fixture
def edit_path_stubs(monkeypatch):
    """把 edit 分支里除「细纲修订」外的一切都桩掉，只观察它是否被调用。"""
    import app.api.routers.writer as writer

    monkeypatch.setattr(writer, "PromptService", lambda _s: SimpleNamespace())
    monkeypatch.setattr(writer, "LLMService", lambda _s: SimpleNamespace())

    processor = SimpleNamespace(
        process_after_edit=AsyncMock(return_value=None),
        process_after_select=AsyncMock(return_value=None),
    )
    # 真实调用是位置参数 ChapterPostProcessor(session, llm_service)
    monkeypatch.setattr(writer, "ChapterPostProcessor", lambda *_a, **_kw: processor)

    class _Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def execute(self, *_a, **_k):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: SimpleNamespace(id=1)))
        async def commit(self): return None
        async def rollback(self): return None

    monkeypatch.setattr(writer, "AsyncSessionLocal", lambda: _Session())

    # 伏笔提取本身不是本用例关注点，桩掉避免噪音
    fs = SimpleNamespace(extract_foreshadowings_from_chapter=AsyncMock(return_value={}))
    monkeypatch.setattr(
        "app.services.foreshadowing_service.ForeshadowingService", lambda _s: fs
    )
    return writer


@pytest.mark.asyncio
async def test_edit_refreshes_outline_revision(edit_path_stubs, monkeypatch):
    """编辑后必须按新正文重算后续章节的 revision_hint。"""
    _patch_env(monkeypatch, True)
    review = AsyncMock(return_value={"hints_written": 2})

    with patch(
        "app.services.outline_revision_service.OutlineRevisionService.review_downstream",
        review,
    ):
        await edit_path_stubs._background_chapter_post_process(
            project_id="p1", chapter_number=4, content="编辑后的新正文",
            user_id=1, mode="edit",
        )

    review.assert_awaited_once()
    kwargs = review.await_args.kwargs
    assert kwargs["finalized_chapter_number"] == 4
    assert kwargs["chapter_content"] == "编辑后的新正文"   # 用的是编辑后的文本


@pytest.mark.asyncio
async def test_edit_skips_when_feature_switch_off(edit_path_stubs, monkeypatch):
    """env 灰度开关关闭时不额外发 LLM 调用（该特性默认关）。"""
    _patch_env(monkeypatch, False)
    review = AsyncMock(return_value={})

    with patch(
        "app.services.outline_revision_service.OutlineRevisionService.review_downstream",
        review,
    ):
        await edit_path_stubs._background_chapter_post_process(
            project_id="p1", chapter_number=4, content="正文", user_id=1, mode="edit",
        )

    review.assert_not_awaited()


@pytest.mark.asyncio
async def test_select_does_not_rerun_revision(edit_path_stubs, monkeypatch):
    """select 路径不重跑：生成收尾刚算过一次，每次选版再算一次是纯浪费。"""
    _patch_env(monkeypatch, True)
    review = AsyncMock(return_value={})

    with patch(
        "app.services.outline_revision_service.OutlineRevisionService.review_downstream",
        review,
    ):
        await edit_path_stubs._background_chapter_post_process(
            project_id="p1", chapter_number=4, content="正文", user_id=1, mode="select",
        )

    review.assert_not_awaited()


@pytest.mark.asyncio
async def test_revision_failure_does_not_break_edit(edit_path_stubs, monkeypatch):
    """细纲修订失败必须被吞掉——编辑保存不能因它失败。"""
    _patch_env(monkeypatch, True)

    with patch(
        "app.services.outline_revision_service.OutlineRevisionService.review_downstream",
        AsyncMock(side_effect=RuntimeError("LLM 挂了")),
    ):
        await edit_path_stubs._background_chapter_post_process(
            project_id="p1", chapter_number=4, content="正文", user_id=1, mode="edit",
        )
    # 未抛出即通过
