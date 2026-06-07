# 自创先进多 Agent 系统集成说明

> 本文档说明如何启用和使用多 Agent 协作写作系统。
>
> 当前状态提示（2026-06-02）：本文是历史集成说明。当前 Agent 主流程是 `taizi -> hubu -> zhongshu -> bingbu -> menxia` 的顺序返回值驱动流程，不再使用 `message_bus.py` / `PERMISSION_MATRIX` 路由；生成仍通过 `generation_bridge.py` 复用 `PipelineOrchestrator`。

## 一、系统架构

```
用户请求 → HybridExecutor → [Agent系统] 或 [传统流水线]
```

### 两种模式

| 模式 | 配置 | 说明 |
|------|------|------|
| **传统流水线** | `use_agent: false` | 使用 PipelineOrchestrator |
| **Agent 系统** | `use_agent: true` | 使用多 Agent 协作 |

---

## 二、启用方式

### 方式一：API 请求参数

在调用 `/api/writer/advanced/generate` 或 `/api/writer/advanced/generate/stream` 时，设置 `flow_config.use_agent: true`：

```json
{
  "project_id": "xxx",
  "chapter_number": 1,
  "writing_notes": "写一段主角突破境界的剧情",
  "flow_config": {
    "use_agent": true,
    "versions": 3,
    "enable_consistency": true
  }
}
```

### 方式二：代码中全局启用

修改 `HybridExecutor` 的默认行为：

```python
executor = HybridExecutor(session, user_id=user.id)
executor.enable_agent_system()  # 默认启用 Agent 系统

result = await executor.generate_chapter(
    project_id="xxx",
    chapter_number=1,
    ...
)
```

---

## 三、Agent 协作流程

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 需求解析智能体   │───▶│ 规划智能体    │───▶│ 协调智能体    │───▶│ 审核智能体    │
│ Taizi   │    │ Zhongshu │    │ Shangshu │    │ Menxia   │
└─────────┘    └──────────┘    └──────────┘    └──────────┘
                                           │
                        ┌──────────────────┼──────────────────┐
                        ▼                  ▼                  ▼
                   ┌──────────┐       ┌──────────┐       ┌──────────┐
                   │ 生成智能体      │       │ 技能智能体      │       │ 一致性智能体      │
                   │ Bingbu   │       │ Hubu     │       │ Libu     │
                   └──────────┘       └──────────┘       └──────────┘
```

### 各 Agent 职责

| Agent | 名称 | 职责 |
|-------|------|------|
| **Taizi** | 需求解析智能体 | 需求解析、指令分拣 |
| **Zhongshu** | 规划智能体 | 策略规划、上下文组装 |
| **Shangshu** | 协调智能体 | 任务分发、结果汇总 |
| **Bingbu** | 生成智能体 | 章节核心生成 |
| **Hubu** | 技能智能体 | 技能系统、技能调度 |
| **Libu** | 一致性智能体 | 角色管理、人物一致性 |
| **Menxia** | 审核智能体 | 质量审核、最终把关 |

---

## 四、配置项说明

`FlowConfig` 中与 Agent 系统相关的配置：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `use_agent` | bool | false | 是否启用 Agent 系统 |
| `versions` | int | 3 | 生成版本数量 |
| `enable_consistency` | bool | false | 是否启用角色一致性检查 |

---

## 五、返回格式

Agent 系统返回格式与传统流水线兼容：

```json
{
  "project_id": "xxx",
  "chapter_number": 1,
  "preset": "agent",
  "best_version_index": 0,
  "variants": [
    {
      "index": 0,
      "version_id": 1,
      "content": "生成的章节内容...",
      "metadata": {
        "version_id": "v1",
        "word_count": 3500
      }
    }
  ],
  "review_summaries": {},
  "debug_metadata": {
    "version_count": 1,
    "mode": "agent_system"
  }
}
```

---

## 六、文件结构

```
backend/app/agents/
├── __init__.py              # 导出和注册
├── base.py                  # Agent 基类
├── message.py               # 消息定义
├── system.py                # WritingAgentSystem
├── message_bus.py           # AgentMessageBus
├── taizi_agent.py           # 需求解析智能体
├── zhongshu_agent.py        # 规划智能体
├── shangshu_agent.py        # 协调智能体
├── bingbu_agent.py          # 生成智能体
├── hubu_agent.py            # 技能智能体
├── libu_agent.py            # 一致性智能体
├── menxia_agent.py          # 审核智能体
└── hybrid_executor.py       # 混合执行器
```

---

## 七、注意事项

1. **向后兼容**：默认使用传统流水线 (`use_agent: false`)，确保现有功能不受影响
2. **流式输出**：Agent 系统支持流式输出，但事件类型与传统流水线不同
3. **错误处理**：Agent 系统出错时会自动降级到传统流水线（需配置）
4. **性能**：Agent 系统增加了消息传递开销，适合对质量要求高的场景

---

## 八、故障排查

### Agent 系统未启动

检查日志中是否有 "Agent system initialized"：

```bash
# 启用 debug 日志
export LOG_LEVEL=DEBUG
```

### 消息超时

Agent 系统默认超时 300 秒（章节生成），可通过配置调整：

```python
config = {
    "version_count": 3,
    "enable_consistency_check": True,
    # 超时配置可在 Agent 代码中调整
}
```

### 版本不生成

检查 LLM 服务是否可用，Agent 系统依赖 `LLMService` 生成内容。

---

## 九、后续优化

- [ ] Redis 消息总线（生产环境）
- [ ] Agent 监控系统
- [ ] 动态 Agent 编排
- [ ] Agent 性能优化
