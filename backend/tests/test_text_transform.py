"""选区变换：只改圈中段落、计费 reason=transform、失败可退。"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.models  # noqa: F401
from app.services.generation_billing_service import charge_transform, refund_generation, transform_price
from app.services.quota_service import QuotaService
from app.services.text_transform_service import transform_selection


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
    assert result.startswith("他推开门")


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
    assert result.endswith("。")
    assert calls["ctor"][1] == "LLMService"
