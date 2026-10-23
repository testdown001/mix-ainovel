# 倒推规划（先定结局，再回填伏笔）实施方案

- 日期：2026-10-23，代码基线 `65d03c8`
- 背景：`docs/blueprint-mode-benchmark-2026-10.md` 第 5.1 节
- 状态：四个阶段均已实施（2026-10-23）

## 一、要解决的问题

现在的蓝图是正向生成的：设定段一次产出世界观、人物、分卷、伏笔，章纲段再按章排。伏笔是模型「顺手埋」的，兑现靠审稿门的 `foreshadowing_payoff` 维度事后检查。实际结果：

- 伏笔和卷末高潮之间没有因果关系。`climax_hint` 是一句话，伏笔清单是另一组东西，两者各写各的。
- 审稿发现「伏笔无兑现章」时，只能定向重写一段章纲，修补的是症状。
- 作者看不到「这本书往哪里去」。分卷只有 `arc_goal / climax_hint` 两个短字段，终局藏在 `full_synopsis` 的一段散文里，不可编辑、不可被下游结构化读取。

倒推规划把顺序反过来：**先定终局和每卷的高潮，问「要让这个高潮成立，前面必须发生什么」，回填出的前置条件就是伏笔。** 伏笔因为被需要才存在，兑现从结构上保证。

## 二、目标形态

新增一个产物「故事骨架」（`StoryBackbone`），放在立项书和蓝图之间：

```
立项书 → 压力推演 → [新] 故事骨架（终局 + 卷高潮 + 回填清单）
       → 确认页（作者可改终局和高潮）
       → 设定段（骨架为锚点，伏笔 = 回填清单）
       → 章纲段（每批任务附「本区间必须埋下的前置条件」）
       → [新] 回填覆盖断言（确定性检查，缺则补问一次）
       → 审稿门（foreshadowing_payoff 拿到确定性输入）
```

骨架的数据结构：

```python
class SetupRequirement(BaseModel):
    """让某个高潮成立的前置条件，回填成伏笔。"""
    name: str                       # 伏笔名，与 BlueprintForeshadowing.name 对齐
    what_must_be_established: str   # 读者在兑现前必须已经知道/见过什么
    why_needed: str                 # 不埋会怎样（高潮变成天降、人物动机站不住……）
    plant_window: Tuple[int, int]   # 允许埋设的章号区间，如 (1, 8)
    develop_hint: str = ""          # 中途怎么浇水，可空
    tier: str = "核心"              # 核心 / 支线

class ClimaxNode(BaseModel):
    volume_index: int
    chapter: int                    # 高潮落在哪一章（卷内区间内）
    event: str                      # 具体发生什么，不是「大战」
    reversal: str                   # 翻转或揭示了什么
    cost: str                       # 主角付出什么
    protagonist_state_after: str    # 高潮后主角的处境/境界/资源（给后续生效区间用）
    setups: List[SetupRequirement]  # 3-6 条

class StoryBackbone(BaseModel):
    endgame: EndgameNode            # 终局：最终对决、核心问题的答案、主角成为什么、代价
    midpoint: Optional[ClimaxNode]  # 全书中点翻案（可空，短篇不需要）
    climaxes: List[ClimaxNode]      # 每卷一条，按卷序
    first_promise: ClimaxNode       # 前 10 章的第一次兑现，独立出来是因为它决定留存
```

存储：`novel_projects.concept_dossier` JSON 已是一个状态字典（`dossier / stress_report / voice_trial`），加一个 `backbone` 键，**零迁移**。卷级高潮同步写进 `volumes.extra["climax"]`（`volumes` 表有 `extra` JSON 列，M1 迁移预留的），前端 `VolumesSection` 直接读。

## 三、分阶段实施

### 阶段一：骨架生成 + 确认页（后端 2 天，前端 1 天）

**新文件 `services/story_backbone_service.py`**（照 `concept_dossier_service.py` 的结构）

