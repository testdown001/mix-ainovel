# Arboris-Novel 待办（下次继续）

> 更新于 **2026-07-31**。质量/RAG 路线图二阶段（6 月）与生成质量五阶段整改（7 月）**均已全部完成**。
> 架构权威见 `CLAUDE.md`；7 月整改的完整清单与逐条勾选状态见 `docs/generation-quality-audit-2026-07.md`；已完成项见 `git log`。

---

## 🔴 优先级 1：运维 —— 网关重建部署

蓝图生成已异步任务化（`8ddee0e`），`gateway/internal/taskdispatcher/dispatcher.go:62` 登记了 `blueprint:generate`（15m 超时），但**服务器上跑的仍是旧网关二进制**，不认识该任务类型：

- 现象：前端提交蓝图任务收 400 → 自动回退同步蓝图生成（安全降级，但异步化收益为零，长蓝图仍可能被 120s 掐断）
- 动作：服务器上重建 gateway 镜像并重启（生产栈命令**必带** `-f docker-compose.prod.yml`，否则会拆掉 prod 栈的 app 副本）
- 验证：提交一次蓝图生成，看是否走异步任务路径（不再回退）；`docker logs gateway | grep panic` 应为空

---

## 🟠 优先级 2：跑评估基线（三件套之①的收尾）

评估基线子系统已交付（`1a9d980`，`backend/run_bench.py` + `app/services/bench/`），但**一次都没跑过**——`bench_results` 不存在，所有质量开关目前仍是「信仰」而非数据。

- 用法见 `docs/bench-guide.md`：先 `--dry-run` 冒烟 → freeze 一个真实项目为夹具 → 跑 standard / premium / full 拿基线 → 对可疑开关做消融（`--baseline full`）
- ⚠️ **首跑前先启动一次后端**，让 `init_db` 给开发库补列（`volumes` 等）
- ⚠️ 跑批走真 LLM 有成本，CLI 有预估 + 确认步骤
- 需要你指定用哪个真实项目做夹具

---

## 🟡 优先级 3：7 月整改遗留的 3 项（2026-07-31 实证）

| 项 | 状态 | 实证位置 |
|----|------|----------|
| outline 结构化字段落库 | ❌ 未做 | `prompts/outline_generation.md:134-139` 每章都让 LLM 产出 `narrative_phase` / `foreshadowing.plant-payoff` / `emotion_hook`，但 `update_or_create_outline(project_id, ch_num, title, summary)` 只落标题+摘要 → **三个字段每章都在生成、每章都被丢弃**（付了 token 没拿到东西，性价比最高的一项） |
| premium enrichment 互斥（#19） | ❌ 未做 | `app/services/standard_post_processing_service.py:179` `enrichment_enabled = enable_enrichment and not optimizer_enabled` 在 optimizer 执行前算死、跑完不复检长度 → premium 档章节偏短时无任何补救（density 只管偏长） |
| revision_hint 生命周期（#33） | 🟡 一半 | 大纲重写/蓝图重建即清 ✅；`consumed` 标记未做，触发点仍在写侧任务 `app/services/generation_write_task_service.py:195` 而非 select/finalize |

---

## 🔵 优先级 4：下一步路线三件套 ②③（未动）

① 评估基线 ✅ 已交付（待跑，见优先级 2）
② **卷级复盘正式重规划 + 卷级发散卡片** —— 未动
③ **两遍制草稿-改写** —— 未动

针对上次分析出的核心思想缺陷：开环规划 / 事实非意义 / 防错非求好 / 约束堆叠上限。

---

## ⚪ 小尾巴（低优先）

- **`backend/app/services/README.ai` 索引严重不全**：无失效条目，但 122 个服务里 **93 个未收录**。补全是纯机械活且容易写不准，价值中等，按需再做。
- **mem0 升 2.x**：6 条迁移清单已归档，当前已锁 `mem0ai==1.0.4` + 关遥测，可长期不动。
- ~~`api/routers/README.ai` 二进制不可读~~ ✅ **已澄清并修复（2026-07-31）**：该文件实为 UTF-8+CRLF 文本，只是 Read/Write 工具按 `.ai` 扩展名判定为二进制而拒读——用 shell 读写即可。已补齐 2 条失效条目（`analytics_enhanced` / `llm_config`）+ 14 个未收录路由。
- ~~remote 迁移~~ ✅ **已完成（2026-07-31）**：`leanb525/mix-ainovel` → `testdown001/mix-ainovel`（切换前已用 `git ls-remote` 验证新地址可达且 HEAD 与本地一致）。

---

## ⚠️ 工作原则（血泪教训，务必遵守）

- **删/改/采纳路线图项前，必须亲自 `grep` 实证现状（含 `tests/`），勿信旧报告/记忆/多代理调研的「现状/缺失」描述** —— 调研的现状部分有严重幻觉。本次勾选审计清单时即靠直接读码抓出 3 项「以为做了其实没做/只做一半」，以及 1 项「审计误判为缺失、实际早已实现」（`register_from_blueprint`）。
- **对抗复审会过度索要测试**：历史上 27 findings 里真代码 bug 仅 2 个，其余是「再加测试」。按价值取舍，勿无脑全采纳。
- **删代码前必查 `tests/` 引用**（历史上 `novel_bench_service` 差点被误删，实有回归测试在用）。
- 提交用显式 pathspec 且 `-m` 放在 `--` **之前**（`git commit -m "msg" -- <paths>`），避免卷入暂存区其他改动（如 `.claude/settings.local.json`）。
- **异步路径「任务超时」先查 `docker logs gateway | grep panic` + `trace.log` 是否为空**，别默认是生成慢（历史真凶是网关 nil-map panic 整进程崩）。
- **dry-run 冒烟是免费的生产体检**（历史上一次冒烟揪出「生产 Qdrant 自始至终是坏的」）。
- 项目未上线，改动直接提交 main。
