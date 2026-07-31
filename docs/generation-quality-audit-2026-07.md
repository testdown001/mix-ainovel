# 生成/构思/润色/长程记忆 深度审计与优化执行方案（2026-07-26）

> 方法：四路并行代码探查（生成管线 / 构思蓝图大纲 / 润色后处理 / 长程记忆RAG）+ 关键结论逐条人工 grep 实证。
> 标注 ✅ = 已亲自读码实证；未标注 = 探查报告结论（附 file:line，可信度高但未逐行复核）。
> 总体结论：**平台的"质量设施"大量处于「建好了但没通电」状态**——六维评审、多版本选优、卷/书摘要、时序状态、写作技能、mem0 蒸馏等核心质量机制在主力档位上实际不生效；同时存在若干会毁数据/越权的 P0。

---

## 交付状态（更新于 2026-07-31）

**阶段 0～4 已全部交付**，共 28 个提交（`7c629fa..95415af`），后端 596 tests passed，前端 type-check/unit + go build/vet 全绿。
下方第四节清单已按实际代码逐条核对勾选（`[x]` 附提交号），**仅剩 3 项未闭环**：

| 项 | 状态 | 实证 |
|----|------|------|
| #33 `revision_hint` 生命周期 | 🟡 一半 | 大纲重写/蓝图重建即清 ✅；但无 `consumed` 标记，触发点仍在写侧任务（`generation_write_task_service.py:195`）而非 select/finalize |
| outline 结构化字段落库 | ❌ 未做 | `outline_generation.md:134-139` 每章都让 LLM 产出 `narrative_phase`/`foreshadowing.plant-payoff`/`emotion_hook`，但 `update_or_create_outline(project_id, ch_num, title, summary)` 只落标题+摘要，三字段全丢弃 |
| #19 premium enrichment 互斥 | ❌ 未做 | `standard_post_processing_service.py:179` `enrichment_enabled = enable_enrichment and not optimizer_enabled` 在 optimizer 执行前算死、跑完不复检长度 → premium 档章节偏短时无补救（density 只管偏长） |

**运维待办**：网关需重新构建部署才认识 `blueprint:generate` 任务类型（旧网关下前端自动回退同步蓝图生成，安全但失去异步收益）。

---

## 一、P0（假功能 / 毁数据 / 越权）

### A. 质量机制实际不生效

1. ✅ **六维评审在 standard/premium 是死路径**：`standard_post_processing_service.py:252-260` 调 `review_chapter(user_id=user_id)`，但 `six_dimension_review_service.py:53-63` 签名无 `user_id` → 必抛 TypeError，被 `:294` except 吞成一行 warning。standard 也不派发异步六维（`pipeline_orchestrator.py:1016-1017` 空标记）。**两个主力档位的质量拦截完全不存在**。测试恰好都设 `enable_six_dimension=False` 掩盖了它。
2. ✅ **即使修好，auto-refine 也取不到反馈**：`:270` 读 `overall_review`、`:273` 读 `analysis`，schema/prompt 里只有 `summary` 和 `issues[]` → 反馈恒空，不会触发 refine。且 `:266` `getattr(config,"six_dimension_min_score",70)` 读的是 `PipelineConfig` 上不存在的字段，`settings.six_dimension_min_score`（config.py:321）从未生效。解析失败默认 80 分伪装通过（`six_dimension_review_service.py:26,161`）。
3. ✅ **多版本+AI选优默认完全不发生**：`writer_chapter_versions` 默认 1（config.py:141-147），前端不传 versions，premium 硬编码 1（pipeline_config_service.py:165）→ `_run_ai_review` 在 `len(versions)<=1` 直接返回（pipeline_review.py:35-36）→ `editor_review.md`（7.3KB 金牌编辑提示词）、采样评审、combined_revision（standard 档）全部不可达。
4. ✅ **卷/书摘要与整个 Agentic 证据层是 telemetry-only**：`evidence_router_service.py:316-320` 注释自述「有意设计：不进入生成提示词」。卷/书摘要唯一进 prompt 的路径是混在 `rag_summaries`（chapter_number=0）里被 top_k=3 撞中，落在 priority=3/800tok 最易被截的段。证据预算裁剪、LLM 评分、`ContextPlan.budgets`、`BudgetEnforcerService` 均无真实消费者。
5. ✅ **standard 档记忆段被 compiler 丢弃**：`[项目长期记忆]`/`[记忆层上下文]`/`[角色当前状态]` 绑定 `project_memory`/`character_state` 模块（prompt_compiler_service.py:21,27），仅 `enable_memory`（=premium）才进 `prompt_modules`（context_planner_service.py:638-640）。而 `project_memory_text` 是**无条件预取**的（generation_prefetch_service.py:83-89）——算了、落库了、拼 prompt 时扔掉。
6. ✅ **`enable_temporal_state` 从未传给 planner**：standard/premium 都置 True（pipeline_config_service.py:154,172），但 orchestrator 的 `planner_flow_config`（pipeline_orchestrator.py:337-357）没有该键 → `temporal_state_service.py` 全文件 + evidence_router 时序分支不可达。
7. ✅ **伏笔回收 `[:10]` 截断**：`foreshadowing_service.py:495-499` 只把最早 10 个未回收伏笔喂给提取 LLM（按 chapter_number ASC）。长篇几十个活跃伏笔时，中后期伏笔永远无法自动 resolve，永久累积；读侧 urgency top_k=6 + 逾期>20章 无差别判 overdue，同质化。
8. ✅ **skills/ 六技能死代码 + Hubu 注入必炸**：`skill_service.py` 构造 `SkillDefinition(category="style")` 传 str，`hubu_agent.py:179` 直接 `.category.value` → AttributeError 被吞。六个技能的 `execute()` 在正常生成流程中从不被调用（仅手动 REST / 工具路径可达）。
9. ✅ **mem0 蒸馏 100% 不触发**：namespace 错配（写入 `user_id=project_id`，memory_layer_service.py:609,734；蒸馏 `novel_{project_id}`，memory_distillation_service.py:70,95）+ `AsyncMemory.from_config` 漏 await（:58）→ 记忆池无限增长，DISTILL_THRESHOLD 形同虚设。

