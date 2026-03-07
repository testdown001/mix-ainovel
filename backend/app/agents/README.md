# 三省六部 Agent 系统

本模块实现多 Agent 协作写作系统，借鉴中国古代官制设计。

## Agent 架构

- **太子省 (TaiziAgent)**: 需求分拣
- **中书省 (ZhongshuAgent)**: 规划中枢
- **尚书省 (ShangshuAgent)**: 调度协调
- **兵部 (BingbuAgent)**: 章节生成
- **户部 (HubuAgent)**: 技能系统
- **吏部 (LibuAgent)**: 角色管理
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
