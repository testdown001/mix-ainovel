"""选区变换：只改圈中段落、计费 reason=transform、失败可退、没兑现要退。"""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

import app.models  # noqa: F401
import app.models.user_quota  # noqa: F401
from app.api.routers import writer
from app.core.dependencies import get_current_user
from app.db.session import get_session
from app.models.novel import Chapter, ChapterVersion, NovelProject
from app.models.user import User
from app.schemas.user import UserInDB
from app.services.generation_billing_service import charge_transform, refund_generation, transform_price
from app.services.quota_service import QuotaService
from app.services.text_transform_service import TransformOutcome, transform_selection


PROSE = (
    "他推开门，夜风灌进来。巷口那盏灯还亮着，像有人等过一整夜。"
    "脚步声从石板上传来，他没有回头，只把衣领翻高了一些。"
    "远处有人低声说话，语气又急又软，像是在商量一件见不得光的事。"
)


@pytest.mark.asyncio
async def test_transform_price_defaults(db_session):
    assert await transform_price(db_session, "expand") == 3
    assert await transform_price(db_session, "rewrite") == 3
    assert await transform_price(db_session, "de_ai") == 2


@pytest.mark.asyncio
async def test_charge_transform_and_refund(db_session):
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(21)
    charged = await charge_transform(db_session, 21, "expand", ref_key="xf-1")
    assert charged == 3
    assert (await svc.get_or_create_quota(21)).credit_balance == 57
    assert await refund_generation(db_session, 21, ref_key="xf-1") == 3
    assert (await svc.get_or_create_quota(21)).credit_balance == 60
    assert await refund_generation(db_session, 21, ref_key="xf-1") == 0


@pytest.mark.asyncio
async def test_charge_transform_insufficient(db_session):
    svc = QuotaService(db_session)
    quota = await svc.get_or_create_quota(22)
    quota.credit_balance = 1
    quota.credit_purchased = 0
    await db_session.commit()
    with pytest.raises(HTTPException) as ei:
        await charge_transform(db_session, 22, "rewrite", ref_key="xf-poor")
    assert ei.value.status_code == 402


@pytest.mark.asyncio
async def test_transform_selection_sends_only_selected_text(monkeypatch, db_session):
    captured = {}

    async def fake_llm(self, **kwargs):
        captured["history"] = kwargs.get("conversation_history")
        return PROSE + "又多写了一句对白。"

    monkeypatch.setattr(
        "app.services.text_transform_service.LLMService.get_llm_response",
        fake_llm,
    )
    result = await transform_selection(
        db_session,
        action="expand",
        selected_text=PROSE,
        context_before="前文一句。",
        context_after="后文一句。",
        user_id=1,
    )
    prompt = captured["history"][0]["content"]
    assert "【选区】" in prompt
    assert PROSE in prompt
    assert "整章" not in prompt
    assert result.delivered is True
    assert result.text.startswith("他推开门")


@pytest.mark.asyncio
async def test_de_ai_uses_humanization_not_prompt_service(monkeypatch, db_session):
    calls = {}

    class FakeHumanize:
        def __init__(self, session, llm):
            calls["ctor"] = (session, type(llm).__name__)

        def scan(self, text):
            return SimpleNamespace(score=95)

        def apply_rule_fixes(self, text, report):
            return text + "。"

        async def humanize(self, text, report, user_id=None):
            raise AssertionError("高分不应再走 LLM humanize")

    monkeypatch.setattr("app.services.text_transform_service.HumanizationService", FakeHumanize)
    result = await transform_selection(
        db_session, action="de_ai", selected_text=PROSE, user_id=1
    )
    assert result.delivered is True
    assert result.text.endswith("。")
    assert calls["ctor"][1] == "LLMService"


@pytest.mark.asyncio
async def test_non_prose_output_is_undelivered(monkeypatch, db_session):
    """模型回的是分析而不是正文 → 退回原文且判未交付，由路由退款。"""

    async def fake_llm(self, **kwargs):
        return "分析：这段可以增加环境描写。\n1. 加入雨声\n2. 补一句心理活动"

    monkeypatch.setattr(
        "app.services.text_transform_service.LLMService.get_llm_response", fake_llm
    )
    result = await transform_selection(
        db_session, action="rewrite", selected_text=PROSE, user_id=1
    )
    assert result.delivered is False
    assert result.text == PROSE
    assert result.note


