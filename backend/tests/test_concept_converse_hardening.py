"""概念对话瘦身与健壮化回归测试（审计 P1 #31/#32）。

覆盖四组修复：
1. 回传 LLM 的历史瘦身：assistant 记录只取 ai_message、user 记录取 value，
   解析失败退回原文截 500 字；落库格式不变（蓝图生成口径独立）。
2. 先校验后落库：LLM 漏必填字段 / 返回非 JSON 对象时 500 且零落库，历史无污染。
3. is_complete 最低轮次兜底：用户消息轮次（含本轮）< 3 强制压制、≥ 3 放行；
   压制时落库的 assistant JSON 与响应一致（前端刷新读历史不误判完成）。
4. 参考素材注入截断：三个 format_* 函数每本素材有上限（800/600/800）。

通过最小 FastAPI 应用挂载真实 novels 路由 + dependency_overrides，
底层走 conftest 的真内存 SQLite 会话，真正命中被修路径。
"""
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

import app.models.user_quota  # noqa: F401  触发 mapper 注册，防 KeyError
from app.api.routers import novels
from app.core.dependencies import get_current_user
from app.db.session import get_session
from app.models.novel import NovelConversation, NovelProject
from app.models.reference_novel import ReferenceNovel
from app.schemas.user import UserInDB
from app.services.reference_novel_library_service import ReferenceNovelLibraryService

OWNER = UserInDB(id=1, username="owner", hashed_password="x")
PROJECT_ID = "proj-converse-1"
CONVERSE_URL = f"/api/novels/{PROJECT_ID}/concept/converse"

VALID_RESPONSE = {
    "ai_message": "这是缪斯的新回复",
    "ui_control": {"type": "text_input", "placeholder": "继续说"},
    "conversation_state": {},
    "is_complete": False,
}


def _build_client(db_session):
    test_app = FastAPI()
    test_app.include_router(novels.router)

    async def _override_session():
        yield db_session

    async def _override_user():
        return OWNER

    test_app.dependency_overrides[get_session] = _override_session
    test_app.dependency_overrides[get_current_user] = _override_user
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


def _patch_services(monkeypatch, response_text):
    """替换 novels 模块内的 PromptService/LLMService，记录 LLM 调用参数。"""
    calls = []

    class _FakePromptService:
        def __init__(self, session):
            pass

        async def get_prompt(self, name):
            return "概念对话系统提示词"

    class _FakeLLMService:
        def __init__(self, session):
            pass

        async def get_llm_response(self, **kwargs):
            calls.append(kwargs)
            return response_text

    monkeypatch.setattr(novels, "PromptService", _FakePromptService)
    monkeypatch.setattr(novels, "LLMService", _FakeLLMService)
    return calls


async def _seed_project(db_session, conversations=()):
    db_session.add(NovelProject(id=PROJECT_ID, user_id=OWNER.id, title="概念项目"))
    for seq, (role, content) in enumerate(conversations, start=1):
        db_session.add(
            NovelConversation(project_id=PROJECT_ID, seq=seq, role=role, content=content)
        )
    await db_session.commit()


async def _list_conversations(db_session):
    result = await db_session.execute(
        select(NovelConversation)
        .where(NovelConversation.project_id == PROJECT_ID)
        .order_by(NovelConversation.seq.asc())
    )
    return list(result.scalars())


def _converse_payload():
    return {"user_input": {"type": "text", "value": "继续推进"}, "conversation_state": {}}


# ------------------------------------------------------------------
# 1. 历史瘦身
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_history_sent_to_llm_only_contains_ai_message(db_session, monkeypatch):
    stored_assistant = json.dumps(
        {
            "ai_message": "上一轮的提案",
            "ui_control": {
                "type": "single_choice",
                "options": [{"id": f"option_{i}", "label": f"选项{i}"} for i in range(8)],
            },
            "conversation_state": {"stage": "opening", "notes": "冗长内部状态" * 50},
            "is_complete": False,
        },
        ensure_ascii=False,
    )
    stored_user = json.dumps({"type": "text", "value": "守墓人的故事"}, ensure_ascii=False)
    await _seed_project(db_session, [("user", stored_user), ("assistant", stored_assistant)])
    calls = _patch_services(monkeypatch, json.dumps(VALID_RESPONSE, ensure_ascii=False))

    async with _build_client(db_session) as client:
        resp = await client.post(CONVERSE_URL, json=_converse_payload())
        assert resp.status_code == 200

    history = calls[0]["conversation_history"]
    # 历史 user 记录只取 value；assistant 记录只取 ai_message（不含 ui_control 等）
    assert history[0] == {"role": "user", "content": "守墓人的故事"}
    assert history[1] == {"role": "assistant", "content": "上一轮的提案"}
    # 本轮用户输入仍原样（结构化 JSON）追加在末尾
    assert history[2]["role"] == "user"
    assert "继续推进" in history[2]["content"]

    # 落库格式不变：老记录原样，新 assistant 记录仍是完整响应 JSON
    records = await _list_conversations(db_session)
    assert len(records) == 4
    assert records[1].content == stored_assistant
    assert "ui_control" in records[3].content


