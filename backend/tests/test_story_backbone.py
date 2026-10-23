"""故事骨架（story_backbone_service）回归。

锁定的契约：
- 分卷预切：卷数 3-6、区间首尾相接覆盖 1..total、第一卷短；
- 篇幅估算：从立项书取最大的合理「N 章」，忽略「前 10/50 章」承诺，找不到回默认 300；
- normalize_backbone：卷序/章号/埋设窗口全部落回合法范围，缺卷补空节点，多卷丢弃；
- pending_setups_for_range 只取窗口与区间相交的条目；
- ensure_backbone 幂等；立项书变动自动重算；作者改过的骨架不自动重算且响应 stale；
- 重算保留作者改过的块；LLM 失败软失败；平台开关关闭不调 LLM；
- patch_backbone 分块合并 + 标记 edited_blocks。
"""
import json

import pytest

from app.models.novel import NovelProject
from app.models.user import User
from app.schemas.concept_dossier import ClimaxNode, SetupRequirement, StoryBackbone
from app.services.llm_service import LLMService
from app.services.prompt_service import PromptService
from app.services.story_backbone_service import (
    StoryBackboneService,
    climaxes_in_range,
    dossier_hash,
    estimate_total_chapters,
    format_backbone_for_prompt,
    normalize_backbone,
    pending_setups_for_range,
    precut_volumes,
)

PROJECT_ID = "backbone-proj-1"


# ---------------------------------------------------------------------------
# 纯函数层
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("total,expected_count", [(30, 3), (80, 3), (120, 4), (300, 5), (800, 6)])
def test_precut_volumes_count_and_coverage(total, expected_count):
    ranges = precut_volumes(total)
    assert len(ranges) == expected_count
    assert ranges[0][0] == 1 and ranges[-1][1] == total
    for (s1, e1), (s2, _) in zip(ranges, ranges[1:]):
        assert e1 + 1 == s2 and s1 <= e1
    # 第一卷短：不超过其余卷的均长
    first_len = ranges[0][1]
    rest_avg = (total - first_len) / (expected_count - 1)
    assert first_len <= rest_avg + 1


def test_estimate_total_chapters_prefers_largest_and_ignores_promises():
    dossier = {
        "notes": "作者希望写 600 章左右的长篇",
        "anticipation": {"ten_chapters": "前 10 章打脸", "fifty_chapters": "前 50 章翻案", "long_term": "最终 600 章决战"},
    }
    assert estimate_total_chapters(dossier) == 600
    assert estimate_total_chapters({"notes": "没提篇幅"}) == 300
    assert estimate_total_chapters({"notes": "前 10 章要爽"}) == 300  # 10 低于下限


def _setup(name, plant_from, plant_to, tier="核心"):
    return SetupRequirement(name=name, plant_from=plant_from, plant_to=plant_to, tier=tier,
                            what_must_be_established=f"读者见过{name}")


def test_normalize_backbone_clamps_everything():
    ranges = [(1, 20), (21, 60), (61, 100)]
    raw = StoryBackbone(
        total_chapters=999,
        first_promise=ClimaxNode(chapter=30, event="第一次打脸", setups=[_setup("旧伤", 1, 40)]),
        climaxes=[
            ClimaxNode(volume_index=2, chapter=10, event="卷二高潮", setups=[_setup("地契", 50, 70), _setup("", 1, 2)]),
            ClimaxNode(volume_index=1, chapter=19, event="卷一高潮", setups=[_setup("师父", 1, 19, tier="随便")]),
            ClimaxNode(volume_index=9, chapter=5, event="多余卷"),
        ],
        midpoint=ClimaxNode(chapter=2, event="中点翻案", setups=[_setup("身份", 1, 99)]),
    )
    bb = normalize_backbone(raw, ranges)
    assert bb.total_chapters == 100
    assert [n.volume_index for n in bb.climaxes] == [1, 2, 3]
    # 卷二高潮 10 落在卷外 → 回到卷内下限 21+3
    assert bb.climaxes[1].chapter == 24
    # 窗口裁到高潮章-3；空名条目丢弃
    assert [(s.plant_from, s.plant_to) for s in bb.climaxes[1].setups] == [(21, 21)]
    assert bb.climaxes[0].chapter == 19
    assert bb.climaxes[0].setups[0].plant_to == 16 and bb.climaxes[0].setups[0].tier == "支线"
    # 缺的卷补空节点
    assert bb.climaxes[2].event == "" and bb.climaxes[2].chapter == 100
    # 第一次兑现 ≤ 12，窗口随之裁
    assert bb.first_promise.chapter == 12 and bb.first_promise.setups[0].plant_to == 9
    # 中点落在 35%-65%
    assert 35 <= bb.midpoint.chapter <= 65


