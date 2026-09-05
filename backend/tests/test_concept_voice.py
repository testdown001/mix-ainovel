"""第二批：试写候选不自动生效，选择可追溯且只影响本书口吻。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.novel import NovelProject
from app.models.user import User
from app.models.creative_memory import CreativeMemoryItem
from app.schemas.concept_dossier import ConceptDossier
from app.schemas.concept_voice import VoiceTrialResult, VoiceCandidate
from app.services.concept_voice_service import ConceptVoiceService, emotional_core_brief
from app.services.concept_dossier_service import ConceptDossierService, format_dossier_for_prompt
from app.services.creative_memory_service import CreativeMemoryService


async def setup_voice(session):
    session.add(User(id=7, username="voice-author", hashed_password="unused"))
    project = NovelProject(id="voice-book", user_id=7, title="旧碗", exclusions="不写爱情",
        concept_dossier={"dossier": {"core_selling_line": "师兄弟重开旧店",
            "emotional_core": {"cherished": "一起吃饭的日子", "hard_choice": "开店的钱拿去买药"}}})
    session.add(project)
    await session.commit()
    result = VoiceTrialResult(scene="师兄拿出开店的钱替师弟买药，嘴上说是借款", candidates=[
        VoiceCandidate(label="克制留白", style_notes="让停顿承载关心，少解释心理", text="师兄把钱推过去，没有接师弟的谢意。"*7),
        VoiceCandidate(label="市井对白", style_notes="对白带生活气，嘴硬但行动温柔", text="钱算借你的。师兄说完，顺手把药包塞进他怀里。"*6),
    ])
    llm = SimpleNamespace(generate_structured=AsyncMock(return_value=result))
    return project, ConceptVoiceService(session, llm, SimpleNamespace(get_prompt=AsyncMock(return_value="试写")))


@pytest.mark.asyncio
async def test_trials_only_enter_generation_memory_after_explicit_selection(db_session):
    project, svc = await setup_voice(db_session)
    assert await svc.view(project) == {"trial": None}
    svc.llm.generate_structured.assert_not_called()
    trial = (await svc.generate(project, 7, "借钱买药"))["trial"]
    assert trial["selected_id"] is None
    assert (await db_session.execute(select(CreativeMemoryItem))).scalars().all() == []
    first, second = trial["candidates"]
    chosen = (await svc.select(project, 7, trial["id"], first["id"]))["trial"]
    assert chosen["selected_id"] == first["id"]
    memories = await CreativeMemoryService(db_session).active_for_generation(
        user_id=7, project_id=project.id, chapter_number=1)
    assert len(memories) == 1
    assert memories[0].scope == "novel" and memories[0].pinned
    assert "不是正史" in memories[0].content and first["text"] in memories[0].content
    assert second["text"] not in memories[0].content
    assert memories[0].evidence["candidate_id"] == first["id"]
    context = await CreativeMemoryService(db_session).build_generation_context(
        user_id=7, project_id=project.id, chapter_number=1)
    from app.services.prompt_compiler_service import PromptCompilerService
    from app.services.prompt_budget_manager import PromptBudgetManager
    sections, _ = PromptCompilerService().compile(
        plan=SimpleNamespace(prompt_modules=["creative_memory", "world_blueprint"], skill_policies=[]),
        sections=[("[世界蓝图]", "背景" * 30000), ("[已确认创作记忆]", context["prompt"])],
    )
    final = "\n".join(value for _, value in PromptBudgetManager().apply_budget(sections))
    assert first["text"] in final and "不是正史" in final
    assert await CreativeMemoryService(db_session).active_for_generation(
        user_id=7, project_id="another-book", chapter_number=1) == []
    await svc.select(project, 7, trial["id"], first["id"])
    await svc.select(project, 7, trial["id"], second["id"])
    rows = (await db_session.execute(select(CreativeMemoryItem))).scalars().all()
    assert len(rows) == 1 and second["text"] in rows[0].content
    assert first["text"] not in rows[0].content


@pytest.mark.asyncio
async def test_stale_or_fabricated_trial_selection_is_rejected(db_session):
    project, svc = await setup_voice(db_session)
    trial = (await svc.generate(project, 7, ""))["trial"]
    with pytest.raises(HTTPException) as bad:
        await svc.select(project, 7, trial["id"], "invented")
    assert bad.value.status_code == 404
    await ConceptDossierService(db_session).patch_dossier(project, {"emotional_core": {"cherished": "新的牵挂"}})
    assert (await svc.view(project))["trial"]["stale"]
    with pytest.raises(HTTPException) as stale:
        await svc.select(project, 7, trial["id"], trial["candidates"][0]["id"])
    assert stale.value.status_code == 409
    assert (await db_session.execute(select(CreativeMemoryItem))).scalars().all() == []


@pytest.mark.asyncio
async def test_failed_regeneration_keeps_trial_and_selected_memory(db_session):
    project, svc = await setup_voice(db_session)
    trial = (await svc.generate(project, 7, ""))["trial"]
    await svc.select(project, 7, trial["id"], trial["candidates"][0]["id"])
    svc.llm.generate_structured.return_value = None
    with pytest.raises(HTTPException):
        await svc.generate(project, 7, "")
    assert (await svc.view(project))["trial"]["selected_id"] == trial["candidates"][0]["id"]


@pytest.mark.asyncio
async def test_voice_routes_check_ownership_before_generation(monkeypatch):
    from app.api.routers import novels
    owner = AsyncMock(side_effect=HTTPException(404, "project"))
    monkeypatch.setattr(novels, "NovelService", lambda session: SimpleNamespace(ensure_project_owner=owner))
    for route, extra in (
        (novels.get_concept_voice_trial, {}),
        (novels.generate_concept_voice_trial, {"payload": {"scene": ""}}),
        (novels.select_concept_voice_trial, {"payload": {"trial_id": "a", "candidate_id": "b"}}),
    ):
        with pytest.raises(HTTPException) as err:
            await route("another-user-project", session=None, current_user=SimpleNamespace(id=7), **extra)
        assert err.value.status_code == 404


def test_emotional_core_survives_schema_and_blueprint_prompt_without_inventing_missing_values():
    dossier = ConceptDossier(emotional_core={"cherished": "一起吃饭的日子", "exception": "嘴上只谈利益却替师弟买药"})
    payload = dossier.model_dump()
    assert dossier.emotional_core.hard_choice == ""
    blueprint_prompt = format_dossier_for_prompt(payload)
    writer_prompt = emotional_core_brief(SimpleNamespace(concept_dossier={"dossier": payload}))
    assert "一起吃饭的日子" in blueprint_prompt and "一起吃饭的日子" in writer_prompt
    assert "嘴上只谈利益却替师弟买药" in writer_prompt and "不是已发生事实" in writer_prompt
    assert emotional_core_brief(SimpleNamespace()) == ""
