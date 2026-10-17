# 小说创作全链路分析与竞品流程对照

- 审计日期：2026-10-17
- 代码基线：`0d4f910`，以当前 `backend/app/`、`frontend/src/`、`gateway/` 的执行路径为准。
- 范围：构思与蓝图、分卷章纲、参考小说、向量检索、长期记忆、人物、情感、爽点、正文与质量反馈。
- 方法：代码调用链核查、默认配置与门控核查、分数域算例，以及竞品官方帮助文档对照。本报告不是实际账号横评，也未进行付费模型的连续完本实验。
- 标注口径：**已实现**不等于所有档位默认启用；**条件缺陷**不等于默认路径全部失效；**代码风险**不等于已经观察到生产事故。改进方案均为建议，未修改业务代码。

## 一、核心判断

本项目已经不是“输入大纲、逐章续写”的简单工具，而是具备完整雏形的长篇创作系统：

1. **规划深度较好**：立项书、情感核心、声音试写、分卷、章纲、章任务书、场景契约之间已有实际传递。
2. **人物与爽点不是空白**：人物欲望—选择—代价—关系变化、读者承诺的打开/兑现、兑现后的余波都已进入代码。
3. **参考小说不只是风格标签**：已经有多源分工、FusionDNA、内容签名和场景级参考仲裁。
4. **最关键的短板是状态一致性**：新叙事正史受选定版本/hash/谱系保护，但旧记忆、部分摘要和后台规划建议还没有统一到同一来源语义。
5. **存在具体检索问题**：hybrid 的 RRF 分数和向量阈值混用；旧章重写的普通 RAG 路径缺少明确的时间上界；向量写入缺少可靠成功收据。
6. **下一阶段不宜继续堆 Agent/评分器**：优先保证 AI 读到的是正确版本、正确时间、正确人物的材料，再证明额外模型调用带来的叙事收益。

推荐定位：**作者掌控的长篇叙事工作台，AI 执行规划、起草、查证和提出修订；作者决定发生什么、采用什么。**

## 二、当前实际创作链路

```text
灵感对话
  ↓
立项书：主角欲望/缺陷/困境、矛盾发动机、情感核心、期待承诺
  ├─ 压力推演与修复建议
  └─ 声音试写与作者选择
  ↓
蓝图设定段：人物/世界/金手指/关系/伏笔/分卷
  ↓
蓝图章纲段：分批规划，主要覆盖前 50 章
  └─ deep 条件满足时审稿、定向修订、复审
  ↓
当前卷目标 + 章纲规划 + 人物行动依据
  ↓
HybridExecutor → Pipeline 或 Agent
  ↓
策略/计费 → ContextPlan → 多路证据与记忆 → 任务书/Prompt
  ↓
fast / standard / premium 场景链
  ↓
正文候选 → 硬事实与场景质量门 → 保存候选批次
  ├─ 部分分析/旧记忆/可选后续规划在生成收尾就被安排
  ↓
作者选择/可靠编辑保存/定稿
  ↓
已选正文修订 + 后处理：摘要、向量、人物意义等
  ↓
下一章检索、读者承诺延续、卷级复盘与规划建议
```

最后两条回写路径目前不是完全同一套提交机制，这是分析长篇稳定性时的重点。

### 分支差异必须单独看

| 路径 | 当前特征 | 不能推导出的保证 |
| --- | --- | --- |
| fast | 低成本快速草稿；跳过完整共享章节质量门 | 不代表具有 premium 的事实/场景验证与承诺台账 |
| standard | 标准生成/后处理，轻量人物与时间状态 | 不保证抽取 premium 场景链的 NarrativeDelta |
| premium 场景链 | 场景契约、节拍候选/评分、逐场正文与验证、读者控制 | 不代表所有审美报告已经同步完成或自动改好 |
| premium 显式非场景/购买 polish | 未显式要求场景时，购买润色会转标准后处理链以交付润色 | 同一 premium 名称不代表完全相同的记忆/控制路径 |
| 四类长篇质量回路 | 章纲修订、卷复盘、两遍制、人物意义；SystemConfig 优先 | 环境兜底均关闭，不能根据存在类名就说线上已启用 |