@pytest.mark.asyncio
async def test_history_unparseable_record_falls_back_truncated(db_session, monkeypatch):
    long_garbage = "这不是JSON文本" * 200  # 1400 字，远超 500 字兜底上限
    await _seed_project(db_session, [("assistant", long_garbage)])
    calls = _patch_services(monkeypatch, json.dumps(VALID_RESPONSE, ensure_ascii=False))

    async with _build_client(db_session) as client:
        resp = await client.post(CONVERSE_URL, json=_converse_payload())
        assert resp.status_code == 200

    history = calls[0]["conversation_history"]
    assert history[0]["role"] == "assistant"
    assert history[0]["content"] == long_garbage[:500]


# ------------------------------------------------------------------
# 2. 先校验后落库
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_required_field_returns_500_without_persisting(db_session, monkeypatch):
    await _seed_project(db_session)
    _patch_services(
        monkeypatch, json.dumps({"ai_message": "漏了 ui_control"}, ensure_ascii=False)
    )

    async with _build_client(db_session) as client:
        resp = await client.post(CONVERSE_URL, json=_converse_payload())
        assert resp.status_code == 500
        assert "缺少必要字段" in resp.json()["detail"]

    # 脏 assistant 消息不落库（重发不受污染）；用户消息单独保留（刷新页面不丢构思）
    records = await _list_conversations(db_session)
    assert len(records) == 1
    assert records[0].role == "user"


@pytest.mark.asyncio
async def test_non_object_response_returns_500_without_persisting(db_session, monkeypatch):
    await _seed_project(db_session)
    _patch_services(monkeypatch, json.dumps([1, 2, 3]))

    async with _build_client(db_session) as client:
        resp = await client.post(CONVERSE_URL, json=_converse_payload())
        assert resp.status_code == 500

    assert await _list_conversations(db_session) == []