- `generate(session, project, user_id) -> Optional[StoryBackbone]`：
  - 输入：立项书全文（`format_dossier_for_prompt`）、推演报告的高危毒点、参考小说的结构手法（复用 `_build_structure_reference`）、题材。
  - 一次 `generate_structured(schema=StoryBackbone)`，`default=None` 软失败。
  - 卷数和章号区间由本服务**先算好再喂给模型**：从立项书的篇幅预期估算总章数（无则 300），按 `screenwriting.md` 的 3–6 卷规则预切，模型只填内容，不改区间。这样设定段的 volumes 和骨架一定对齐。
  - 后处理：`plant_window` 裁剪到 `[1, climax.chapter - 3]`；每个高潮至少 3 条 setup，不足不补造，只记 warning。
- `format_backbone_for_prompt(backbone) -> str`：给设定段和章纲段用的文本投影。
- `pending_setups_for_range(backbone, start, end) -> List[SetupRequirement]`：`plant_window` 与区间相交的条目，章纲段按批取。
- `setup_coverage(backbone, outline_items) -> CoverageReport`：确定性检查，见阶段二。

**新 prompt `prompts/story_backbone.md`**，核心指令：

> 你拿到的是立项书，不是大纲。先写终局：最后一战是什么、核心冲突的答案是什么、主角变成了什么人、付出了什么。再从终局往回推每一卷的高潮。对每个高潮回答一个问题：「读者要在这一刻不觉得突兀、不觉得天降，前面必须已经知道什么、见过什么？」把答案写成前置条件，给出允许埋设的章号区间。前置条件不是「主角变强」这种结果，是「读者见过师父用过这招一次」这种具体的既视事实。

**触发点**：`concept_dossier_service` 推演完成后，同一条 `safe_create_task` 链上追加骨架生成；确认页 `GET /concept/backbone` 同步兜底（per-project asyncio 锁，和 dossier 一样）。

**端点**（`novels.py`，薄壳）：

- `GET /{id}/concept/backbone` → `{backbone, generated_at}`；未生成则同步生成。
- `PATCH /{id}/concept/backbone` → 分块合并（`endgame` / `climaxes[i]` / `first_promise`），作者改过的标 `revised_by_author=True`。
- `POST /{id}/concept/backbone/regenerate` → 重跑，覆盖未经作者修改的块。

**确认页 `BlueprintConfirmation.vue`**：在立项书卡片和「生成档位」之间插一张「故事去向」卡：

- 顶部一句终局（可编辑）。
- 一条横向节点线：第一次兑现 → 卷 1 高潮 → … → 中点翻案 → … → 终局。每个节点点开看 event / reversal / cost 和它的前置条件列表。
- 前置条件以「第 X–Y 章之间要让读者见过：……」的格式展示。这是作者第一次看到「伏笔为什么存在」。
- 拉取失败降级：不显示该卡，流程照旧。

**门控**：不注册能力位，所有档位都跑（产品没有免费档，骨架是质量底线，不是卖点）。平台开关 `blueprint.backbone_enabled`（默认 true）只作为 kill-switch。失败或关闭时，后续各段按没有骨架的旧路径走。

### 阶段二：骨架驱动设定段与章纲段（后端 2 天）

**设定段** `blueprint_generation_service.generate_blueprint_for_project`：

- 立项书锚点之后再加一条 user 消息：`[故事骨架]` + `format_backbone_for_prompt(backbone)`。
- `screenwriting.md` 第 7 条「分卷规划」改为：若输入含骨架，`volumes` 的区间和 `climax_hint` 必须照抄骨架；第 8 条「伏笔必须可兑现」改为：`foreshadowings` **必须首先包含骨架的全部前置条件**（`name` 一致，`planted_chapter` 落在 `plant_window` 内，`target_chapter` = 对应高潮章），之后才允许补充自己的伏笔。
- 落库前确定性对账 `_reconcile_with_backbone(settings_data, backbone)`：
  - volumes 区间以骨架为准（作者确认过的东西赢）；`extra["climax"]` 写入高潮全文。
  - 骨架 setup 在 `foreshadowings` 里缺失的，**代码直接补入**（字段齐全，不需要模型），`planted_chapter` 取窗口起点；模型自己加的伏笔保留。
  - 对账结果进 `logger.info`，缺失条数进 span 属性。

