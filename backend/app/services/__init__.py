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

# 融合服务（来自 AI_NovelGenerator 的设计理念）
from .finalize_service import FinalizeService
from .consistency_service import ConsistencyService, ConsistencyCheckResult, ConsistencyViolation, ViolationSeverity
from .knowledge_retrieval_service import KnowledgeRetrievalService, FilteredContext, RetrievedKnowledge
from .enrichment_service import EnrichmentService, EnrichmentResult
from .blueprint_service import BlueprintService
from .context_planner_service import ContextPlan, ContextPlannerService, RetrievalTask, SkillPolicy, GenerationEvidencePack, EvidenceItem
from .evidence_router_service import EvidenceRouterService, RoutedEvidenceResult
from .history_context_service import HistoryContextService
from .context_access_service import ContextAccessService
from .prompt_assembly_service import PromptAssemblyService
from .prompt_compiler_service import PromptCompilerService
from .narrative_verifier_service import NarrativeVerifierService
from .generation_result_service import GenerationResultService
from .generation_telemetry_service import GenerationTelemetryService
from .standard_post_processing_service import StandardPostProcessingService
from .version_generation_service import VersionGenerationService
from .text_compression_service import TextCompressionService
from .scene_generation_service import SceneGenerationService

# 任务档案服务
from .writing_archive_service import WritingArchiveService

__all__ = [
    # 基础服务
    "LLMService",
    "VectorStoreService",
    "RetrievedChunk",
    "RetrievedSummary",
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
    "HistoryContextService",
    "ContextAccessService",
    "PromptAssemblyService",
    "PromptCompilerService",
    "NarrativeVerifierService",
    "GenerationResultService",
    "GenerationTelemetryService",
    "StandardPostProcessingService",
    "VersionGenerationService",
    "TextCompressionService",
    "SceneGenerationService",
    # 任务档案服务
    "WritingArchiveService",
]