def test_normalize_drops_empty_midpoint():
    bb = normalize_backbone(StoryBackbone(midpoint=ClimaxNode(chapter=50, event="")), [(1, 100)])
    assert bb.midpoint is None


def _sample_backbone():
    return normalize_backbone(StoryBackbone(
        total_chapters=100,
        endgame={"final_confrontation": "剑冢决战", "core_answer": "规则改了", "setups": [_setup("剑冢", 10, 60)]},
        first_promise=ClimaxNode(chapter=8, event="拍卖会打脸", setups=[_setup("账本", 1, 4)]),
        midpoint=ClimaxNode(chapter=50, event="身份反转", setups=[_setup("胎记", 20, 40)]),
        climaxes=[
            ClimaxNode(volume_index=1, chapter=20, event="卷一高潮", setups=[_setup("旧伤", 2, 10)]),
            ClimaxNode(volume_index=2, chapter=60, event="卷二高潮", setups=[_setup("地契", 25, 50)]),
            ClimaxNode(volume_index=3, chapter=100, event="卷三高潮", setups=[_setup("血脉", 70, 90)]),
        ],
    ), [(1, 20), (21, 60), (61, 100)])


def test_pending_setups_for_range_and_climaxes_in_range():
    bb = _sample_backbone()
    names = [s.name for s, _ in pending_setups_for_range(bb, 1, 10)]
    assert names == ["账本", "旧伤", "剑冢"]  # 终局前置条件窗口从第 10 章起，与区间相交
    pairs = [(s.name, c) for s, c in pending_setups_for_range(bb, 26, 50)]
    assert ("地契", 60) in pairs and ("胎记", 50) in pairs and ("剑冢", 100) in pairs
    assert ("血脉", 100) not in pairs
    assert [n.chapter for n in climaxes_in_range(bb, 1, 25)] == [8, 20]
    assert pending_setups_for_range(None, 1, 10) == []


def test_format_backbone_for_prompt_sections():
    text = format_backbone_for_prompt(_sample_backbone())
    assert "【故事骨架】" in text and "终局：剑冢决战" in text
    assert "第 1 卷" in text and "前置条件「旧伤」" in text and "第 2-10 章之间埋设" in text
    assert "中点翻案" in text
    assert format_backbone_for_prompt(None) == ""
    assert "前置条件" not in format_backbone_for_prompt(_sample_backbone(), with_setups=False)


# ---------------------------------------------------------------------------
# 服务层
# ---------------------------------------------------------------------------

async def _seed_project(db_session, *, with_dossier=True):
    user = User(id=9, username="u9", hashed_password="x")
    project = NovelProject(id=PROJECT_ID, user_id=9, title="未命名灵感")
    if with_dossier:
        project.concept_dossier = {
            "dossier": {"core_selling_line": "当铺文", "notes": "写 100 章"},
            "stress_report": {"toxic_points": [{"issue": "爽点太迟", "severity": "高危", "reason": "x"}]},
        }
    db_session.add_all([user, project])
    await db_session.commit()
    return project


def _patch_prompts(monkeypatch):
    async def fake_get_prompt(self, name):
        return f"SYSTEM-{name}"

    monkeypatch.setattr(PromptService, "get_prompt", fake_get_prompt)


