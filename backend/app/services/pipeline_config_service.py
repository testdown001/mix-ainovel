from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..core.config import settings
from ..core.feature_gating import normalize_preset
from ..services.writer_shared import resolve_version_count as _shared_resolve_version_count

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    preset: str = "fast"  # 默认快速模式（免费档位）
    model_code: Optional[str] = None  # 所选模型目录 code(章鱼1.0/2.0/3.0)，决定正文实际调用的真实大模型
    version_count: int = 2
    enable_preview: bool = False
    enable_optimizer: bool = False
    enable_consistency: bool = False
    enable_enrichment: bool = False
    async_finalize: bool = False
    enable_constitution: bool = False
    enable_persona: bool = False
    enable_six_dimension: bool = False
    six_dimension_min_score: int = 70
    enable_reader_sim: bool = False
    enable_self_critique: bool = False
    enable_memory: bool = False
    # 轻量状态记忆（CharacterState/TimelineEvent 抽取落库，不含 mem0）：纯 preset 驱动，
    # 不加入 FLOW_OVERRIDE_SWITCHES，不开放 flow_config 覆写
    enable_state_tracking: bool = False
    enable_rag: bool = True
    rag_mode: str = "simple"
    enable_foreshadowing: bool = False
    enable_faction: bool = False
    enable_anti_hallucination: bool = False
    rag_retrieval_mode: str = "hybrid"
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
    enable_outline_revision: bool = False


class PipelineConfigService:
    def __init__(self, session):
        self.session = session

    async def resolve_config(self, flow_config: Optional[Dict[str, Any]]) -> PipelineConfig:
        """解析最终生效的 PipelineConfig。

        开关生效遵循固定的 3 层覆写顺序（后者覆盖前者）：
          1) preset 块：fast/standard/premium 各自硬编码一组开关；
          2) settings 全局开关：writer_fast_mode（强制 preset=fast）、
             enable_humanization / enable_author_fingerprint / enable_pacing_control 等；
          3) flow_config 显式覆写：仅下方 allowlist 中的键允许被请求覆盖。

        🎯 三种生成模式（2026-06-02 精简）：
          - fast (free):     极速路径，轻量处理，30-60秒
          - standard (creator+): 六维评审+世界观+打磨，3-5分钟
          - premium (flagship+): 完整流程+自我批判+读者模拟，5-10分钟
        """
        flow_config = flow_config or {}
        # 旧名（basic/enhanced/ultimate/platinum/literary）在入口归一化到现行三档，
        # 与档位门控共用同一张映射表（core/feature_gating.PRESET_ALIASES）
        preset = normalize_preset(flow_config.get("preset"))

        # 全局快速模式强制覆盖
        if getattr(settings, "writer_fast_mode", False):
            preset = "fast"

        config = PipelineConfig(preset=preset)
        config.version_count = await self.resolve_version_count(flow_config.get("versions"))
        config.literary_adaptive_postprocess = bool(
            getattr(settings, "writer_literary_adaptive_postprocess", True)
        )

        config.rag_retrieval_mode = getattr(settings, "rag_retrieval_mode", "vector")
        config.enable_pacing_control = bool(getattr(settings, "enable_pacing_control", False))
        config.pacing_model = getattr(settings, "pacing_model", "default")
        config.six_dimension_min_score = int(getattr(settings, "six_dimension_min_score", 70))

        if getattr(settings, "enable_humanization", True):
            config.enable_humanization = True
            config.humanization_threshold = getattr(settings, "humanization_threshold", 70)
        if getattr(settings, "enable_author_fingerprint", True):
            config.enable_fingerprint = True

        # === 快速模式 (free) ===
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

        # === 标准模式 (creator+) ===
        elif preset == "standard":
            config.enable_constitution = True
            config.enable_persona = True
            config.enable_foreshadowing = True
            config.enable_faction = True
            config.enable_power_system = True
            config.enable_character_relationships = True
            config.enable_trajectory_analysis = True
            config.enable_temporal_state = True
            config.enable_state_tracking = True
            config.enable_six_dimension = True
            config.enable_enrichment = True
            # enable_polish 不再随 preset 默认开启：润色是勾选计费项（每章额外扣积分），
            # 仅当用户勾选经 flow_config 覆写打开（FLOW_OVERRIDE_SWITCHES creator+ 门控）
            config.rag_mode = settings.rag_default_mode
            if getattr(settings, "enable_entity_registry", True):
                config.enable_anti_hallucination = True

        # === 精品模式 (flagship+) ===
        elif preset == "premium":
            config.version_count = 1
            config.enable_constitution = True
            config.enable_persona = True
            config.enable_foreshadowing = True
            config.enable_faction = True
            config.enable_power_system = True
            config.enable_character_relationships = True
            config.enable_trajectory_analysis = True
            config.enable_temporal_state = True
            config.enable_memory = True
            config.enable_state_tracking = True
            config.enable_six_dimension = True
            config.enable_self_critique = True
            config.enable_reader_sim = True
            config.enable_consistency = True
            config.enable_enrichment = True
            # enable_polish 同 standard：勾选计费项，不随 preset 默认开启（optimizer 照跑，
            # 仅在用户勾选时才「合并润色」语义生效，见 standard_post_processing merge_polish）
            config.enable_optimizer = True
            config.rag_mode = settings.rag_default_mode
            if getattr(settings, "enable_entity_registry", True):
                config.enable_anti_hallucination = True
            # A1 滚动细纲修订：flagship 独占 + env 灰度开关（默认关），仅 premium 档启用
            if getattr(settings, "outline_revision_enabled", False):
                config.enable_outline_revision = True

        # === Ultra Fast Mode（settings 级别覆盖）===
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
            config.enable_state_tracking = False
            config.enable_outline_revision = False
            config.disable_guardrail_rewrite = True
            config.skip_history_summary_backfill = True
            config.use_local_anti_hallucination = True
            logger.info("Ultra fast mode: 已启用快速路径并跳过所有后处理步骤")

        # === flow_config 显式覆写（白名单机制）===
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
        if flow_config.get("model_code"):
            config.model_code = str(flow_config["model_code"])

        return config

    async def resolve_version_count(self, requested_count: Optional[int]) -> int:
        return await _shared_resolve_version_count(self.session, requested_count)
