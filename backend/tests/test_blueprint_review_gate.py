"""蓝图审稿门（blueprint_review_service）回归。

锁定的契约：
- parse_chapter_range："chapters:5-8"/"chapters:12"/坏输入 的解析口径；
- ReviewReport.issues_for_settings/chapters 按 target 前缀分流；
- revise_settings_blocks：只合并被点名且过类型守卫的白名单块，失败/坏产出保留原设定；
- revise_chapter_ranges：只替换点名章号，未点名章原样保留（identity 不变）；
- review 缺提示词时返回 None（审稿门跳过，不阻断蓝图）；
- 蓝图生成侧纯函数：_extract_outline_items 提取 planning、批任务免费档带精简标记、
  _inject_blueprint_exclusions 注入禁区。
"""
import json

import pytest

from app.schemas.concept_dossier import BlueprintReviewReport, ReviewIssue
from app.services.blueprint_generation_service import (
    _build_batch_task,
    _build_settings_summary,
    _extract_outline_items,
    _format_outline_tail,
    _inject_blueprint_exclusions,
)
from app.services.blueprint_review_service import (
    BlueprintReviewService,
    _outline_lines,
    parse_chapter_range,
)
from app.services.llm_service import LLMService


# ---------------------------------------------------------------------------
# 纯函数
# ---------------------------------------------------------------------------

def test_parse_chapter_range():
    assert parse_chapter_range("chapters:5-8") == (5, 8)
    assert parse_chapter_range("chapters:12") == (12, 12)
    assert parse_chapter_range("chapters:12-12") == (12, 12)
    assert parse_chapter_range("settings:golden_finger") is None
    assert parse_chapter_range("chapters:8-5") is None  # hi < lo
    assert parse_chapter_range("chapters:abc") is None
    assert parse_chapter_range("") is None


def test_report_issue_routing():
    report = BlueprintReviewReport(
        total_score=55,
        issues=[
            ReviewIssue(target="settings:golden_finger", problem="限制形同虚设"),
            ReviewIssue(target="chapters:5-8", problem="连续四章赶路"),
            ReviewIssue(target="", problem="无定位问题"),
        ],
    )
    assert [i.problem for i in report.issues_for_settings()] == ["限制形同虚设"]
    assert [i.problem for i in report.issues_for_chapters()] == ["连续四章赶路"]


def test_extract_outline_items_with_planning():
    data = {
        "chapter_outline": [
            {
                "chapter_number": 1,
                "title": "当铺开门",
                "summary": "主角接手当铺",
                "chapter_function": "爽点",
                "hook_type": "新危机压脸：黑衣人上门",
                "coolpoint": "信息差打脸：识破赝品",
                "foreshadowing_ops": [{"op": "plant", "name": "死当账本"}],
                "must_not_include": ["提前揭示会长身份"],
                "character_focus": {"character_name": "主角", "choice": "留下晚饭等师弟回来", "next_expectation": "师弟会不会赴约"},
            },
            {"chapter_number": 2, "title": "无规划章", "summary": "过渡"},
        ]
    }
    items = _extract_outline_items(data)
    assert items[0]["planning"]["chapter_function"] == "爽点"
    assert items[0]["planning"]["foreshadowing_ops"] == [{"op": "plant", "name": "死当账本"}]
    assert items[0]["planning"]["must_not_include"] == ["提前揭示会长身份"]
    assert items[0]["planning"]["character_focus"]["choice"] == "留下晚饭等师弟回来"
    assert "planning" not in items[1]  # 缺规划字段 → 无 planning 键，下游 no-op


def test_build_batch_task_planning_gate_and_tail():
    tail = _format_outline_tail(
        [{"chapter_number": n, "title": f"t{n}", "summary": f"s{n}"} for n in range(1, 9)]
    )
    assert "第8章" in tail and "第3章" not in tail  # 只取尾部 5 章

    with_planning = _build_batch_task(26, 50, tail, include_planning=True)
    assert "第 26-50 章" in with_planning
    assert "前批已生成章纲的尾部" in with_planning
    assert "输出精简" not in with_planning

    free_tier = _build_batch_task(1, 25, "", include_planning=False)
    assert "输出精简" in free_tier  # 免费档跳过章级规划字段


def test_inject_blueprint_exclusions():
    assert _inject_blueprint_exclusions("BASE", "") == "BASE"
    injected = _inject_blueprint_exclusions("BASE", "不要后宫\n不要系统")
    assert injected.startswith("BASE")
    assert "创作禁区" in injected and "不要后宫" in injected


