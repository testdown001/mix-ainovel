import asyncio

from app.services.pipeline_config_service import PipelineConfigService


class _DummySession:
    async def execute(self, stmt):
        """Mock execute 返回空 scalar 结果"""
        class _ScalarResult:
            def scalar_one_or_none(self):
                return None
            def scalars(self):
                return self
            def all(self):
                return []
            def first(self):
                return None
        return _ScalarResult()


def test_pipeline_config_service_resolves_fast_override():
    service = PipelineConfigService(_DummySession())

    config = asyncio.run(
        service.resolve_config(
            {
                "preset": "fast",
                "enable_rag": True,
                "enable_scene_by_scene": True,
                "enable_reference_prose": True,
            }
        )
    )

    assert config.preset == "fast"
    assert config.enable_fast_path is True
    assert config.enable_scene_by_scene is True
    assert config.enable_reference_prose is True


def test_pipeline_config_service_resolves_literary_defaults():
    service = PipelineConfigService(_DummySession())

    config = asyncio.run(service.resolve_config({"preset": "literary"}))

    assert config.preset == "literary"
    assert config.enable_scene_by_scene is True
    assert config.enable_reference_prose is True
