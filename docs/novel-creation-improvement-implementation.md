# 小说创作改进：实现与运维说明

本轮基于 `novel-creation-workflow-analysis-2026-10-17.md` 实施。原分析保留为旧基线记录；本文说明新的运行契约。未执行真实付费模型重建或连续长篇横评。

## 已实现

### 检索与索引

- cosine、RRF、rerank 分数分域处理；hybrid 单路降级先转换排名，不再按 0.35 误删全部 RRF 命中。
- 服务端构造当前章之前的 RetrievalScope，贯通向量、BM25、按 ID 回填、摘要、状态及 Agent 工具。
- 所有事实使用当前选版、内容哈希和前序谱系验证。未来章纲仍可作为计划，不作为已发生事实。
- embedding 按运行时 provider/model/base URL/维度指纹分集合，凭据不进入指纹。
- 先完成 embedding，再写独立 staging revision；取得回执且 SQL CAS 成功后，才发布 active index/hash。
- BM25 故障记录降级，可独立补建，不重新消耗 embedding。旧向量空间不会因切模型立即删除。

### 正文采用与持久派生

- 选版、保存、恢复、自动选版和定稿共享采用边界。正文、修订号及派生 outbox 同事务提交。
- 相同版本重复采用幂等。生成开始前捕获自动选版基线，不在生成后刷新基线强行覆盖作者编辑。
- 摘要、索引、记忆、伏笔和后续规划通过 `chapter_derivation_jobs` 运行；候选阶段只做草稿评审。
- 数据库租约支持多副本、过期恢复和独立重试。抽取 checkpoint 可复用；失效/迟到结果不能发布。
- 新版 Mem0 关闭自动事实推理/合并，读侧检查 SQL 收据。旧无来源条目保留，但不进入正史上下文。

### 叙事与作者体验

- 非 fast 复用既有最终质量检查提取可选 NarrativeDelta。缺失/无效不伪装成空事实，也不追加一次补调。
- fast、手改与历史缺失明确显示 coverage。管理员可显式补抽取；不伪造正文已经通过质量检查。
- 章规划支持 `emotional_intent`（quiet/balanced/intense）和 `reader_effect`；quiet 优先于通用曲线。
- 写作台保留一键流程，增加折叠的正史/人物关系/承诺/参考分工面板。
- 在实际正文请求边界记录上下文及执行收据；包含/裁剪不等于模型真实采纳，报告完成不等于正文已修改。
- 诊断默认读取当前选版，可指定候选版本；不混合另一版评分、最新归档和当前正文。
- 修复 SSE 会话创建、所有权或基线读取失败时无法终止的问题；失败仍结束流并执行退款路径。

## 数据库升级

在 backend 虚拟环境、正确数据库配置及备份就绪后执行：

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
alembic current
```

新增迁移：

- `m7h8i9j0k1l2`：派生 outbox、active index、伏笔来源。
- `n8i9j0k1l2m3`：平台预算修复批次。

应用启动 bootstrap 也会创建新增表并补必要列，但不能用盲目 stamp 代替版本化迁移。迁移不删除正文或历史。

## 存量作品的行为变化

- 旧 `rag_ingest_hash` 不被视为已成功写入的证明；无 active revision/来源的数据不自行转成可信索引。
- 无来源或已失效的旧摘要、自动人物状态和自动伏笔不会冒充当前事实；存储本身保留。
- 人工/蓝图计划与派生事实分开；来源不足期间，使用已采用原文摘录、可验证前文摘要与有效正史保底。
- 修改早章会使依赖旧谱系的后文派生数据失效；不会改写或删除后文正文。
- 模型切换后需重建相应向量空间；可信 BM25 文本可独立作为降级资料。
- 一键写作仍可使用，但上下文不足可能降低连续性，面板会显示缺口；不会自动批量调用模型补齐。

## 管理员渐进修复 API

需要管理员 Bearer token。基础路径：

`/api/admin/novel-projects/{project_id}/derived-state/repairs`

1. `POST /estimate`：正文范围 1–100 章，`kinds` 可选 `summary/index/state/narrative_delta`。估算不调用模型，生成服务端持久凭证。
2. `POST` 基础路径：提交估算 ID/token、明确平台预算和确认标志。凭证绑定管理员及正文/谱系，15 分钟有效。
3. `GET /{job_id}`：查看完成步骤、预算、错误及降级。
4. `POST /{job_id}/cancel`：停止未开始工作；在途请求不强行伪装成未消耗。

估算示例：

```json
{"chapter_start":1,"chapter_end":10,"kinds":["summary","index","narrative_delta"]}
```

启动示例（占位值替换为估算响应）：

```json
{
  "estimate_id":"<id>",
  "estimate_token":"<estimate_token>",
  "platform_budget_tokens":1000000,
  "confirm_platform_budget":true
}
```

示例预算不是建议统一额度。管理员应按本次估算自行授权；不足时安全停止，不会突破上限继续下一次调用。

### 预算语义

- 不扣作者积分，不新增线上默认补抽取步骤。
- budget/reserved/used 单位是**保守 token 调用上界**，不是美元报价，也不是供应商实际 token 账单。
- 调用开始前原子预留，包含 UTF-8 输入上界、输出限制及重试余量；不确定的失败消耗不退预算。
- 修复生成输出上限 2048，禁止结构验证补调；每次后备/内部请求仍经预算边界。
- 状态可能为 estimated/queued/running/completed/cancelled/stale/budget_exhausted/failed。正文变更后需重新估算，不能沿用旧凭证。

## 兼容与界面接口

- 选版优先传 `version_id + expected_revision_id + expected_content_hash`；保留 index 解析兼容。覆盖已有正文缺基线为 428，基线冲突为 409。
- 只读正史：`GET /api/writer/novels/{id}/chapters/{n}/narrative-state`。不调用模型，返回覆盖率及参考状态。
- 诊断可传 `version_id`，收据均绑定版本/正文哈希；旧记录缺失为 unknown。
- API 端可操作管理员修复；本轮未新增独立管理员批量重建页面。

## 验证与后续运行

- 回归覆盖采用 CAS/幂等、候选与未来事实拒读、租约恢复、迟到任务、失败索引、预算拒绝、SSE 终止和 UI 收据。
- SQLite 使用真实内存库测试迁移、任务及来源；MySQL DDL 编译检查不代替上线环境演练。
- 前端验证包含 Vitest、type-check、build、CSS layer 和无 LLM Playwright smoke。
- benchmark 已采用同一选版/索引边界，记录 resolved config、执行收据、token/耗时及每千字采用稿指标；缺定价保持 unknown。
- 连续 20–50 章付费试验与人工盲读尚需管理员单独预算执行，不能用单测通过宣称已证明小说更好看。
