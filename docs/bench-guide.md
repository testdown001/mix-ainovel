# 评估基线（bench）使用指南

回答一个问题：**每个质量开关的真实贡献是多少？**

做法：在固定的基准场景（夹具）上，以不同管线配置生成同一章、机械评分 + LLM 评审打分、
横向对比（含消融），产出可复查的报告。这是「评估驱动开发」的基础设施——改管线前先跑基线，
改完再跑，用数字说话。

- 代码：`backend/app/services/bench/`（fixtures / configs / scoring / runner / report）
- CLI：`backend/run_bench.py`
- 夹具：`backend/bench_fixtures/*.json`
- 评审提示词：`backend/prompts/bench_judge.md`（六维绝对评分）、`bench_judge_pair.md`（A/B 对比）
- 报告：`backend/storage/bench/reports/<run_tag>/`

## 前置条件

bench 跑在**开发库**上（`AsyncSessionLocal` 读 `backend/.env`），LLM 走 SystemConfig
里已配置的真实通道（后台「接口管理」）：

```bash
cd backend && source .venv/bin/activate
python run_bench.py list            # 列出夹具与内置配置（顺带验证 .env 可加载）
```

- `.env` 缺 `SECRET_KEY` / 连不上库 / SystemConfig 没配 `llm.api_key`（env
  `LLM_API_KEY` 也可，与 LLMService 的真实解析一致），CLI 都会给出人话报错。
- 报 `Unknown column ...` 说明开发库 schema 陈旧：先把后端启动一次
  （`uvicorn app.main:app` 或 `start-dev.sh`，`init_db()` 启动修复会补列）再跑 bench。
- 配了 `llm_grader.*` 通道则评审走 grader（便宜模型省钱），否则自动降级默认通道。
- 所有 bench 项目挂在专用用户 `bench@local` 名下，标题带 `[run_tag]` 前缀，随时可清理。
- **播种含先行章向量入库（best-effort）**：Qdrant 与 embedding 通道可用时，先行章
  正文/摘要会写入向量库，目标章生成才有真实 RAG 检索。任一不可用时播种照常完成，
  但报告头部会显著标注「本 run 向量层不可用，RAG 相关配置差异无效」。
- **时间预算默认关闭**：bench 测的是各配置的质量上限，生产的
  `GENERATION_TIME_BUDGET_SEC=540` 预算降级会按耗时随机砍后处理步、把配置差异
  污染成预算运气差异——CLI 默认将其置 0（已显式导出该 env 则不覆盖）；要保留
  生产行为加 `--respect-time-budget`。即便如此，任一样本被预算砍步都会在报告
  cell 详情与消融表备注里警示「数字不可信」。

## 第零步：零成本冒烟

```bash
python run_bench.py run --scenarios demo_xuanhuan --configs standard --dry-run --cleanup
```

`--dry-run` 桩掉全部 LLM 出口（含评审），用假正文全链路走通播种→生成→评分→报告→清理，
零成本。改动 bench 代码或管线后先冒烟再花钱。

## 第一步：拿基线（standard vs premium vs full）

```bash
python run_bench.py run --scenarios demo_xuanhuan \
  --configs standard,premium,full --run-tag baseline-01 --yes
```

内置配置：
- `standard` / `premium`：两档 preset 原样（回答「档位差异值多少钱」）；
- `full`：premium 底座 + 显式开满全部 13 个可覆写质量开关（消融的基准）。

跑之前 CLI 会打印成本预估（cell 数 × 每 cell 调用量级 + 评审调用数），需要 `--yes`
或交互确认。默认 `--baseline standard`：premium/full 的每个样本都会与 standard 的
正文做 A/B 对比（每对调用 2 次、互换位置消除位置偏差，两轮不一致记平）。

## 第二步：对可疑开关做消融

读完基线报告后，对 delta 最可疑的开关做消融（full 减一开关）：

