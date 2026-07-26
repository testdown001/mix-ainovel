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

    card = svc.format_memory_card_for_prompt([novel])
    assert len(card.split("\n", 1)[1]) == 800


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
    # memory_card 为空时退回空对象 dump，不报错
    assert "短参考" in svc.format_memory_card_for_prompt([novel])
