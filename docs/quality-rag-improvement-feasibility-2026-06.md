# Arboris-Novel 剧情质量与检索链路改进可行性分析报告

> 日期：2026-06-11
> 范围：章节大纲/剧情质量逻辑 + 向量检索 + Reranker
> 对标：2024–2026 学术前沿（DOME、SCORE、Agents' Room、LongStoryEval、ChronoRAG 等 17 篇）+ 商业产品（Sudowrite / NovelAI / Novelcrafter / 蛙蛙写作等）

## ⚠️ 现状描述勘误（2026-06-11 第一阶段执行实证）

本报告「项目现状/半截工程」部分基于多代理代码调研，执行第一阶段时**逐项实证发现三处「缺失」实为「已实现/不存在」（代理幻觉）**，以实际代码为准：

- **B2a 卷摘要：不存在**。全仓无任何 `volume` 标识符，"VolumeSummary 表已建未用"是幻觉，已取消。
- **B2c Mem0 更新：已实现**。`finalize_service.py` 已有 premium 档 `add_chapter_memory`，已取消。
- **A2 SCORE 闭环：已实现**。状态写回（`memory_layer_service.update_character_state` 每章快照继承上一章）、生成前注入（`build_chapter_state_context`→prompt 标注「数据库实时查询，零幻觉」）、一致性检查+重写（`consistency_service`+`combined_revision` 在 standard 后处理）整套已在，已取消。

**实证为真并落地的四项**：C1（reranker 原默认 False=白写）、B2b（hybrid 原非默认）、B1#1（chunk/summary 原未按章节排序）、A3（mission 生成后原确无评审，已新增 grader 通道前置评审：评推进主线/前文冲突/钩子有效，未配置则跳过，绝不阻断）。

报告的**外部调研部分（论文/商业对标/技术选型）独立可靠**。结论：采用任何改进项前**务必以实际代码实证现状**。

## 一、结论摘要

项目架构骨架与 2026 年学术/商业共识方向一致，部分能力（六维评审+守门员、证据路由、token 预算编排）属差异化领先位——没有任何商业产品内置自动化生成中一致性管线，全靠人工触发审计。

三类系统性缺口：

1. **「规划-执行-反馈」闭环断裂**：大纲一次性生成后永不修订、评审只在正文后不在大纲前、计划（情感曲线/mission）与实际产出无比对。与 DOME/CritiCS 等 2025 共识差距最大。
2. **多处「半截工程」**：卷摘要检索链路在但无人写入数据（空转）、证据评分与预算不影响生成（纯遥测）、Mem0 初始化了但更新链路缺失、Reranker 实现了但默认关。**打通已有半截的 ROI 远高于引入新技术。**
3. **检索缺时序感知**：无章节邻近加权、无时间衰减、角色状态无双时态字段、伏笔纯关键词匹配。对"几十章前的设定/伏笔"长篇核心痛点覆盖不足。

## 二、现状定位对标

| 能力 | 现状 | 前沿 | 判定 |
|---|---|---|---|
| 自动一致性管线 | 六维评审+gatekeeper+claim验证 | 商业产品全人工 | ✅ 领先 |
| 上下文预算编排 | prompt_budget_manager 四级+缓存友好 | NovelAI Token Budget | ✅ 持平偏先进 |
| Contextual chunk 前缀 | 已实现 `[第N章·标题]摘要` | Anthropic Contextual Retrieval | ✅ 半落地（缺 hybrid 默认开） |
| 混合检索 | Vector+BM25+RRF(k=60) | 共识基线 | ✅ 持平（非默认） |
| 大纲工作流 | 一次性全书，无修订回路 | DOME 滚动细纲/蛙蛙三级 | ❌ 落后一代 |
| 评审时机 | 仅正文后 | CritiCS：前移大纲收益更高 | ❌ 缺位 |
| 状态时序 | 按章快照无有效期 | Graphiti bi-temporal | ❌ 缺位 |
| 伏笔召回 | 关键词+状态表 | 语义+联想召回 | ❌ 缺位 |
| Reranker | 已实现 Jina 兼容，默认关 | 标配默认开 | ⚠️ 一键之差 |
| 质量回归基准 | novel_bench 快照 | WebNovelBench 中文八维 | ⚠️ 可升级 |

## 三、改进项明细

### A 组 大纲与剧情质量
- **A1 滚动细纲+章后大纲修订回路** P0｜大纲一次性生成永不改（writer.py:954-1070）｜DOME/蛙蛙｜复用 RegenerateOutlinesRequest，finalize 后加漂移检测触发重生成｜中｜缓解 30+ 章中盘无主线
- **A2 章后状态表回写+生成前逐项校验（SCORE）** P0｜结构齐全但缺闭环，CRITICAL 无统一重写｜arXiv:2503.23512，与现有结构同构｜state_rag 注入+combined_revision 复用｜小-中｜跨章漂移受控
- **A3 评审前移到 mission 阶段** P0｜六维只评正文｜CritiCS EMNLP2024｜mission 生成后用 llm_grader 小模型评 3 项，不过关重生成｜小｜prompt 阶段拦截省一个量级 token
- **A4 跨章一致性激活** P1｜ConsistencyService 支持跨章但只传单章｜补滑动窗口参数｜小
- **A5 计划-执行偏差比对** P1｜pacing 输出计划无比对告警｜六维情绪维度 vs mission.satisfaction_design｜小-中
- **A6 WebNovelBench 八维+pairwise judge** P1｜绝对打分不可靠｜2606.01629/2505.14818｜多版本择优改 pairwise｜中
- **A7 大纲事件图结构化** P2 观望｜StoryWriter/STORYTELLER｜面大收益未实证，先做 A1/A2