**章纲段** `_build_batch_task` 多一段：

```
【本批必须埋下的前置条件】（来自故事骨架，是硬约束）
- 师父的旧伤（第 2–6 章之间）：读者要见过他避开某个动作一次，不解释原因。服务于第 24 章高潮。
- …
【本批内要兑现的高潮】第 24 章：……（event / reversal / cost）
```

每批只给与区间相交的条目，不给整表，省 token。`foreshadowing_ops` 的现有约束（埋设章必须有 `plant`）直接覆盖这一段。

**回填覆盖断言**（放在现有的数量断言之后、审稿门之前）：

- `setup_coverage(backbone, outline_items)`：对每条 setup，检查窗口内是否有某章的 `foreshadowing_ops` 含 `{"op":"plant","name":…}`（名称归一化：去空白、全半角）；高潮章是否有 `payoff`。
- 核心级缺失 → 补问一次，复用现有补问代码路径（`retry_task_parts`），任务改成「以下前置条件尚未埋设，请只重写第 X–Y 章中最合适的一章把它埋进去，其余章节不动」。
- 补问后仍缺 → 不阻断，记录到 `review_report["setup_coverage"]`，审稿门和前端都能看到。若某次请求没有章级规划字段（`chapter_planning` 未放行的边缘情况），断言退化为只查高潮章 `summary` 是否提到该前置条件名，并记 warning。

**审稿门** `blueprint_review_service.review`：把 `CoverageReport` 文本化后附在审稿输入里，`blueprint_review.md` 的 `foreshadowing_payoff` 维度改为「以覆盖报告为准打分，不要自己数」。模型数伏笔不可靠，这一维度应该由代码算。

### 阶段三：续排与正文侧接入（后端 1.5 天）

- `writer.py regenerate-outlines` 路径的 `writer_shared.extract_outline_planning_metadata` 之前，用 `pending_setups_for_range` 把该区间的待埋前置条件拼进任务；滚动审稿门 `review_outline_range` 的输入也带上。续排到第 N 卷时，骨架里该卷的高潮是现成的目标，不再只有一句 `climax_hint`。
- `volume_retrospective_service` 复盘时读 `extra["climax"]`，replan 建议对照的是具体高潮而不是模糊方向。
- `constitution_seed_service`：终局和各卷 `reversal` 进 `forbidden_content` 的「禁止提前揭示」条目，正文侧经宪法注入链路自动防剧透。
- 可选：`ClimaxNode.protagonist_state_after` 是 P0-2「生效区间」的天然种子，后续做人物分阶段时直接取。

### 阶段四（可选）：备选终局

确认页加「换一个结局」：`POST .../backbone/alternatives` 用高温生成 2 个不同终局的骨架（只出 endgame + climaxes 的 event，不出 setups），作者选一个再回填。对应基准文档的 P1-5。等阶段一到三跑稳再做。

## 四、改动清单

| 文件 | 改动 |
| --- | --- |
| `schemas/concept_dossier.py` | 新增 `SetupRequirement / ClimaxNode / EndgameNode / StoryBackbone / BackboneResponse / BackbonePatchRequest` |
| `services/story_backbone_service.py` | 新建：生成、格式化、按区间取 setup、覆盖检查、与设定段对账 |
| `prompts/story_backbone.md` | 新建 |
| `prompts/screenwriting.md` | 第 7、8 条加「有骨架时」分支；输出 schema 不变 |
| `prompts/screenwriting_outline.md` | 伏笔操作一节说明「前置条件」段是硬约束 |
| `prompts/blueprint_review.md` | `foreshadowing_payoff` 改为读覆盖报告 |
| `services/concept_dossier_service.py` | 推演完成后调度骨架生成 |
| `services/blueprint_generation_service.py` | 注入骨架锚点；`_build_batch_task` 加前置条件段；对账；覆盖断言与补问 |
| `services/blueprint_review_service.py` | 审稿输入附覆盖报告 |
| `services/novel_service.replace_blueprint` | volumes 落库时把 `extra["climax"]` 一并写入 |
| `api/routers/novels.py` | 三个 backbone 端点 |
| `db/system_config_defaults.py` | `blueprint.backbone_enabled` |
| `frontend/.../BlueprintConfirmation.vue` | 「故事去向」卡 |
| `frontend/.../VolumesSection.vue` | 显示 `extra.climax` |
| `frontend/src/api/novel.ts` | 三个客户端方法 |
| `tests/test_story_backbone.py` | 新建，见下 |
| `tests/test_blueprint_two_stage.py` | 现有用例补「无骨架」断言，确保旧路径不变 |