### B. 毁数据 / 越权 / 静默截断

10. ✅ **scenes×3 + concepts×4 端点无所有权校验**：`novels.py:2125/2148/2205`（GET/PUT/generate scenes）与 `:1719/1760/1789/1831`（concepts CRUD）只 `get_current_user`，不 `ensure_project_owner` → 任何登录用户可读写他人项目数据、借他人项目烧 LLM。
11. ✅ **重生成先毁旧章**：`pipeline_orchestrator.py:300-303` 生成前把 `real_summary=None`、`selected_version_id=None`、`status="generating"` 先 commit，`replace_chapter_versions` 再 DELETE 旧版本 → 中途任何失败让已完稿章节退化为无摘要无版本、卡 generating。
12. ✅ **二次生成蓝图摧毁扩写大纲**：`replace_blueprint`（novel_service.py:424-428）先 DELETE 项目全部 ChapterOutline 再从 1 重编号。用户扩到 300 章、写了 20 章后点「重新生成蓝图」→ 280 章大纲消失、章号与 chapters 表错位。伏笔超出新末章的静默 drop（:725-726）。
13. ✅ **蓝图 8192 max_tokens 静默截断**：`novels.py:825`。50 章大纲+世界观+角色 中文轻松超限；截断后 `repair_json` 自动补全括号成"合法"JSON，Blueprint 除 title 外全有默认值 → 残缺蓝图（28 章、伏笔 []）静默落库。无数量下限断言。
14. ✅ **`finish_reason=length` 只打日志**：`llm_service.py:1221-1229` 返回半截内容；写作 max_tokens=6000（4000 字中文最坏可超），`is_probable_chapter_plain_text` 不检测截断 → 句中断掉的章节被当合格正文落库。
15. ✅ **`/chapters/outline` 无校验可覆盖已完成章**：`writer.py:1053-1060` 直接 `item["chapter_number"]`（缺字段 KeyError→500），不校验范围/已完成章；隔壁 `regenerate-outlines` 两项校验都有（:1295-1300），属遗漏。
16. **构思阶段同步长调用 vs 生产链路超时**：蓝图 LLM timeout 600s（novels.py:823），生产链 网关 write_timeout 120s（deploy/gateway-config.yaml:8）→ nginx 300s，必被掐断；后端继续跑并落库 → 用户看到失败实际已成功，重试重扣。批量大纲 500 章 = 20 次串行 LLM 更甚。且长调用全程霸占 DB 连接（池 5+10，db/session.py:32-36）。构思阶段无异步任务化（章节生成有）。

