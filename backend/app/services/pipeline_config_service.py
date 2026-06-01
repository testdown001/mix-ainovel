from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..core.config import settings
from ..services.writer_shared import resolve_version_count as _shared_resolve_version_count

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    preset: str = "basic"
    version_count: int = 2
    enable_preview: bool = False
    enable_optimizer: bool = False
    enable_consistency: bool = False
    enable_enrichment: bool = False
    async_finalize: bool = False
    enable_constitution: bool = False
    enable_persona: bool = False
    enable_six_dimension: bool = False
    enable_reader_sim: bool = False
    enable_self_critique: bool = False
    enable_memory: bool = False
    enable_rag: bool = True
    rag_mode: str = "simple"
    enable_foreshadowing: bool = False
    enable_faction: bool = False
    enable_anti_hallucination: bool = False
    rag_retrieval_mode: str = "vector"
    enable_pacing_control: bool = False
    pacing_model: str = "default"
    enable_humanization: bool = False
    humanization_threshold: int = 70
    enable_lightweight_humanization: bool = False
    enable_fingerprint: bool = False
    enable_polish: bool = False
    enable_mission_brief: bool = False
    enable_density_compression: bool = False
    enable_scene_by_scene: bool = False
    enable_prose_sculpting: bool = False
    enable_golden_paragraph: bool = False
    enable_reference_prose: bool = False
    enable_voice_samples: bool = False
    enable_narrative_variety: bool = False
    use_slim_prompt: bool = False
    literary_adaptive_postprocess: bool = True
    enable_fast_path: bool = False
    disable_guardrail_rewrite: bool = False
    skip_history_summary_backfill: bool = False
    use_local_anti_hallucination: bool = False
    enable_power_system: bool = False
    enable_character_relationships: bool = False
    enable_trajectory_analysis: bool = False
    enable_temporal_state: bool = False


