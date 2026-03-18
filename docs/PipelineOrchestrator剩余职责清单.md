# PipelineOrchestrator 剩余职责清单

更新时间：`2026-03-16`

## 当前结论

`PipelineOrchestrator` 已经从“巨型业务实现体”收缩为“主流程编排器 + 少量内核 helper”。

当前文件行数：

- [pipeline_orchestrator.py](/home/aikev/code/arboris-novel/backend/app/services/pipeline_orchestrator.py)
  约 `1922` 行

已经外提到服务层的职责：

- 配置解析：`PipelineConfigService`
- 策略判断：`GenerationPolicyService`
- 历史上下文：`HistoryContextService`
- 上下文访问：`ContextAccessService`
- 任务式取证：`EvidenceRouterService`
- Prompt 组装：`PromptAssemblyService`
- Prompt 编译：`PromptCompilerService`
- Mission 构造：`MissionBuilderService`
- 单版本生成：`SingleVersionGenerationService`
- 版本生成：`VersionGenerationService`
- 标准模式后处理：`StandardPostProcessingService`
- 文学模式场景生成：`SceneGenerationService`
- 文本压缩：`TextCompressionService`
- 声纹样本：`VoiceSampleService`
- 验证汇总：`NarrativeVerifierService`
- 增强后审：`EnhancedReviewService`
- 结果装配：`GenerationResultService`
- 中间产物发射：`GenerationTelemetryService`
- 批量生成：`BatchGenerationService`
- 生成支持查询：`GenerationSupportService`
- 生成预热调度：`GenerationPrefetchService`
- 生成预热结果解析：`GenerationContextResolutionService`
- 生成证据阶段汇总：`GenerationEvidenceStageService`
- 生成提示上下文补全：`GenerationPromptContextService`
- 生成 Prompt 阶段装配：`GenerationPromptStageService`
- 生成收尾阶段：`GenerationFinalizeService`
- 快速分支执行：`FastGenerationFlowService`
- 文学分支执行：`LiteraryGenerationFlowService`
- 标准分支执行：`StandardGenerationFlowService`
- 后台任务门面：`GenerationBackgroundTaskService`
- 后台只读分析：`GenerationAnalysisTaskService`
- 后台写入更新：`GenerationWriteTaskService`

## 当前仍保留在 Orchestrator 的职责

### 1. 应保留的内核职责

- `generate_chapter()` 的主流程阶段串联。
- 阶段顺序控制。
- 阶段间数据对象的拼装与传递。
- 与路由层的运行时契约保持一致。

这些职责天然属于编排器，不建议再拆成无意义的薄服务。

### 2. 仍在文件内但值得后续收口的局部逻辑

- 当前已无明显“并行预热调度”残留逻辑。
- 若后续继续收口，优先考虑把 `generate_chapter()` 拆成显式阶段对象，而不是继续切更薄的工具层。
### 3. 当前仍是 live helper 的方法

- `_run_stage_b_analyses_async`
  说明：已迁出到 `GenerationBackgroundTaskService`，当前应视为完成收口。

- `_load_project_reference_novels`
  说明：已迁出到 `GenerationSupportService`，当前应视为完成收口。

- `_load_chapter_blueprint`
  说明：已迁出到 `GenerationSupportService`，当前应视为完成收口。

- `_build_fast_rag_queries`
  说明：已迁出到 `GenerationSupportService`，当前应视为完成收口。

- `_validate_coolpoint_rhythm`
  说明：已迁出到 `GenerationSupportService`，当前应视为完成收口。

- `simple RAG` 并行预取
  说明：已迁出到 `EvidenceRouterService.prefetch_local_plot()`，当前应视为完成第一步收口。

- `伏笔 brief / 结构化伏笔` 并行预取
  说明：已迁出到 `EvidenceRouterService.prefetch_symbolic_foreshadowing()`，当前应视为完成第一步收口。

- `项目长期记忆文本` 并行预取
  说明：已迁出到 `ContextAccessService.prefetch_project_memory_text()`，当前应视为完成收口。

- `用户写作风格偏好` 并行预取
  说明：已迁出到 `UserStyleService.prefetch_user_style()`，当前应视为完成收口。

- `风格指纹` 并行预取
  说明：已迁出到 `FingerprintService.prefetch_fingerprint_context()`，当前应视为完成收口。

- `轨迹分析` 并行预取
  说明：已迁出到 `TrajectoryAnalysisService.prefetch_trajectory_context()`，当前应视为完成收口。

- `writer prompt` 并行预取
  说明：已迁出到 `WriterPromptService.prefetch_writer_prompt()`，当前应视为完成收口。

- `EnhancedWritingFlow` 预热
  说明：已迁出到 `EnhancedContextService.prefetch_enhanced_context()`，当前应视为完成收口。

- `_with_timeout`
  说明：已迁出到 `AsyncTaskService.run_with_timeout()`，当前应视为完成收口。

## 建议的后续重构顺序

### 第一优先级

- 收口 `simple RAG` 并行预取逻辑，使 `EvidenceRouterService` 不仅负责执行，还负责并发调度策略。
- 继续收口 `symbolic_rag` 的剩余执行路径，使 `foreshadowing` 的“预取 + 执行”进一步统一。

### 第二优先级

- 评估流式链路中的队列等待/超时处理是否也值得统一进并发工具。
- 评估 `GenerationBackgroundTaskService` 是否还需要进一步细分只读分析与写入型任务。

### 第三优先级

- 若编排器体积继续收缩，考虑把 `generate_chapter()` 进一步拆成显式阶段对象或阶段图。
- 若不拆，也建议保留当前 service-first 结构，避免再把实现塞回 orchestrator。

## 当前判断

`PipelineOrchestrator` 现在已经足够接近“真正的编排器”。

后续不建议为了“继续拆而拆”做过度重构。
更合理的方向是：

1. 补强回归测试矩阵。
2. 收口少量仍散落的并行预取逻辑。
3. 在文档和接口层巩固当前 service-first 基线。
