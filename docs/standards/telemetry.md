# 创作主链路观测标准

> 对应路线图 M0。目标是使内容可靠性、AI 成本与诊断质量可衡量。

## 统一字段

所有领域事件尽量携带：`event`、`project_id`、`user_id`、`chapter_number`、`version_id`、`source`、`duration_ms`、`success`、`error_code`。

正文、提示词、模型原始输出和访问令牌不得写入指标或结构化日志。

## 首批事件

| 事件 | 触发时机 | 关键指标 |
|---|---|---|
| `volume.synced` | 蓝图分卷投影同步完成 | 卷数、是否由旧 JSON 回填 |
| `world_state.snapshot_created` | 创建状态切片 | 章节、源版本、来源、状态哈希 |
| `world_state.seed_loaded` | 为下一章读取状态种子 | 目标章节、来源快照 |
| `chapter.save_succeeded` | 章节保存成功 | 耗时、修订来源 |
| `chapter.save_conflict` | 保存被乐观锁拒绝 | 客户端/服务端修订号 |
| `chapter.version_restored` | 恢复历史版本并创建新快照 | 新版本、父版本来源 |
| `manuscript.exported` | 全书导出响应开始发送 | 格式、字节数、仅内存标记 |
| `ai.suggestion_accepted` | 作者采纳 AI 建议 | 操作类型、来源版本、token/积分 |
| `diagnostic.completed` | 诊断任务完成 | 耗时、问题数、置信度分布、成本 |

## 发布门槛

- M2 起监控保存成功率与冲突率；保存失败必须可按错误码聚合。
- M4 起监控 AI 建议采纳率、重试率、单次操作成本与耗时。
- M5 起监控诊断误报反馈率、完成率和增量索引成本。
