"""立项书蒸馏与压力推演（concept_dossier_service）回归。

锁定的契约：
- ConceptDossier/PremiseStressReport schema 全字段有默认值（LLM 漏字段软降级）；
- high_risk_points 只挑 severity 含「高」的毒点；
- format_dossier_for_prompt：有料出节、空立项书出空串；
- _compact_history_text：user 取 value、assistant 取 ai_message、坏记录截断兜底；
- ensure_dossier 幂等：已有产物不再调 LLM；高危毒点触发一轮自动修订（revised=True）；
- 蒸馏失败（LLM 抛异常）软失败：不落任何产物、不外抛。
"""
import json

import pytest

from app.models.novel import NovelProject
from app.models.user import User
from app.schemas.concept_dossier import (
    ConceptDossier,
    PremiseStressReport,
    ToxicPoint,
)
from app.services.concept_dossier_service import (
    ConceptDossierService,
    _compact_history_text,
    format_dossier_for_prompt,
    humanize_dossier_jargon,
    humanize_stress_report_dict,
)
from app.services.llm_service import LLMService
from app.services.novel_service import NovelService
from app.services.prompt_service import PromptService

PROJECT_ID = "dossier-proj-1"


# ---------------------------------------------------------------------------
# 纯函数层
# ---------------------------------------------------------------------------

def test_schema_defaults_tolerate_missing_fields():
    dossier = ConceptDossier()
    assert dossier.core_selling_line == ""
    assert dossier.protagonist.desire == ""
    assert dossier.coolpoint_chain == []
    report = PremiseStressReport()
    assert report.toxic_points == []
    assert report.high_risk_points() == []


def test_high_risk_points_filters_by_severity():
    report = PremiseStressReport(
        toxic_points=[
            ToxicPoint(issue="爽点太迟", severity="高危"),
            ToxicPoint(issue="桥段过老", severity="中危"),
            ToxicPoint(issue="标题平庸", severity="低危"),
        ]
    )
    assert [p.issue for p in report.high_risk_points()] == ["爽点太迟"]


def test_format_dossier_for_prompt_sections():
    dossier = ConceptDossier(
        core_selling_line="废柴接手欠债当铺，死当藏大能遗产",
        genre="都市异能",
        protagonist={"name": "陈默", "desire": "查清灭门真相", "flaw": "不信任何人"},
        conflict_engine="每件死当兑现都引来原主仇家",
        coolpoint_chain=["信息差打脸：拍卖会识破赝品"],
        anticipation={"ten_chapters": "第一次当铺兑现打脸"},
    ).model_dump()
    text = format_dossier_for_prompt(dossier)
    assert "【故事立项书】" in text
    assert "废柴接手欠债当铺" in text
    assert "欲望=查清灭门真相" in text
    assert "矛盾发动机" in text
    assert "信息差打脸" in text
    assert "前10章=第一次当铺兑现打脸" in text


def test_format_dossier_for_prompt_empty_returns_blank():
    assert format_dossier_for_prompt({}) == ""
    assert format_dossier_for_prompt(None) == ""  # type: ignore[arg-type]


def test_humanize_dossier_jargon_replaces_internal_paths():
    raw = (
        "改 `protagonist.identity` 只保留普通人身份，"
        "`predicament` 只保留失忆+被追杀，其余放 notes。"
        "同时收紧 golden_finger.limitations 与 growth_curve，"
        "补 conflict_engine，翻新 coolpoint_chain，把兑现写进 anticipation。"
    )
    text = humanize_dossier_jargon(raw)
    assert "protagonist" not in text
    assert "identity" not in text
    assert "predicament" not in text
    assert "notes" not in text
    assert "golden_finger" not in text
    assert "limitations" not in text
    assert "growth_curve" not in text
    assert "conflict_engine" not in text
    assert "coolpoint_chain" not in text
    assert "anticipation" not in text
    assert "主角身份处境" in text
    assert "主角开局困境" in text
    assert "补充说明" in text
    assert "金手指限制与代价" in text
    assert "金手指成长曲线" in text
    assert "矛盾发动机" in text
    assert "爽点链" in text
    assert "期待感承诺" in text


def test_humanize_stress_report_dict_cleans_fix_suggestions():
    cleaned = humanize_stress_report_dict({
        "toxic_points": [
            {
                "issue": "开局信息过载",
                "severity": "高危",
                "reason": "前3章概念太多",
                "fix_suggestion": "改 protagonist.identity，其余放 notes",
            }
        ],
        "summary": "建议补 conflict_engine",
    })
    assert cleaned["toxic_points"][0]["fix_suggestion"] == "改 主角身份处境，其余放 补充说明"
    assert "conflict_engine" not in cleaned["summary"]
    assert "矛盾发动机" in cleaned["summary"]


