import asyncio

from app.services.context_planner_service import ContextPlan, ContextPlannerService


def test_context_planner_builds_phase_tasks_and_skill_policies():
    service = ContextPlannerService()

    plan = asyncio.run(
        service.build_plan(
            project_id="proj-1",
            chapter_number=9,
            writing_notes="强化人物冲突，并回收之前埋下的伏笔",
            flow_config={
                "preset": "platinum",
                "selected_skills": [
                    {"skill_id": "foreshadowing"},
                    {"skill_id": "dialogue_polish"},
                ],
                "enable_rag": True,
                "enable_memory": True,
                "enable_fast_path": False,
                "enable_consistency": True,
                "enable_foreshadowing": True,
                "enable_constitution": True,
                "enable_power_system": True,
                "enable_character_relationships": True,
                "enable_reader_sim": True,
                "enable_self_critique": True,
                "enable_six_dimension": True,
                "enable_mission_brief": True,
                "rag_retrieval_mode": "vector",
            },
            selected_skills=[
                {"skill_id": "foreshadowing"},
                {"skill_id": "dialogue_polish"},
            ],
            user_id=7,
            blueprint={
                "characters": [{"name": "林玄"}, {"name": "苏璃"}],
                "chapter_outline": [{"chapter_number": idx} for idx in range(1, 13)],
            },
            outline_data={
                "chapter_number": 9,
                "title": "终局前夜",
                "summary": "大战前夕，主角需要回收旧伏笔并重新整合队伍。",
            },
            history_context={
                "previous_summary": "主角刚刚拿到关键情报。",
                "story_skeleton": "主线逐步逼近终局，旧线索开始交汇。",
                "completed_chapters": [{"chapter_number": idx} for idx in range(1, 9)],
            },
        )
    )

    assert isinstance(plan, ContextPlan)
    assert plan.chapter_phase == "resolution"
    assert plan.intent["chapter_title"] == "终局前夜"
    assert any(task.source == "local_plot_rag" for task in plan.retrieval_tasks)
    assert any(task.source == "global_arc_rag" for task in plan.retrieval_tasks)
    assert any(task.source == "state_rag" for task in plan.retrieval_tasks)
    assert any(task.source == "symbolic_rag" for task in plan.retrieval_tasks)
    assert "mission_brief" in plan.prompt_modules
    assert "foreshadowing_check" in plan.verification_tasks
    assert "commercial_hook_check" in plan.verification_tasks
    assert any(policy.skill_id == "foreshadowing" and policy.phase == "retrieve" for policy in plan.skill_policies)
    assert any(policy.skill_id == "dialogue_polish" and policy.phase == "pre_prompt" for policy in plan.skill_policies)


def test_context_planner_build_retrieval_queries_prefers_plan_and_dedupes():
    service = ContextPlannerService()
    plan = ContextPlan.from_dict(
        {
            "intent": {"core_goal": "推进决战"},
            "chapter_phase": "climax",
            "retrieval_tasks": [
                {
                    "task_id": "local_plot",
                    "source": "local_plot_rag",
                    "mode": "vector",
                    "query_template": "{outline_title}",
                    "priority": 3,
                    "max_items": 4,
                },
                {
                    "task_id": "global_arc",
                    "source": "global_arc_rag",
                    "mode": "summary",
                    "query_template": "{story_skeleton}",
                    "priority": 2,
                    "max_items": 3,
                },
                {
                    "task_id": "state",
                    "source": "state_rag",
                    "mode": "structured",
                    "query_template": "{character_names}",
                    "priority": 2,
                    "max_items": 3,
                },
            ],
            "skill_policies": [],
            "prompt_modules": ["chapter_goal"],
            "verification_tasks": ["continuity_check"],
            "budgets": {},
            "is_fast_path": False,
            "metadata": {},
        }
    )

    queries = service.build_retrieval_queries(
        plan=plan,
        outline_title="终局前夜",
        outline_summary="大战前夕的总动员",
        writing_notes="大战前夕的总动员",
        character_names=["林玄", "苏璃", "林玄"],
        story_skeleton="主线逐步逼近终局，旧线索开始交汇。",
        fast_rag_queries=["不会被使用"],
    )

    assert queries[0] == "终局前夜"
    assert "大战前夕的总动员" in queries
    assert "主线逐步逼近终局，旧线索开始交汇。" in queries
    assert "林玄 苏璃 林玄" in queries
    assert len(queries) <= 4


def test_context_planner_prefers_external_skill_policies():
    service = ContextPlannerService()

    plan = asyncio.run(
        service.build_plan(
            project_id="proj-2",
            chapter_number=4,
            writing_notes="保持人物对白辨识度",
            flow_config={
                "preset": "enhanced",
                "enable_rag": True,
                "enable_fast_path": False,
                "enable_consistency": True,
            },
            selected_skills=[{"skill_id": "dialogue_polish"}],
            skill_policies=[
                {
                    "skill_id": "dialogue_polish",
                    "phase": "pre_prompt",
                    "params": {"intensity": "strong"},
                    "retrieval_hints": ["角色对白样本", "人物口头禅"],
                    "prompt_hints": ["对白风格差异化"],
                    "verify_hints": ["对白风格漂移检查"],
                }
            ],
            blueprint={"chapter_outline": [{"chapter_number": idx} for idx in range(1, 8)]},
            outline_data={"title": "旧友重逢", "summary": "通过对白推进人物关系"},
            history_context={},
        )
    )

    assert len(plan.skill_policies) == 1
    assert plan.skill_policies[0].params["intensity"] == "strong"
    assert plan.skill_policies[0].prompt_hints == ["对白风格差异化"]