def test_settings_summary_retains_character_motives_relationships_and_promises():
    summary = _build_settings_summary(
        {
            "title": "旧店重开",
            "characters": [{"name": "师弟", "goals": "讨回自己的诊金", "personality": "不愿受施舍"}],
            "relationships": [{"character_from": "师兄", "character_to": "师弟", "description": "上次争吵后尚未和解"}],
        },
        [],
        dossier={
            "protagonist": {"name": "师兄", "desire": "把旧店开起来", "flaw": "不肯承认错误"},
            "emotional_core": {"cherished": "给师弟留着的饭桌", "hard_choice": "开店的钱用来买药"},
            "anticipation": {"ten_chapters": "师弟愿意回来吃饭", "fifty_chapters": "两人共同接下旧店", "long_term": "一起守住这个家"},
        },
    )
    for evidence in (
        "讨回自己的诊金", "不愿受施舍", "上次争吵后尚未和解", "不肯承认错误",
        "给师弟留着的饭桌", "开店的钱用来买药", "师弟愿意回来吃饭", "两人共同接下旧店", "一起守住这个家",
    ):
        assert evidence in summary


def test_outline_review_lines_include_optional_character_choice_evidence():
    text = _outline_lines([
        {"chapter_number": 1, "title": "留座", "summary": "师兄给师弟留了饭。", "planning": {
            "character_focus": {"character_name": "师兄", "wants": "等师弟回来", "choice": "把最后一碗饭留下", "relationship_change": "开始回应师弟的沉默", "next_expectation": "师弟会不会赴约"},
        }},
        {"chapter_number": 2, "title": "安静吃饭", "summary": "两人吃完饭，各自收拾碗筷。"},
    ])
    assert "把最后一碗饭留下" in text
    assert "开始回应师弟的沉默" in text
    assert "师弟会不会赴约" in text
    assert "第2章" in text


@pytest.mark.asyncio
async def test_review_sees_character_attachment_sources_and_accepts_legacy_seven_dimensions(db_session, monkeypatch):
    service = BlueprintReviewService(db_session)
    captured = {}

    async def fake_prompt(name):
        return "REVIEW"

    legacy_dimensions = {
        "opening_strength": 80, "first_coolpoint_timing": 80, "hook_chain": 80,
        "volume_escalation": 80, "foreshadowing_payoff": 80, "anticipation_delivery": 80,
        "toxic_recheck": 80,
    }

    async def fake_structured(**kwargs):
        captured.update(kwargs)
        return BlueprintReviewReport(total_score=80, dimension_scores=legacy_dimensions)

    monkeypatch.setattr(service.prompt_service, "get_prompt", fake_prompt)
    monkeypatch.setattr(service.llm_service, "generate_structured", fake_structured)
    report = await service.review(
        settings_data={
            "title": "旧店重开", "characters": [{"name": "师弟", "goals": "拿回诊金", "personality": "不愿受施舍"}],
            "relationships": [{"character_from": "师兄", "character_to": "师弟", "description": "争吵之后尚未和解"}],
        },
        outline_items=[{"chapter_number": 1, "title": "留座", "summary": "师兄留下晚饭。", "planning": {
            "character_focus": {"character_name": "师兄", "choice": "把最后一碗饭留下", "next_expectation": "师弟会不会赴约"},
        }}],
        stress_report=None,
        dossier={
            "protagonist": {"name": "师兄", "flaw": "不肯承认错误"},
            "emotional_core": {"cherished": "给师弟留着的饭桌"},
            "anticipation": {"ten_chapters": "师弟愿意回来吃饭"},
        },
        user_id=7,
    )
    for evidence in ("不肯承认错误", "不愿受施舍", "争吵之后尚未和解", "给师弟留着的饭桌", "把最后一碗饭留下", "师弟会不会赴约"):
        assert evidence in captured["prompt"]
    assert captured["prompt"].count("师弟愿意回来吃饭") == 1
    assert report.total_score == 80
    assert report.dimension_scores == legacy_dimensions