def _fake_llm(monkeypatch, calls, *, event="卷一高潮"):
    async def fake_generate_structured(self, *, prompt, schema, **kwargs):
        calls.append(prompt)
        assert schema is StoryBackbone
        return StoryBackbone(
            endgame={"final_confrontation": "终局一战"},
            first_promise=ClimaxNode(chapter=8, event="第一次打脸"),
            climaxes=[
                ClimaxNode(volume_index=1, chapter=15, event=event, setups=[_setup("旧伤", 1, 10)]),
                ClimaxNode(volume_index=2, chapter=50, event="卷二高潮"),
                ClimaxNode(volume_index=3, chapter=99, event="卷三高潮"),
                ClimaxNode(volume_index=4, chapter=100, event="卷四高潮"),
            ],
        )

    monkeypatch.setattr(LLMService, "generate_structured", fake_generate_structured)


@pytest.mark.asyncio
async def test_ensure_backbone_generates_once_and_prompt_carries_context(db_session, monkeypatch):
    await _seed_project(db_session)
    _patch_prompts(monkeypatch)
    calls = []
    _fake_llm(monkeypatch, calls)

    service = StoryBackboneService(db_session)
    state = await service.ensure_backbone(PROJECT_ID, 9)
    assert len(calls) == 1
    prompt = calls[0]
    assert "当铺文" in prompt and "爽点太迟" in prompt
    assert "全书预计 100 章，分 4 卷" in prompt  # notes 里的 100 章被采用（≤200 → 4 卷）

    backbone = service.read_backbone(state)
    assert backbone is not None and backbone.total_chapters == 100
    assert [n.volume_index for n in backbone.climaxes] == [1, 2, 3, 4]
    meta = state["backbone_meta"]
    assert meta["source_hash"] == dossier_hash(state["dossier"])
    assert meta["revised_by_author"] is False and len(meta["ranges"]) == 4

    # 幂等
    await service.ensure_backbone(PROJECT_ID, 9)
    assert len(calls) == 1
    project = await db_session.get(NovelProject, PROJECT_ID)
    assert isinstance(project.concept_dossier["backbone"], dict)


@pytest.mark.asyncio
async def test_dossier_change_regenerates_unless_author_revised(db_session, monkeypatch):
    project = await _seed_project(db_session)
    _patch_prompts(monkeypatch)
    calls = []
    _fake_llm(monkeypatch, calls)
    service = StoryBackboneService(db_session)
    await service.ensure_backbone(PROJECT_ID, 9)

    # 立项书改了 → 自动重算
    state = dict(project.concept_dossier)
    state["dossier"] = {**state["dossier"], "core_selling_line": "新卖点"}
    project.concept_dossier = state
    await db_session.commit()
    assert service.is_stale(service.get_state(project))
    await service.ensure_backbone(PROJECT_ID, 9)
    assert len(calls) == 2
    assert not service.is_stale(service.get_state(project))

    # 作者改过 → 立项书再改也不自动重算，只标 stale
    await service.patch_backbone(project, {"endgame": {"final_confrontation": "作者定的终局"}})
    state = dict(project.concept_dossier)
    state["dossier"] = {**state["dossier"], "core_selling_line": "又改了"}
    project.concept_dossier = state
    await db_session.commit()
    await service.ensure_backbone(PROJECT_ID, 9)
    assert len(calls) == 2
    assert service.is_stale(service.get_state(project))

    # 显式重算：作者改过的块保留
    await service.ensure_backbone(PROJECT_ID, 9, force=True)
    assert len(calls) == 3
    backbone = service.read_backbone(service.get_state(project))
    assert backbone.endgame.final_confrontation == "作者定的终局"
    assert backbone.climaxes[0].event == "卷一高潮"


@pytest.mark.asyncio
async def test_patch_backbone_merges_blocks_and_marks_edits(db_session, monkeypatch):
    project = await _seed_project(db_session)
    _patch_prompts(monkeypatch)
    calls = []
    _fake_llm(monkeypatch, calls)
    service = StoryBackboneService(db_session)
    await service.ensure_backbone(PROJECT_ID, 9)

    state = await service.patch_backbone(project, {
        "climaxes": {"2": {"event": "作者改的卷二", "chapter": 999}, "7": {"event": "无此卷"}},
        "first_promise": {"cost": "丢了半条命"},
        "unknown_block": {"x": 1},
    })
    backbone = service.read_backbone(state)
    assert backbone.climaxes[1].event == "作者改的卷二"
    assert backbone.climaxes[1].chapter <= 100  # PATCH 后仍归一化到卷内
    assert backbone.climaxes[0].event == "卷一高潮"
    assert backbone.first_promise.cost == "丢了半条命" and backbone.first_promise.event == "第一次打脸"
    meta = state["backbone_meta"]
    assert meta["revised_by_author"] is True
    assert sorted(meta["edited_blocks"]) == ["climaxes.2", "first_promise"]

    with pytest.raises(ValueError):
        await service.patch_backbone(project, {"endgame": {"setups": "not-a-list"}})


