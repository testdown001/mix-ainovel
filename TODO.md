# Arboris-Novel 待办（下次继续）

> 更新于 **2026-08-01**（7 月整改遗留三项已于 `8527a9f` 全部收掉）。质量/RAG 路线图二阶段（6 月）与生成质量五阶段整改（7 月）**均已全部完成**。
> 架构权威见 `CLAUDE.md`；7 月整改的完整清单与逐条勾选状态见 `docs/generation-quality-audit-2026-07.md`；已完成项见 `git log`。

---

## ✅ 2026-07-31 / 08-01 已完成（原优先级 1、2 及运维项）

| 项 | 结果 |
|----|------|
| 网关重建部署 | **本就不需要** —— 实证现网镜像构建于 2026-07-26T17:52Z，晚于 `8ddee0e`，二进制里 `blueprint:generate` 在场。旧 TODO 的判断是过期记忆 |
| 跑评估基线 | 跑了三轮（b01/b02/b03）。**结论：n=1 无区分力**，同配置极差 1.74 而配置间差异仅 ~0.5，三轮排名全翻盘。要可信结论须每 cell ≥3 样本（成本放大，需拍板） |
| 4 个线上静默故障 | 全修并生产实证（`9e36d65` `701e383` `5362b99` `a3dc9dc`）：CharacterState 永不落库 / mem0 占位 key / mem0 维度错配 / 重排空转 / 健康检查说谎 |
| 重排改后台可配可测 | `c95fee1` + `fb604e5`，**已实际跑通**：`/v1/rerank` + `BAAI/bge-reranker-v2-m3` |
| SPA 发版旧 chunk 404 | `b745f3f`：index.html 加 no-cache + 客户端 reload 自愈 |

---

## ✅ 7 月整改遗留 3 项已全部收掉（`8527a9f`，2026-08-01）

| 项 | 处理 |
|----|------|
| **outline 结构化字段落库** | ✅ 落进 `outline.metadata["planning"]`；`narrative_phase` **替换**掉 PacingController 的位置公式猜测注入生成提示，`emotion_hook` 补一行。顺带把 `update_or_create_outline` 的 metadata **由整体替换改为合并**（否则会抹掉别处写入的 `prediction`）。plant/payoff 只落库不注入——伏笔子系统已有真实抽取的注入通道，再来一路平行的计划版就是约束堆叠 |
| **premium enrichment 互斥（#19）** | ✅ 两处「跑完再复检」：optimizer 被预算跳过时恢复 enrichment（原来连坐不跑，旁边 polish 有对称降级却漏了它）；optimizer 产出低于字数下限时启用 enrichment 兜底（density 只压不扩，此前无救） |
| **revision_hint 生命周期（#33）** | ✅ 补上真实缺口：编辑章节后伏笔会重提取、大纲修订不会 → 陈旧 hint 一直注入。**审计另记两条经复核不成立**：①「触发点在写侧任务」——`generation_write_task_service` 只是实现所在模块，真正触发点是 `generation_finalize_service.schedule_followups:117`，与伏笔提取并列；②「缺 consumed 标记」——hint 描述的是「前章既成事实 vs 本章未改大纲」的持续性矛盾，大纲被改写前一直成立（改写时已清除），定稿即标 consumed 会让重生成拿不到仍有效的指导，是净损失 |

---

## 🔴 优先级 1：评估基线要拿可信结论

三轮基线的最大产出是**量出了噪声水平**，不是分数。现状：

- n=1 下 run-to-run 噪声（±1.7）远大于配置间差异（~0.5），**不能用它给预设排名**
- 跨轮还叠了外部变量：默认模型被后台从 gpt-5.5 换成 gpt-5.6
- **环境又变了**：重排现已真正生效（b01~b03 期间全程空转），CharacterState/mem0/向量层也都修好了 —— 旧三轮的数字对新系统已无参考价值

→ 下次跑批必须：每 cell **≥3 样本**、跑批期间**不动后台配置**、跑前记录环境快照（现已自动记 `rerank_enabled`/`rerank_configured`）。
→ ⚠️ 成本按倍数增长，属于**需要你拍板的成本放大**。

---

