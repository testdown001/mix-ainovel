# AI 小说生成系统重审（2026-09-15）

## 结论先行

当前系统已经具备比较完整的工程底座：概念对话、蓝图、章纲、上下文规划、参考小说融合、记忆、场景生成、后处理、质量分析和生产观测都已经存在。真正限制成文质量的原因不是缺少更多提示词，而是主流程仍然以“规划一次 → 整章写一次 → 生成后评分”为主，叙事状态没有在场景之间形成强约束，评审也很少拥有否决或回滚权。

要让作品接近成熟的起点作者，最急的方向是把系统改成一个有状态的叙事控制回路：每个场景先有可验证的任务契约，再写正文；正文必须更新人物、因果、伏笔和读者期待状态；改写只能提交候选版本，经过事实和视角校验后才能定稿。

这份审计基于当前源码（本地最新修复提交 `07193bd`）和近期研究。`docs/generation-quality-audit-2026-07.md` 中关于“大纲元数据丢失”和“优化后短文本未再检查”的结论已经被当前代码修复，因此不再列为现存问题。

本批 P0 已落地：premium 默认场景化；场景契约、滚动状态和失败阻断；定稿前质量门禁与正文哈希；改写失败回滚；Responses strict schema 与推理模型采样参数适配。standard/fast 仍保留低延迟路径。

本批 P1 已落地：premium 场景增加读者追读控制器（候选节拍、独立评分和回退）；参考小说拆为带来源与版本的机制卡，按本场相关性仲裁并记录采用/改写/拒绝；选定正文的叙事状态以版本哈希为基线折叠，包含实体事实、冲突、读者承诺和情绪牵挂；创作记忆在更宽候选池上按场景相关性排序；细纲修订提示增加 compare-and-set 消费凭据，成功写入后标记 consumed。未通过仲裁的参考材料不会注入正文提示，未选草稿不会更新 canonical state。

## 当前真实架构

主路径大致是：

```text
灵感/概念对话
  -> 故事蓝图
  -> 章节规划与上下文规划
  -> SingleVersionGenerationService（多数标准/高级配置为一次整章调用）
  -> 后处理与质量分析
  -> 版本/章节持久化
```

文学化场景路径现在是 premium 的默认质量分支，standard 仍可显式选择整章路径：

```text
场景列表 -> 逐场景生成 -> 拼接整章 -> 节奏/密度/金句/人性化处理 -> 持久化
```

代码证据：`pipeline_config_service.py` 的 standard 默认仍可整章调用，premium 已默认打开 `enable_scene_by_scene`；`enable_prose_sculpting`、`enable_golden_paragraph` 仍按开关控制。`scene_generation_service.py` 的场景现在先生成契约、逐场审校并传递状态，失败或截断场景会阻断整章，不再拼接残章。

## P0：应该立即修复

| 优先级 | 现象与代码证据 | 对小说的影响 | 建议验收标准 |
|---|---|---|---|
| P0 | standard 仍可单次整章生成；旧默认 `writer_chapter_versions=1` | 长章节容易出现中后段松散、情绪线突然跳变、结尾没有有效余波。长文本研究也反复发现一次性输出难以维持结构 | premium 默认按“章导演 → 场景契约 → 场景生成 → 过渡审计”运行；每个场景有目标、阻力、选择、转折、后果和情绪变化 |
| P0 | 场景失败后允许带 `missing_scenes` 继续返回 | 章节可能缺关键因果节点却被当成可用稿，读者会感到跳戏或人物行为无理由 | 必需场景失败时不得提交章节；自动用备用模型/缩短上下文重试，仍失败则标记失败并保留可重试状态 |
| P0 | 文学后处理的节奏、密度、金句改写主要依赖长度阈值，缺少事实/实体/视角差分 | 后处理可能把已经校验过的设定、人物关系、伏笔或 POV 改坏 | 所有改写输出为 candidate；通过事实、实体、时间、POV、结尾钩子校验后才替换；失败则回滚原文 |
| P0 | `generation_analysis_task_service.py` 的读者模拟、反幻觉、质量检测主要在生成持久化后异步执行 | 系统能发现问题，却无法阻止坏稿成为当前版本，也不能稳定触发修订 | 采用 draft → candidate → verified → selected 两阶段提交；关键硬错在 selected 前阻断，软错才异步记录 |
| P0 | `generate_structured()` 目前是 JSON 提示词 + `json_object` + 修复重试，Responses 客户端仍是可选路径 | 复杂章纲、状态差分和审计结果容易落出 schema；修复器会掩盖真实 provider 错误 | 结构化边界统一使用 provider 原生 strict schema；记录原始响应、schema 错误、重试次数和最终版本 |