def test_compact_history_text_extracts_and_survives_bad_records():
    class Record:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    records = [
        Record("user", json.dumps({"id": "1", "value": "想写当铺文"}, ensure_ascii=False)),
        Record("assistant", json.dumps({"ai_message": "当铺文可以做信息差", "ui_control": {}}, ensure_ascii=False)),
        Record("assistant", "这不是JSON但也不能整轮丢失"),
    ]
    text = _compact_history_text(records)
    assert "作者：想写当铺文" in text
    assert "构思助手：当铺文可以做信息差" in text
    assert "这不是JSON" in text  # 坏记录截断兜底


# ---------------------------------------------------------------------------
# ensure_dossier：幂等 + 高危自动修订 + 软失败
# ---------------------------------------------------------------------------

async def _seed_project(db_session, with_history=True):
    user = User(id=7, username="u7", hashed_password="x")
    project = NovelProject(id=PROJECT_ID, user_id=7, title="未命名灵感")
    db_session.add_all([user, project])
    await db_session.commit()
    if with_history:
        novel_service = NovelService(db_session)
        await novel_service.append_conversation(
            PROJECT_ID, "user", json.dumps({"id": "1", "value": "想写都市当铺文"}, ensure_ascii=False)
        )
        await novel_service.append_conversation(
            PROJECT_ID, "assistant",
            json.dumps({"ai_message": "核心卖点可以是死当藏遗产", "ui_control": {}}, ensure_ascii=False),
        )
    return project


def _patch_prompts(monkeypatch):
    async def fake_get_prompt(self, name):
        return f"SYSTEM-{name}"

    monkeypatch.setattr(PromptService, "get_prompt", fake_get_prompt)


@pytest.mark.asyncio
async def test_ensure_dossier_distill_stress_revise_and_idempotent(db_session, monkeypatch):
    await _seed_project(db_session)
    _patch_prompts(monkeypatch)

    calls = []

    async def fake_generate_structured(self, *, prompt, schema, **kwargs):
        calls.append(schema.__name__)
        if schema is ConceptDossier:
            return ConceptDossier(core_selling_line="卖点句V" + str(len(calls)))
        return PremiseStressReport(
            overall_verdict="建议修订",
            toxic_points=[ToxicPoint(issue="爽点太迟", severity="高危", fix_suggestion="提前到第5章")],
        )

    monkeypatch.setattr(LLMService, "generate_structured", fake_generate_structured)

    service = ConceptDossierService(db_session)
    state = await service.ensure_dossier(PROJECT_ID, 7, run_stress=True)

    # 蒸馏 + 推演 + 高危自动修订 = 3 次结构化调用
    assert calls == ["ConceptDossier", "PremiseStressReport", "ConceptDossier"]
    assert state["dossier"]["core_selling_line"].startswith("卖点句")
    assert state["stress_report"]["toxic_points"][0]["issue"] == "爽点太迟"
    assert state["revised"] is True

    # 幂等：产物齐备后不再调 LLM
    calls.clear()
    state2 = await service.ensure_dossier(PROJECT_ID, 7, run_stress=True)
    assert calls == []
    assert state2["dossier"] == state["dossier"]

    # 落库确认
    project = await db_session.get(NovelProject, PROJECT_ID)
    assert isinstance(project.concept_dossier, dict)
    assert project.concept_dossier["revised"] is True


@pytest.mark.asyncio
async def test_ensure_dossier_stress_platform_switch_off(db_session, monkeypatch):
    """blueprint.stress_enabled=false 时即使 run_stress=True 也不推演。"""
    from app.models.system_config import SystemConfig

    await _seed_project(db_session)
    _patch_prompts(monkeypatch)
    db_session.add(SystemConfig(key="blueprint.stress_enabled", value="false"))
    await db_session.commit()

    calls = []

    async def fake_generate_structured(self, *, prompt, schema, **kwargs):
        calls.append(schema.__name__)
        return ConceptDossier(core_selling_line="卖点句")

    monkeypatch.setattr(LLMService, "generate_structured", fake_generate_structured)

    state = await ConceptDossierService(db_session).ensure_dossier(
        PROJECT_ID, 7, run_stress=True
    )
    assert calls == ["ConceptDossier"]
    assert "stress_report" not in state


@pytest.mark.asyncio
async def test_ensure_dossier_free_tier_skips_stress(db_session, monkeypatch):
    await _seed_project(db_session)
    _patch_prompts(monkeypatch)

    calls = []

    async def fake_generate_structured(self, *, prompt, schema, **kwargs):
        calls.append(schema.__name__)
        return ConceptDossier(core_selling_line="卖点句")

    monkeypatch.setattr(LLMService, "generate_structured", fake_generate_structured)

    state = await ConceptDossierService(db_session).ensure_dossier(
        PROJECT_ID, 7, run_stress=False
    )
    assert calls == ["ConceptDossier"]
    assert "stress_report" not in state  # 免费档无推演，确认页按无报告降级展示