### B 组 向量检索/RAG
- **B1 检索时序感知三件套** P0 本组最高ROI｜仅按 project_id 过滤无邻近加权（vector_store_service.py:135-141）｜ChronoRAG 2508.18748+Sudowrite 分层｜①结果按章节号排序标注 ②score×章节距离衰减 ③local_plot 近10章优先预过滤｜小｜时序幻觉直接减少
- **B2 打通三处半截工程** P0｜①VolumeSummary 检索在但无写入(evidence_router_service.py:377-394)空转 ②Mem0 初始化但无章后 update ③hybrid 实现但默认 vector｜①finalize 满N章触发卷摘要入库 ②premium 接通 memory update ③默认改 hybrid｜小-中｜hybrid+已有 contextual prefix = 完整 Contextual Retrieval（失败率降67%）
- **B3 CharacterState 双时态字段** P1｜Zep/Graphiti 2501.13956，不引 Neo4j 只借字段｜加 valid_from_chapter/invalidated_at_chapter，更新标记失效非覆盖｜中（需 Alembic）
- **B4 伏笔语义化检索** P1｜仅 keywords+status，埋A收B即失联｜伏笔 content 向量化，symbolic_rag 补语义查询+原文锚点(AnchorMem)｜中
- **B5 查询分解不做HyDE** P1｜多跳分解 MRR@10+36.7%；HyDE 私有语料收益存疑｜multi_query 补 LLM 分解，修 chapter_context_service.py:281 硬编码｜小-中
- **B6 叙事感知切块** P2 观望｜LitSeg；现有 contextual prefix+中文标点已缓解，Late Chunking 与 C2 绑定

### C 组 Reranker
- **C1 默认开启+失败监控** P0 一键之差｜RAG_RERANKER_ENABLED 默认 False 等于白写｜standard/premium 默认开(fast 保持关)，失败回退打 telemetry，截断 800→1024｜极小
- **C2 Reranker/Embedding 选型升级** P1｜Qwen3-Reranker-0.6B/4B 中文最强且支持指令；Qwen3-Embedding-4B 或 BGE-M3｜接口已兼容，换模型=配置+全量重建向量｜配置小+重建中｜先 C1 拿基线再 A/B

## 四、明确不做
- 完整 GraphRAG（增量与连载语料冲突）
- ColBERT 多向量（reranker 已覆盖）
- Listwise LLM 通用重排（成本高一量级，grader 末端已是）
- 引入 Zep/Letta/MemGPT 整套（依赖重，借鉴 bi-temporal 字段即可）
- 1M 长上下文全量塞（成本千倍，NoCha 实证最强模型整本一致性仅 55.8%，外置追踪不可替代）
- HyDE（私有小说伪文档易偏）

## 五、实施路线图

**第一阶段（约2周，纯打通+开关，不引入新依赖）**：
C1 Reranker默认开 → B2 三处半截打通 → B1 时序三件套 → A3 mission 前置评审 → A2 状态校验闭环
预期：检索失败率与时序幻觉显著下降，跨章漂移受控；改动全在现有服务内。

**第二阶段（约3-4周）**：
A1 滚动细纲 → A4 跨章一致性激活 → B3 双时态状态 → B4 伏笔语义化 → A5 情感曲线闭环
预期：解决 30+ 章中盘塌陷与伏笔失联两大核心痛点。

**第三阶段（按效果决策）**：
A6 评估基准 → C2 模型 A/B → B5 查询分解 → 观望项（A7/B6/HippoRAG 联想）

**产品侧低垂果实**：对话式全书审计（Sudowrite Chat/Novelcrafter Tinker），项目检索+一致性能力已足够支撑，做会员入口成本低感知强。

## 关键论文索引
DOME 2412.13575 | Agents'Room 2410.02603 | StoryWriter 2506.16445 | SCORE 2503.23512 | FlawedFictions 2504.11900 | NoCha 2406.16264 | LongStoryEval 2512.12839 | WebNovelBench 2505.14818 | CritiCS 2410.02428 | 信息失真 2505.12572 | ChronoRAG 2508.18748 | Late Chunking 2409.04701 | Zep/Graphiti 2501.13956 | HippoRAG2 2502.14802 | AnchorMem 2604.17377 | LitSeg 2605.27156 | Judge可靠性 2606.01629 | Contextual Retrieval(Anthropic 2024.09)