## P1：完成 P0 后紧接着做

### 1. 加入“读者追读控制器”

系统已经有 `reader_loop`、`emotion_hook`、`commercial_hook` 等字段，但它们目前更像提示词约束，不是决定下一步叙事动作的控制器。建议在每章和每场维护以下状态：

```text
读者当前在意谁、想要什么
已打开的问题/承诺，以及预计何时兑现
本场新增的压力、代价和信息差
本场兑现了什么，兑现后关系/处境怎样改变
下一场必须留下的牵挂
```

在写正文前，让一个便宜的辅助模型从 2–4 个候选 beat 中选择下一步动作，再由主模型把动作写成场景。选择分数至少包含因果推进、情绪转折、信息增量、兑现/余波比例和重复风险。这样“上瘾感”来自连续的选择与后果，不是每章机械加一个悬念。

### 2. 参考小说融合需要运行时仲裁

现有 `reference_fusion.md` 和 `FusionDNA` 已经做对了几件事：要求每本参考书有明确分工、单一叙事声音、reader loop、冲突取舍和 evidence limits；`reference_reading_contract.py` 也会限制来源和版本。这是良好基础。

仍需补一层运行时策略：

- 每本书拆成 `plot_mechanics / voice / rhythm / relationship / market_hook` 角色，并带权重；
- 每个场景只检索与本场功能相符的机制卡，不把所有参考材料整段塞进 prompt；
- 出现冲突时按“本书设定与人物声线 > 主参考的结构机制 > 补充参考的局部技法”裁决；
- 记录每个参考机制被采用、改写或拒绝的 provenance，并增加“不可复刻事件、专名、句式”的负约束；
- 用盲测比较“无参考、单本、融合三本”的读者偏好、创新度和重复率。

参考资料的价值应当是可迁移的阅读动力机制，而不是模仿某本书的表面句式。

### 3. 记忆从“最近/高置信”升级为“相关、有效、无矛盾”

`creative_memory_service.py` 当前最多选 12 条 active memory，排序主要是 pinned、confidence、updated_at；`memory_layer_service.py` 再补角色状态、近章事件和因果链。这会把“最近的记忆”误当成“本章最需要的记忆”。

建议把记忆卡升级为带有效期的实体-事件图：每条记忆记录适用角色、时间范围、来源章节、置信度、是否被新事实取代，以及与其他记忆的冲突关系。生成前按本场角色、地点、时间和目标做相关性排序，生成后用 `state_delta` 更新图；冲突必须先裁决，不能同时注入模型。

### 4. 修复修订提示的消费生命周期

`outline_revision_service.py` 写入 `revision_hint.status=pending`，读取端只读取 pending，当前没有可靠的 consumed 标记。这样同一条修订意见可能被后续章节重复注入。应在成功生成或章节选定后用 compare-and-set 标记 `consumed`，并保存 consumed_by、consumed_at、source_version；章节重写时只重新激活仍然有效的提示。

### 5. 高级章节需要有限候选多样性

`version_generation_service.py` 支持多版本，但默认一版时 AI review 会跳过。全量生成两份正文成本高，建议先生成 2–4 个 beat 计划或结尾方案，由评论器选择，再生成一份正文；只有关键章、转折章或用户主动要求时才生成两份完整候选。

## 推理模型和 API 架构建议

