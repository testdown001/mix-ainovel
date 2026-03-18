import asyncio

from app.services.version_generation_service import VersionGenerationService


class _DummyOrchestrator:
    def __init__(self):
        self.generated_indexes = []

    def _resolve_style_hints(self, enhanced_context, version_count):
        return [{"label": f"style-{idx}"} for idx in range(version_count)]

    async def _generate_single_version(self, **kwargs):
        index = kwargs["index"]
        self.generated_indexes.append(index)
        return {
            "index": index,
            "content": f"版本{index}",
            "metadata": {"style_hint": kwargs.get("style_hint")},
        }

    async def _run_ai_review(self, *, versions, chapter_mission, user_id):
        return 99, {"score": 88, "selected": 0}

    # 新增属性以支持 VersionGenerationService.run()
    @property
    def generation_policy_service(self):
        """Mock generation_policy_service"""
        class _PolicyService:
            def resolve_style_hints(self, enhanced_context, version_count):
                return [{"label": f"style-{idx}"} for idx in range(version_count)]
        return _PolicyService()

    @property
    def single_version_generation_service(self):
        """Mock single_version_generation_service"""
        class _VersionService:
            async def generate(self, **kwargs):
                index = kwargs["index"]
                self.generated_indexes.append(index)
                return {
                    "index": index,
                    "content": f"版本{index}",
                    "metadata": {"style_hint": kwargs.get("style_hint")},
                }
        svc = _VersionService()
        svc.generated_indexes = self.generated_indexes
        return svc


def test_version_generation_service_runs_versions_and_clamps_best_index():
    orchestrator = _DummyOrchestrator()
    service = VersionGenerationService(orchestrator)

    config = type("Config", (), {"disable_guardrail_rewrite": False})()
    result = asyncio.run(
        service.run(
            prompt_input="prompt_input",
            writer_prompt="writer_prompt",
            enhanced_context=None,
            version_count=2,
            project_id="proj-1",
            chapter_number=4,
            outline_title="第四章",
            outline_summary="摘要",
            chapter_mission={"goal": "推进剧情"},
            forbidden_characters=[],
            allowed_new_characters=[],
            user_id=1,
            writer_blueprint={"characters": []},
            memory_context=None,
            config=config,
            chapter_target_word_count=3000,
            chapter_word_count_max=4000,
            genre_profile=None,
        )
    )

    assert orchestrator.generated_indexes == [0, 1]
    assert len(result["versions"]) == 2
    assert result["best_version_index"] == 1
    assert result["ai_review_result"]["score"] == 88