@pytest.mark.asyncio
async def test_ensure_dossier_llm_failure_is_soft(db_session, monkeypatch):
    await _seed_project(db_session)
    _patch_prompts(monkeypatch)

    async def broken(self, **kwargs):
        raise RuntimeError("upstream 503")

    monkeypatch.setattr(LLMService, "generate_structured", broken)

    state = await ConceptDossierService(db_session).ensure_dossier(
        PROJECT_ID, 7, run_stress=True
    )
    assert "dossier" not in state  # 软失败：无产物但不外抛
    project = await db_session.get(NovelProject, PROJECT_ID)
    assert project.concept_dossier is None


@pytest.mark.asyncio
async def test_ensure_dossier_without_history_noop(db_session, monkeypatch):
    await _seed_project(db_session, with_history=False)
    _patch_prompts(monkeypatch)

    async def should_not_call(self, **kwargs):  # pragma: no cover - 断言保护
        raise AssertionError("无对话历史不应调用 LLM")

    monkeypatch.setattr(LLMService, "generate_structured", should_not_call)
    state = await ConceptDossierService(db_session).ensure_dossier(
        PROJECT_ID, 7, run_stress=True
    )
    assert "dossier" not in state


# ---------------------------------------------------------------------------
# 分块编辑 + 采纳修复
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_dossier_merges_nested(db_session, monkeypatch):
    project = await _seed_project(db_session, with_history=False)
    project.concept_dossier = {
        "dossier": {
            "core_selling_line": "旧卖点",
            "protagonist": {"name": "陈默", "desire": "旧欲望"},
        }
    }
    await db_session.commit()

    service = ConceptDossierService(db_session)
    state = await service.patch_dossier(project, {"protagonist": {"desire": "新欲望"}})
    assert state["dossier"]["protagonist"] == {"name": "陈默", "desire": "新欲望"}
    assert state["dossier"]["core_selling_line"] == "旧卖点"


def test_hoist_misplaced_stress_fields():
    """2026-08-15 测试服实测：模型把 toxic_points/overall_verdict 误嵌进
    golden_finger_collapse，顶层空报告——纠偏后上提到顶层。"""
    from app.services.concept_dossier_service import _hoist_misplaced_stress_fields

    drifted = PremiseStressReport.model_validate({
        "toxic_points": [],
        "overall_verdict": "",
        "summary": "",
        "golden_finger_collapse": {
            "verdict": "有隐患",
            "toxic_points": [{"issue": "对手全是纸片", "severity": "中危"}],
            "overall_verdict": "建议修订",
            "summary": "总评在这里",
        },
    })
    fixed = _hoist_misplaced_stress_fields(drifted)
    assert fixed.overall_verdict == "建议修订"
    assert fixed.summary == "总评在这里"
    assert [p.issue for p in fixed.toxic_points] == ["对手全是纸片"]
    assert fixed.golden_finger_collapse.verdict == "有隐患"  # 子对象自身字段不动

    # 顶层已有内容时不动
    normal = PremiseStressReport(overall_verdict="可开工", toxic_points=[ToxicPoint(issue="a")])
    assert _hoist_misplaced_stress_fields(normal) is normal


@pytest.mark.asyncio
async def test_get_state_humanizes_stored_english_fix_suggestions(db_session):
    """已落库的英文路径在读取时换成中文区块名，旧报告不用重跑推演。"""
    project = await _seed_project(db_session, with_history=False)
    project.concept_dossier = {
        "dossier": {"core_selling_line": "卖点"},
        "stress_report": {
            "toxic_points": [
                {"issue": "开局信息过载", "fix_suggestion": "改 protagonist.identity，其余放 notes"},
            ],
        },
    }
    await db_session.commit()
    await db_session.refresh(project)
    state = ConceptDossierService(db_session).get_state(project)
    suggestion = state["stress_report"]["toxic_points"][0]["fix_suggestion"]
    assert "protagonist" not in suggestion
    assert "notes" not in suggestion
    assert "主角身份处境" in suggestion
    assert "补充说明" in suggestion


@pytest.mark.asyncio
async def test_apply_stress_fixes_requires_report(db_session):
    project = await _seed_project(db_session, with_history=False)
    project.concept_dossier = {"dossier": {"core_selling_line": "卖点"}}
    await db_session.commit()
    result = await ConceptDossierService(db_session).apply_stress_fixes(project, 7)
    assert result is None  # 无推演报告 → 409 由路由层给出
