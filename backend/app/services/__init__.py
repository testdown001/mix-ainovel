# AIMETA P=服务包初始化_导出所有服务类|R=包标识|NR=不含服务实现|E=-|X=internal|A=-|D=none|S=none|RD=./README.ai
"""
服务层包初始化

导出所有服务类，包括：
- 基础服务：LLM、向量存储、嵌入等
- 融合服务：定稿、一致性检查、知识检索、扩写、蓝图管理
"""

# 基础服务
from .llm_service import LLMService
from .vector_store_service import VectorStoreService, RetrievedChunk, RetrievedSummary
from .async_task_service import AsyncTaskService

# 融合服务（来自 AI_NovelGenerator 的设计理念）
from .finalize_service import FinalizeService
from .consistency_service import ConsistencyService, ConsistencyCheckResult, ConsistencyViolation, ViolationSeverity
from .knowledge_retrieval_service import KnowledgeRetrievalService, FilteredContext, RetrievedKnowledge
from .enrichment_service import EnrichmentService, EnrichmentResult
from .blueprint_service import BlueprintService
from .context_planner_service import ContextPlan, ContextPlannerService, RetrievalTask, SkillPolicy, GenerationEvidencePack, EvidenceItem
from .evidence_router_service import EvidenceRouterService, RoutedEvidenceResult
from .evidence_grader_service import EvidenceGraderService
from .history_context_service import HistoryContextService
from .context_access_service import ContextAccessService
from .enhanced_context_service import EnhancedContextService
from .enhanced_review_service import EnhancedReviewService
from .generation_context_resolution_service import (
    GenerationContextResolutionService,
    ResolvedPrefetchContext,
)
from .generation_evidence_stage_service import (
    GenerationEvidenceStageService,
    ResolvedEvidenceStage,
)
from .generation_prompt_context_service import (
    GenerationPromptContextService,
    PromptContextInputs,
)
from .generation_prompt_stage_service import (
    GenerationPromptStageService,
    PromptStageResult,
)
from .generation_finalize_service import GenerationFinalizeService
from .fast_generation_flow_service import FastGenerationFlowService, FastGenerationFlowResult
from .literary_generation_flow_service import LiteraryGenerationFlowService, LiteraryGenerationFlowResult
from .standard_generation_flow_service import StandardGenerationFlowService, StandardGenerationFlowResult
from .prompt_assembly_service import PromptAssemblyService
from .prompt_compiler_service import PromptCompilerService
from .narrative_verifier_service import NarrativeVerifierService
from .generation_result_service import GenerationResultService
from .generation_telemetry_service import GenerationTelemetryService
from .standard_post_processing_service import StandardPostProcessingService
from .version_generation_service import VersionGenerationService
from .text_compression_service import TextCompressionService
from .scene_generation_service import SceneGenerationService
from .mission_builder_service import MissionBuilderService
from .voice_sample_service import VoiceSampleService
from .single_version_generation_service import SingleVersionGenerationService
from .batch_generation_service import BatchGenerationService
from .pipeline_config_service import PipelineConfig, PipelineConfigService
from .generation_support_service import GenerationSupportService
from .generation_prefetch_service import GenerationPrefetchService, GenerationPrefetchTasks
from .generation_analysis_task_service import GenerationAnalysisTaskService
from .generation_background_task_service import GenerationBackgroundTaskService
from .generation_write_task_service import GenerationWriteTaskService
from .user_style_service import UserStyleService
from .fingerprint_service import FingerprintService
from .trajectory_analysis_service import TrajectoryAnalysisService
from .writer_prompt_service import WriterPromptService
from .temporal_state_service import TemporalStateService, WorldStateSnapshot
from .memory_distillation_service import MemoryDistillationService

# 任务档案服务
from .writing_archive_service import WritingArchiveService

__all__ = [
    # 基础服务
    "LLMService",
    "VectorStoreService",
    "RetrievedChunk",
    "RetrievedSummary",
    "AsyncTaskService",
    # 融合服务
    "FinalizeService",
    "ConsistencyService",
    "ConsistencyCheckResult",
    "ConsistencyViolation",
    "ViolationSeverity",
    "KnowledgeRetrievalService",
    "FilteredContext",
    "RetrievedKnowledge",
    "EnrichmentService",
    "EnrichmentResult",
    "BlueprintService",
    "ContextPlan",
    "ContextPlannerService",
    "RetrievalTask",
    "SkillPolicy",
    "GenerationEvidencePack",
    "EvidenceItem",
    "EvidenceRouterService",
    "RoutedEvidenceResult",
    "EvidenceGraderService",
    "HistoryContextService",
    "ContextAccessService",
    "EnhancedContextService",
    "EnhancedReviewService",
    "GenerationContextResolutionService",
    "ResolvedPrefetchContext",
    "GenerationEvidenceStageService",
    "ResolvedEvidenceStage",
    "GenerationPromptContextService",
    "PromptContextInputs",
    "GenerationPromptStageService",
    "PromptStageResult",
    "GenerationFinalizeService",
    "FastGenerationFlowService",
    "FastGenerationFlowResult",
    "LiteraryGenerationFlowService",
    "LiteraryGenerationFlowResult",
    "StandardGenerationFlowService",
    "StandardGenerationFlowResult",
    "PromptAssemblyService",
    "PromptCompilerService",
    "NarrativeVerifierService",
    "GenerationResultService",
    "GenerationTelemetryService",
    "StandardPostProcessingService",
    "VersionGenerationService",
    "TextCompressionService",
    "SceneGenerationService",
    "MissionBuilderService",
    "VoiceSampleService",
    "SingleVersionGenerationService",
    "BatchGenerationService",
    "PipelineConfig",
    "PipelineConfigService",
    "GenerationSupportService",
    "GenerationPrefetchService",
    "GenerationPrefetchTasks",
    "GenerationAnalysisTaskService",
    "GenerationBackgroundTaskService",
    "GenerationWriteTaskService",
    "UserStyleService",
    "FingerprintService",
    "TrajectoryAnalysisService",
    "WriterPromptService",
    "TemporalStateService",
    "WorldStateSnapshot",
    "MemoryDistillationService",
    # 任务档案服务
    "WritingArchiveService",
]