# ------------------------------------------------------------------
# 3. is_complete 最低轮次兜底
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_complete_suppressed_before_min_turns(db_session, monkeypatch):
    await _seed_project(db_session)  # 无历史 → 本轮是第 1 个用户轮次
    _patch_services(
        monkeypatch,
        json.dumps(dict(VALID_RESPONSE, is_complete=True), ensure_ascii=False),
    )

    async with _build_client(db_session) as client:
        resp = await client.post(CONVERSE_URL, json=_converse_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_complete"] is False
        assert not body.get("ready_for_blueprint")

    # 压制后落库的 assistant JSON 与响应一致，前端刷新读历史不会误判完成
    records = await _list_conversations(db_session)
    stored = json.loads(records[-1].content)
    assert stored["is_complete"] is False


@pytest.mark.asyncio
async def test_is_complete_allowed_from_third_user_turn(db_session, monkeypatch):
    user_msg = json.dumps({"type": "text", "value": "推进"}, ensure_ascii=False)
    assistant_msg = json.dumps(VALID_RESPONSE, ensure_ascii=False)
    await _seed_project(
        db_session,
        [
            ("user", user_msg),
            ("assistant", assistant_msg),
            ("user", user_msg),
            ("assistant", assistant_msg),
        ],
    )  # 已有 2 个用户轮次，本轮为第 3 轮 → 放行
    _patch_services(
        monkeypatch,
        json.dumps(dict(VALID_RESPONSE, is_complete=True), ensure_ascii=False),
    )

    async with _build_client(db_session) as client:
        resp = await client.post(CONVERSE_URL, json=_converse_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_complete"] is True
        assert body["ready_for_blueprint"] is True

    records = await _list_conversations(db_session)
    stored = json.loads(records[-1].content)
    assert stored["is_complete"] is True


# ------------------------------------------------------------------
# 4. 参考素材注入截断
# ------------------------------------------------------------------

def _format_service():
    # format_* 均不依赖实例状态，跳过 __init__（其会实例化 LLM/搜索等服务）
    return ReferenceNovelLibraryService.__new__(ReferenceNovelLibraryService)


def test_reference_material_formatting_truncated():
    novel = SimpleNamespace(
        title="超长参考",
        author="作者",
        outline_content="纲" * 3000,
        style_samples_content="样" * 3000,
        memory_card={"takeaways": ["长" * 3000]},
    )
    svc = _format_service()

    concept = svc.format_for_concept_prompt([novel])
    assert concept.count("纲") == 800

    style = svc.format_style_samples_for_prompt([novel])
    assert style.count("样") == 600

    # 字段级注入后整块（含标题行）截到 800；超长的单字段不再吃掉整个预算之外的空间
    card = svc.format_memory_card_for_prompt([novel])
    assert len(card) == 800
    assert card.startswith("参考小说：超长参考")
    assert "可复用要点" in card


def test_reference_material_formatting_short_content_unchanged():
    novel = SimpleNamespace(
        title="短参考",
        author=None,
        outline_content="短纲要",
        style_samples_content=None,
        memory_card=None,
    )
    svc = _format_service()
    assert "短纲要" in svc.format_for_concept_prompt([novel])
    assert svc.format_style_samples_for_prompt([novel]) == ""
    # memory_card 为空时不再注入空 JSON 占位块——没有内容就一个字都不占
    assert svc.format_memory_card_for_prompt([novel]) == ""


def test_memory_card_prompt_prioritizes_plot_thinking_fields():
    """字段级注入：剧情思考类（冲突模版/爽点/伏笔）在前，且不再是 JSON dump。

    旧实现整段 json.dumps 再拦腰截 800 字：缩进和引号吃掉大半预算，截断点落在
    哪个字段全凭运气，排前面的 genre/target_audience 这类低价值字段反而永远活着。
    """
    novel = SimpleNamespace(
        title="参考A",
        author=None,
        outline_content=None,
        style_samples_content=None,
        memory_card={
            "genre": "都市异能",
            "target_audience": "男频",
            "main_conflict_pattern": "以弱抗强的资源争夺",
            "cool_point_patterns": ["当众打脸", "扮猪吃虎"],
            "foreshadowing_techniques": ["三章一收的短伏笔"],
        },
    )
    svc = _format_service()
    card = svc.format_memory_card_for_prompt([novel])
    assert "主线冲突模版：以弱抗强的资源争夺" in card
    assert "爽点模式：当众打脸；扮猪吃虎" in card
    assert "伏笔技法：三章一收的短伏笔" in card
    # 非注入字段与 JSON 语法不该出现
    assert "genre" not in card
    assert "{" not in card


def test_format_recommend_compass_uses_engine_and_charm():
    svc = _format_service()
    novel = SimpleNamespace(
        title="某书",
        memory_card={
            "main_conflict_pattern": "以弱抗强的资源争夺",
            "core_selling_point": "低调装逼打脸",
            "cool_point_patterns": ["当众打脸", "扮猪吃虎"],
        },
    )
    text = svc.format_recommend_compass_for_concept([novel])
    assert "选项推荐罗盘" in text
    assert "核心底层逻辑：以弱抗强的资源争夺" in text
    assert "读者最大魅力点：低调装逼打脸；当众打脸；扮猪吃虎" in text
    assert "禁止抄原作人名" in text
    assert svc.format_recommend_compass_for_concept([]) == ""


def test_format_recommend_compass_falls_back_to_fusion_dna():
    svc = _format_service()
    text = svc.format_recommend_compass_for_concept(
        [],
        fusion_dna={
            "narrative_strategy": "压迫升级",
            "key_techniques": ["章末刀切"],
        },
    )
    assert "核心底层逻辑：压迫升级" in text
    assert "章末刀切" in text


def test_normalize_choice_recommendations_pins_single_non_opt_out():
    parsed = {
        "ui_control": {
            "type": "single_choice",
            "options": [
                {"id": "a", "label": "阴郁悬疑", "recommended": False},
                {"id": "b", "label": "当众打脸后反杀", "recommended": True, "recommend_reason": "转译该书打脸上瘾感"},
                {"id": "c", "label": "全不满意，我另有想法", "recommended": True},
            ],
        }
    }
    novels._normalize_choice_recommendations(parsed)
    options = parsed["ui_control"]["options"]
    assert options[0]["id"] == "b"
    assert options[0]["recommended"] is True
    assert sum(1 for option in options if option.get("recommended")) == 1
    assert options[-1]["recommended"] is False


def test_normalize_choice_recommendations_fills_when_llm_forgets():
    parsed = {
        "ui_control": {
            "type": "single_choice",
            "options": [
                {"id": "a", "label": "市井烟火"},
                {"id": "b", "label": "全不满意/自由描述"},
            ],
        }
    }
    novels._normalize_choice_recommendations(parsed)
    assert parsed["ui_control"]["options"][0]["recommended"] is True
    assert parsed["ui_control"]["options"][1].get("recommended") is not True


@pytest.mark.asyncio
async def test_converse_injects_recommend_compass_from_fusion_dna(db_session, monkeypatch):
    await _seed_project(db_session)
    project = await db_session.get(NovelProject, PROJECT_ID)
    project.fusion_dna = {
        "narrative_strategy": "以压迫换升级",
        "key_techniques": ["当众打脸", "章末刀切"],
    }
    await db_session.commit()
    calls = _patch_services(monkeypatch, json.dumps(VALID_RESPONSE, ensure_ascii=False))

    async with _build_client(db_session) as client:
        resp = await client.post(CONVERSE_URL, json=_converse_payload())
        assert resp.status_code == 200

    prompt = calls[0]["system_prompt"]
    assert "选项推荐罗盘" in prompt
    assert "核心底层逻辑：以压迫换升级" in prompt
    assert "当众打脸" in prompt


@pytest.mark.asyncio
async def test_converse_injects_all_bound_reference_novel_material(db_session, monkeypatch):
    """构思不是只保存书名：两本已绑定书的大纲内容都会进入实际 LLM 系统提示词。"""
    await _seed_project(db_session)
    first = ReferenceNovel(
        title="参考甲",
        user_id=OWNER.id,
        status="ready",
        outline_content="甲书独有的身份错位结构",
        memory_card={"main_conflict_pattern": "以弱抗强"},
    )
    second = ReferenceNovel(
        title="参考乙",
        user_id=OWNER.id,
        status="ready",
        outline_content="乙书独有的双线追凶结构",
        memory_card={"main_conflict_pattern": "时间竞赛"},
    )
    db_session.add_all([first, second])
    await db_session.flush()
    project = await db_session.get(NovelProject, PROJECT_ID)
    project.reference_novel_ids = [first.id, second.id]
    await db_session.commit()
    calls = _patch_services(monkeypatch, json.dumps(VALID_RESPONSE, ensure_ascii=False))

    async with _build_client(db_session) as client:
        resp = await client.post(CONVERSE_URL, json=_converse_payload())
        assert resp.status_code == 200

    prompt = calls[0]["system_prompt"]
    assert "参考甲" in prompt and "甲书独有的身份错位结构" in prompt
    assert "参考乙" in prompt and "乙书独有的双线追凶结构" in prompt


@pytest.mark.asyncio
async def test_converse_single_choice_always_has_one_recommended(db_session, monkeypatch):
    await _seed_project(db_session)
    payload = {
        "ai_message": "选一个方向",
        "ui_control": {
            "type": "single_choice",
            "options": [
                {"id": "option_1", "label": "他给仇人抬棺，棺是空的"},
                {"id": "option_2", "label": "全不满意，我另有想法"},
            ],
        },
        "conversation_state": {},
        "is_complete": False,
    }
    _patch_services(monkeypatch, json.dumps(payload, ensure_ascii=False))

    async with _build_client(db_session) as client:
        resp = await client.post(CONVERSE_URL, json=_converse_payload())
        assert resp.status_code == 200

    options = resp.json()["ui_control"]["options"]
    assert options[0]["recommended"] is True
    assert options[0]["label"] == "他给仇人抬棺，棺是空的"
    assert options[1]["recommended"] is False