class PipelineConfigService:
    """统一解析 pipeline flow_config 到运行时 PipelineConfig。"""

    def __init__(self, session):
        self.session = session

    async def resolve_config(self, flow_config: Optional[Dict[str, Any]]) -> PipelineConfig:
        """解析最终生效的 PipelineConfig。

        开关生效遵循固定的 4 层覆写顺序（后者覆盖前者），排障时按此顺序判断生效值：
          1) preset 块：basic/fast/enhanced/ultimate/platinum/literary 各自硬编码一组开关；
          2) settings 全局开关：writer_fast_mode（强制 preset=fast，literary 除外）、
             enable_humanization / enable_author_fingerprint / enable_pacing_control 等；
          3) writer_ultra_fast_mode：进一步关闭几乎所有后处理；
          4) flow_config 显式覆写：仅下方 allowlist 中的键允许被请求覆盖。

        开关使用率审计结论（2026-06-01）：当前 ~44 个布尔开关均"可达"——
        要么被某个 preset 置 True，要么在 flow_config allowlist 中可被显式开启，
        不存在"永远为假的死分支"可安全删除；复杂度集中在上述覆写顺序而非死代码。
        后续可考虑的合并：humanization 三开关
        (enable_humanization / humanization_threshold / enable_lightweight_humanization)
        归并为单一 level 枚举，降低组合维度。
        """
        flow_config = flow_config or {}
        preset = flow_config.get("preset", "basic")

        if getattr(settings, "writer_fast_mode", False) and preset not in ("literary",):
            preset = "fast"

        config = PipelineConfig(preset=preset)
        config.version_count = await self.resolve_version_count(flow_config.get("versions"))
        config.literary_adaptive_postprocess = bool(
            getattr(settings, "writer_literary_adaptive_postprocess", True)
        )

        config.rag_retrieval_mode = getattr(settings, "rag_retrieval_mode", "vector")
        config.enable_pacing_control = bool(getattr(settings, "enable_pacing_control", False))
        config.pacing_model = getattr(settings, "pacing_model", "default")

        if getattr(settings, "enable_humanization", True):
            config.enable_humanization = True
            config.humanization_threshold = getattr(settings, "humanization_threshold", 70)
        if getattr(settings, "enable_author_fingerprint", True):
            config.enable_fingerprint = True

        if preset in ("enhanced", "ultimate", "platinum"):
            config.enable_constitution = True
            config.enable_persona = True
            config.enable_foreshadowing = True
            config.enable_faction = True
            config.enable_power_system = True
            config.enable_character_relationships = True
            config.enable_trajectory_analysis = True
            config.enable_temporal_state = True
            config.rag_mode = settings.rag_default_mode
            if getattr(settings, "enable_entity_registry", True):
                config.enable_anti_hallucination = True

        if preset == "enhanced":
            config.enable_six_dimension = True
            config.enable_enrichment = True
            config.enable_polish = True

        if preset == "ultimate":
            config.enable_memory = True
            config.enable_six_dimension = True
            config.enable_consistency = True
            config.enable_enrichment = True
            config.enable_polish = True

        if preset == "platinum":
            config.version_count = 1
            config.enable_memory = True
            config.enable_six_dimension = True
            config.enable_self_critique = True
            config.enable_reader_sim = True
            config.enable_consistency = True
            config.enable_enrichment = True
            config.enable_polish = True
            config.enable_optimizer = True

        if preset == "literary":
            config.version_count = 1
            config.enable_rag = True
            config.rag_mode = settings.rag_default_mode
            config.enable_constitution = True
            config.enable_persona = True
            config.enable_foreshadowing = True
            config.enable_faction = True
            config.enable_power_system = True
            config.enable_character_relationships = True
            config.enable_trajectory_analysis = True
            config.enable_temporal_state = True
            config.enable_memory = True
            config.enable_humanization = True
            config.enable_fingerprint = True
            config.enable_mission_brief = True
            config.enable_scene_by_scene = True
            config.enable_prose_sculpting = True
            config.enable_golden_paragraph = True
            config.enable_reference_prose = True
            config.enable_voice_samples = True
            config.enable_narrative_variety = True
            config.use_slim_prompt = True
            if getattr(settings, "enable_entity_registry", True):
                config.enable_anti_hallucination = True

        if preset == "basic":
            config.enable_rag = True
            config.version_count = 1

        if preset == "fast":
            config.version_count = 1
            config.enable_fast_path = True
            config.enable_rag = True
            config.rag_mode = "simple"
            config.enable_constitution = False
            config.enable_persona = False
            config.enable_foreshadowing = False
            config.enable_faction = False
            config.enable_power_system = False
            config.enable_character_relationships = False
            config.enable_trajectory_analysis = False
            config.enable_memory = False
            config.enable_humanization = False
            config.enable_lightweight_humanization = True
            config.enable_fingerprint = False
            config.enable_mission_brief = False
            config.enable_scene_by_scene = False
            config.enable_prose_sculpting = False
            config.enable_golden_paragraph = False
            config.enable_reference_prose = False
            config.enable_voice_samples = False
            config.enable_narrative_variety = False
            config.use_slim_prompt = False
            config.enable_six_dimension = False
            config.enable_self_critique = False
            config.enable_reader_sim = False
            config.enable_consistency = False
            config.enable_optimizer = False
            config.enable_enrichment = False
            config.enable_density_compression = False
            config.enable_preview = False
            config.disable_guardrail_rewrite = True
            config.skip_history_summary_backfill = True
            config.use_local_anti_hallucination = True
            config.enable_anti_hallucination = bool(getattr(settings, "enable_entity_registry", True))

        if getattr(settings, "writer_ultra_fast_mode", False):
            config.version_count = 1
            config.enable_fast_path = True
            config.enable_scene_by_scene = False
            config.enable_self_critique = False
            config.enable_consistency = False
            config.enable_humanization = False
            config.enable_lightweight_humanization = False
            config.enable_optimizer = False
            config.enable_enrichment = False
            config.enable_polish = False
            config.enable_reader_sim = False
            config.enable_anti_hallucination = False
            config.enable_density_compression = False
            config.enable_six_dimension = False
            config.enable_fingerprint = False
            config.enable_mission_brief = False
            config.enable_narrative_variety = False
            config.enable_reference_prose = False
            config.enable_voice_samples = False
            config.enable_prose_sculpting = False
            config.enable_golden_paragraph = False
            config.enable_constitution = False
            config.enable_persona = False
            config.enable_foreshadowing = False
            config.enable_faction = False
            config.enable_memory = False
            config.disable_guardrail_rewrite = True
            config.skip_history_summary_backfill = True
            config.use_local_anti_hallucination = True
            logger.info("Ultra fast mode: 已启用快速路径并跳过所有后处理步骤")

        for key in (
            "enable_preview",
            "enable_optimizer",
            "enable_consistency",
            "enable_enrichment",
            "async_finalize",
            "enable_rag",
            "enable_polish",
            "enable_mission_brief",
            "enable_density_compression",
            "enable_pacing_control",
            "enable_scene_by_scene",
            "enable_prose_sculpting",
            "enable_golden_paragraph",
            "enable_reference_prose",
            "enable_voice_samples",
            "enable_narrative_variety",
            "use_slim_prompt",
            "literary_adaptive_postprocess",
            "enable_fast_path",
            "enable_lightweight_humanization",
            "disable_guardrail_rewrite",
            "skip_history_summary_backfill",
            "use_local_anti_hallucination",
            "enable_power_system",
            "enable_character_relationships",
            "enable_trajectory_analysis",
        ):
            if key in flow_config and flow_config[key] is not None:
                setattr(config, key, bool(flow_config[key]))

        if flow_config.get("rag_mode"):
            config.rag_mode = str(flow_config["rag_mode"])
        if flow_config.get("rag_retrieval_mode"):
            config.rag_retrieval_mode = str(flow_config["rag_retrieval_mode"])
        if flow_config.get("pacing_model"):
            config.pacing_model = str(flow_config["pacing_model"])

        return config

    async def resolve_version_count(self, requested_count: Optional[int]) -> int:
        return await _shared_resolve_version_count(self.session, requested_count)