OpenAI 当前模型文档建议推理、工具调用和多轮任务使用 Responses API；最新模型支持 Structured Outputs、提示词缓存、持久化推理状态和上下文压缩。[官方最新模型指南](https://developers.openai.com/api/docs/guides/latest-model) 还特别强调，复杂任务应明确结果、成功标准、约束和可用上下文，让模型选择路径。

当前项目的 `OpenAIResponsesLLMClient` 仍是可选格式，未使用 `previous_response_id`、持久化 reasoning 或 compaction；`chat_with_tools` 也明确拒绝 Responses 格式。建议建立 provider capability matrix，按模型能力决定 payload：推理模型自动移除不兼容的 `temperature/top_p`，结构化输出走严格 schema，工具型导演走 Responses API，普通 prose 写作可以继续使用低成本 chat 路径。

建议的路由如下：

| 任务 | 模型/推理强度 | 目标 |
|---|---|---|
| 故事蓝图、卷纲、冲突裁决、场景 beat 选择 | 最新推理模型，medium/high | 维护因果、选择和长程计划 |
| 事实/实体/时间/伏笔审计 | 低成本推理模型，low/medium | 高召回找错，结构化输出 |
| 场景正文和对白 | 成本可控的写作模型，low/medium | 语气、节奏、人物声线 |
| 参考资料抽取、记忆压缩、候选排序 | 小模型或批处理模型 | 降低成本，保持主模型上下文干净 |

静态系统指令、schema 和写作规则放在 prompt 前缀以获得缓存；本章动态状态、最近文本和 scene contract 放在末尾。所有调用都要记录模型、reasoning effort、输入/输出 token、缓存命中、延迟、重试和失败原因。

## 研究对系统设计的直接启示

| 研究 | 关键发现 | 应用到本项目 |
|---|---|---|
| [Suspenseful Stories, EACL 2024](https://aclanthology.org/2024.eacl-long.147/) | 单纯让 LLM 写悬念不可靠；基于叙事学和认知心理的迭代提示能改善悬念 | 为每场维护读者问题、风险、承诺和兑现状态，采用“规划—生成—评审—再规划” |
| [CritiCS, EMNLP 2024](https://aclanthology.org/2024.emnlp-main.1046/) | 集体 critic 多轮修改能同时改善计划和成文质量 | 把评论器放到 selected 之前，评论 beat 计划和正文，而不是只写 review metadata |
| [SWAG, Findings EMNLP 2024](https://aclanthology.org/2024.findings-emnlp.824/) | 用辅助 LLM 选择下一步动作，把故事生成转成搜索，优于单次端到端生成 | 加 reader-action controller，从候选动作中选择下一场的推进方式 |
| [Ex3, ACL 2024](https://aclanthology.org/2024.acl-long.494/) | 单纯 hierarchical plan-then-write 仍会失去连贯性；结构抽取与树状扩展更稳 | 章纲不能是一次性静态大纲，要能在场景结果后动态扩展和修订 |
| [Long-form Story Generation, INLG 2024](https://aclanthology.org/2024.inlg-genchal.13/) | 即使有很长上下文，长篇一致性和控制仍难；按章节迭代并提供上下文更有效 | 采用 rolling story state、章节摘要、最近文本和可验证 scene contract |
| [LongWriter, 2024](https://arxiv.org/abs/2408.07055) | 长上下文模型常在约 2k 词后输出退化；按段落拆分并提供目标长度可改善长输出 | 不把 3000–4000 字作为一次调用的默认任务；按场景预算生成 |
| [Creative Planning Tutorial, NAACL 2025](https://aclanthology.org/2025.naacl-tutorial.1/) | 创作任务存在 planning gap，规划应包含写作前和写作中的动作 | 把规划当作运行时状态，而不是只生成一份章纲 |
| [DOME, NAACL 2025](https://aclanthology.org/2025.naacl-long.63/) | 刚性大纲和宏观规划不足会造成情节与一致性问题；动态层次大纲能随不确定性调整 | 引入卷/章/场三级动态大纲，并允许基于真实场景结果回写后续计划 |
| [WriteHERE, EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1254/) | 检索、推理、组合需要递归异构规划，不应只有 outline | 把参考检索、记忆检索、情绪规划和正文组合拆成不同阶段 |
| [CogWriter, Findings ACL 2025](https://aclanthology.org/2025.findings-acl.511/) | 写作可拆为规划、转译、复查和监控，层次规划 agent 配合并行生成 agent | 对应本项目的 director、scene writer、verifier、monitor 四类角色 |
| [Storyteller, Findings ACL 2025](https://aclanthology.org/2025.findings-acl.1071/) | STORYLINE 与叙事实体知识图持续和生成交互可改善连贯性 | 让人物/关系/事件图成为每场输入和输出，而非只做历史摘要 |
| [SuperWriter, Findings ACL 2026](https://aclanthology.org/2026.findings-acl.428/) | 结构化思考、分层偏好优化和树搜索能把最终质量传递到中间步骤 | 在积累真实用户偏好后，再考虑对 beat 选择和审计器做 DPO/MCTS |

研究也提醒不要只追求“像参考书”。创意故事评测发现，LLM 作品可以有复杂文风，但新颖性、惊喜度和多样性仍可能低于人类；[创意故事评测](https://arxiv.org/abs/2411.02316) 与 [CS4 创意基准](https://arxiv.org/abs/2410.04197) 都显示约束、连贯性和新颖性之间存在取舍。因此必须同时测“读得顺”和“没看过”。

## 建议的目标架构

```text
Story DNA / Reference Roles / Canon Graph
                ↓
        Volume & Chapter Director
                ↓
        Beat Contracts (2–4 candidates)
                ↓  reader-action selection
 Scene Writer → State Delta → Transition Verifier
      ↑              ↓              ↓
  rolling context  Canon/Emotion   retry or revise
                ↓
  Chapter Reader Pass → Candidate Score → Selected Commit
                ↓
  Memory/outline update + metrics + provenance
```

核心数据契约建议至少包括：

```text
StoryState: canonical_entities, relationships, timeline, open_promises,
            emotional_state, style_fingerprint, reference_provenance
BeatContract: scene_function, goal, obstacle, choice, turn, consequence,
              open_question, micro_payoff, target_emotion, required_facts,
              forbidden_facts
SceneResult: text, facts_added, state_delta, promises_opened, promises_closed,
             emotion_before_after, quality_scores, source_ids
```

关键原则是正文不是唯一产物。每场正文必须同时产生可审计的 `state_delta`；没有状态差分，后续场景只能再次猜测人物和世界发生了什么。

## 30 天实施顺序

**第 0 周（P0，1–2 天）**

1. 禁止带 `missing_scenes` 的章节进入 selected。
2. 为 prose sculpting、golden paragraph、enrichment 增加事实/实体/POV/长度/结尾钩子验证和回滚。
3. 修复 `revision_hint` 的 consumed 生命周期和并发 compare-and-set。
4. 建立模型能力矩阵；推理模型调用移除不兼容采样参数，JSON 边界切换 strict schema。

**第 1 周（质量主链）**

1. 新增 serial quality path，默认用于 premium：章导演、场景契约、滚动状态、过渡审计、失败重试。
2. 引入 draft/candidate/verified/selected 状态，关键硬错在持久化前阻断。
3. 用 2–4 个 beat 计划候选替代默认的多份整章正文。

**第 2 周（追读与参考）**

1. 加 reader-action controller 和 open-loop ledger。
2. 将参考书按角色、权重和本场功能检索；保存采用/拒绝 provenance。
3. 增加实体-事件图的时间有效性、冲突和 supersession。

**第 3–4 周（评测和模型升级）**

1. 接入 Responses API 的推理导演、结构化审计和上下文压缩/缓存。
2. 建立 50–100 章回归集，做盲测 pairwise preference。
3. 指标至少包括：前 200 字吸引力、场景因果推进、情绪转折、人物目标兑现、未决问题质量、伏笔回收、实体一致性、创新度、重复率和生成成本。
4. 只有在偏好数据稳定后，才考虑 DPO/MCTS 或领域微调。

## 最终判断

系统当前最需要的不是继续堆更多“文风”“爽点”“高级润色”提示词，而是把已有模块组织成可回滚、可验证、能根据读者状态选择下一动作的叙事控制系统。先完成 P0 的提交门禁和场景化主链，再做参考融合和模型升级，质量提升会比单纯更换模型或增加 token 更确定。
