"""Y5 volumes 分卷接线到大纲生成回归。

覆盖：
1. `_build_volume_context` 单元：空/无效/不落卷 → ("", "")；命中卷 → 段落含当前卷
   name/arc_goal/climax_hint、相邻卷一句话、卷内位置（前段/中段/卷尾冲刺）；
2. `generate_chapters_outline`：有 volumes → prompt 含所属卷信息与卷内阶段；
   无 volumes → prompt 与改动前逐字一致（快照断言）；
3. `regenerate_chapter_outlines(generate_fresh)`：各批 prompt 含该批所属卷的分卷段、
   阶段提示为卷内位置；无 volumes 时不出现分卷段（既有行为不变）。
"""
import asyncio
import json
from types import SimpleNamespace as NS

import app.models.user_quota  # noqa: F401  防 mapper KeyError
from app.api.routers import writer


VOLS = [
    {"name": "崛起", "start_chapter": 1, "end_chapter": 40,
     "arc_goal": "少年入门修行", "climax_hint": "宗门大比夺魁"},
    {"name": "风云", "start_chapter": 41, "end_chapter": 100,
     "arc_goal": "闯荡外界结仇魔宗", "climax_hint": "斩杀魔宗圣子"},
    {"name": "登天", "start_chapter": 101, "end_chapter": 160,
     "arc_goal": "问鼎天下巅峰", "climax_hint": "终战天帝"},
]


# ---------------------------------------------------------------------------
# _build_volume_context 单元
# ---------------------------------------------------------------------------

def test_volume_context_empty_returns_blank():
    assert writer._build_volume_context([], 1, 5) == ("", "")


def test_volume_context_invalid_entries_returns_blank():
    bad = [{"name": "坏卷", "start_chapter": "x", "end_chapter": 10},
           {"name": "倒挂", "start_chapter": 10, "end_chapter": 3},
           "not-a-dict"]
    assert writer._build_volume_context(bad, 1, 5) == ("", "")


def test_volume_context_out_of_range_returns_blank():
    assert writer._build_volume_context(VOLS, 200, 210) == ("", "")


def test_volume_context_front_stage_with_neighbors():
    section, phase = writer._build_volume_context(VOLS, 41, 50)
    assert "[分卷规划]" in section
    assert "当前卷：「风云」（第 41 ~ 100 章）" in section
    assert "卷目标：闯荡外界结仇魔宗" in section
    assert "卷高潮：斩杀魔宗圣子" in section
    # 相邻卷一句话
    assert "上一卷：「崛起」（第 1 ~ 40 章）：少年入门修行" in section
    assert "下一卷：「登天」（第 101 ~ 160 章）：问鼎天下巅峰" in section
    # 卷内阶段：41-50 在 41-100 卷的前 1/6 → 前段
    assert "本批卷内位置：前段" in section
    assert "前段" in phase and "「风云」" in phase


def test_volume_context_mid_and_tail_stages():
    # 15-25 在 1-40 卷中（25/40=0.625）→ 中段
    _, mid_phase = writer._build_volume_context(VOLS, 15, 25)
    assert "中段" in mid_phase
    # 31-40 抵达卷尾（40/40=1.0）→ 卷尾冲刺，非末卷提示为下一卷留钩子
    _, tail_phase = writer._build_volume_context(VOLS, 31, 40)
    assert "卷尾冲刺" in tail_phase and "下一卷" in tail_phase
    # 末卷卷尾不再提「下一卷」
    last_section, last_phase = writer._build_volume_context(VOLS, 141, 160)
    assert "卷尾冲刺" in last_phase
    assert "下一卷" not in last_phase
    assert "下一卷" not in last_section


# ---------------------------------------------------------------------------
# 端点级公共桩（模式复用 test_outline_batch_rolling.py）
# ---------------------------------------------------------------------------

class _DummySession:
    def __init__(self):
        self.committed = 0

    async def commit(self):
        self.committed += 1


class _FakePromptService:
    def __init__(self, session):
        pass

    async def get_prompt(self, name):
        return "大纲生成系统提示词"


class _FakeCacheService:
    async def invalidate_project_schema(self, project_id):
        pass


class _ScriptedLLM:
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