@pytest.mark.asyncio
async def test_patch_without_backbone_raises(db_session):
    project = await _seed_project(db_session)
    with pytest.raises(ValueError):
        await StoryBackboneService(db_session).patch_backbone(project, {"endgame": {}})


@pytest.mark.asyncio
async def test_ensure_backbone_soft_fails_and_respects_switch(db_session, monkeypatch):
    from app.models.system_config import SystemConfig

    project = await _seed_project(db_session)
    _patch_prompts(monkeypatch)

    async def broken(self, **kwargs):
        raise RuntimeError("upstream 503")

    monkeypatch.setattr(LLMService, "generate_structured", broken)
    state = await StoryBackboneService(db_session).ensure_backbone(PROJECT_ID, 9)
    assert "backbone" not in state
    assert "dossier" in project.concept_dossier  # 立项书不受影响

    calls = []
    _fake_llm(monkeypatch, calls)
    db_session.add(SystemConfig(key="blueprint.backbone_enabled", value="false"))
    await db_session.commit()
    state = await StoryBackboneService(db_session).ensure_backbone(PROJECT_ID, 9)
    assert calls == [] and "backbone" not in state


@pytest.mark.asyncio
async def test_ensure_backbone_without_dossier_noop(db_session, monkeypatch):
    await _seed_project(db_session, with_dossier=False)
    _patch_prompts(monkeypatch)

    async def should_not_call(self, **kwargs):  # pragma: no cover
        raise AssertionError("无立项书不应调用 LLM")

    monkeypatch.setattr(LLMService, "generate_structured", should_not_call)
    state = await StoryBackboneService(db_session).ensure_backbone(PROJECT_ID, 9)
    assert "backbone" not in state


@pytest.mark.asyncio
async def test_background_dossier_chain_triggers_backbone(db_session, monkeypatch):
    """立项书后台链在蒸馏完成后接着跑骨架。"""
    from app.services import concept_dossier_service as cds
    from app.services import story_backbone_service as sbs

    seen = []

    class _FakeDossierService:
        def __init__(self, session):
            pass

        async def ensure_dossier(self, project_id, user_id, *, run_stress):
            return {"dossier": {"core_selling_line": "x"}}

    async def fake_backbone(project_id, user_id):
        seen.append((project_id, user_id))

    class _Ctx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(cds, "ConceptDossierService", _FakeDossierService)
    monkeypatch.setattr(sbs, "background_ensure_backbone", fake_backbone)
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", lambda: _Ctx())
    await cds.background_ensure_dossier("p1", 3, run_stress=False)
    assert seen == [("p1", 3)]


def test_backbone_json_roundtrip_through_state():
    bb = _sample_backbone()
    state = {"backbone": json.loads(json.dumps(bb.model_dump()))}
    assert StoryBackboneService.read_backbone(state).model_dump() == bb.model_dump()
    assert StoryBackboneService.read_backbone({"backbone": "garbage"}) is None


# ---------------------------------------------------------------------------
# 阶段二：与设定段对账 / 章纲回填覆盖
# ---------------------------------------------------------------------------