不需要 Alembic 迁移。

## 五、测试

`tests/test_story_backbone.py`：

1. 预切卷区间：300 章 → 卷数在 3–6 之间，区间连续覆盖 1..300；模型返回乱区间时被覆盖回预切值。
2. `plant_window` 裁剪：窗口末端 ≥ 高潮章 - 3 时被裁；窗口起点 < 1 时取 1。
3. `pending_setups_for_range(1, 25)` 只返回窗口与区间相交的条目。
4. `setup_coverage`：有 plant 且高潮章有 payoff → 覆盖；名称带空格/全角仍匹配；缺 plant → 列为 missing。
5. `_reconcile_with_backbone`：模型漏掉的 setup 被代码补入 `foreshadowings`，模型自己加的保留；volumes 区间以骨架为准。
6. 骨架生成失败（`generate_structured` 返回 None）→ `generate_blueprint_for_project` 走旧路径，LLM 调用次数和旧用例一致。
7. 覆盖断言触发补问：第一次章纲缺核心 setup 的 plant → 第三次 LLM 调用的 user 消息含该 setup 名；补问后仍缺 → 不抛，`review_report["setup_coverage"]["missing"]` 含它。
8. PATCH 分块合并：改 `climaxes[1].event` 不影响其它块，`revised_by_author=True`；regenerate 不覆盖作者改过的块。

用 `test_blueprint_two_stage.py` 的 `_patch_two_stage` 假 LLM 模式，响应列表多塞一段骨架 JSON 即可。

## 六、成本与风险

- **多一次模型调用**：骨架一次 `generate_structured`，约 3–5k 输出 token，比一批章纲便宜。所有用户都跑，不计费，和立项书同样定位。
- **模型不按窗口埋设**：靠确定性对账和覆盖断言兜底，不靠模型自觉。这是本方案与「在 prompt 里多写一句要求」的本质区别。
- **骨架和作者后来的改动冲突**：作者在蓝图页手改分卷或删伏笔后，骨架不自动跟随。阶段一只在蓝图生成前编辑骨架；蓝图落库后骨架变只读参考，续排读的是 `volumes.extra["climax"]` 和伏笔账本，不是骨架本身。
- **章号估算偏差**：预切总章数来自立项书的篇幅预期，偏差会让后几卷的高潮章号不准。续排时 `volume_retrospective` 的 replan 本来就负责修这个；骨架给的是相对位置，不是契约。
- **旧项目**：没有骨架的项目一切照旧；`BlueprintConfirmation` 不显示新卡。

## 七、验收

- 跑一组 5 个不同题材的立项书，对比有/无骨架两条路径的蓝图：
  - 确定性指标：核心伏笔兑现率（有 `payoff` 章的核心伏笔 / 核心伏笔总数），目标从现状的抽样值提升到 ≥ 90%；伏笔埋设章到兑现章的平均距离分布（不应全部挤在 1–10 章）。
  - 审稿门 `foreshadowing_payoff` 和 `volume_escalation` 两维的分数变化。
  - 人读：只看每卷高潮节点和它的前置条件列表，判断「这个高潮读者会不会觉得天降」。
- 阶段三上线后，抽 3 个项目续排到第 2 卷，看 `revision_hint` 里「与规划矛盾」类提示是否减少。

## 八、顺序

阶段一 → 二是一个 PR（骨架不接入设定段就没有意义）；阶段三单独一个 PR；阶段四看数据再定。预计后端 5–6 天，前端 1.5 天。
