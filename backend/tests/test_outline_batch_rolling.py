"""Y3 批量大纲滚动摘要 + 批次数量核验回归。

覆盖 /chapters/regenerate-outlines 的 generate_fresh 分批路径：
1. 批次间滚动上下文携带前批「第N章：标题——摘要前30字」摘要行（不再只有标题）；
2. 累积超字符预算时更早批次退化为纯标题行（_build_rolling_outline_context 单元）；
3. 单批产出缺章时用缺失章号补问一次；仍缺则记 warning 留洞继续（不 500）。
"""
import asyncio
import json
import logging
from types import SimpleNamespace as NS

import app.models.user_quota  # noqa: F401  防 mapper KeyError
from app.api.routers import writer


# ---------------------------------------------------------------------------
# _build_rolling_outline_context 单元：字符预算与退化语义
# ---------------------------------------------------------------------------

def _entry(num, summary_len=30):
    full = f"第{num}章：T{num:03d}——" + "摘" * summary_len
    brief = f"第{num}章 - T{num:03d}"
    return (num, full, brief)


def test_rolling_context_under_budget_all_full():
    entries = [_entry(i) for i in range(1, 11)]
    lines = writer._build_rolling_outline_context(entries, char_budget=2000)
    assert len(lines) == 10
    assert all("——" in line for line in lines)
    # 保持章节号升序
    assert lines[0].startswith("第1章：") and lines[-1].startswith("第10章：")


def test_rolling_context_over_budget_older_degrade_to_titles():
    """超预算时：最近的条目保留摘要行，更早的一律退化为纯标题行。"""
    entries = [_entry(i) for i in range(1, 101)]  # 每条 full 约 40+ 字，总量远超 2000
    lines = writer._build_rolling_outline_context(entries, char_budget=2000)
    assert len(lines) == 100
    # 最近的条目（尾部）保留摘要行
    assert "——" in lines[-1]
    # 最早的条目退化为纯标题行
    assert lines[0] == "第1章 - T001"
    assert "——" not in lines[0]
    # 一旦退化，更早的条目不再回头保留摘要（前缀连续为标题行）
    first_full = next(i for i, line in enumerate(lines) if "——" in line)
    assert all("——" not in line for line in lines[:first_full])
    # 摘要行累积不超预算
    assert sum(len(line) for line in lines if "——" in line) <= 2000


# ---------------------------------------------------------------------------
# 端点级：分批生成的滚动上下文与补问语义
# ---------------------------------------------------------------------------

class _DummySession:
    def __init__(self):
        self.committed = 0

    async def commit(self):
        self.committed += 1


class _FakeNovelService:
    instances = []

    def __init__(self, session, project=None):
        self.session = session
        self.saved = []  # (chapter_number, title, summary)
        self.project = project if project is not None else NS(chapters=[], outlines=[])
        _FakeNovelService.instances.append(self)

    async def ensure_project_owner(self, project_id, user_id):
        return self.project

    async def _serialize_project(self, project):
        return NS(
            blueprint=NS(
                model_dump=lambda: {
                    "title": "测试蓝图",
                    "full_synopsis": "总纲",
                    "genre": "玄幻",
                }
            )
        )

    async def update_or_create_outline(self, project_id, chapter_number, title, summary, metadata=None):
        self.saved.append((chapter_number, title, summary))


class _FakePromptService:
    def __init__(self, session):
        pass

    async def get_prompt(self, name):
        return "大纲生成系统提示词"


class _FakeCacheService:
    async def invalidate_project_schema(self, project_id):
        pass


class _ScriptedLLM:
    """按调用顺序返回预置回包，并记录每次收到的 user prompt。"""

    responses: list = []
    calls: list = []

    def __init__(self, session):
        pass

    async def get_llm_response(self, system_prompt=None, conversation_history=None, **kwargs):
        _ScriptedLLM.calls.append(conversation_history[0]["content"])
        idx = len(_ScriptedLLM.calls) - 1
        if idx < len(_ScriptedLLM.responses):
            return _ScriptedLLM.responses[idx]
        return json.dumps({"chapters": []})


def _payload(nums, title=lambda n: f"T{n:03d}", summary=lambda n: f"S{n:03d}事件摘要内容"):
    return json.dumps(
        {"chapters": [
            {"chapter_number": n, "title": title(n), "summary": summary(n)} for n in nums
        ]},
        ensure_ascii=False,
    )