def _payload(nums):
    return json.dumps(
        {"chapters": [
            {"chapter_number": n, "title": f"T{n:03d}", "summary": f"S{n:03d}事件摘要内容"}
            for n in nums
        ]},
        ensure_ascii=False,
    )


def _install_fakes(monkeypatch, blueprint_dict, project):
    class _FakeNovelService:
        def __init__(self, session):
            self.session = session

        async def ensure_project_owner(self, project_id, user_id):
            return project

        async def _serialize_project(self, p):
            return NS(blueprint=NS(model_dump=lambda: dict(blueprint_dict)))

        async def update_or_create_outline(self, project_id, chapter_number, title, summary, metadata=None):
            pass

    async def _fake_load_schema(service, project_id, user_id):
        return NS(blueprint=NS(chapter_outline=[]))

    monkeypatch.setattr(writer, "NovelService", _FakeNovelService)
    monkeypatch.setattr(writer, "PromptService", _FakePromptService)
    monkeypatch.setattr(writer, "LLMService", _ScriptedLLM)
    monkeypatch.setattr(writer, "CacheService", _FakeCacheService)
    monkeypatch.setattr(writer, "_load_project_schema", _fake_load_schema)


def _run_generate(monkeypatch, blueprint_dict, start_chapter=1, num_chapters=5,
                  estimated_total_chapters=None):
    _ScriptedLLM.responses = [_payload(range(start_chapter, start_chapter + num_chapters))]
    _ScriptedLLM.calls = []
    _install_fakes(monkeypatch, blueprint_dict, NS(outlines=[], chapters=[]))
    request = NS(
        start_chapter=start_chapter,
        num_chapters=num_chapters,
        estimated_total_chapters=estimated_total_chapters,
        user_prompt=None,
    )
    asyncio.run(
        writer.generate_chapters_outline(
            "p1", request, session=_DummySession(), current_user=NS(id=1)
        )
    )
    return _ScriptedLLM.calls[0]


def _run_regen_fresh(monkeypatch, blueprint_dict, total_chapters, responses):
    _ScriptedLLM.responses = list(responses)
    _ScriptedLLM.calls = []
    _install_fakes(monkeypatch, blueprint_dict, NS(outlines=[], chapters=[]))
    request = NS(total_chapters=total_chapters, chapter_numbers=None)
    asyncio.run(
        writer.regenerate_chapter_outlines(
            "p1", request, session=_DummySession(), current_user=NS(id=1)
        )
    )
    return list(_ScriptedLLM.calls)


# ---------------------------------------------------------------------------
# generate_chapters_outline
# ---------------------------------------------------------------------------

def _expected_prompt_without_volumes(blueprint_text):
    """无 volumes 时的完整 prompt 快照（与改动前的模板逐字一致）。"""
    progress_context = """
[故事进度信息（重要！）]
- 预计总章节数：100 章
- 本次生成范围：第 1 章 ~ 第 5 章
- 当前进度：约 5.0%
- 当前所处阶段：开篇期（前20%）——应着重世界观铺设、角色登场、主线冲突引入
- ⚠️ 严禁在本批次安排故事结局！必须持续展开新事件和冲突，以「未完待续」的悬念结束本批次。
"""
    return f"""
[世界蓝图]
{blueprint_text}

[已有章节大纲]
暂无
{progress_context}
[生成任务]
请从第 1 章开始，续写接下来的 5 章的大纲。
这些章节只是整部小说（预计100章）的一小部分，不要试图在这5章内讲完整个故事！
要求返回 JSON 格式，包含一个 chapters 数组，每个元素包含 chapter_number, title, summary。
"""


def test_generate_outline_without_volumes_prompt_snapshot(monkeypatch):
    """无 volumes（含 volumes 键缺失/空列表）→ prompt 与改动前逐字一致。"""
    for bp in ({"title": "测试蓝图", "genre": "玄幻"},
               {"title": "测试蓝图", "genre": "玄幻", "volumes": []}):
        # 端点会把 volumes 从 [世界蓝图] JSON 中剔除（分卷信息由 [分卷规划] 段专门承载，
        # 也保证旧蓝图 prompt 与 schema 加字段前逐字一致）——期望文本按剔除后计算
        stripped = {k: v for k, v in bp.items() if k != "volumes"}
        blueprint_text = json.dumps(stripped, ensure_ascii=False, indent=2)
        prompt = _run_generate(monkeypatch, bp, start_chapter=1, num_chapters=5,
                               estimated_total_chapters=100)
        assert prompt == _expected_prompt_without_volumes(blueprint_text)
        assert "[分卷规划]" not in prompt
        assert '"volumes"' not in prompt


