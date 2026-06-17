# A1 滚动细纲修订回路 · 设计方案

> 状态：**设计已定稿（2026-06-17），待实现**。决策已拍板，可直接进入编码。
> 架构权威见 `CLAUDE.md`；本文件是 A1 单项的实现蓝图。

## 1. 目标与意义

大纲（`ChapterOutline.summary`）是每章生成的**直接指令源**——`prompt_assembly_service.py:262` 把 `outline_summary` 作为 `[当前章节目标]` 注入 prompt。但大纲是「一次性规划」产物，AI 实际写出的内容会逐章偏离它（角色提前和解、伏笔提前埋、冲突被写淡），而当前**没有任何回路把「实际写了什么」反馈去修订「后面还没写的大纲」**（已实证：`generation_finalize_service` / `generation_background_task_service` / `chapter_post_processor` 均不碰大纲）。

后果是长篇连载的**叙事漂移 / 复利误差**：越往后大纲与真实故事鸿沟越大，几十万字后大纲失效、章节质量断崖。A1 是路线图里唯一直接对抗这一顽疾的**全局骨架自我修复**机制，是「长篇不崩」旗舰卖点的地基。

## 2. 已拍板决策

| 决策点 | 结论 |
|--------|------|
| 会员档位 | **flagship 旗舰独占**（与 `enable_memory`/CharacterState 同档；LLM 成本 + 旗舰卖点） |
| MVP 范围 | **纯后端注入提示**，本期不动前端（无采纳/忽略 UI） |
| 作用方式 | **仅注入提示，绝不自动改写 `summary`**（作者意图保护，防 AI 把故意反转当漂移纠掉） |
| review 范围 K | 后续 **3** 章（可经 SystemConfig 调） |
| 灰度开关 | SystemConfig `quality.outline_revision_enabled`，**默认关**，灰度放量 |

它**不是 A5 的翻版**（A5 是 read-only 比对），而是**伏笔流的同构体**：`提取 → 存 → 后续注入`，落点从「伏笔表」换成「大纲」。

## 3. 数据模型 —— 零新增表

复用 `ChapterOutline.metadata_`（JSON，`app/models/novel.py:162`，已存导演脚本/节拍）。新增约定 key，写在**被建议的目标章节**上：

```jsonc
// chapter_outlines[chapter_number = 目标章].metadata.revision_hint
{
  "revision_hint": {
    "source_chapter": 5,                 // 触发本建议的定稿章号
    "severity": "high",                  // high/medium/low
    "reason": "第5章中A与B已提前和解，原大纲『冲突升级』与前文矛盾",
    "suggestion": "改为：合作中暴露价值观分歧，埋二次冲突的种子",
    "status": "pending"                  // pending/accepted/dismissed（预留给后续前端，本期恒 pending）
  }
}
```

- 只保留**最新一条**（同目标章按 `source_chapter` 覆盖），不堆积。
- ⚠️ 写时必须先 `get_outline` 读出现有 metadata **再 merge**：`update_or_create_outline` 传 dict 时是整体替换（`novel_service.py:1005-1006`），直接传会覆盖导演脚本。

## 4. 写侧（定稿后异步任务，照搬伏笔链）

挂载路径（与 `run_foreshadowing_extraction` 完全并列）：
```
GenerationFinalizeService.schedule_followups        # generation_finalize_service.py:92-101 旁新增分支
  └─ if enable_outline_revision:                    # 新触发条件，与 enable_memory 同源
       asyncio.create_task( run_outline_revision )
          └─ GenerationBackgroundTaskService.run_outline_revision   # 门面转发（generation_background_task_service.py）
               └─ GenerationWriteTaskService.run_outline_revision   # 独立 AsyncSessionLocal + 双层 try/except 降级
                    └─ OutlineRevisionService.review_downstream(...) # 新服务（核心）
```

