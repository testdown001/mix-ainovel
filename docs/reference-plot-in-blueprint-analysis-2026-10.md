# 参考小说的剧情分析在蓝图阶段到底用上了多少

- 日期：2026-10-23，代码基线 `d547222`
- 方法：读代码调用链 + 查生产库（`reference_novels` 4 本 ready、2 本 failed；`novel_projects` 1 个绑定参考的项目）
- 结论先行：**参考小说的剧情分析在蓝图阶段基本没有起作用**。不是提示词写得不够，是三层都断了：产出的剧情结构信息很薄且不稳定；蓝图只消费其中最薄的一块；生产数据里这一块恰好全空。

## 一、蓝图阶段实际拿到的参考是什么

蓝图设定段、章纲段、以及新加的故事骨架，三处都只调 `_build_structure_reference`（`blueprint_generation_service.py:77`），它拼两样东西：

| 来源 | 内容 | 生产实际值 |
| --- | --- | --- |
| `project_contract` → FusionDNA | 组合逻辑、统一叙事声音、各书分工（每条压到 95/75 字）、读者循环五要素、节奏/对白/场景一句话 | 唯一绑定参考的项目 `fusion_dna` 为 NULL → 走 `fallback_dna`，内容是通用占位句（「先让读者在意人物想保住什么」） |
| `format_structure_for_blueprint` → `beat_library.structure` | `volume_rhythm` / `conflict_escalation` / `hook_pattern` 三个字段 | **4 本 ready 参考书这三个字段全部为空字符串** → 恒为空串 |

更糟的是，那个项目绑定的参考书（渔猎八一）状态是 `failed`，`load_project_reference_novels` 只返回 ready 的书，所以这个项目的蓝图实际收到的参考 = **什么都没有**，而前端没有任何提示。

参考小说真正有剧情含量的产物，蓝图一个都没读：

| 产物 | 剧情含量 | 谁在用 |
| --- | --- | --- |
| `outline_content` | 三段剧情大纲 + 人物表 + 主线冲突与节奏点（id=7 示例约 900 字，质量尚可） | 只进**概念对话**（`format_for_concept_prompt`） |
| `beat_library.beats` | 情境→铺垫/转折/兑现/翻车点，这是「剧情思考」的最小单元 | 只在**正文生成**按章情境向量检索 top-3；概念对话给一个索引 |
| `memory_card` | `pacing_traits`（「小案 5-10 章结，大案分卷写，每 2-3 章有突破」）、`main_conflict_pattern`、`payoff_rhythm` | 只在正文生成字段级注入；蓝图不读 |

也就是说：章纲段要排 50 章，参考书里最接近「怎么排章」的信息（节奏特点、桥段的铺垫链、三段大纲）一条都没给它。

## 二、产出侧：分析本身的剧情结构信息很薄

1. **输入量**。每个维度一次搜索型模型调用，`max_tokens=2000`（约 1500 字），五个维度合计约 7500 字描述一本几百万字的书。`plot` 维度的 focus 写的是「各卷/各阶段的核心目标与结局、关键转折点位置」，拿回来的实际是百科式三段：开篇立威 / 悬案攻坚 / 扫黑博弈。
2. **抽取目标本身不是卷级结构**。`reference_outline_extraction.md` 要求的就是「三段剧情大纲（每段 40-80 字）」，设计上就没打算产出分卷。`BeatStructure` 三个字段倒是想要分卷节奏，但它挂在桥段抽取下面，检索维度 `beats/pacing/plot` 里没有一个在找「分卷 / 卷名 / 目录 / 每卷多少章」，模型拿不到依据就留空——4 本全空不是偶然。
3. **桥段数量不足**。要求 8-15 条，实际 2 / 8 / 5 / 5。
4. **稳定性**。`analyze()` 五路抽取用 `asyncio.gather` 不带 `return_exceptions`，任一路抛异常整本标 `failed`，已成功的大纲和桥段一起丢掉。生产两条 failed：id=9 搜索通道 502；id=10 是 `MemoryCard.commercial_data` 模型返回字符串「未提及」而 schema 要 dict，一个字段类型问题废掉整本书。
5. **FusionDNA 没生成**。它是后台任务（`_background_generate_fusion_dna`），生产那个项目从未成功，蓝图永远在用 fallback。

