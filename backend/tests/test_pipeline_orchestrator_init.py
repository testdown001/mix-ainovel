from types import SimpleNamespace

import app.services.pipeline_orchestrator as module


def test_pipeline_orchestrator_init_wires_dependencies_in_safe_order(monkeypatch):
    class _Noop:
        def __init__(self, *args, **kwargs):
            pass

    class _PromptAssembly:
        def __init__(self, *args, **kwargs):
            pass

    class _PromptCompiler:
        def __init__(self, *args, **kwargs):
            pass

    class _GenerationPromptContext:
        def __init__(self, *, prompt_service, context_access_service, prompt_assembly_service):
            assert prompt_assembly_service is not None

    class _GenerationPromptStage:
        def __init__(self, *, prompt_assembly_service, prompt_compiler, prompt_service, enhanced_context_service):
            assert prompt_assembly_service is not None
            assert prompt_compiler is not None

    class _GenerationContextResolution:
        def __init__(self, *, evidence_router, generation_policy_service, llm_service, session):
            assert generation_policy_service is not None

    class _GenerationFinalize:
        def __init__(self, *, generation_background_task_service, narrative_verifier, generation_result_service, generation_policy_service):
            assert generation_background_task_service is not None
            assert narrative_verifier is not None

    class _FastFlow:
        def __init__(self, *, session, llm_service, single_version_generation_service, text_compression_service):
            assert single_version_generation_service is not None
            assert text_compression_service is not None

    class _LiteraryFlow:
        def __init__(self, *, session, llm_service, scene_generation_service, generation_policy_service, text_compression_service, guardrails):
            assert scene_generation_service is not None
            assert text_compression_service is not None
            assert guardrails is not None

    class _StandardFlow:
        def __init__(self, *, session, llm_service, version_generation_service, standard_post_processing_service, text_compression_service):
            assert version_generation_service is not None
            assert standard_post_processing_service is not None
            assert text_compression_service is not None

    monkeypatch.setattr(module, "LLMService", _Noop)
    monkeypatch.setattr(module, "PromptService", _Noop)
    monkeypatch.setattr(module, "NovelService", _Noop)
    monkeypatch.setattr(module, "ContextPlannerService", _Noop)
    monkeypatch.setattr(module, "PipelineConfigService", _Noop)
    monkeypatch.setattr(module, "GenerationSupportService", _Noop)
    monkeypatch.setattr(module, "EvidenceRouterService", _Noop)
    monkeypatch.setattr(module, "HistoryContextService", _Noop)
    monkeypatch.setattr(module, "GenerationResultService", _Noop)
    monkeypatch.setattr(module, "GenerationPolicyService", _Noop)
    monkeypatch.setattr(module, "ContextAccessService", _Noop)
    monkeypatch.setattr(module, "EnhancedContextService", _Noop)
    monkeypatch.setattr(module, "PromptAssemblyService", _PromptAssembly)
    monkeypatch.setattr(module, "PromptCompilerService", _PromptCompiler)
    monkeypatch.setattr(module, "NarrativeVerifierService", _Noop)
    monkeypatch.setattr(module, "MissionBuilderService", _Noop)
    monkeypatch.setattr(module, "TextCompressionService", _Noop)
    monkeypatch.setattr(module, "SceneGenerationService", _Noop)
    monkeypatch.setattr(module, "VoiceSampleService", _Noop)
    monkeypatch.setattr(module, "SingleVersionGenerationService", _Noop)
    monkeypatch.setattr(module, "StandardPostProcessingService", _Noop)
    monkeypatch.setattr(module, "VersionGenerationService", _Noop)
    monkeypatch.setattr(module, "AsyncTaskService", _Noop)
    monkeypatch.setattr(module, "GenerationContextResolutionService", _GenerationContextResolution)
    monkeypatch.setattr(module, "GenerationEvidenceStageService", _Noop)
    monkeypatch.setattr(module, "GenerationPromptContextService", _GenerationPromptContext)
    monkeypatch.setattr(module, "GenerationPromptStageService", _GenerationPromptStage)
    monkeypatch.setattr(module, "GenerationBackgroundTaskService", _Noop)
    monkeypatch.setattr(module, "GenerationFinalizeService", _GenerationFinalize)
    monkeypatch.setattr(module, "FastGenerationFlowService", _FastFlow)
    monkeypatch.setattr(module, "LiteraryGenerationFlowService", _LiteraryFlow)
    monkeypatch.setattr(module, "StandardGenerationFlowService", _StandardFlow)
    monkeypatch.setattr(module, "UserStyleService", _Noop)
    monkeypatch.setattr(module, "FingerprintService", _Noop)
    monkeypatch.setattr(module, "TrajectoryAnalysisService", _Noop)
    monkeypatch.setattr(module, "WriterPromptService", _Noop)
    monkeypatch.setattr(module, "GenerationPrefetchService", _Noop)
    monkeypatch.setattr(module, "default_context_builder", SimpleNamespace())
    monkeypatch.setattr(module, "default_guardrails", SimpleNamespace())

    orchestrator = module.PipelineOrchestrator(SimpleNamespace())

    assert orchestrator is not None
