# 三省六部 Agent 系统（已收敛）

本模块提供可选的 Agent 执行模式，借鉴中国古代官制命名。

> **现状说明（2026-06-01）**：真实生成引擎是唯一的 `PipelineOrchestrator`；Agent 模式为薄壳，
> 兵部经 `generation_bridge` 回调同一个 orchestrator，并非独立引擎。流程已收敛为顺序的
> 三阶段（规划→生成→审查），不再依赖消息总线/权限矩阵。原 **尚书省(调度)/吏部(角色)**
> 从不被主流程调用，已删除。结合业界/学术调研（pipeline 为主流，多 Agent 无已证质量增益），
> 推荐以 pipeline 为唯一主路径。

## Agent 架构（5 个）

- **太子省 (TaiziAgent)**: 需求分拣（规划阶段）
- **中书省 (ZhongshuAgent)**: 规划中枢（规划阶段）
- **户部 (HubuAgent)**: 技能系统（规划阶段，可选）
- **兵部 (BingbuAgent)**: 章节生成（回调 PipelineOrchestrator）
- **门下省 (MenxiaAgent)**: 质量审核

## 使用方法

```python
from app.agents.system import WritingAgentSystem

async def generate():
    system = WritingAgentSystem(session)
    await system.initialize()
    
    result = await system.execute_chapter_generation(
        project_id="xxx",
        chapter_number=1,
        user_input="写一段主角突破境界的剧情"
    )
```

## 与现有系统共存

使用 `HybridExecutor` 可以在 Agent 系统和传统流水线之间切换：

```python
from app.agents.hybrid_executor import HybridExecutor

executor = HybridExecutor(session)
# 使用 Agent 系统
result = await executor.generate_chapter(use_agent=True, ...)
# 使用传统流水线
result = await executor.generate_chapter(use_agent=False, ...)
```