## 三、改进方案（按性价比排序）

### A. 先止血：分析不再整本失败（半天）
- `MemoryCard.commercial_data` 改为 `Any` 或加 validator 把字符串收成 `{"note": ...}`；其余非核心字段同样放宽。
- `analyze()` 的 gather 加 `return_exceptions=True`，单路失败只记 warning，成功的产物照常落库，状态标 `ready`（或 `partial`），前端显示哪一路缺失。
- 修完后对 id=9、10 重新分析。

### B. 产出一份真正的「剧情结构」（1-2 天）——这是核心
新增产物 `plot_structure`（JSON，`reference_novels` 加一列或塞进 `beat_library.structure` 扩展），字段与故事骨架同构：
- `stages[]`：阶段/卷名、起止**比例**（不是章号）、本阶段主角目标、主要对手量级、阶段末高潮事件类型、主角状态变化
- `opening`：前三章做法（异常点 / 首个钩子 / 首个兑现在第几章）
- `turning_points[]`：全书转折点及其位置比例
- `escalation_axis`：升级沿哪条轴（境界 / 地图 / 势力 / 身份）
- `ending_shape`：结局形态
- 保留 `hook_pattern`

输入侧新增一个检索维度 `structure`：query 用「目录 分卷 卷名 每卷 章节数 阶段」。起点、番茄的书**卷名和目录是公开且精确的**，比书评里的印象可靠得多，也是最便宜的分卷信号。`plot` 维度 `max_tokens` 提到 4000。

### C. 蓝图消费改造（1-2 天）
1. **故事骨架生成**注入参考书的 `plot_structure`：这是「剧情参考」最该生效的地方——倒推各卷高潮时，给它看参考书的升级轴、各阶段高潮类型、转折点位置。骨架的 `climaxes` 和参考的 `stages` 同构，可以做「参考书骨架 vs 本书骨架」对照并要求差异化。
2. **章纲段每批检索桥段**：复用 `ReferenceBeatService.select_beats_for_chapter` 的向量匹配，用「本卷目标 + 本批前置条件 + 本批高潮」做 query，取 top-3 桥段的 setup/turn/payoff 注入批任务。正文已经这么做了，章纲没有。
3. 章纲段摘要加入 `memory_card` 的 `pacing_traits` / `main_conflict_pattern` / `payoff_rhythm` 三个字段（已有 `format_memory_card_for_prompt`，截取即可）。
4. FusionDNA 缺失时不要用通用占位句充数：`fallback_dna` 的文本对蓝图没有信息量，有 `plot_structure` 就用它，没有就什么都不注入，并在日志里说清。

### D. 可见性（半天）
- 确认页和蓝图页显示「参考了《X》的：分卷节奏 / 桥段 N 条 / 节奏特点」，用的是哪一项一目了然。
- 项目绑定的参考书为 `failed` 或分析未完成时，确认页给出警告和「重新分析」入口，而不是静默跳过。

### 不建议
- 继续加大 `outline_content` 字数。三段百科大纲再长也不是分卷结构。
- 让模型「在章纲里参考原书剧情」。没有结构化的输入，这句话只会得到形容词。

## 四、验收
- 生产 4 本 ready 书重新分析后 `plot_structure.stages` 非空率 100%，桥段 ≥ 8 条的比例。
- 绑定参考的项目生成蓝图时，`app.log` 里「蓝图章纲结构参考注入」长度 > 0。
- 人读：拿一本参考书的 `stages` 和本书骨架的 `climaxes` 并排，判断升级节奏是否被借到、剧情是否被照搬。