def test_reconcile_settings_with_backbone_rewrites_volumes_and_adds_setups():
    from app.services.story_backbone_service import reconcile_settings_with_backbone

    bb = _sample_backbone()
    ranges = [(1, 20), (21, 60), (61, 100)]
    settings = {
        "volumes": [
            {"name": "卷一·当铺", "start_chapter": 1, "end_chapter": 120, "arc_goal": "立足", "climax_hint": "模型写的"},
            {"name": "卷二", "start_chapter": 121, "end_chapter": 260, "arc_goal": "扩张", "climax_hint": ""},
            {"name": "卷三", "start_chapter": 261, "end_chapter": 400, "arc_goal": "终局", "climax_hint": ""},
        ],
        "foreshadowings": [
            {"name": "「旧伤」", "planted_chapter": 3, "target_chapter": 20},  # 归一化后与骨架同名 → 不重复补
            {"name": "模型自己的伏笔", "planted_chapter": 5, "target_chapter": 30},
        ],
    }
    stats = reconcile_settings_with_backbone(settings, bb, ranges)
    assert stats["volumes_rewritten"] == 1
    vols = settings["volumes"]
    assert [(v["start_chapter"], v["end_chapter"]) for v in vols] == ranges
    assert vols[0]["name"] == "卷一·当铺" and vols[0]["arc_goal"] == "立足"  # 卷数一致时保留模型卷名/目标
    assert vols[0]["climax_hint"] == "卷一高潮" and vols[0]["climax"]["chapter"] == 20
    names = [f["name"] for f in settings["foreshadowings"]]
    assert "「旧伤」" in names and "模型自己的伏笔" in names
    # 账本/地契/血脉/胎记/剑冢 由代码补入；旧伤已存在
    assert stats["setups_added"] == 5
    added = {f["name"]: f for f in settings["foreshadowings"]}
    assert added["账本"]["planted_chapter"] == 1 and added["账本"]["target_chapter"] == 8
    assert added["剑冢"]["target_chapter"] == 100 and added["剑冢"]["type"] == "setup"


def test_reconcile_with_mismatched_volume_count_names_from_theme():
    from app.services.story_backbone_service import reconcile_settings_with_backbone

    bb = _sample_backbone()
    bb.climaxes[0].volume_theme = "当铺立足"
    settings = {"volumes": [{"name": "只有一卷", "start_chapter": 1, "end_chapter": 100}], "foreshadowings": []}
    reconcile_settings_with_backbone(settings, bb, [(1, 20), (21, 60), (61, 100)])
    assert settings["volumes"][0]["name"] == "第1卷·当铺立足"
    assert len(settings["volumes"]) == 3


def _item(n, summary="", ops=None):
    item = {"chapter_number": n, "title": f"第{n}章", "summary": summary}
    if ops is not None:
        item["planning"] = {"foreshadowing_ops": ops}
    return item


def test_setup_coverage_ops_and_summary_fallback():
    from app.services.story_backbone_service import setup_coverage

    bb = _sample_backbone()
    items = [
        _item(2, "读者见过账本", ops=[{"op": "plant", "name": "账 本"}]),   # ops 命中（名称归一化）
        _item(5, "他避开左肩，没人解释旧伤"),                              # 无 ops → 摘要提名退化命中
        _item(8, "拍卖会打脸", ops=[{"op": "payoff", "name": "账本"}]),
        _item(20, "卷一高潮"),                                            # 旧伤高潮章无 ops，摘要未提 → 无兑现
    ]
    report = setup_coverage(bb, items, limit_chapter=25)
    by = {e.name: e for e in report.entries}
    assert by["账本"].planted and by["账本"].via == "ops" and by["账本"].payoff
    assert by["旧伤"].planted and by["旧伤"].via == "summary" and not by["旧伤"].payoff
    # 窗口起点 > 25 的条目不计入；地契 25-50 起点 ≤25 计入且未埋
    assert "血脉" not in by and "地契" in by and not by["地契"].planted
    assert report.total == 5 and report.planted == 2  # 账本/胎记(20-40)/旧伤/地契/剑冢(10-60)
    assert [e.name for e in report.missing(core_only=True)] == ["胎记", "地契", "剑冢"]
    text = report.to_prompt()
    assert "已埋 2/5" in text and "「地契」" in text and "未埋" in text
    assert setup_coverage(None, items) is None


# ---------------------------------------------------------------------------
# 阶段三：续排约束 / 宪法防剧透 / 卷复盘输入
# ---------------------------------------------------------------------------