## 🔵 优先级 2：下一步路线三件套 ③（未动）

① 评估基线 ✅ 已交付并跑过（结论见上）
② **卷级复盘正式重规划 + 卷级发散卡片** ✅ 已交付（`39c5a20` + `9d71757`）
③ **两遍制草稿-改写** —— 未动

针对核心思想缺陷：~~开环规划~~（②已闭环）/ 事实非意义 / 防错非求好 / 约束堆叠上限。

### ② 的交付说明与遗留

- `VolumeRetrospectiveService`（自动）：卷末章定稿 → 对比「本卷原规划 vs 本卷实际摘要」
  → 复盘 + 修订下一卷规划，写入 `NovelBlueprint.volumes[i+1]["replan"]`
- `VolumeDivergenceService`（作者主动）：基于故事实际位置发散 N 个下一卷走向，
  三轴评分（surprise/continuity/tension）取 Top-K；选中的卡片写入**同一个 replan 槽位**
- 读侧 `[卷级重规划]` 段注入，排在章级 `[大纲修订提示]` 之前（先定卷方向再谈本章微调）
- 门控：flagship 独占 + env 灰度 `VOLUME_RETROSPECTIVE_ENABLED`（**默认关**，
  发散端点走 `muse_divergence` 能力位）
- 🔜 **遗留：前端未接**。后端两个端点已上线（`POST /api/novels/{id}/volumes/{n}/diverge`
  与 `.../diverge/apply`），但没有 UI 入口——卷级发散卡片目前只能用 API 调用。
  接入位置建议在小说详情页的分卷区域。
- 🔜 **遗留：灰度未开**。`VOLUME_RETROSPECTIVE_ENABLED` 默认关，要实跑需在服务器
  `deploy/.env` 打开并重启（自动复盘才会触发；发散端点不受该开关影响）。

---

## ⚪ 小尾巴（低优先）

- **`backend/app/services/README.ai` 索引严重不全**：无失效条目，但 122 个服务里 **93 个未收录**。纯机械活且容易写不准，价值中等，按需再做。
- **mem0 升 2.x**：6 条迁移清单已归档，当前锁 `mem0ai==1.0.4` + 关遥测，可长期不动。

---

## ⚠️ 工作原则（血泪教训，务必遵守）

- **删/改/采纳路线图项前，必须亲自 `grep` 实证现状（含 `tests/`），勿信旧报告/记忆/多代理调研的「现状/缺失」描述**。本 TODO 的「网关需重建」就是一条过期两周的记忆，实证后作废。
- **best-effort `except` 是静默故障的温床**：跑批/上线后必查日志里的「失败/降级」计数，别只看报告分数——分数可能是在降级系统上打出来的（一次跑批揪出 4 个）。
- **别替用户「体贴」地改写他填的值**：自动给 rerank 地址补 `/rerank`，把用户填对的 `…/v1/rerank/multimodal` 改成 404。多供应商场景下路径推导必然出错。
- **测试勿 `import app.main`**：它在导入时就 `dictConfig` 并设 `propagate=False`，会打坏其它用例的 caplog（一次性搞挂 3 个无关测试）。要测其中逻辑先把纯函数抽出去。
- **对抗复审会过度索要测试**：历史上 27 findings 里真代码 bug 仅 2 个，其余是「再加测试」。按价值取舍。
- **删代码前必查 `tests/` 引用**（`novel_bench_service` 差点被误删，实有回归测试在用）。
- 提交用显式 pathspec 且 `-m` 放在 `--` **之前**（`git commit -m "msg" -- <paths>`），避免卷入 `.claude/settings.local.json` 等。
- **异步路径「任务超时」先查 `docker logs gateway | grep panic` + `trace.log` 是否为空**，别默认是生成慢（真凶曾是网关 nil-map panic 整进程崩）。
- **生产栈命令必带 `-f docker-compose.prod.yml`**，裸 `docker compose` 会拆掉 prod 栈的 app 副本。
- **前端发版后有人报动态导入失败**：先 `curl -sI <站点>/` 看 index.html 有无 Cache-Control，再看旧 chunk 是否 404——两条一对就是缓存问题，非构建问题。
- 项目未上线，改动直接提交 main。
