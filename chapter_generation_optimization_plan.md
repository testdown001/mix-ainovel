# 章节生成精简优化方案

> 参考项目：[inliver233/Ai-Novel](https://github.com/inliver233/Ai-Novel)
> 目标：将章节生成从 8-10 分钟降低到 30-90 秒

---

## 一、现状诊断：为什么要 8-10 分钟？

通过对 `pipeline_orchestrator.py`（2000+行）的完整分析，当前 **literary 模式** 的一次章节生成涉及的 LLM 调用如下：

| # | 步骤 | LLM 调用数 | 是否串行 |
|---|------|-----------|---------|
| 1 | 章节导演脚本 (chapter_mission) | 1 | 串行 |
| 2 | RAG 检索规划 (_plan_retrieval) | 1 | 串行 |
| 3 | 检索关键词生成 (fallback) | 0-1 | 串行 |
| 4 | 查询反思扩展 (_reflect_and_expand) | 0-1 | 串行 |
| 5 | 知识过滤 (_filter_knowledge) | 1 | 串行 |
| 6 | 声纹样本生成 (_generate_voice_samples) | 1 | 串行 |
| 7 | 正文生成 (scene_by_scene 模式 3 场景) | **3** | 串行 |
| 8 | 护栏修复重写 (guardrail rewrite) | 0-1 | 串行 |
| 9 | 一致性检查 (consistency) | 1 | 串行 |
| 10 | 综合优化 (optimizer) | 1 | 串行 |
| 11 | 文学润色 (polish) | 0-1 | 串行 |
| 12 | 扩写补字 (enrichment) | 0-2 | 串行 |
| 13 | 密度压缩 (density_compression) | 0-1 | 串行 |
| 14 | 质量检测 (quality_detection) | 1 | 串行 |
| 15 | 散文雕琢 (prose_sculpting) | 0-1 | 串行 |
| 16 | 黄金段落 (golden_paragraph) | 0-1 | 串行 |
| 17 | 人性化 (humanization) | 0-1 | 串行 |
| 18 | 反幻觉检查 (anti_hallucination) | 0-1 | 串行 |
| 19 | 字数超限压缩 (_compress_overlength) | 0-2 | 串行 |
| 20 | 章节摘要生成 | 1 | 串行 |
| | **合计** | **~15-22 次** | **全部串行** |

**根本问题**：每次 LLM 调用平均 20-40 秒，15-22 次串行调用 = 5-15 分钟。

---

## 二、参考项目 (Ai-Novel) 的做法

Ai-Novel 的章节生成管道极其简洁：

| # | 步骤 | LLM 调用数 |
|---|------|-----------|
| 1 | [可选] 章节规划 (plan) | 0-1 |
| 2 | 记忆检索 (无 LLM，纯数据库查询 + 向量匹配) | **0** |
| 3 | 章节正文生成 (支持流式) | **1** |
| 4 | [可选] 后期编辑 (post-edit) | 0-1 |
| 5 | [可选] 内容优化 (content-optimize) | 0-1 |
| | **合计** | **1-3 次** |

### 核心理念差异

1. **记忆检索零 LLM 调用**：Ai-Novel 用世界书关键词触发（纯字符串/拼音匹配）+ 向量相似度搜索代替 LLM 生成检索关键词。不做 LLM 过滤，而是用预算管理裁剪。

2. **一次生成代替多轮打磨**：正文只用 1 次 LLM 调用完成，通过精心设计的 Prompt Block 系统保证质量，而不是生成后用 N 次 LLM 调用修补。

3. **Prompt 预算管理代替后处理**：27 个 Prompt Block 按优先级注入（must > important > optional），超 Token 时按优先级丢弃，而非先全部塞进去再用 LLM 压缩。

4. **流式输出**：用户在生成过程中就能看到实时文本，体验上几乎零等待。

---

## 三、执行方案

### 方案概要：从 "生成 + N 轮打磨" 转向 "一次高质量生成"

```
当前：  Mission → RAG(3 LLM) → 生成(3 LLM) → 打磨(8-12 LLM) = 15-22 LLM 调用
目标：  上下文组装(0 LLM) → 生成(1 LLM) → [可选]润色(0-1 LLM) = 1-2 LLM 调用
```

### 第 1 步：消除 RAG 阶段的 LLM 调用

**砍掉 4 个 LLM 调用**：`_plan_retrieval`、`_generate_search_queries`、`_reflect_and_expand`、`_filter_knowledge`

**替代方案**：
- 检索关键词：直接从 `ChapterBlueprint` 的 `chapter_focus` + `brief_summary` 提取关键词（字符串分词，无需 LLM）
- 检索结果过滤：按向量相似度分数截断（score > 0.6），按 Token 预算裁剪，不做 LLM 分类
- 参考 Ai-Novel 的世界书触发机制：基于关键词匹配自动注入相关设定

### 第 2 步：取消 scene_by_scene 分场景生成

**砍掉 2 个额外 LLM 调用**（3 场景→1 次调用）

**替代方案**：
- 将场景列表作为 Prompt 的一部分注入（参考 Ai-Novel 的 chapter_info block），让 LLM 一次性生成完整章节
- 在 Prompt 中用 Scene/Sequel 结构指导（Ai-Novel 已验证可行），而非拆分成多次调用

### 第 3 步：合并/删除后处理流水线

当前 literary 模式的后处理链有 **8-12 个独立 LLM 调用**，应大幅精简：

| 步骤 | 处理 | 理由 |
|------|------|------|
| optimizer (综合优化) | **删除** | 将优化要求嵌入生成 Prompt |
| polish (润色) | **保留，可选** | 作为唯一的后处理步骤 |
| enrichment (扩写) | **删除** | 通过 Prompt 中的字数约束一次到位 |
| density_compression | **删除** | 通过 max_tokens 控制物理长度 |
| prose_sculpting | **删除** | 将散文技巧写入系统 Prompt |
| golden_paragraph | **删除** | 将黄金段落要求写入 Prompt |
| humanization | **删除** | 将人性化指令写入 Prompt |
| quality_detection | **保留，异步** | 不阻塞返回，异步执行并存入 metadata |
| consistency | **删除** | 通过护栏本地规则检查代替 LLM |
| anti_hallucination | **保留，本地化** | 用 EntityRegistry 的正则匹配代替 LLM |
| _compress_overlength | **删除** | 用 max_tokens 硬限制 |

### 第 4 步：取消导演脚本生成

**砍掉 1 个 LLM 调用**

**替代方案**：
- `chapter_mission` 中的信息（场景列表、word_budget、macro_beat 等）从 `ChapterBlueprint` 中直接构建
- 温度、POV 等信息已经存在于蓝图中，不需要额外 LLM 推理

### 第 5 步：取消声纹样本生成

**砍掉 1 个 LLM 调用**

**替代方案**：
- 将角色信息直接注入 Prompt（参考 Ai-Novel 的 character_cards block），让写作 LLM 自行把握角色语气

### 第 6 步：增加流式输出支持

参考 Ai-Novel 的 SSE 流式生成：
- 正文生成阶段使用流式返回
- 前端实时显示生成文本
- 用户感知等待大幅降低

### 第 7 步：引入 Prompt 预算管理

参考 Ai-Novel 的 Block 优先级系统：
- `must`：系统角色 + 章节要求 + 输出格式（必须保留）
- `important`：前文摘要 + 蓝图约束 + 写作风格（尽量保留）
- `optional`：RAG 检索结果 + 角色卡 + 世界观（Token 不够时可裁剪）

这样可以避免 Prompt 超限导致的内容丢失或质量下降。

---

## 四、优化后的管道

```
新管道 (fast 模式):
┌─────────────────────────────────┐
│ 1. 上下文组装 (0 LLM)           │
│    ├─ 从 Blueprint 提取章节约束  │
│    ├─ 前文摘要 (DB 查询)         │
│    ├─ 向量检索 (embedding 查询)  │
│    ├─ 角色/世界观注入            │
│    └─ Prompt 预算裁剪            │
├─────────────────────────────────┤
│ 2. 章节生成 (1 LLM)             │ ← 流式返回
│    ├─ 精心设计的系统 Prompt       │
│    ├─ 包含所有写作约束           │
│    └─ max_tokens 硬控字数        │
├─────────────────────────────────┤
│ 3. 本地护栏检查 (0 LLM)         │
│    ├─ 禁止角色检查 (正则)        │
│    ├─ POV 一致性 (规则)          │
│    └─ 实体幻觉检查 (字典匹配)    │
├─────────────────────────────────┤
│ 4. [可选] 润色 (0-1 LLM)        │ ← 用户可关闭
├─────────────────────────────────┤
│ 5. 异步后台任务 (不阻塞返回)     │
│    ├─ 向量化存储                 │
│    ├─ 质量检测                   │
│    └─ 摘要生成                   │
└─────────────────────────────────┘

LLM 调用总计: 1-2 次 (vs 当前 15-22 次)
预计耗时: 30-90 秒 (vs 当前 8-10 分钟)
```

---

## 五、优点总结

| 维度 | 当前 | 优化后 |
|------|------|--------|
| **LLM 调用次数** | 15-22 次 | 1-2 次 |
| **生成耗时** | 8-10 分钟 | 30-90 秒 |
| **API 费用** | ~15-22x 单次调用成本 | ~1-2x 单次调用成本 |
| **用户体验** | 长时间空白等待 | 流式实时看到文字 |
| **代码复杂度** | pipeline_orchestrator.py 2000+ 行 | 预计 500-800 行 |
| **PipelineConfig 开关** | 30+ 个 boolean 开关 | 5-8 个核心开关 |
| **可维护性** | 每加一个后处理步骤要改很多地方 | 只需调整 Prompt 模板 |
| **质量保障方式** | 靠 N 轮 LLM 修补 | 靠 Prompt 工程一次到位 |

**核心原则**："把质量控制从 runtime LLM 调用转移到 Prompt 工程中"。通过更好的 Prompt 设计（参考 Ai-Novel 的 27 个模板 Block），在一次调用中就达到高质量输出，而不是先粗糙生成再多轮修补。

---

## 六、风险和注意事项

1. **质量可能暂时下降**：取消后处理链后，初期生成质量依赖 Prompt 调优，需要迭代测试
2. **需要重新设计 writing.md Prompt**：当前 Prompt 假设有后处理兜底，精简后需要将优化指令融入生成 Prompt
3. **保留回退能力**：建议通过 preset 机制保留 `literary` 模式作为回退，新增 `fast` preset 作为精简管道
4. **渐进式推进**：建议先实现 `fast` preset，验证效果后再考虑是否替换默认模式

---

## 七、实施路径建议

```
Phase 1: 新增 fast preset (不影响现有功能)
  ├─ 在 PipelineConfig 中新增 fast preset 定义
  ├─ 实现精简管道的 generate_chapter_fast() 方法
  ├─ 设计新的 writing_fast.md Prompt 模板
  └─ 前端增加模式选择开关

Phase 2: RAG 检索优化
  ├─ 实现无 LLM 的关键词提取
  ├─ 实现基于分数截断的检索结果过滤
  └─ 引入 Prompt 预算管理

Phase 3: 流式输出
  ├─ 后端 SSE 流式接口
  ├─ 前端实时文本显示
  └─ 错误处理和重试

Phase 4: 质量调优
  ├─ Prompt 模板迭代测试
  ├─ 对比 fast vs literary 的输出质量
  └─ 根据反馈调整参数
```