def test_format_backbone_batch_constraints_only_intersecting():
    from app.services.story_backbone_service import format_backbone_batch_constraints

    bb = _sample_backbone()
    text = format_backbone_batch_constraints(bb, 1, 10)
    assert "本批必须埋下的前置条件" in text
    assert "「账本」[核心]（第 1-4 章之间）" in text and "服务于第 8 章" in text
    assert "「旧伤」[核心]（第 2-10 章之间）" in text
    assert "「剑冢」[核心]（第 10-10 章之间）" in text  # 窗口 10-60 被裁到本批
    assert "「血脉」" not in text
    assert "本批内要兑现的高潮" in text and "第 8 章 第一次兑现：拍卖会打脸" in text
    assert "第 20 章 第 1 卷高潮" not in text
    assert format_backbone_batch_constraints(None, 1, 10) == ""
    assert format_backbone_batch_constraints(bb, 91, 95) == ""  # 没有窗口/高潮落在 91-95


def test_format_backbone_batch_constraints_edge_window():
    from app.services.story_backbone_service import format_backbone_batch_constraints

    bb = _sample_backbone()
    text = format_backbone_batch_constraints(bb, 88, 92)
    assert "「血脉」[核心]（第 88-90 章之间）" in text


def test_spoiler_guards_from_backbone():
    from app.services.constitution_seed_service import build_forbidden_content
    from app.services.story_backbone_service import spoiler_guards

    bb = _sample_backbone()
    bb.climaxes[1].reversal = "师父其实是凶手"
    bb.midpoint.reversal = "主角不是陈家血脉"
    guards = spoiler_guards(bb)
    assert "防剧透：第 60 章之前不得揭示「师父其实是凶手」" in guards
    assert "防剧透：第 50 章之前不得揭示「主角不是陈家血脉」" in guards
    assert any(g.startswith("防剧透：终局前不得提前交代「规则改了」") for g in guards)
    assert spoiler_guards(None) == []

    items = build_forbidden_content(exclusions="不写虐恋", stress_report=None, genre="仙侠", backbone=bb)
    assert items[0] == "用户禁区：不写虐恋"
    assert any("师父其实是凶手" in i for i in items)
    assert any("越级战斗" in i for i in items)  # 题材禁忌仍在


def test_writer_build_volume_context_shows_climax_node():
    from app.api.routers.writer import _build_volume_context

    volumes = [
        {"name": "卷一", "start_chapter": 1, "end_chapter": 20, "arc_goal": "立足", "climax_hint": "翻案",
         "climax": {"chapter": 20, "event": "当众翻案", "reversal": "掌门是赝品", "cost": "断一指"}},
        {"name": "卷二", "start_chapter": 21, "end_chapter": 60},
    ]
    section, _ = _build_volume_context(volumes, 15, 20)
    assert "骨架高潮节点（第 20 章）：当众翻案" in section
    assert "· 翻转：掌门是赝品" in section and "· 代价：断一指" in section
    section2, _ = _build_volume_context([{"name": "卷", "start_chapter": 1, "end_chapter": 9}], 1, 5)
    assert "骨架高潮节点" not in section2


def test_writer_build_backbone_section_reads_project_state():
    from types import SimpleNamespace as NS

    from app.api.routers.writer import _build_backbone_section

    bb = _sample_backbone()
    project = NS(concept_dossier={"backbone": bb.model_dump()})
    assert "「账本」" in _build_backbone_section(project, 1, 5)
    assert _build_backbone_section(NS(), 1, 5) == ""
    assert _build_backbone_section(NS(concept_dossier={"backbone": "bad"}), 1, 5) == ""


def test_retrospective_input_includes_climax_node():
    from app.services.volume_retrospective_service import _build_retrospective_input

    current = {"name": "卷一", "start_chapter": 1, "end_chapter": 20, "arc_goal": "立足", "climax_hint": "翻案",
               "climax": {"chapter": 20, "event": "当众翻案", "cost": "断一指"}}
    nxt = {"name": "卷二", "start_chapter": 21, "end_chapter": 60}
    text = _build_retrospective_input(current, nxt, "实际写成……")
    assert "骨架高潮（第20章）：当众翻案" in text and "代价：断一指" in text
    assert text.count("骨架高潮") == 1  # 下一卷无节点不输出