def test_generate_outline_with_volumes_injects_section_and_stage(monkeypatch):
    bp = {"title": "测试蓝图", "genre": "玄幻", "volumes": VOLS}
    prompt = _run_generate(monkeypatch, bp, start_chapter=1, num_chapters=5,
                           estimated_total_chapters=160)
    # 分卷规划段：所属卷 + 相邻卷
    assert "[分卷规划]" in prompt
    assert "当前卷：「崛起」（第 1 ~ 40 章）" in prompt
    assert "卷目标：少年入门修行" in prompt
    assert "卷高潮：宗门大比夺魁" in prompt
    assert "下一卷：「风云」" in prompt
    # 进度阶段从全书百分比改为卷内位置（1-5 章在 1-40 卷 → 前段）
    assert "当前所处阶段：本批章节处于本卷「崛起」的前段" in prompt
    assert "开篇期（前20%）" not in prompt
    # 全书进度与防结局约束仍保留
    assert "当前进度：约 3.1%" in prompt
    assert "严禁在本批次安排故事结局" in prompt


def test_generate_outline_with_volumes_but_out_of_range_falls_back(monkeypatch):
    """批次章号不落任何卷 → 与无 volumes 行为一致（不注入分卷段，阶段回退百分比）。"""
    bp = {"title": "测试蓝图", "genre": "玄幻", "volumes": VOLS}
    prompt = _run_generate(monkeypatch, bp, start_chapter=200, num_chapters=5,
                           estimated_total_chapters=300)
    assert "[分卷规划]" not in prompt
    assert "发展期（20%-70%）" in prompt


# ---------------------------------------------------------------------------
# regenerate_chapter_outlines(generate_fresh) 分批路径
# ---------------------------------------------------------------------------

def test_regen_fresh_batches_carry_per_batch_volume_section(monkeypatch):
    """50 章 = 2 批：各批 prompt 注入该批所属卷的分卷段，阶段提示为卷内位置。"""
    bp = {"title": "测试蓝图", "genre": "玄幻", "full_synopsis": "总纲", "volumes": VOLS}
    calls = _run_regen_fresh(
        monkeypatch, bp, total_chapters=50,
        responses=[_payload(range(1, 26)), _payload(range(26, 51))],
    )
    assert len(calls) == 2
    # 第一批 1-25 属「崛起」(1-40)，25/40=0.625 → 中段
    assert "当前卷：「崛起」（第 1 ~ 40 章）" in calls[0]
    assert "本批章节处于本卷「崛起」的中段" in calls[0]
    assert "下一卷：「风云」" in calls[0]
    # 第二批 26-50 起始仍在「崛起」，50/40>0.8 → 卷尾冲刺
    assert "当前卷：「崛起」（第 1 ~ 40 章）" in calls[1]
    assert "本批章节处于本卷「崛起」的卷尾冲刺" in calls[1]
    # 阶段提示不再是全书百分比文案（50 章预计总数下原为发展期）
    for prompt in calls:
        assert "当前处于开篇期" not in prompt
        assert "当前处于发展期" not in prompt


def test_regen_fresh_without_volumes_no_volume_section(monkeypatch):
    """无 volumes → 不出现分卷段，阶段提示保持全书百分比（既有行为）。"""
    bp = {"title": "测试蓝图", "genre": "玄幻", "full_synopsis": "总纲"}
    calls = _run_regen_fresh(
        monkeypatch, bp, total_chapters=25,
        responses=[_payload(range(1, 26))],
    )
    assert len(calls) == 1
    assert "[分卷规划]" not in calls[0]
    # 25/25=100% → 收束期文案（改动前行为）
    assert "当前处于收束期" in calls[0]