```bash
python run_bench.py run --scenarios demo_xuanhuan --configs full \
  --ablate optimizer,polish,rag --baseline full --run-tag ablate-01 --yes
```

- `--ablate` 逗号分隔开关名（可省 `enable_` 前缀），自动生成 `full-minus-X` 变体并补 `full`；
- **跑消融务必 `--baseline full`**：这样成对对比直接就是 full vs full-minus-X，
  报告消融表里的「变体胜负」才回答「关掉 X 输给 full 吗」。
- **消融 `rag` 前先确认 Qdrant 与 embedding 通道可用**：向量层不可用时 RAG 检索
  空转，`full-minus-rag` 与 full 的 Δ 恒 ≈ 0（假阴性）。报告头部有「向量层不可用」
  标记，看到它就别用该 run 下 RAG 相关结论。

**⚠️ 开关交互（`configs.py` KNOWN_INTERACTIONS 注册表，已实证）**：
- `full-minus-enrichment` 是 **no-op**：optimizer 开启时 enrichment 在后处理里被压制
  （`enrichment_enabled = enable_enrichment and not optimizer_enabled`），该变体与
  full 管线一字不差。runner 直接**跳过生成**（省成本），消融表标「与基准管线等价，未跑」。
  要单独测 enrichment，用不开 optimizer 的底座自建配置。
- `full-minus-optimizer` **语义变了**：关掉 optimizer 会反向激活独立 polish/enrichment
  步——该行回答的是「组合步 vs 独立步」而非「有无 optimizer」，消融表备注列有注记。
- 新实证到交互在 `KNOWN_INTERACTIONS` 登记即可，报告自动标注。

**⚠️ 消融边界（重要局限）**：只有 `PipelineConfigService.resolve_config` 的 flow_config
覆写白名单内的开关可消融（`run_bench.py list` 会列出，当前 13 个）。preset 驱动键
（`enable_memory` / `enable_six_dimension` / `enable_self_critique` 等）经 flow_config
覆写会被**静默忽略**，无法单独消融——它们的贡献只能通过 standard vs premium 的档位
对比近似回答。白名单收缩时 `tests/test_bench_core.py` 的防漂移断言会翻红。

## 第三步：冻结真实项目做夹具

demo 夹具是手工小场景，真实基准应从真实项目冻结：

```bash
python run_bench.py freeze --project-id <项目UUID> --upto 3 --target 4 \
  --scenario-id my_novel_ch4 --out bench_fixtures/my_novel_ch4.json \
  --must-include 丹阁,焚寂
```

- `--upto N`：取前 N 个**已完成章**（selected_version_id 非空）的正文+摘要做先行章；
  `--target M`：基准要生成的目标章号（需在项目大纲范围内）。
- `must_include` 无法从项目推断：对照目标章大纲人工补 2-3 个剧情关键词，
  否则机械评分的必含词维度无据可依。
- 冻结产物是自包含 JSON，可进 git；每次跑批都从它播种全新项目副本
  （每个 场景×配置×样本 独立播种，绝不共享——生成会写记忆/伏笔/实体状态）。

## 读报告

`backend/storage/bench/reports/<run_tag>/report.md`（+ `report.json` 机器可读、
`chapters/*.txt` 正文存档——**数字存疑时先读正文**）：

- **头部**：向量层不可用警告（如有）+ **环境快照**（默认 LLM 模型/host、grader
  是否配置、writer_chapter_versions、fast/ultra_fast 模式、时间预算生效值、
  rag_retrieval_mode、reranker、db_provider）——**对比两次 run 前先比对快照**，
  环境不同的数字不可比。
- **① 配置 × 场景总表**：六维均分（沉浸/节奏/钩子/人物/文笔/契合，1-10）、机械分
  （长度/必含词/verification，0-100）、人味分†、4-gram 重复度‡、时长、对基线胜负。
  † 人味分与管线内 humanize 步同尺（`HumanizationService.scan`），非独立指标；
  ‡ 重复度按正文前 3000 字定长口径计算（不足取全量），消除长度伪影。