# ---------------------------------------------------------------------------
# 阶段四：备选终局
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alternatives_generate_store_and_apply(db_session, monkeypatch):
    from app.schemas.concept_dossier import BackboneAlternative, BackboneAlternativeSet

    project = await _seed_project(db_session)
    _patch_prompts(monkeypatch)
    prompts = []

    async def fake_generate_structured(self, *, prompt, schema, **kwargs):
        prompts.append((schema.__name__, prompt))
        if schema is BackboneAlternativeSet:
            return BackboneAlternativeSet(alternatives=[
                BackboneAlternative(label="弑师证道", endgame={"final_confrontation": "剑冢弑师", "core_answer": "规则由我定"},
                                    climax_events=["a1", "a2", "a3", "a4", "多出来的"], why_different="答案不同"),
                BackboneAlternative(label="空终局", endgame={"final_confrontation": ""}),  # 无终局丢弃
            ])
        event = "弑师线卷一高潮" if any("作者选定的终局方向" in p for _, p in prompts[-1:]) else "卷一高潮"
        return StoryBackbone(
            endgame={"final_confrontation": "终局一战"},
            first_promise=ClimaxNode(chapter=8, event="第一次打脸"),
            climaxes=[ClimaxNode(volume_index=i, chapter=c, event=event if i == 1 else f"卷{i}")
                      for i, c in ((1, 15), (2, 50), (3, 75), (4, 100))],
        )

    monkeypatch.setattr(LLMService, "generate_structured", fake_generate_structured)
    service = StoryBackboneService(db_session)
    assert await service.generate_alternatives(project, 9) == []  # 还没有骨架
    await service.ensure_backbone(PROJECT_ID, 9)

    items = await service.generate_alternatives(project, 9)
    assert [i["id"] for i in items] == ["alt-1"]
    assert items[0]["climax_events"] == ["a1", "a2", "a3", "a4"]  # 截到卷数
    assert "现方案" in prompts[-1][1] and "共 4 卷" in prompts[-1][1]
    stored, generated_at = service.list_alternatives(service.get_state(project))
    assert stored == items and generated_at

    assert await service.apply_alternative(PROJECT_ID, 9, "no-such") is None
    state = await service.apply_alternative(PROJECT_ID, 9, "alt-1")
    assert state is not None
    anchor_prompt = prompts[-1][1]
    assert "作者选定的终局方向" in anchor_prompt and "剑冢弑师" in anchor_prompt and "第 4 卷高潮：a4" in anchor_prompt
    backbone = service.read_backbone(state)
    assert backbone.climaxes[0].event == "弑师线卷一高潮"
    meta = state["backbone_meta"]
    assert meta["revised_by_author"] is True and meta["chosen_alternative"] == "弑师证道"
    assert meta["edited_blocks"] == ["endgame", "climaxes.1", "climaxes.2", "climaxes.3", "climaxes.4"]
    assert "backbone_alternatives" not in state

    # 采用后立项书再改也不自动推翻作者选的方向
    state["dossier"] = {**state["dossier"], "notes": "改了"}
    project.concept_dossier = state
    await db_session.commit()
    before = len(prompts)
    await service.ensure_backbone(PROJECT_ID, 9)
    assert len(prompts) == before


@pytest.mark.asyncio
async def test_apply_alternative_failure_keeps_backbone(db_session, monkeypatch):
    project = await _seed_project(db_session)
    _patch_prompts(monkeypatch)
    calls = []
    _fake_llm(monkeypatch, calls)
    service = StoryBackboneService(db_session)
    await service.ensure_backbone(PROJECT_ID, 9)
    state = service.get_state(project)
    state["backbone_alternatives"] = {"items": [{"id": "alt-1", "label": "x", "endgame": {"final_confrontation": "y"}}]}
    project.concept_dossier = state
    await db_session.commit()

    async def broken(self, **kwargs):
        raise RuntimeError("503")

    monkeypatch.setattr(LLMService, "generate_structured", broken)
    assert await service.apply_alternative(PROJECT_ID, 9, "alt-1") is None
    kept = service.read_backbone(service.get_state(project))
    assert kept is not None and kept.climaxes[0].event == "卷一高潮"
