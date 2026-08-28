from app.services.context_planner_service import ContextPlannerService
from app.services.prompt_compiler_service import PromptCompilerService


def test_published_skill_snapshot_is_carried_into_prompt_policy():
    planner = ContextPlannerService()
    snapshot = {
        "id": 42,
        "version_label": "v1.0.0",
        "phase": "verify",
        "rules": ["以动作收尾"],
        "prohibitions": ["不要作者式总结"],
        "checker_keys": ["natural_ending"],
        "prompt_hints": ["具体信息"],
        "verify_hints": ["结尾自然度"],
    }
    policies = planner._build_skill_policies([{"skill_id": "natural_closing", "version_snapshot": snapshot}])
    assert policies[0].version_id == 42
    assert policies[0].prohibitions == ["不要作者式总结"]
    section = PromptCompilerService().build_skill_instruction_section(
        type("Plan", (), {"skill_policies": policies})()
    )
    assert section is not None
    assert "必须做到：以动作收尾" in section[1]
    assert "明确避免：不要作者式总结" in section[1]