---

## 二、P1（语义漂移 / 长篇结构性缺陷）

### 润色链
17. ✅ **最能破坏正文的步骤没有正文校验**：`is_probable_chapter_plain_text` 只用于 optimizer/polish（pipeline_review.py:412,471）。combined_revision（无长度守卫无校验，:222-232）、consistency auto_fix（✅ `return response.strip()` 连 sanitize 都没有，consistency_service.py:281；`if fixed` 就整章覆盖，pipeline_review.py:325-328）、enrichment、humanize 均裸奔。一个 JSON 回包/"已修复"三个字即可替换整章。
18. **多步全文重写无改前改后对比**：全链没有一处重写后重新打分并可回滚，"越改越差"设计上不可检出。AI 评审本身是节选评审（>3600 字只看头/中/尾各 1200，ai_review_service.py:137-162）却驱动全文重写。
19. ✅ **premium 永失字数下限兜底**：`enrichment_enabled = enable_enrichment and not optimizer_enabled`（standard_post_processing_service.py:168），premium 两者都开 → enrichment 恒关；optimizer prompt 又要求 ±10% 字数 → 短章在最贵档无人救。
20. ✅ **polish 计费错位**：standard/premium 无条件 `enable_polish=True`（pipeline_config_service.py:157,179），计费只看用户勾选 `extra.enable_polish`（task_worker.py:229-241）→ 不勾选=白跑 polish 不扣分；与「勾选时每章额外扣 5 分」的产品口径矛盾。另 `/api/optimizer/*` 零计费、apply 无校验直接覆盖 content。
21. **时间预算被击穿**：`_over_budget` 在 optimizer/polish/enrichment/density 四步前只查一次（standard_post_processing_service.py:171）；enrichment/consistency 走 `generate` 默认 timeout=1500s；LLM 重试 3 次每次独立 180s → 单步 ≫180s 假设。fast/literary 分支完全无预算保护；literary 场景循环无 try/except，空场景静默丢。
22. ✅ **场景 2+ 丢硬约束**：scene_generation_service.py:63-72，第二场景起 core_context 压到 1500 字，`forbidden_characters`/`writer_blueprint`/POV 约束在拼接尾部被截没。

### 长程记忆
23. ✅ **叙事摘要卷概要缩进 bug**：narrative_summary_service.py:250-255，`parts.append` 在 for 外 → 只有最后一卷进 LLM 输入。一行修。
24. **早期章节记忆必然淹没**：唯一长程通道 story_skeleton 3000 字硬顶，>10 章远章仅采样 ~6 章×80 字（history_context_service.py:159-168）。300 章时第 1-50 章设定基本只能靠 6 个 RAG chunk 撞运气。
25. ✅ **consistency 的角色状态输入恒空**：只认 `extra["raw_state_text"]`（consistency_service.py:399-403），全仓无人写入（写入方已删）。
26. **standard 档 `[角色当前状态]`（priority=1 段）恒空**：CharacterState 只由 premium 的 memory 更新写入；A5 情感偏差同理仅 premium 生效。
27. ✅ **实体注册表近空转**：`register_from_blueprint` 零调用者；别名替换是全文无条件 `str.replace`（子串误替换风险）；`resolve_alias` 编辑距离阈值对 2-3 字中文名易误匹配。
28. **三处无上限历史注入**：大纲生成带全部摘要+全部大纲（writer.py:1087-1095,1178-1186）、批量推演带全部（:1569-1606）、AI 评审带全部摘要+串行补齐缺失摘要（:785-812）。300 章 = 6-10 万字级输入。摘要回填对所有缺摘要章节无 semaphore 并发 gather（history_context_service.py:47-69）→ 老项目首次生成 = 并发风暴。书摘要每章 finalize 重算且输入无顶（300 章=24k 字）。

