from app.services.context_planner_service import ContextPlan
from app.services.narrative_verifier_service import NarrativeVerifierService


def test_narrative_verifier_builds_report_from_plan_and_reviews():
    service = NarrativeVerifierService()
    plan = ContextPlan.from_dict(
        {
            "intent": {"core_goal": "推进高潮并回收旧伏笔"},
            "chapter_phase": "climax",
            "retrieval_tasks": [],
            "skill_policies": [{"skill_id": "foreshadowing", "phase": "retrieve"}],
            "prompt_modules": [],
            "verification_tasks": [
                "continuity_check",
                "consistency_check",
                "commercial_hook_check",
                "skill_policy_check",
            ],
            "budgets": {},
            "is_fast_path": False,
            "metadata": {},
        }
    )

    report = service.verify(
        plan=plan,
        chapter_text="林玄刚要推门，却听见门外忽然传来一声低笑。下一刻，整座大殿的灯火同时熄灭。",
        review_summaries={
            "consistency": {
                "violations": [{"message": "轻微时间线冲突"}],
            }
        },
        evidence_summary={
            "total_items": 7,
            "category_counts": {"symbolic_items": 2},
        },
    )

    assert report["plan_phase"] == "climax"
    assert report["task_count"] == 4
    assert report["status_counts"]["warning"] >= 1
    assert any(task["task"] == "commercial_hook_check" for task in report["tasks"])
    assert any(task["task"] == "skill_policy_check" for task in report["tasks"])
    assert report["summary"]


def test_narrative_verifier_detects_weak_commercial_hook():
    service = NarrativeVerifierService()
    plan = ContextPlan.from_dict(
        {
            "intent": {},
            "chapter_phase": "development",
            "retrieval_tasks": [],
            "skill_policies": [],
            "prompt_modules": [],
            "verification_tasks": ["commercial_hook_check"],
            "budgets": {},
            "is_fast_path": False,
            "metadata": {},
        }
    )

    report = service.verify(
        plan=plan,
        chapter_text="这一章到这里就结束了。众人各自散去，准备明天再说。",
        review_summaries={},
        evidence_summary={},
    )

    hook_task = report["tasks"][0]
    assert hook_task["task"] == "commercial_hook_check"
    assert hook_task["status"] == "warning"
