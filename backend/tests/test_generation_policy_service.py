from types import SimpleNamespace

from app.services.generation_policy_service import GenerationPolicyService


def test_generation_policy_service_resolves_temperature():
    service = GenerationPolicyService()

    high = service.resolve_temperature({"macro_beat": "高潮爆发"})
    low = service.resolve_temperature({"macro_beat": "过渡日常"})
    default = service.resolve_temperature({})

    assert high == 0.85
    assert low == 0.60
    assert default == 0.75


def test_generation_policy_service_resolves_literary_profile():
    service = GenerationPolicyService()
    config = SimpleNamespace(
        literary_adaptive_postprocess=True,
        enable_prose_sculpting=True,
        enable_golden_paragraph=True,
        enable_humanization=True,
    )

    profile = service.resolve_literary_postprocess_profile(
        config=config,
        chapter_mission={"chapter_type": "过渡", "macro_beat_description": "过渡日常"},
        target_word_count=2200,
    )

    assert profile["enable_golden_paragraph"] is False
    assert profile["enable_prose_sculpting"] is False
    assert profile["enable_humanization"] is False


def test_generation_policy_service_build_stage_flags():
    service = GenerationPolicyService()
    config = SimpleNamespace(
        enable_preview=False,
        enable_optimizer=True,
        enable_polish=False,
        enable_mission_brief=True,
        enable_consistency=True,
        enable_enrichment=False,
        enable_constitution=True,
        enable_persona=False,
        enable_six_dimension=True,
        enable_reader_sim=False,
        enable_self_critique=True,
        enable_memory=True,
        enable_rag=True,
        rag_mode="two_stage",
        enable_scene_by_scene=False,
        enable_prose_sculpting=True,
        enable_golden_paragraph=False,
        enable_reference_prose=False,
        enable_voice_samples=False,
        enable_narrative_variety=False,
        use_slim_prompt=False,
        literary_adaptive_postprocess=True,
        enable_fast_path=False,
        disable_guardrail_rewrite=True,
        use_local_anti_hallucination=True,
        enable_power_system=True,
        enable_character_relationships=False,
        enable_trajectory_analysis=True,
    )

    flags = service.build_stage_flags(config)

    assert flags["optimizer"] is True
    assert flags["mission_brief"] is True
    assert flags["rag_mode"] is True
    assert flags["power_system"] is True
