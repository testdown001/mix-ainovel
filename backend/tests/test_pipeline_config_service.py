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


def test_pipeline_config_service_maps_literary_alias_to_premium():
    # 旧名 literary 在入口归一化为 premium（三档收敛后的官方映射）；
    # 精品模式默认进入场景化质量主链；显式 false 才回退整章路径。
    service = PipelineConfigService(_DummySession())

    config = asyncio.run(service.resolve_config({"preset": "literary"}))

    assert config.preset == "premium"
    assert config.version_count == 1
    assert config.enable_memory is True
    assert config.enable_self_critique is True
    assert config.enable_scene_by_scene is True
