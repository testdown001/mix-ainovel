import asyncio
from types import SimpleNamespace

from app.services.enhanced_writing_flow import EnhancedWritingFlow


def test_enhanced_writing_flow_uses_rule_mode_for_foreshadowing_reminders():
    flow = EnhancedWritingFlow(
        db=SimpleNamespace(),
        llm_service=SimpleNamespace(),
        prompt_service=SimpleNamespace(),
    )

    captured = {}

    async def _get_constitution(project_id):
        return None

    async def _ensure_default_persona(project_id):
        return SimpleNamespace(style_guide="起点风")

    async def _get_reminders(project_id, chapter_number, chapter_outline=None, user_id=None, use_llm=True):
        captured["use_llm"] = use_llm
        return {"foreshadowings_to_develop": []}

    async def _get_faction_context(project_id):
        return "（无势力设定）"

    flow.constitution_service = SimpleNamespace(
        get_constitution=_get_constitution,
        get_constitution_context=lambda constitution: "",
    )
    flow.writer_persona_service = SimpleNamespace(
        ensure_default_persona=_ensure_default_persona,
        get_persona_context=lambda persona: "人格上下文",
        get_version_style_hint=lambda persona, idx: f"hint-{idx}",
    )
    flow.foreshadowing_service = SimpleNamespace(
        get_foreshadowing_reminders=_get_reminders,
    )
    flow.faction_service = SimpleNamespace(
        get_faction_context=_get_faction_context,
    )

    context = asyncio.run(
        flow.prepare_writing_context(
            project_id="proj-1",
            chapter_number=7,
            chapter_outline="章节大纲",
        )
    )

    assert captured["use_llm"] is False
    assert context["writer_persona"] == "人格上下文"