`OutlineRevisionService.review_downstream(project_id, finalized_chapter_number, chapter_content, ...)`：
1. 读定稿章 outline + 后续 K 章 outline（`novel_service.get_outline`）；缺后续大纲 → 降级返回。
2. 用新 prompt 模板 `prompts/outline_revision.md` + `generate_structured`（稳定 schema：`[{chapter_number, severity, reason, suggestion}]`）让 LLM 判断哪几章因本章实际走向而过时。
3. 逐条 **merge** 写入目标章 `outline.metadata.revision_hint`（先读后并，见 §3 警告）。

写任务降级范式照 `generation_write_task_service.py:102-138`：独立 session、内层 `rollback()+raise`、外层 `logger.exception` 吞掉，**绝不影响主生成**。

## 5. 读侧（生成时注入，复用 A5 prefetch 管线骨架）

```
generation_prefetch_service.py:140 旁   →  新建 outline_revision_task = OutlineRevisionService.build_revision_brief(project_id, chapter_number)
generation_evidence_stage_service.py:75 旁  →  await prefetch_tasks.outline_revision_task → outline_revision_brief
generation_prompt_stage_service.py:114 旁   →  注入新段 [大纲修订提示]（与 trajectory_context 并列透传）
```

`build_revision_brief(project_id, chapter_number)`：读**本章** outline.metadata.revision_hint（status=pending）→ 格式化提示文本，文案强调「原规划可能已过时，**参考**建议但以全文连贯为先」。无建议 → None，不注入（绝大多数章节零噪音）。

> 注：读侧只读不写、不改 summary；建议的「消费」纯粹是 prompt 注入。

## 6. 档位门控（feature_gating 单一真相源，严禁硬编码档位）

1. `core/feature_gating.py` `CAPABILITIES` 新增：
   `Capability("outline_revision", "滚动细纲修订", "章节定稿后据实际内容修订后续大纲建议，对抗长篇叙事漂移。", "flagship")`
   —— 自动驱动门控 + 定价页展示，永不漂移。
2. 写侧触发条件 `config.enable_outline_revision`：在 `pipeline_config_service.py` 新增字段（默认 False），在 premium 块（`:171` 附近，与 `enable_memory = True` 同处）置 True；再叠加 SystemConfig `quality.outline_revision_enabled` 总开关（默认关）。
3. `generation_policy_service.py:142` stage_flags 加 `"outline_revision": config.enable_outline_revision`（telemetry/调试可见）。

## 7. 灰度 / 降级（核心安全约束）

- **绝不静默改 summary**：只写 metadata + 注入提示，作者终审。
- **全程降级**：任一环节失败/缺数据 → 跳过，主生成零影响。
- **成本控制**：只 review 后续 K=3 章；SystemConfig 总开关默认关，灰度放量；仅 flagship 触发。
- **幂等**：同目标章按 source_chapter 覆盖，重复定稿不堆积。

## 8. 落地步骤（建议顺序）

1. `prompts/outline_revision.md`（启动时自动同步进 DB）。
2. `app/services/outline_revision_service.py`：`review_downstream`（写侧）+ `build_revision_brief`（读侧）。
3. 写侧三层挂载：`generation_write_task_service` → `generation_background_task_service` 门面 → `generation_finalize_service.schedule_followups` 触发（含 `enable_outline_revision` 条件 + `chapter`/`best_content` 实参）。
4. config：`pipeline_config_service.enable_outline_revision` 推导 + SystemConfig 总开关 + `generation_policy_service` stage_flag。
5. 读侧：`generation_prefetch_service` 建 task → `generation_evidence_stage_service` await → `generation_prompt_stage_service` 注入 `[大纲修订提示]` 段。
6. feature_gating 注册 `outline_revision` capability。
7. 测试（实现时单列）：写侧 merge 不覆盖导演脚本 / 缺后续大纲降级 / LLM 异常降级 / 读侧无建议返回 None / 端到端注入；非 flagship 不触发。

## 9. 验收

- flagship 档生成章节 N 定稿后，后续 3 章中确有「过时」的，其 outline.metadata 出现 revision_hint；生成该章时 prompt 含 `[大纲修订提示]` 段。
- 非 flagship / 总开关关 / 无后续大纲 / LLM 失败：均无任何写入、无注入、主生成正常。
- `summary` 字段始终不被自动改写。