# ---------------------------------------------------------------------------
# 定向修订：设定块
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revise_settings_blocks_merges_whitelisted_and_type_guarded(db_session, monkeypatch):
    settings_data = {
        "title": "旧标题",
        "golden_finger": {"name": "当铺系统", "limitations": "无"},
        "world_setting": {"core_rules": "旧规则"},
        "full_synopsis": "旧梗概",
        "relationships": [{"character_from": "师兄", "character_to": "师弟", "description": "盟友"}],
    }
    report = BlueprintReviewReport(
        total_score=50,
        issues=[
            ReviewIssue(target="settings:golden_finger", severity="高", problem="限制形同虚设", fix_hint="加代价"),
            ReviewIssue(target="settings:title", severity="中", problem="标题平庸", fix_hint="加冲突感"),
            ReviewIssue(target="settings:relationships", severity="中", problem="只有盟友标签", fix_hint="写清彼此尚未说破的事"),
        ],
    )

    async def fake_llm(self, system_prompt, conversation_history, **kwargs):
        return json.dumps({
            "revised_blocks": {
                "golden_finger": {"name": "当铺系统", "limitations": "每次兑现折寿一年"},
                "title": "新标题",
                "world_setting": "标量污染",   # 未点名 + 类型不符 → 双重拒绝
                "full_synopsis": "未点名的重写",  # 未点名 → 拒绝
                "relationships": [{"character_from": "师兄", "character_to": "师弟", "description": "争吵后仍为对方留饭"}],
            }
        }, ensure_ascii=False)

    monkeypatch.setattr(LLMService, "get_llm_response", fake_llm)

    merged = await BlueprintReviewService(db_session).revise_settings_blocks(
        settings_data=settings_data, report=report, user_id=7,
    )
    assert merged["golden_finger"]["limitations"] == "每次兑现折寿一年"
    assert merged["title"] == "新标题"
    assert merged["world_setting"] == {"core_rules": "旧规则"}  # 类型守卫
    assert merged["full_synopsis"] == "旧梗概"  # 未点名不改
    assert merged["relationships"][0]["description"] == "争吵后仍为对方留饭"


@pytest.mark.asyncio
async def test_revise_settings_blocks_llm_failure_keeps_original(db_session, monkeypatch):
    async def broken(self, *args, **kwargs):
        raise RuntimeError("upstream 503")

    monkeypatch.setattr(LLMService, "get_llm_response", broken)
    settings_data = {"title": "旧标题"}
    report = BlueprintReviewReport(
        issues=[ReviewIssue(target="settings:title", problem="p", fix_hint="f")]
    )
    merged = await BlueprintReviewService(db_session).revise_settings_blocks(
        settings_data=settings_data, report=report, user_id=7,
    )
    assert merged is settings_data  # 软失败保留原设定


# ---------------------------------------------------------------------------
# 定向修订：章号区间
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revise_chapter_ranges_replaces_only_named(db_session, monkeypatch):
    outline_items = [
        {"chapter_number": n, "title": f"旧{n}", "summary": f"旧摘要{n}"} for n in range(1, 11)
    ]
    report = BlueprintReviewReport(
        total_score=50,
        issues=[ReviewIssue(target="chapters:5-6", severity="高", problem="连续赶路", fix_hint="加冲突")],
    )

    async def fake_llm(self, system_prompt, conversation_history, **kwargs):
        prompt = conversation_history[0]["content"]
        assert "第 5、6 章" in prompt  # 修订任务点名章号
        return json.dumps({
            "chapter_outline": [
                {"chapter_number": 5, "title": "新5", "summary": "新摘要5", "chapter_function": "爽点"},
                {"chapter_number": 9, "title": "越界9", "summary": "不在点名范围"},
            ]
        }, ensure_ascii=False)

    monkeypatch.setattr(LLMService, "get_llm_response", fake_llm)

    merged = await BlueprintReviewService(db_session).revise_chapter_ranges(
        outline_items=outline_items,
        report=report,
        settings_summary="【蓝图设定摘要】x",
        outline_system_prompt="OUTLINE-SYS",
        user_id=7,
        extract_items=_extract_outline_items,
    )
    by_number = {item["chapter_number"]: item for item in merged}
    assert by_number[5]["title"] == "新5"
    assert by_number[5]["planning"]["chapter_function"] == "爽点"
    assert by_number[6]["title"] == "旧6"  # 点名但 LLM 没给 → 保留原章
    assert by_number[9]["title"] == "旧9"  # 越界产出被丢弃
    assert by_number[1] is outline_items[0]  # 未点名章 identity 不变


@pytest.mark.asyncio
async def test_review_without_prompt_returns_none(db_session):
    # 空 Prompt 表 → get_prompt 返回 None → 审稿门跳过（不外抛）
    report = await BlueprintReviewService(db_session).review(
        settings_data={"title": "t"},
        outline_items=[{"chapter_number": 1, "title": "t", "summary": "s"}],
        stress_report=None,
        dossier=None,
        user_id=7,
    )
    assert report is None


@pytest.mark.asyncio
async def test_min_score_default_and_config(db_session):
    from app.models.system_config import SystemConfig

    service = BlueprintReviewService(db_session)
    assert await service.get_min_score() == 70  # 无配置回默认

    db_session.add(SystemConfig(key="blueprint.review_min_score", value="85"))
    await db_session.commit()
    assert await service.get_min_score() == 85
