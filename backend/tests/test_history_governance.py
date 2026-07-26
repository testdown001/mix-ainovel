"""W4 无上限历史注入治理测试。

覆盖：
- 2.8a writer.py 三处历史注入治理（大纲生成/批量推演/AI 评审）
- 2.8b history_context_service 摘要回填限流 + 总量上限
- 2.8c book_summary / narrative_summary 输入上限
- 2.3  story_skeleton 远章采样优先保留未回收伏笔埋设章
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.routers import writer as writer_module
from app.services.book_summary_service import (
    BOOK_SUMMARY_HEAD_VOLUMES,
    BOOK_SUMMARY_MAX_VOLUMES,
    BookSummaryService,
)
from app.services.history_context_service import (
    SKELETON_FAR_QUOTA,
    SUMMARY_BACKFILL_CONCURRENCY,
    SUMMARY_BACKFILL_MAX_CHAPTERS,
    HistoryContextService,
)
from app.services.narrative_summary_service import (
    INITIAL_MAX_CHAPTERS,
    NarrativeSummaryService,
)


@pytest.fixture(autouse=True)
def _ensure_models_loaded():
    """确保所有 ORM 模型在测试前加载完毕。"""
    import app.models  # noqa: F401
    import app.models.user_quota  # noqa: F401


# ---------------------------------------------------------------------------
# 2.8a 大纲生成上下文：近 20 章全量 + 更早仅标题
# ---------------------------------------------------------------------------

def _make_outline(num):
    return SimpleNamespace(chapter_number=num, title=f"T{num:03d}", summary=f"O{num:03d}大纲内容")


def test_outline_context_recent_full_older_brief():
    """50 章项目：只有最近 20 章保留完整摘要，更早 30 章仅剩「第N章 - 标题」。"""
    entries = [
        (o.chapter_number, f"第{o.chapter_number}章 - {o.title}: {o.summary}", f"第{o.chapter_number}章 - {o.title}")
        for o in [_make_outline(i) for i in range(1, 51)]
    ]
    lines = writer_module._build_recent_full_older_brief(
        entries, writer_module.OUTLINE_CONTEXT_RECENT_CHAPTERS
    )
    text = "\n".join(lines)

    # 近 20 章（31-50）保留全量摘要
    assert "O031大纲内容" in text
    assert "O050大纲内容" in text
    # 更早章节（1-30）不含摘要，只剩标题行
    assert "O005大纲内容" not in text
    assert "O030大纲内容" not in text
    assert "第5章 - T005" in text
    assert "第30章 - T030" in text
    # 有省略说明
    assert "仅列出标题" in text
    # 未超上限时不裁剪、无说明行
    short = writer_module._build_recent_full_older_brief(entries[:10], 20)
    assert len(short) == 10
    assert all("大纲内容" in line for line in short)


# ---------------------------------------------------------------------------
# 2.8a 批量推演：近 20 全量摘要 + 远章标题列表；大纲当前章 ±20 全量
# ---------------------------------------------------------------------------

def test_prediction_prompt_governs_history():
    project = SimpleNamespace(
        outlines=[_make_outline(i) for i in range(1, 51)],
        chapters=[
            SimpleNamespace(chapter_number=i, real_summary=f"S{i:03d}摘要内容")
            for i in range(1, 51)
        ],
    )
    bp = SimpleNamespace(
        title="书名",
        genre="玄幻",
        style="热血",
        one_sentence_summary="一句话",
        full_synopsis="完整概要",
        foreshadowings=[],
    )
    shared_ctx = writer_module._build_prediction_shared_context(project, bp)
    prompt = writer_module._build_prediction_prompt(48, "T048", "O048大纲内容", shared_ctx)

    # 已完成摘要：最近 20 章（28-47）全量
    assert "S046摘要内容" in prompt
    assert "S028摘要内容" in prompt
    # 远章（1-27）摘要被裁掉，只剩标题
    assert "S005摘要内容" not in prompt
    assert "第5章 - T005" in prompt
    # 大纲：当前章 ±20（28-50）全量，更远仅标题
    assert "O040大纲内容" in prompt
    assert "O010大纲内容" not in prompt
    assert "第10章 - T010" in prompt


def test_prediction_prompt_small_project_unchanged():
    """小项目（10 章）不触发裁剪，行为与治理前一致。"""
    project = SimpleNamespace(
        outlines=[_make_outline(i) for i in range(1, 11)],
        chapters=[
            SimpleNamespace(chapter_number=i, real_summary=f"S{i:03d}摘要内容")
            for i in range(1, 11)
        ],
    )
    bp = SimpleNamespace(
        title="书名", genre="玄幻", style="热血",
        one_sentence_summary="一句话", full_synopsis="完整概要", foreshadowings=[],
    )
    shared_ctx = writer_module._build_prediction_shared_context(project, bp)
    prompt = writer_module._build_prediction_prompt(8, "T008", "O008大纲内容", shared_ctx)
    for i in range(1, 8):
        assert f"S{i:03d}摘要内容" in prompt
    for i in range(1, 11):
        assert f"O{i:03d}大纲内容" in prompt


# ---------------------------------------------------------------------------
# 2.8a AI 评审：最近 10 章 + 缺失摘要不再串行补齐
# ---------------------------------------------------------------------------

def test_evaluation_history_recent_10_no_backfill():
    chapters = [
        SimpleNamespace(
            chapter_number=i,
            selected_version=SimpleNamespace(content=f"第{i}章正文内容" * 10),
            real_summary=None if i == 25 else f"S{i:03d}摘要",
        )
        for i in range(1, 31)
    ]
    outlines_map = {i: _make_outline(i) for i in range(1, 31)}

    completed = writer_module._build_evaluation_history(chapters, outlines_map, 31)

    assert len(completed) == writer_module.EVALUATION_RECENT_CHAPTERS == 10
    assert [c["chapter_number"] for c in completed] == list(range(21, 31))
    # 缺失摘要标注「（无摘要）」而不是触发 LLM 补齐
    by_num = {c["chapter_number"]: c for c in completed}
    assert by_num[25]["summary"] == "（无摘要）"
    assert by_num[30]["summary"] == "S030摘要"


# ---------------------------------------------------------------------------
# 2.8b 摘要回填：并发 ≤ 3 且单次最多回填最近 30 章
# ---------------------------------------------------------------------------

class _DummyResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def all(self):
        return self._rows


class _DummySession:
    def __init__(self):
        self.execute = AsyncMock(return_value=_DummyResult())
        self.committed = False

    async def commit(self):
        self.committed = True


class _ConcurrencyTrackingLLM:
    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.call_count = 0

    async def _resolve_llm_config(self, user_id):
        return {}

    async def get_summary(self, content, **kwargs):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.call_count += 1
        await asyncio.sleep(0.005)
        self.active -= 1
        return f"回填摘要:{content[:6]}"


def test_backfill_concurrency_capped_and_bounded():
    """40 章缺摘要：只回填最近 30 章，并发受限；更早 10 章不回填但走正文节选兜底进入上下文。"""
    chapters = [
        SimpleNamespace(
            chapter_number=i,
            selected_version=SimpleNamespace(content=f"第{i}章正文内容，足够长的正文。"),
            real_summary=None,
        )
        for i in range(1, 41)
    ]
    llm = _ConcurrencyTrackingLLM()
    prompt_service = SimpleNamespace(get_prompt=AsyncMock(return_value="extraction prompt"))
    session = _DummySession()
    svc = HistoryContextService(session, prompt_service, llm)

    result = asyncio.run(
        svc.collect_history_context(
            project_id="proj-1",
            chapter_number=41,
            outlines_map={},
            chapters=chapters,
            user_id=1,
            allow_summary_backfill=True,
        )
    )

    assert llm.call_count == SUMMARY_BACKFILL_MAX_CHAPTERS == 30
    assert llm.max_active <= SUMMARY_BACKFILL_CONCURRENCY == 5
    # 最近 30 章（11-40）被回填，更早 10 章不写 real_summary
    for ch in chapters:
        if ch.chapter_number >= 11:
            assert ch.real_summary and ch.real_summary.startswith("回填摘要:")
        else:
            assert ch.real_summary is None
    assert session.committed is True
    # 被回填上限跳过的远章不消失：走大纲/正文节选兜底进入上下文
    nums = [c["chapter_number"] for c in result["completed_chapters"]]
    assert nums == list(range(1, 41))
    fallback_entries = [c for c in result["completed_chapters"] if c["chapter_number"] <= 10]
    assert all(c.get("summary") for c in fallback_entries)


# ---------------------------------------------------------------------------
# 2.8c 书摘要输入上限：40 卷 → 前 5 卷 + 最近 25 卷 + 省略标注
# ---------------------------------------------------------------------------

def test_book_summary_input_trimmed():
    vol_dicts = [
        {
            "volume_number": i,
            "title": f"第{i}卷",
            "summary": f"V{i:03d}卷摘要",
            "chapter_range": f"{i * 10 - 9}-{i * 10}",
        }
        for i in range(1, 41)
    ]
    llm = SimpleNamespace(get_summary=AsyncMock(return_value="全书摘要"))
    service = BookSummaryService(SimpleNamespace(), llm)

    result = asyncio.run(service._generate_book_summary(vol_dicts, user_id=1))

    assert result == "全书摘要"
    user_content = llm.get_summary.call_args.args[0]
    tail_count = BOOK_SUMMARY_MAX_VOLUMES - BOOK_SUMMARY_HEAD_VOLUMES
    # 前 5 卷 + 最近 25 卷保留
    assert "V001卷摘要" in user_content
    assert "V005卷摘要" in user_content
    assert "V016卷摘要" in user_content
    assert "V040卷摘要" in user_content
    # 中段（6-15 卷）被省略且有标注
    assert "V006卷摘要" not in user_content
    assert "V015卷摘要" not in user_content
    assert f"第6卷~第15卷共 10 卷" in user_content
    assert f"最近 {tail_count} 卷" in user_content


def test_book_summary_input_not_trimmed_when_small():
    vol_dicts = [
        {"volume_number": i, "title": f"第{i}卷", "summary": f"V{i:03d}卷摘要", "chapter_range": "1-10"}
        for i in range(1, 6)
    ]
    llm = SimpleNamespace(get_summary=AsyncMock(return_value="全书摘要"))
    service = BookSummaryService(SimpleNamespace(), llm)

    asyncio.run(service._generate_book_summary(vol_dicts, user_id=1))

    user_content = llm.get_summary.call_args.args[0]
    for i in range(1, 6):
        assert f"V{i:03d}卷摘要" in user_content
    assert "省略" not in user_content


# ---------------------------------------------------------------------------
# 2.8c 叙事摘要首建输入上限：超 30 章只送最近 30 章 + 卷级概要
# ---------------------------------------------------------------------------

def test_narrative_first_build_capped():
    service = NarrativeSummaryService(SimpleNamespace(), SimpleNamespace())
    chapter_summaries = [
        {"chapter_number": i, "summary": f"C{i:03d}章摘要"} for i in range(1, 41)
    ]
    volume_summaries = [{"volume_number": 1, "title": "第1卷", "summary": "卷1概要"}]

    content = service._build_prompt_content(chapter_summaries, volume_summaries, [], None)

    # 只送最近 30 章（11-40）
    assert "C011章摘要" in content
    assert "C040章摘要" in content
    assert "C005章摘要" not in content
    assert "C010章摘要" not in content
    assert f"更早 {40 - INITIAL_MAX_CHAPTERS} 章摘要已省略" in content
    # 卷级概要仍在（覆盖早期剧情）
    assert "卷1概要" in content


def test_narrative_first_build_full_when_small():
    service = NarrativeSummaryService(SimpleNamespace(), SimpleNamespace())
    chapter_summaries = [
        {"chapter_number": i, "summary": f"C{i:03d}章摘要"} for i in range(1, 11)
    ]
    content = service._build_prompt_content(chapter_summaries, [], [], None)
    assert "# 全部章节摘要" in content
    for i in range(1, 11):
        assert f"C{i:03d}章摘要" in content


# ---------------------------------------------------------------------------
# 2.3 skeleton 远章采样：优先保留埋有未回收伏笔的章
# ---------------------------------------------------------------------------

def _make_completed(num):
    return {"chapter_number": num, "title": f"T{num}", "summary": f"第{num}章的事件。"}


def test_skeleton_prioritizes_foreshadow_chapters():
    chapters = [_make_completed(i) for i in range(1, 41)]

    skeleton = HistoryContextService.build_story_skeleton(
        chapters, current_chapter=41, priority_chapters={7, 13, 22}
    )

    assert skeleton is not None
    # 埋有未回收伏笔的远章被优先保留
    assert "第7章 T7" in skeleton
    assert "第13章 T13" in skeleton
    assert "第22章 T22" in skeleton
    # 远章总数不超配额
    far_lines = [
        line for line in skeleton.split("\n")
        if line.startswith("第") and int(line.split("章")[0][1:]) <= 30
    ]
    assert len(far_lines) <= SKELETON_FAR_QUOTA


def test_skeleton_degrades_to_stride_sampling_without_priority():
    """无伏笔信息（查询失败降级）时保持原等步长采样行为。"""
    chapters = [_make_completed(i) for i in range(1, 41)]

    skeleton = HistoryContextService.build_story_skeleton(chapters, current_chapter=41)

    assert skeleton is not None
    # 原等步长采样：远章 1, 8, 15, 22, 29, 30
    assert "第1章 T1" in skeleton
    assert "第8章 T8" in skeleton
    # 第 7 章不在等步长节点上
    assert "第7章 T7" not in skeleton


def test_load_unresolved_foreshadow_chapters_degrades_on_error():
    session = SimpleNamespace(execute=AsyncMock(side_effect=RuntimeError("db down")))
    svc = HistoryContextService(session, SimpleNamespace(), SimpleNamespace())

    result = asyncio.run(svc._load_unresolved_foreshadow_chapters("proj-1"))

    assert result == set()


def test_load_unresolved_foreshadow_chapters_returns_planted_set():
    session = SimpleNamespace(execute=AsyncMock(return_value=_DummyResult(rows=[(3,), (17,), (None,)])))
    svc = HistoryContextService(session, SimpleNamespace(), SimpleNamespace())

    result = asyncio.run(svc._load_unresolved_foreshadow_chapters("proj-1"))

    assert result == {3, 17}


def test_skeleton_keeps_anchors_when_priority_chapters_flood():
    """伏笔章多于配额时只占 quota-2 席，首/尾锚点仍保留，骨架不失整体覆盖。"""
    chapters = [_make_completed(i) for i in range(1, 41)]

    skeleton = HistoryContextService.build_story_skeleton(
        chapters, current_chapter=41, priority_chapters={3, 5, 8, 12, 15, 18, 20}
    )

    assert skeleton is not None
    far_nums = [
        int(line.split("章")[0][1:])
        for line in skeleton.split("\n")
        if line.startswith("第") and int(line.split("章")[0][1:]) <= 30
    ]
    # 首/尾锚点保留
    assert 1 in far_nums and 30 in far_nums
    # 伏笔章最多 quota-2 席，总数不超配额
    assert len([n for n in far_nums if n in {3, 5, 8, 12, 15, 18, 20}]) <= SKELETON_FAR_QUOTA - 2
    assert len(far_nums) <= SKELETON_FAR_QUOTA


def test_backfill_total_timeout_falls_back(monkeypatch):
    """回填超总墙钟上限：不阻塞生成，未完成章走大纲/正文节选兜底进入上下文。"""
    import app.services.history_context_service as hcs

    monkeypatch.setattr(hcs, "SUMMARY_BACKFILL_TOTAL_TIMEOUT_SEC", 0.05)

    class _SlowLLM(_ConcurrencyTrackingLLM):
        async def get_summary(self, content, **kwargs):
            await asyncio.sleep(1.0)
            return "慢摘要"

    chapters = [
        SimpleNamespace(
            chapter_number=i,
            selected_version=SimpleNamespace(content=f"第{i}章正文内容，足够长的正文。"),
            real_summary=None,
        )
        for i in range(1, 9)
    ]
    prompt_service = SimpleNamespace(get_prompt=AsyncMock(return_value="extraction prompt"))
    session = _DummySession()
    svc = HistoryContextService(session, prompt_service, _SlowLLM())

    result = asyncio.run(
        svc.collect_history_context(
            project_id="proj-1",
            chapter_number=9,
            outlines_map={},
            chapters=chapters,
            user_id=1,
            allow_summary_backfill=True,
        )
    )

    # 摘要均未写入（全部超时），但所有章仍通过兜底进入上下文
    assert all(ch.real_summary is None for ch in chapters)
    nums = [c["chapter_number"] for c in result["completed_chapters"]]
    assert nums == list(range(1, 9))