### 构思/大纲
29. **批量大纲批次间只传标题**：BATCH_SIZE=25 串行（writer.py:1208-1220），后批只见前批标题无摘要（:1227-1228,1307）→ 远期批次事件线/伏笔线必然漂移；数量不核验不补齐，单批失败静默跳过 → 大纲留洞。
30. **无分卷/幕结构**：Blueprint 无 volumes 字段；500 章与 50 章共用同一套百分比阶段模板；"卷"只是事后每 10 章聚合的摘要。
31. **概念对话 token 膨胀**：历史全量回传且 assistant 存的是整个响应 JSON（含 6-8 条 options + conversation_state，novels.py:393-396,560）；参考素材零截断每轮重注；无 prompt 预算介入。
32. **先落库后校验**：novels.py:559-568，LLM 漏 `ui_control` → 500 但脏消息已入库，下轮当历史发回。`is_complete` 100% LLM 自报无后端约束。
33. ✅ **A1 revision_hint 永不消费/过期**：全仓无第二个引用点，status 恒 pending → 重复注入、过时不清、多来源互相覆盖只留最后一条。触发点是"版本生成完成"而非"定稿/选版"，选了别的版本建议就基于弃稿。
34. **outline_generation 的结构化字段全丢**：`narrative_phase`/`foreshadowing.plant/payoff`/`emotion_hook` 两条落库路径都不读；伏笔表另靠 summary 文本反推。`estimated_total_chapters` 前端恒不传 → 阶段防误收尾提示失效。

---

## 三、P2（打磨与清理，节选）

- ✅ optimizer prompt f-string `{{{{` 转义 bug → JSON 模板渲染成 `{{...}}`，推高解析失败率（pipeline_review.py:375-378）。
- 人味化规则表：替换产物本身在扣分词表里（显而易见→显然）自我抵消；12 个全知叙述词无替换条目；`"一切都"→""` 盲替换；structural 扣分穿透 40 上限（实际可达 60）；代码阈值与 editor_review.md 阈值两套标准。
- standard/premium 不跑免费的 `apply_rule_fixes`，直接烧 LLM humanize。
- 硬截断兜底从尾部砍段 → 章尾钩子（提示词铁律）被删。
- 护栏本地补丁是破坏性字符串手术（禁名全局替换"那人"、cue 删除留断句、章尾截断）。
- ✅ 死代码/死配置：`knowledge_context` 恒 None、`temp_offset` 死参数、`writing_presets.py` 第二套预设零调用、pipeline_review 三个无调用方法、PacingController 仅 three_act 可达、`stage_timings_ms` 空壳、mission_brief 默认全关注入裸 JSON、hybrid 检索默认被 settings 覆盖回 vector、`README.ai` 索引已删文件且缺 5 个新服务、`docs/novel_workflow.md` 参数过时。
- retrieve_for_generation 不过 RAG_MIN_SCORE、rerank 失败不回缩 2×top_k；hybrid `_backtrack_summaries` 语义错误（再检索≠回溯所属章）。
- 融合 DNA 降级路径输出纯套话仍以权威标签注入；参考小说库全局共享按标题去重、failed 状态每轮重试。
- 全仓无 TODO/FIXME 标注，所有退化路径均为静默 except——失败在响应里不可区分（review_summaries 无 skipped/degraded 语义）。

---

## 四、优化执行方案（分五阶段）

原则：先修「假功能/毁数据/越权」（零新架构、立竿见影），再让长程记忆真正进 prompt（长篇核心竞争力），再补构思长线结构，最后策略打磨与死代码清理。每项落地必须带回归测试（本仓既有教训：死路径正是被 `enable_six_dimension=False` 的测试掩盖的）。

### 阶段 0：安全与数据完整性热修（0.5-1 天，无需拍板）
- [x] scenes×3 / concepts×4 补 `ensure_project_owner` + 端点回归测试（#10）—— 7 端点所有权校验
- [x] 重生成不再先毁章：旧摘要/选中版本延迟到新版本落库成功后再替换（#11）—— 成功才原子替换，顺带修了既有 MissingGreenlet
- [x] `replace_blueprint` 保护：项目已有超出蓝图范围的扩写大纲或已完成章时，拒绝全删重编（409 + 前端确认弹窗），或只更新蓝图字段不动大纲（#12）—— 有创作成果才 409
- [x] `/chapters/outline` 对齐 regenerate 校验：章号范围 + 跳过已完成 + `item.get()` 容错（#15）

