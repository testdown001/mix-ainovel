# 生成失败诊断

管理员进入「小说项目 → 详情 → 生成失败诊断」，展开记录查看失败阶段、任务 ID、执行 ID、异常类型、审校问题的文本证据/解释和脱敏堆栈。

- API：`GET /api/admin/novels/{project_id}/generation-diagnostics`，仅管理员可读。
- 单章 Worker 和批量生成中的单章异常边界都记录诊断；重试沿用任务 ID，通过执行 ID 和日志 ID 区分失败尝试，不增加任务中心卡片。
- 每本小说 Redis 列表最多 100 条，展示最近 30 天记录，列表最后更新后 30 天过期。不需要数据库迁移。
- 不保存完整草稿、提示词或任意异常属性；审校报告只保留问题类别、严重性、引用证据与解释。常见凭据字段、Bearer、sk 密钥与 URL 用户密码会脱敏。
- Redis 写入限定 3 秒，故障不阻断退款/任务状态收束。结构化服务日志 `generation_diagnostic` 保留备用诊断，可按日志 ID / task_id 关联。后台读取失败明确返回 503，不伪装成无记录。
- 上线前失败无法补回当时未保存的审校报告，历史异常堆栈仍需查询原服务器日志。

验证：`pytest tests/test_generation_diagnostics.py tests/test_task_worker.py tests/test_task_execution_identity.py`；前端 `vue-tsc --build`。