- **② 消融差异表**：Δ = full − 变体，**正值 = 该开关有正贡献**；|Δ| 达阈值
  （六维 0.5 / 机械 3.0）标 ▲（正贡献显著）/ ▼（负贡献显著，关掉反而更好——重点复查）。
  Δ时长为正表示该开关的耗时代价。多场景时附均值行。**备注列**呈现 no_op（未跑）/
  语义变化注记 / 时间预算砍步警告。
- **③ 每 cell 详情**：逐样本分数 + 评审一句话理由摘录 + A/B 对比理由 +
  预算砍步/收尾任务超时警示。
- **④ 失败 cell 清单**：生成炸掉/评审失败的样本，显式列出（绝不静默丢 cell）。

判读原则：
- 单次生成方差不小，**Δ < 0.5 的六维差异当噪声看**；要下结论先
  `--chapters-per-cell 3` 平滑（每样本独立播种，成本 ×3）。
- 成对对比两轮不一致记 tie 是特性不是缺陷——说明差距小于评审模型的位置偏差。
- 单场景容易过拟合：重要结论至少跑 2-3 个不同题材/阶段的夹具再下。
- LLM 评审自身有偏好（偏长文、偏华丽），机械分与评审分方向矛盾时优先读正文。

## 成本量级

每样本 LLM 调用粗估：standard ≈ 10 次，premium ≈ 14 次，full ≈ 14+13 次；评审每样本
1 次绝对评分 + 非基线 2 次对比。一次「1 场景 × (full + 3 消融) × 1 样本」≈ 120+ 次
生成调用——**先用 `--dry-run` 冒烟、`list` 看预估，确认了再 `--yes`**。评审建议配置
独立 `llm_grader.*` 通道用便宜模型。

## 清理

```bash
python run_bench.py run ... --cleanup            # 跑完立即按 run_tag 清理
python run_bench.py cleanup --run-tag <标签>      # 事后按批次清理（中断后也用它）
python run_bench.py cleanup --all-bench --yes    # 清空 bench 用户全部项目（需 --yes）
```

不加 `--cleanup` 时 bench 项目保留在库中（方便进后台肉眼复查生成结果），标题
`[run_tag] 场景id`、属主 `bench@local`。清理是逐表显式删除（不依赖外键级联），
覆盖无外键约束的 `chapter_reviews` / `writing_archives`，并 best-effort 删除
Qdrant 里该项目的章节向量（Qdrant 不可用时仅 warning，不阻断）。

## 已知局限

- **白名单外开关不可消融**（见上），preset 驱动键只能档位对比近似。
- **单次生成方差**：`chapters_per_cell=1` 的 delta 只是线索不是结论。
- 评审用同一 LLM 家族给自己打分存在同源偏好；重要对比建议 grader 配置异源模型。
- **人味分是循环论证**：它与生成管线内 humanize 步用同一把尺
  （`HumanizationService.scan`），管线按这把尺改文后再用它打分必然偏高——
  只能当「AI 腔检测器」参考，不能佐证 humanization 相关开关的贡献。
- **重复度是定长口径**：只看正文前 3000 字（不足取全量）——是为消除长度伪影
  刻意为之，长文 3000 字之后的重复不在此指标覆盖内，存疑读正文。
- **RAG 消融依赖向量层**：Qdrant/embedding 不可用时 `minus-rag` 的 Δ≈0 是假阴性，
  以报告头部标记为准。
- bench 用户不做积分计费（走同步管线路径，不经 task_worker 扣费口），成本就是 LLM 调用本身。
- `fast` 档不在内置配置里（它是免费兜底档，不参与质量对比）；需要时可在
  `configs.py` 里加 `BenchConfig(name="fast", preset="fast")`。