### 阶段 1：让已建质量机制通电（2-3 天，纯修 bug）
- [x] 六维评审：去 `user_id` 实参；反馈键改 `summary`/`issues[].description|suggestion`；阈值读 `settings.six_dimension_min_score`；解析失败返回 `degraded=True` 不再伪装 80 分；补「低分→触发 refine」真单测（#1/#2）
- [x] 叙事摘要缩进一行修（#23）
- [x] 伏笔回收：`[:10]` → 按当前章大纲相关性（embedding 相似度）预筛 top20 + 逾期加权；读侧 overdue 阈值随总章数缩放（#7）—— 实际预筛 30 条语义排序；overdue 阈值 `max(20, total//5)`（`5f16252`）
- [x] mem0 蒸馏：namespace 统一 + 补 await；若评估 mem0 价值不足则显式停用并记档（#9）—— 双 bug 已修；另锁 `mem0ai==1.0.4` + 关遥测（`a609717`）
- [x] `finish_reason=length`：写作调用截断→标记失败/重试；后处理步截断→回退原文（#14）—— `LLMResponseTruncated` + 重试升额 + 计量
- [x] combined_revision / auto_fix / enrichment / humanize 统一挂 `is_probable_chapter_plain_text` + 0.5× 长度守卫（复用现成函数）（#17）—— 重写守卫四处
- [x] optimizer `{{{{` 转义修复
- [x] `enable_temporal_state` 传入 planner_flow_config；或按 Occam 直接删时序快照死路径（#6）—— 阶段 2b 接通（`708b7e8`）：先修共享 session 并发→串行 + 五处 `_safe_rollback`，evidence_router 时序分支改补充语义后才传开关
- [x] Hubu 技能注入 category 兼容修复（skill_base 已有兼容写法，抄过来）（#8）
- [x] enrichment/consistency 显式 `timeout=180`；`_over_budget` 每步复检（#21）

### 阶段 2：长程记忆真正进 prompt（约 1 周，长篇核心）
- [x] **卷/书摘要转正**：作为独立 prompt 段（`[卷级前情]`/`[全书脉络]`，priority 2，各 800/600 tok）直接注入，不再依赖 rag_summaries 撞运气；telemetry-only 定位保留给证据评分（#4）—— 已拍板并落地，DB 直查 + 5s 降级，非 fast 档
- [x] **standard 档解锁基础记忆**：`[项目长期记忆]` 已无条件预取 → 进 standard 的 prompt_modules（成本已花，零新增调用）；CharacterState 写侧是否下放 standard（#5/#26）—— 已拍板下放：新增 `enable_state_tracking` 轻量路径（零 mem0），premium 完整路径不变（`e7f36ec`）
- [x] story_skeleton 远章采样改进：伏笔/实体关联章优先 + 卷摘要衔接，替代等步长抽样（#24）—— 伏笔章 quota-2 席 + 首尾锚点（`704df25`）
- [x] consistency 角色状态输入接通：改读 CharacterState 结构化字段而非已死的 `raw_state_text`（#25）
- [ ] revision_hint 生命周期：注入后标 consumed、大纲重写时清除、触发点挪到 select/finalize（#33）—— 🟡 **只做了一半**：大纲重写/蓝图重建即清已实现；`consumed` 标记未做，触发点仍在写侧任务（`generation_write_task_service.py:195`）
- [x] 世界蓝图段改结构化摘要注入（替代 `json.dumps` 截断成破损 JSON）—— digest 含能力/嵌套键/伏笔，按行截断
- [x] 实体注册表接通：蓝图落库时调 `register_from_blueprint`；别名替换加词边界保护（#27）—— ⚠️ 前半为**审计误判**：`_sync_blueprint_entities` 自 `5c63103` 起就在注册蓝图实体；后半已加护栏公共函数 + `resolve_alias` 短名阈值收紧（`830c978`）
- [x] 无上限历史注入治理：大纲/评审/推演三处改用「近 N 章全量 + 远章卷摘要」；摘要回填加 semaphore(3-5)；书摘要输入改增量（#28）—— 回填 cap30 + 并发 5 + 总墙钟 180s + 被跳过章走大纲兜底（`704df25`）