@pytest.mark.asyncio
async def test_echoed_selection_is_undelivered(monkeypatch, db_session):
    """模型把选区原样抄回 → 一字未改，同样不算交付。"""

    async def fake_llm(self, **kwargs):
        return PROSE

    monkeypatch.setattr(
        "app.services.text_transform_service.LLMService.get_llm_response", fake_llm
    )
    result = await transform_selection(
        db_session, action="expand", selected_text=PROSE, user_id=1
    )
    assert result.delivered is False
    assert result.text == PROSE


@pytest.mark.asyncio
async def test_de_ai_without_any_rule_hit_is_undelivered(monkeypatch, db_session):
    """去 AI 味高分直接返回：规则一处没改就是没兑现，不能白收 2 分。"""

    class FakeHumanize:
        def __init__(self, session, llm):
            pass

        def scan(self, text):
            return SimpleNamespace(score=97)

        def apply_rule_fixes(self, text, report):
            return text  # 无命中，原样返回

        async def humanize(self, text, report, user_id=None):
            raise AssertionError("高分不应再走 LLM humanize")

    monkeypatch.setattr("app.services.text_transform_service.HumanizationService", FakeHumanize)
    result = await transform_selection(
        db_session, action="de_ai", selected_text=PROSE, user_id=1
    )
    assert result.delivered is False
    assert result.text == PROSE


# ---------------------------------------------------------------------------
# 路由级：没兑现必须退款，账面净额归零
# ---------------------------------------------------------------------------

XF_OWNER = UserInDB(id=41, username="xf-owner", hashed_password="x")
XF_PROJECT = "proj-transform-1"


def _build_client(db_session):
    test_app = FastAPI()
    test_app.include_router(writer.router)

    async def _override_session():
        yield db_session

    async def _override_user():
        return XF_OWNER

    test_app.dependency_overrides[get_session] = _override_session
    test_app.dependency_overrides[get_current_user] = _override_user
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


async def _seed_project(db_session):
    db_session.add_all([
        User(id=XF_OWNER.id, username=XF_OWNER.username, email="xf@example.com", hashed_password="x"),
        NovelProject(id=XF_PROJECT, user_id=XF_OWNER.id, title="选区测试"),
    ])
    chapter = Chapter(project_id=XF_PROJECT, chapter_number=1, status="successful", word_count=len(PROSE))
    db_session.add(chapter)
    await db_session.flush()
    version = ChapterVersion(chapter_id=chapter.id, content=PROSE)
    db_session.add(version)
    await db_session.flush()
    chapter.selected_version_id = version.id
    await db_session.commit()
    return chapter


@pytest.mark.asyncio
async def test_route_refunds_when_transform_undelivered(monkeypatch, db_session):
    await _seed_project(db_session)
    svc = QuotaService(db_session)
    before = (await svc.get_or_create_quota(XF_OWNER.id)).credit_balance

    async def fake_transform(session, **kwargs):
        return TransformOutcome(kwargs["selected_text"], False, "模型这次没返回可用的正文")

    monkeypatch.setattr(
        "app.services.text_transform_service.transform_selection", fake_transform
    )
    async with _build_client(db_session) as client:
        resp = await client.post(
            f"/api/writer/novels/{XF_PROJECT}/transform",
            json={"chapter_number": 1, "action": "rewrite", "selected_text": PROSE},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["delivered"] is False
    assert data["charged"] == 3
    assert data["refunded"] == 3
    assert data["applied"] is False
    assert data["result_text"] == PROSE
    assert "退回" in data["message"]
    db_session.expire_all()
    assert (await svc.get_or_create_quota(XF_OWNER.id)).credit_balance == before


@pytest.mark.asyncio
async def test_route_keeps_charge_when_delivered(monkeypatch, db_session):
    await _seed_project(db_session)
    svc = QuotaService(db_session)
    before = (await svc.get_or_create_quota(XF_OWNER.id)).credit_balance

    async def fake_transform(session, **kwargs):
        return TransformOutcome(kwargs["selected_text"] + "他终于回头。", True)

    monkeypatch.setattr(
        "app.services.text_transform_service.transform_selection", fake_transform
    )
    async with _build_client(db_session) as client:
        resp = await client.post(
            f"/api/writer/novels/{XF_PROJECT}/transform",
            json={"chapter_number": 1, "action": "rewrite", "selected_text": PROSE},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["delivered"] is True
    assert data["charged"] == 3
    assert data["refunded"] == 0
    assert data["result_text"].endswith("他终于回头。")
    db_session.expire_all()
    assert (await svc.get_or_create_quota(XF_OWNER.id)).credit_balance == before - 3