证据：[场景与 reader controller 解析](../backend/app/services/pipeline_config_service.py#L400)、[生成质量门调用](../backend/app/services/pipeline_orchestrator.py#L966)、[质量回路环境默认](../backend/app/core/config.py#L195)。

## 三、分项分析

### 3.1 蓝图规划：已分层，但需要把“计划”与“事实”明确分开

**现有优势**

- 立项书不是单一梗概：含卖点、主角欲望/缺陷/困境、冲突发动机、金手指限制、10/50 章与长线期待。
- 情感核心单独表达珍惜之物、为谁破例、关键关系、有代价的两难和读者牵挂。
- 蓝图分设定与章纲两段，章纲按 25 章批次生成并传递前批尾部；主要细化前 50 章，而不是一次锁死百万字全书。
- 设定摘要会保留卷目标、卷末高潮、人物依据和伏笔；章纲字段还会同步到 ChapterBlueprint，供下游实际读取。
- deep 审稿可修订再审，但一般质量增益层仍有软失败语义，不能宣传成低分一定禁止进入正文。

证据：[立项书 Schema](../backend/app/schemas/concept_dossier.py#L18)、[情感核心](../backend/app/schemas/concept_dossier.py#L56)、[初始章数策略](../backend/app/services/blueprint_generation_service.py#L133)、[批次章纲生成](../backend/app/services/blueprint_generation_service.py#L580)、[章规划映射](../backend/app/services/chapter_planning_service.py#L173)。

**主要改进方向**

不是再生成更长的大纲，而是让作者看到五层不同的东西：

1. 全书方向：核心冲突、主题和长线承诺。
2. 当前卷：阶段目标、对手变化、代价与高潮。
3. 已确认章纲：本章功能、人物焦点、必须/禁止发生的事。
4. 临时执行方案：Director/场景节拍给出的写法，尚非事实。
5. 已发生事实：作者采用的正文及其有效状态增量。

可保留远期粗规划，把近期少量章纲细化成可执行任务；自动复盘只提出有来源的修订建议，不静默替作者重排整本书。这里建议的是细化层级与确认机制，不是把现有“前 50 章规划”误判为全书过度细化。

### 3.2 人物：字段和注入已经较强，缺的是持续变化的可追踪性

代码已有 `wants / stakes / choice / cost / relationship_change / next_expectation`，并将主角欲望、缺陷、魅力依据和情感牵挂传给规划/正文。还做了语义组预算，避免世界观过长挤掉情感关系；作者选定的 `character_focus` 会在 Director 后确定性补回。

证据：[人物规划字段与预算](../backend/app/services/character_planning_context.py#L11)、[保留作者人物焦点](../backend/app/services/pipeline_orchestrator.py#L694)、[正文人物行动依据](../backend/app/services/pipeline_orchestrator.py#L945)。

**因此不建议再造一套普通人物卡。** 应把现有数据连成作者可检查的连续变化：

```text
我想要什么 → 什么在阻拦 → 为什么作此选择 → 付出什么
→ 谁因此改变对我的看法 → 下一次相遇如何体现这次变化
```

人物状态应至少区分：

- 稳定设定：经历、价值观、说话习惯。
- 当前处境：位置、伤势、资源、已知信息。
- 关系变化：信任、亏欠、戒备、误会及其具体事件证据。
- 意义变化：信念受到什么挑战，哪种选择越来越难。
- 读者牵挂：读者正在等待这个人得到/失去/承认什么。

前两类并不能自动覆盖后三类。人物意义层已有实现但默认关闭；应先用小范围样本验证它能否使后续言行发生合理变化，而不是只检查“抽取了一条意义记忆”。

例如，上一章某人背叛过主角，下一章即使继续合作，也应在试探、条件、沉默或行动中留下痕迹，不必每次都复述背叛事件。

### 3.3 情感：已有表达层，曲线校正却仍是较粗代理

已有章任务书的松弛点、留白、笔墨分配；场景层还保留关系温度、日常细节、对白停顿/言外之意，背景压缩不会把这些一并删去。情感审校要求引用正文，并允许 `context_needed`，还会保护承载声音与潜台词的原句，这比“每章提高情绪强度”更合理。

证据：[情感连续性与场景表达](../backend/app/services/chapter_mission_context.py#L35)、[局部修改与原句保护](../backend/app/services/emotional_editing_service.py#L93)。

**但偏差检测存在口径不一致：**

- 预期：PacingController 生成的通用结构曲线。
- 实际：该章所有 CharacterState 的情绪强度峰值。
- 入口未把作者确认的逐章情绪目标作为该偏差服务的首选输入。
- 这些 CharacterState 的来源本身还受旧记忆回写语义影响。

证据：[规则预期](../backend/app/services/emotion_deviation_service.py#L39)、[人物峰值聚合](../backend/app/services/emotion_deviation_service.py#L61)、[轨迹调用入口](../backend/app/services/trajectory_analysis_service.py#L41)。

**人物情绪 ≠ 读者情绪 ≠ 阅读张力。** 一个角色平静接受告别，读者可能很难过；一个配角很愤怒，也不表示整章张力足够。安静的余波章不应因低于通用曲线就被要求再加冲突。

建议采用：

1. 作者已确认的章功能/焦点人物/情绪目标优先。
2. 无明确规划时才用通用结构作参考。
3. 用正文事件检查“触发—选择—行动—关系后果”，而非只校准标量。
4. 分开呈现人物感受、关系方向、读者期待与张力。
5. 审美建议继续保持可拒绝，不变成事实硬门。

### 3.4 爽点与追读：已有承诺台账，应扩覆盖，不应另造一套

现有 `ReaderPromise` 记录问题、人物、预计兑现章号、证据；`NarrativeDelta` 记录欲望、压力、兑现、余波、下一牵挂及承诺开闭。到期承诺会优先进入场景上下文。ReaderAction 还会评价节拍是否推进既有承诺，且不要求每场都是高潮。

证据：[读者承诺与增量](../backend/app/services/narrative_state_service.py#L24)、[到期优先](../backend/app/services/narrative_state_service.py#L122)、[节拍评价与选择](../backend/app/services/reader_action_service.py#L79)。

**实际短板是：**

- 自动 reader controller 主要覆盖 premium 场景分支。
- standard、premium 非场景/购买 polish 路径不保证生成相同增量。
- 手动修改早章会让旧 hash/谱系失效，这是正确保护；但本次检索未找到独立、完整的增量重建入口。
- 同一作品切换模式或改过前文后，不能假设追读台账依然完整。

建议在现有台账上补“缺失/失效/待重建”状态与重建任务，并向作者显示开始章、最后进展、原文证据、预计兑现和实际兑现。

爽点应理解为：

```text
先前期待/压迫 → 人物主动选择 → 有效行动
→ 可感知收益或认知改变 → 代价/他人反应/情感余波 → 新期待
```

打脸、升级、身份反转只是其中几种。关系和解、终于说出口、掌握关键真相，也可能承担本章兑现。不要把“每章几次爽点”作为跨题材统一指标。

### 3.5 小说参考：机制完整，应加强证据层级和可解释性

**先明确当前材料来源：参考入口主要是书名、作者、题材，分析依赖多维搜索结果，不是上传全本原著后逐章细读。** AI 仿写样本也明确不是原文。因此当前能力更准确地称为“参考作品机制分析与迁移”，不能宣传成已经验证过的原著全文理解或原文级语义检索。

证据：[参考创建请求](../backend/app/schemas/reference_novel.py#L101)、[搜索资料与并行分析](../backend/app/services/reference_novel_library_service.py#L137)、[仿写非原文标注](../backend/app/services/reference_novel_library_service.py#L619)。

当前参考链包括参考书分析/绑定、结构手法进入蓝图章纲、FusionDNA v2、场景相关卡片、ReaderLoop 和节拍阶段的 adopted/adapted/rejected 仲裁。

FusionDNA 会校验有序来源 IDs 与内容签名；参考材料未齐时明确走 provisional fallback。绑定/重分析发生变化后，旧融合不能冒充当前结果。这是值得保留的设计，而不只是把几本书简介塞进 Prompt。

证据：[融合有效性与来源签名](../backend/app/services/reference_reading_contract.py#L53)、[蓝图章纲使用结构参考](../backend/app/services/blueprint_generation_service.py#L566)、[场景参考仲裁](../backend/app/services/reader_action_service.py#L79)。

**需要分开的三种参考：**以下是材料分层建议，不代表当前已具备原著全文摄入管线。

| 参考种类 | 适合提取 | 不应当作 |
| --- | --- | --- |
| 原文材料 | 对话组织、场景转折、铺垫与兑现的具体证据 | 当前小说已发生事实 |
| AI 分析卡/结构卡 | 冲突升级方法、叙述距离、节奏与关系推进方式 | 原著逐字证据或客观评价 |
| 作者选定风格/试写 | 本书声音、偏好与禁忌 | 必须照搬的情节 |

建议界面让作者按目的分工：主叙事声音、结构节奏、关系/对白等；生成时说明本章采用了哪种方法、拒绝了什么参考、为什么。已有多源分工不需要重造，重点是作者能检查。

如果下一步做真正的参考细读，应增加作者提供片段/章节与可定位引文，保留 source kind/span、提取模型与置信度，不要靠更多搜索摘要冒充原文证据。

验证时尤其看：用了参考后，本书人物选择是否仍成立；是否出现参考角色/地名/专属事件；主声线是否被辅助参考覆盖。参考更多不等于更原创或更一致。

### 3.6 向量使用：应先修检索契约，再调召回数量

向量适合找“与本场有关的过往原文”，不适合独自决定“当前什么是真的”。当前已具备多查询、语境化 embedding 前缀、BM25/hybrid、rerank 和预算控制，但有三个直接影响实际效果的问题。

#### A. 条件缺陷：RRF 分数误用向量阈值

普通生成的 `retrieve_multi_query()` 默认取 `rag_min_score=0.35`。hybrid 返回的却是加权 RRF 排名分数，`RRF_K=60`，默认权重 0.6/0.4。

两路都排第 0 的最好情况：

```text
score = 0.6 / 60 + 0.4 / 60 = 0.0166667
0.0166667 < 0.35
```

随后统一过滤，最高分片段也被删除；rerank 在过滤之后，无法救回。这是 **hybrid + 默认阈值** 的分数域错误，不是默认纯 vector 全部失效；调低阈值或走其他单查询路径可能不触发。

证据：[多查询默认门槛/分支](../backend/app/services/chapter_context_service.py#L201)、[统一阈值过滤](../backend/app/services/chapter_context_service.py#L271)、[RRF 公式](../backend/app/services/hybrid_retrieval_service.py#L161)、[默认检索模式/配置](../backend/app/core/config.py#L348)。

建议引入明确的 `score_kind`；cosine、RRF、reranker 分值不得共用同一阈值。不能用全局把 min_score 改成 0 来代替契约修复。

#### B. 代码风险：修订旧章时可能召回未来事实

Qdrant 普通查询过滤 project_id，但没有当前章上界/来源版本校验。普通 local-plot 预取不传 chapter_number，结果又在早期转成字符串；后面难以按章号/hash补过滤。历史摘要支路的 `< current_chapter` 保护不能覆盖 RAG 支路。

证据：[Qdrant 过滤](../backend/app/services/vector_store_service.py#L150)、[local-plot 预取](../backend/app/services/generation_prefetch_service.py#L118)、[证据返回与字符串化](../backend/app/services/evidence_router_service.py#L80)。

例如已有第 40 章“右手受伤”，再写第 10 章时，语义相关查询可能把伤势当成已发生事实。

建议所有事实召回传统一 `as_of_chapter` 和有效来源约束，且保留结构化 metadata 到最终编译。**未来章纲作为计划仍可读取，但必须标成计划；参考小说也不能混进本书事实。**

#### C. 代码风险：索引失败可能被标记成成功

当前 ingestion 先删该章旧向量，再生成 embedding；底层 upsert 部分错误只记日志，调用方没有明确成功收据，后处理仍可能推进 ingest hash。故障条件下可能造成旧索引丢失、DB 却认为已同步。

证据：[先删后生成 embedding](../backend/app/services/chapter_ingest_service.py#L69)、[upsert 错误处理](../backend/app/services/vector_store_service.py#L357)、[推进 ingest hash](../backend/app/services/chapter_post_processor.py#L270)。

建议先准备完整新数据，再执行可恢复的版本切换；只有拿到 chunks/summary 写入收据，才推进索引状态。正文保存成功和检索索引成功应是两种状态：索引失败可重试，不回滚作者正文，也不能假报同步完成。

此外，系统已有证据分类预算与最终 Prompt 预算，问题不是“完全没控 token”。需要修的是字符串化后的保真：部分正文证据失去原始 score/provenance 后再参与裁剪，可能不利于关键原文证据保留。应把原始排名、score kind、版本来源和裁剪原因保留到最终编译。[证据转换/追加](../backend/app/services/evidence_router_service.py#L650)、[分类预算](../backend/app/services/evidence_router_service.py#L797)

### 3.7 长期记忆：已有多层，但还没有统一的事实提交边界

不要用“有没有向量库”来衡量长期记忆。至少需要分五层：

| 层 | 解决的问题 | 在本项目中的落点 |
| --- | --- | --- |
| 创作意图 | 作者想写什么、喜欢什么声音 | 立项书、试写、CreativeMemory |
| 稳定设定 | 人物/世界的基础规则 | 蓝图、人物/设定数据、宪法等 |
| 正史状态 | 当前谁知道什么、关系怎样、承诺是否兑现 | NarrativeState、人物/时间/实体状态等 |
| 压缩记忆 | 几十章之后还记得阶段进展 | 章/卷/全书/叙事摘要 |
| 原文证据 | 为什么相信这条记忆，能否找回细节 | Qdrant/BM25 检索片段 |

当前新 NarrativeState 只重放已选、verified、hash 与谱系有效的增量，并隔离冲突，方向正确。可是旧 memory/state/伏笔在生成收尾可能直接使用推荐 `best_content`，尚未等作者选版。

证据：[正史回放](../backend/app/services/narrative_state_service.py#L139)、[候选阶段 memory/state/伏笔调度](../backend/app/services/generation_finalize_service.py#L84)。

场景：生成 A“亲人去世”和 B“亲人获救”，作者最终选 B。如果 A 的后台记忆仍被后续召回，新正史虽然正确，模型仍可能从旧记忆获得冲突信息。**新正史回放保护正确，并不能自动保护其他检索入口。**

建议不用再加一个“更强记忆库”，而是统一派生记忆信封：

```text
project / source_kind / source_chapter_range
source_version_id / source_content_hash / lineage
status(draft/canonical/stale) / valid_from / valid_until
evidence_span / derived_at
```

逐步实施：

1. 候选分析放 draft 命名空间；明确只供该草稿分支使用。
2. 作者采纳或可靠保存后，提交 canonical 更新事件。
3. 后台落库前复核来源仍有效；迟到结果失效而非覆盖。
4. 修改早章时，把受影响的 delta、摘要、记忆和规划建议标 stale，再按依赖顺序重建。
5. 事实查询按写作时间读取；创作意图和未来计划走不同知识类型。

同样的问题会影响开启后的章纲修订与卷复盘：目前它们也可能在推荐候选生成时启动，而建议所依赖的正文/卷摘要还未确认或未更新。应补来源版本/hash，保持“建议产生”与“作者应用”分离，而不是让后台任务直接决定未来剧情。

证据：[后续规划调度](../backend/app/services/generation_finalize_service.py#L119)、[章纲建议来源](../backend/app/services/outline_revision_service.py#L77)、[卷摘要与下一卷建议](../backend/app/services/volume_retrospective_service.py#L122)。

### 3.8 正文质量：硬门、审美报告、实际修改必须分开

代码有一个合理方向：事实/因果/场景缺失作为硬问题，情绪节奏和读者偏好作为建议，避免把克制和留白机械优化掉。局部修订还限制改动范围，保护原句。

但：

- premium 场景分支的一部分六维评审、读者模拟是异步报告。
- 报告完成不等于正文已经应用其建议。
- 有开关不等于当次实际执行；预算降级也可能跳过步骤。
- 同模型独立请求打分，不等于独立模型或真实读者验证。

证据：[质量门边界](../backend/app/services/generation_quality_gate.py#L62)、[六维后台执行](../backend/app/services/generation_finalize_service.py#L64)、[读者模拟与报告快照](../backend/app/services/generation_analysis_task_service.py#L45)。

建议在现有诊断/进度基础上，给作者一份简洁执行清单：

```text
事实检查：通过（针对版本 X）
情感审校：完成，有 2 条建议
读者模拟：后台处理中
人物意义：未启用
润色：已执行 / 未交付已退款
建议修改：未应用
```

另外，场景 ReaderAction 成功路径每场多出“候选提议＋评分”两次结构化调用；S 个场景仅此就增加约 2S 次请求，还不包含写正文、场景检查、Director 和整章检查。先用消融证明收益，不把调用次数当质量。

证据：[候选与评分调用](../backend/app/services/reader_action_service.py#L68)、[场景正文/检查](../backend/app/services/scene_generation_service.py#L230)。

## 四、竞品流程对照：借鉴什么，不应臆测什么

以下是官方公开流程，不是模型文笔排名；公开资料未说明的内部实现记为“未证实”，不等于没有。

### Novelcrafter：作者导演与时间化设定

流程是 Codex → 幕/章/场景 → 作者给 Scene Beat → AI 起草 → 作者接受、重试、丢弃或保留候选；规划可重组。可借鉴的是作者控制“发生什么”，AI 帮助“怎么写”。[官方正文生成指南](https://www.novelcrafter.com/courses/ultimate-beginners-guide/generating-prose-with-ai)、[官方 Plan 文档](https://www.novelcrafter.com/help/docs/plan/organizing-scenes-chapters-acts)

其 Codex Progressions 将结婚、受伤、物品丢失等变化绑定到场景，只有该场景及之后进入上下文，回到之前场景时不读取未来变化。这是作者维护的时间化状态，不应描述成自动验证后的事实提交。[官方 Progressions 文档](https://www.novelcrafter.com/help/docs/codex/progressions-additions)

**对本项目的推论**：应优先借鉴按时间读取、作者可见的状态变化与上下文控制，而不只是继续扩展自动抽取。

### Sudowrite：Story Bible 到场景的分层扩写

流程为 Braindump/Genre/Style → Synopsis → Characters/Worldbuilding → Outline → Scenes → Draft。各字段影响哪些下游步骤有明确说明，不是每次都全量拼接。[官方 Story Bible 文档](https://docs.sudowrite.com/using-sudowrite/1ow1qkGqof9rtcyGnrWUBS/what-is-story-bible/jmWepHcQdJetNrE991fjJC)

新版使用 Scenes，而非仅旧 Beats；起草前会检查场景过短/过于庞杂，显示修复建议、字数/积分预估，作者可以调整或忽略。[官方 Scenes & Draft](https://docs.sudowrite.com/using-sudowrite/1ow1qkGqof9rtcyGnrWUBS/scenes--draft/49p5MTVxTKkVFEC5rVUzpY)

Chapter Continuity 已有前序章节关联和实际历史上下文展示；Saliency Engine 会按任务筛选人物/世界设定，作者还能隐藏条目。这不能概括成“没有长期上下文”，也不能据公开文档推断底层一定采用某种向量数据库。[官方 Chapter Continuity](https://docs.sudowrite.com/using-sudowrite/1ow1qkGqof9rtcyGnrWUBS/chapter-continuity/4KL8gFeLZQ6GSBjDWtSbV6)、[官方 Saliency Engine](https://docs.sudowrite.com/using-sudowrite/1ow1qkGqof9rtcyGnrWUBS/saliency-engine/4KL8gFeLZNvk8CEeXpfwB2)

**对本项目的推论**：借鉴生成前预检、字段依赖解释、实际使用资料卡。已有后端检索与诊断不应只在技术面板里体现。

### NovelAI：直接续写与可观察上下文

正文输入/续写，配合作者维护的 Memory、Author’s Note 和按条件激活的 Lorebook；不能把它等同无限自动记忆。[官方 Story Settings](https://docs.novelai.net/en/text/editor/storysettings/)、[官方 Lorebook](https://docs.novelai.net/en/text/lorebook/)

Context Viewer 会展示真实拼接的正文/Memory/Lorebook、激活与排除原因、token 和裁剪信息。这是“本次到底读到了什么”，不是一个记忆功能开关。[官方 Advanced Settings](https://docs.novelai.net/en/text/editor/advancedsettings/)

**对本项目的推论**：复用已有 context plan/archive/diagnostics，补“本章实际读入资料”视图，区分召回、过滤、预算裁剪、最终注入四个阶段。

### 阅文作家助手：网文作者工作流与真实读者反馈

阅文官网确认的能力包括大纲设定、全文检索、纠错、妙笔辅助资料、历史版本/云同步，以及读者互动和作品数据。它体现的是围绕作者持续写作与发布经营的工作台；官网这些公开描述不足以证明它有与本项目相同的自动蓝图/多源融合/正史验证机制。[阅文官方产品介绍](https://www.yuewen.com/app/?type=appzj)

**对本项目的推论**：模型“读者模拟”不能代替真实作者采纳、改写、连读反馈。应优先收集这些一方产品信号，而不是只累积模型自评分。

### 对照总结

| 维度 | 本项目已有基础 | 最值得借鉴的产品化方向 |
| --- | --- | --- |
| 分层规划 | 立项书/蓝图/卷/章/场景 | Sudowrite 的阶段依赖与预检；Novelcrafter 的可重组规划 |
| 人物状态 | 静态规划、轻量状态、意义层、NarrativeState | Novelcrafter 的可见时间生效点；统一版本谱系 |
| 上下文 | 多查询/RAG/摘要/记忆/预算/归档 | NovelAI 的实际注入查看；Sudowrite 的来源卡 |
| 参考小说 | 多源分析与 FusionDNA/场景仲裁 | 保持分工与证据可解释；不据资料空白判定竞品没有 |
| 情感爽点 | 章意图/场景表达/读者承诺/审校 | 强化作者选择与持续后果，不靠统一爽点次数 |
| 质量反馈 | 事实硬门、模型评审、读者模拟 | 模型报告与实际改文、作者采纳、真实连读反馈分开 |

## 五、推荐的目标创作流程

保留现有服务能力，但作者主流程不应呈现成十几个技术开关。

1. **确认故事契约**：卖点、主角想要/珍惜什么、冲突发动机、长短期待；可选声音试写。
2. **确认参考分工**：每本参考借鉴什么，不借鉴什么；显示 ready/provisional。
3. **确认当前卷与近期章意图**：章功能、人物选择、关系变化、兑现/余波；远期仍可粗规划。
4. **生成前预检**：缺少关键人物依据、过期承诺、冲突正史、无效融合、预算与费用。
5. **编译可查看的上下文包**：已确认事实/本章计划/参考方法/作者偏好分区，显示来源、版本和时间。
6. **起草并有界修订**：按需要用整章或场景链；事实错要修，审美建议可拒绝；保留声音与留白。
7. **作者采纳/编辑**：候选与正式正文分开，冲突保存不覆盖；明确本次实际用了哪些建议。
8. **按采用版本提交派生状态**：记忆、承诺、摘要、向量和后续规划都有来源与成功状态，下一章按时间读取。

整个流程只需几个关键作者确认点；不必每个内部阶段都要求点一次确认。

## 六、改进优先级

以下为实施建议，不是本轮已完成的修改。

| 优先级 | 工作项 | 影响与最小切入点 |
| --- | --- | --- |
| P0 | 修复 hybrid 分数域/阈值契约 | 正常启用 hybrid 时不再把最好结果全部滤掉；先补 multi-query 回归 |
| P0 | 事实召回统一时间/来源约束 | Qdrant、BM25、全书/卷摘要、旧记忆都遵守同一 as-of；未来计划分区保留 |
| P0 | 分离候选与正史记忆 | 先把未选稿更新标成 draft，查询拒绝把它当 canonical；再迁移至采纳事件提交 |
| P1 | 索引写入回执与恢复 | 准备新版本后切换；失败不推进 ingest hash，支持重试与对账 |
| P1 | NarrativeDelta 跨分支覆盖/重建 | 复用现有台账；前章修改后可重建，切换模式不静默丢追读状态 |
| P1 | 后续章纲/卷复盘来源绑定 | 选版/可靠保存后触发；校验 source hash；迟到建议标 stale |
| P1 | 作者可见的实际上下文与执行状态 | 在已有归档/诊断基础上，解释读到什么、过滤什么、哪些只形成报告 |
| P1 | 情感目标同源 | 已确认章规划优先，规则曲线兜底；不把人物峰值当读者情绪 |
| P2 | 人物关系/承诺进展视图 | 复用既有实体和证据，串联选择、代价、关系后果和长线牵挂 |
| P2 | 题材化评估与成本消融 | 证明哪种模式适合哪类章节；不用“一套高潮频率”覆盖言情/悬疑/升级流 |

**暂不优先**：增加更多 Agent、再建独立爽点记忆库、无差别增大 top-k/上下文、全面开启所有质量回路、用更高维 embedding 掩盖检索契约错误。

## 七、如何验收“真的更会写小说”

### 7.1 先做不依赖文笔的确定性回归

| 用例 | 预期 |
| --- | --- |
| 两路同一片段排名第一，走普通 multi-query hybrid | 不因 cosine 阈值错误变成零片段 |
| 第 40 章受伤后，重写第 10 章 | 不把第 40 章伤势作为已发生事实；可读取明确标注的未来计划 |
| 生成 A/B，选 B，A 的记忆任务迟到 | 正史及后续规划不采纳 A；A 只能保留为草稿分析 |
| 修改早章，后续 delta/摘要/建议引用旧 hash | 标失效，并可依依赖重建；不静默继续注入 |
| embedding 或 upsert 故障 | 正文保存不受损；旧有效索引可恢复，索引状态不假成功 |
| 作者设计低强度余波章 | 不因通用三幕曲线强迫添加高潮/牺牲 |
| 参考换绑或重分析时旧融合返回 | 旧结果不能覆盖当前来源；fallback 状态明确 |
| premium 场景切换至 standard/购买 polish | 台账覆盖差异可解释，缺失增量可补，不假称一直完整 |
| 章纲/卷复盘任务基于 A，作者已改为 B | A 的建议无有效来源，不自动成为当前规划 |

### 7.2 再做连续阅读，而不是单章自评分

当前已有 `services/bench/` 与 `run_serial_bench.py`。连读评估支持对齐的连续 3–8 章，要求逐字证据，维度包括牵挂、关系记忆、节奏、兑现和潜台词，应复用它，不另造只给总分的评测。

证据：[连读 Schema 与证据校验](../backend/app/services/bench/serial_reading.py#L12)。

建议用几类不同叙事任务建立冻结样本：升级/都市、悬疑、关系/言情，以及安静余波章。对比 standard、premium 场景、场景加节拍搜索、再加人物意义等配置。候选配置必须验证实际生效；不支持的消融需在测试专用依赖注入中实现，不能只改一个被忽略的开关。

现有 benchmark 的 `full` 也不是所有能力的无条件全开，模块已有开关交互/no-op 注解；比较时应记录 resolved config 和执行清单。[配置与消融约束](../backend/app/services/bench/configs.py#L1)

先连续生成较短试验，再扩到 20–50 章；连读盲评仍可按 3–8 章滑动窗口取样，并在较远章点检查事实/承诺恢复。报告至少包含：

- **事实正确性**：未来泄漏、废稿污染、矛盾事实、失效来源进入 Prompt 的次数。
- **检索有效性**：人工标注关键证据的召回率；召回到最终注入的漏损；hybrid 过滤前后数量。
- **人物/关系连续性**：具体选择是否有动机，关系事件是否改变后续言行。
- **兑现质量**：已铺垫承诺是否有实际推进/兑现，是否重复开同类悬念，是否有后果。
- **作者负担**：采纳率、实际改写率、修复严重错误耗时。
- **成本**：实际 token/耗时/重试、每千字最终采用稿的费用；不仅统计生成字数。

以上是待建立的验收方案，不是已测得的成绩。不能用“多了几个评审服务”替代这些结果。

## 八、结论

保留现有分层规划、人物行动依据、多源参考契约、版本化正文和叙事增量；这些是继续发展的正确基础。

下一轮最有价值的建设顺序是：

**检索真的能取回证据 → 证据属于正确时间和版本 → 正史只随作者采用而变化 → 人物/承诺在后续行动中留下痕迹 → 用连续盲读证明收益。**

当这条链可靠后，再增加文风优化、人物意义和更多自动规划，才不容易变成“更贵、更复杂，但长篇还是会忘事”。