### 阶段 3：构思与大纲长线结构（约 1 周）
- [x] 蓝图生成异步任务化（走 Go dispatcher，同章节生成路径），根治 120s/300s 链路掐断 + 连接池占用（#16）—— `8ddee0e`，网关登记 `blueprint:generate`（15m 超时）；⚠️ **网关需重建部署才生效**，旧网关下前端仅在 400/404/网络错误时回退同步
- [x] 蓝图分两段生成：设定（世界观/角色/金手指/卷规划）与章纲分开调用，各自 max_tokens 充足；落库前数量断言（outlines≥承诺章数、伏笔≥5），不足自动补问一次（#13）—— `cc83f25`，数量断言按 1..promised **覆盖率**计（防编号偏移），补问一次仍不足则 502 零落库
- [x] 大纲批次滚动上下文：每批带前批「压缩摘要」（每章 30 字）而非仅标题；数量核验不足自动补；前端修 `estimated_total_chapters` 传参（#29/#34）—— `374a085`，滚动摘要 2000 字预算
- [x] 轻量分卷：蓝图新增 `volumes[{name, chapter_range, arc_goal, climax}]`，大纲生成按卷分批、卷内阶段模板替代全书百分比（#30）—— 已拍板做轻量版（`cc83f25`/`374a085`）
- [x] 概念对话瘦身：历史回传只取 `ai_message`/user value（存储不动）；参考素材注入加截断；`is_complete` 加最低轮次（如 ≥3）后端约束；先校验后落库（#31/#32）—— 素材 800/600/800 截断
- [ ] outline_generation 结构化字段落库：`foreshadowing.plant/payoff` 进伏笔表、`emotion_hook`/`narrative_phase` 进 outline.metadata —— ❌ **未做**（2026-07-31 实证）：prompt 已产出这三个字段，`update_or_create_outline(project_id, ch_num, title, summary)` 只落标题+摘要，字段被丢弃

### 阶段 4：策略打磨与清理（按价值取舍，穿插进行）
- [x] 多版本决策：要么 standard 开 version_count=2 实验（成本×2 需拍板），要么删 editor_review 选优死代码——不要养着 7KB 提示词不用（#3）—— 已拍板：**保留机制但不默认开**（`ai_review_service.py` 与 `editor_review.md` 保留，用户显式传 `versions>1` 时生效）
- [x] refine 后重打分、分数下降则回退（低成本对比验证）（#18）—— `56bec05`
- [ ] premium enrichment 互斥修复：optimizer 后仍短则补跑 enrichment（#19）—— ❌ **未做**（2026-07-31 实证）：`standard_post_processing_service.py:179` 在 optimizer 执行前就把 `enrichment_enabled` 算死，跑完不复检长度
- [x] polish 计费口径对齐（强开不计费 or 勾选才跑才计费）（#20）—— 已拍板「勾选才跑才计费」（`f9c756c`）：preset 不再强开、`enable_polish` 移出 `FLOW_OVERRIDE_SWITCHES`（纯积分项，free 也可购买）、付费必交付（预算不跳过）、无 `model_code` 也照收附加费
- [x] literary 分支：场景 try/except + 预算保护，或明确标记实验性（#21/#22）—— `a660679`，场景级容错 + 时间预算 + 硬约束保真 + 残章全额退款 + `degraded` 标记 + 不收润色费
- [x] 人味化规则表清理（自我抵消对、盲替换、上限穿透、双套阈值统一）；standard 先跑免费 `apply_rule_fixes` 再决定是否 LLM humanize —— `ee01560`
- [x] 硬截断保护章尾：从中部压缩或保留最后一段 —— `56bec05` `hard_trim` 重写（保开头 + 保末段钩子、牺牲中部、`max_chars` 无例外硬上限）
- [x] 死代码清理批次（writing_presets / knowledge_context / temp_offset / pipeline_review 三方法 / README.ai / novel_workflow.md）—— `f335a45`；`api/routers/README.ai` 因当时误判为二进制而漏掉，已于 2026-07-31 补齐（2 条失效条目 + 14 个未收录路由）
- [x] 静默降级治理：统一 `review_summaries` 里 skipped/degraded/failed 语义，前端可见 —— `skipped_for_budget` / `degraded` / 失败步 `applied:False` 已贯通

### 需用户拍板的商业/产品决策 —— **5 项已全部拍板（2026-07-26）**
1. ✅ 卷/书摘要转正（反转既往「telemetry-only 有意设计」的评审结论）→ **转正**，作为独立 prompt 段注入
2. ✅ standard 档是否下放 CharacterState 写入 → **下放**，走 `enable_state_tracking` 轻量路径（零 mem0），完整记忆仍 premium 独占
3. ✅ polish 计费口径 → **勾选才跑才计费**，且付费必交付
4. ✅ 多版本选优 → **保留机制但不默认开**（不做 standard 开 2 版本的成本×2 实验，也不删 `editor_review`）
5. ✅ 分卷结构改造优先级 → **做轻量版**，排进阶段 3
