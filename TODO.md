# Arboris-Novel 待办（下次继续）

> 更新于 2026-06-17（A5 落地后）。记录质量/RAG 路线图剩余项 + 小尾巴，供下次开工**直接上手、无需重新实证**。
> 架构权威见 `CLAUDE.md`；已完成项见 `git log`。

---

## 🔴 质量/RAG 路线图二阶段（剩余 1 项）

### A1 滚动细纲修订回路  ·  最高价值 · **大工程** · 需充分设计（建议专门会话）
- **现状（已实证）**：大纲只有手动 `NovelService.update_or_create_outline`（`app/services/novel_service.py:959`），仅被 `app/api/routers/writer.py:1055/1303/1364` 手动调用；**生成完成流程不自动回写/修订后续大纲**（`pipeline_orchestrator`/`generation_finalize_service`/`generation_background_task_service`/`chapter_post_processor` 均无大纲修订）。
- **切入点**：章节定稿后，根据本章「实际写出的内容」评估后续章节大纲是否需调整，自动（或建议式）修订。
- **风险**：牵动核心生成流程；自动改大纲可能偏离作者意图 —— 倾向「生成修订建议」而非「静默覆盖」。务必充分设计 + 灰度。
- **可借力 A5 的同款架构**：A5 已铺好「定稿后异步分析 → 注入后续 prompt」的降级范式（见 `EmotionDeviationService` + `TrajectoryAnalysisService.prefetch_trajectory_context`），A1 的「建议式修订」可照此模式做（自包含 + 缺数据降级 + prompt 注入/提示作者）。

---

## 🟡 小尾巴（低优先，可顺手）
- ~~**`satisfaction_design.intensity` 恒未写入**~~ **✅ 已修复（见 git log）**：`_build_emotion_points` 新增优先读 `EmotionDeviationService.build_actual_intensity_curve`（CharacterState 实际情绪峰值）作为实际强度，缺则退回 mission 规划强度（仍从无写入）、再退默认 5.0。一处改动同时修复故事形状分析（不再恒 FLAT）+ 复用 A5 数据。无 CharacterState 的非精品档自然降级为既有 5.0 行为（无回归）。
- **`backend/app/api/routers/README.ai`**：二进制文件（`file` 判 data，Read 工具拒读），仍含已删的 `analytics_enhanced` 过时条目，无法安全编辑。评估转为纯文本或重建。（注：`backend/app/services/README.ai` 是 UTF-8 文本，可用 sed 行删——A5 已用此法清掉 emotion_analyzer_enhanced 条目。）
- **remote 迁移**：GitHub 提示仓库已迁移 `leanb525/mix-ainovel` → `testdown001/mix-ainovel`。确认后执行 `git remote set-url origin git@github.com:testdown001/mix-ainovel.git`。

---

## ⚠️ 工作原则（血泪教训，务必遵守）
- **删/改/采纳路线图项前，必须亲自 `grep` 实证现状（含 `tests/`），勿信旧报告/记忆/多代理调研的「现状/缺失」描述** —— 调研的现状部分有严重幻觉。A5 本次即靠直接 grep 确认了「`satisfaction_design.intensity` 全仓无写入」「standard 档 `enable_memory=False`」「`creative_guidance` 缓存由 `novel_service:1271` 写入」三条关键事实，才定准设计。
- **对抗复审会过度索要测试**：A5 复审 27 findings 里多数是「再加测试」，真正代码 bug 仅 2 个（方向判定离群、规划点 0.0 兜底）。按价值取舍，勿无脑全采纳。
- **删代码前必查 `tests/` 引用**（历史上 `novel_bench_service` 差点被误删，实有回归测试在用）。
- 提交用显式 pathspec 且 `-m` 放在 `--` **之前**（`git commit -m "msg" -- <paths>`），避免卷入暂存区其他改动（如 `.claude/settings.local.json`）。
- 项目未上线，改动直接提交 main。

---

## ✅ 已完成（已提交 main，详见 git log）
| 提交 | 主题 |
|------|------|
| `00619a1` | 部署：前端静态服务 + 两栈装配 + HTTPS + 文档 |
| `9d677c1` | 测试：支付宝/微信回调验签 |
| `9a7a65b` | CI：纳入 go test |
| `3bf3e0b` | 测试：前端订阅推导 |
| `584d5bb` | 清理：死代码（净删 1140 行） |
| `9e8de95` | 质量：B4 伏笔语义化 |
| `da5df97` | **质量：A5 情感曲线偏差校正**（规划曲线 vs CharacterState 实际情绪，偏差注入 prompt；18 测试，全量 316 passed） |
| `60b21a7` | 清理：删零引用 emotion_analyzer_enhanced + README.ai 索引 |
| _本次_ | 质量：故事形状分析改读 CharacterState 实际强度（修 `satisfaction_design.intensity` 恒未写入 → FLAT 退化；复用 A5 数据；321 passed） |