def _run_regen(monkeypatch, responses, total_chapters, project=None):
    _FakeNovelService.instances = []
    _ScriptedLLM.responses = list(responses)
    _ScriptedLLM.calls = []

    bound_project = project if project is not None else NS(chapters=[], outlines=[])

    class _BoundNovelService(_FakeNovelService):
        def __init__(self, session):
            super().__init__(session, project=bound_project)

    async def _fake_load_schema(service, project_id, user_id):
        return NS(blueprint=NS(chapter_outline=[]))

    monkeypatch.setattr(writer, "NovelService", _BoundNovelService)
    monkeypatch.setattr(writer, "PromptService", _FakePromptService)
    monkeypatch.setattr(writer, "LLMService", _ScriptedLLM)
    monkeypatch.setattr(writer, "CacheService", _FakeCacheService)
    monkeypatch.setattr(writer, "_load_project_schema", _fake_load_schema)

    request = NS(total_chapters=total_chapters, chapter_numbers=None)
    session = _DummySession()
    result = asyncio.run(
        writer.regenerate_chapter_outlines(
            "p1", request, session=session, current_user=NS(id=1)
        )
    )
    return _FakeNovelService.instances[0], session, result


def test_second_batch_prompt_contains_prior_batch_summaries(monkeypatch):
    """50 章 = 2 批：第二批 prompt 必须携带第一批的「第N章：标题——摘要前30字」行。"""
    service, session, result = _run_regen(
        monkeypatch,
        responses=[_payload(range(1, 26)), _payload(range(26, 51))],
        total_chapters=50,
    )

    assert len(_ScriptedLLM.calls) == 2
    second_prompt = _ScriptedLLM.calls[1]
    # 滚动上下文段存在，且是摘要行而非纯标题行
    assert "[前序批次已生成的章节大纲" in second_prompt
    assert "第1章：T001——S001事件摘要内容" in second_prompt
    assert "第25章：T025——S025事件摘要内容" in second_prompt
    # 第一批 prompt 不含滚动上下文段
    assert "[前序批次已生成的章节大纲" not in _ScriptedLLM.calls[0]
    # 两批全部落库
    assert sorted(result.updated_chapters) == list(range(1, 51))
    assert result.total_target == 50


def test_batch_shortfall_triggers_one_followup(monkeypatch, caplog):
    """单批缺 5 章：补问一次（复用该批上下文），补齐后总数完整；补问只允许落缺失章。"""
    # 补问回包夹带第 3 章（已生成过）的重写，必须被 allowed 过滤掉
    retry_payload = _payload([3, 21, 22, 23, 24, 25], title=lambda n: f"R{n:03d}")
    with caplog.at_level(logging.WARNING):
        service, session, result = _run_regen(
            monkeypatch,
            responses=[_payload(range(1, 21)), retry_payload],
            total_chapters=25,
        )

    assert len(_ScriptedLLM.calls) == 2
    followup_prompt = _ScriptedLLM.calls[1]
    assert "补齐" in followup_prompt
    assert "21、22、23、24、25" in followup_prompt
    # 补问 prompt 复用该批上下文（含生成任务段）
    assert "[生成任务]" in followup_prompt
    assert sorted(result.updated_chapters) == list(range(1, 26))
    # 第 3 章只落库一次（补问回包中的重写被过滤）
    ch3_writes = [s for s in service.saved if s[0] == 3]
    assert len(ch3_writes) == 1 and ch3_writes[0][1] == "T003"
    assert "缺章" in caplog.text
    assert "仍缺章" not in caplog.text


def test_batch_shortfall_gives_up_after_one_followup(monkeypatch, caplog):
    """补问仍缺：记 warning 留洞继续，端点正常返回（不 500、不二次补问）。"""
    with caplog.at_level(logging.WARNING):
        service, session, result = _run_regen(
            monkeypatch,
            responses=[_payload(range(1, 21)), json.dumps({"chapters": []})],
            total_chapters=25,
        )

    # 只补问一次，不无限重试
    assert len(_ScriptedLLM.calls) == 2
    assert sorted(result.updated_chapters) == list(range(1, 21))
    assert "仍缺章" in caplog.text
    assert session.committed >= 1


def test_batch_complete_no_followup(monkeypatch):
    """产出齐全时不触发补问（保持原单次调用行为）。"""
    service, session, result = _run_regen(
        monkeypatch,
        responses=[_payload(range(1, 26))],
        total_chapters=25,
    )
    assert len(_ScriptedLLM.calls) == 1
    assert sorted(result.updated_chapters) == list(range(1, 26))
