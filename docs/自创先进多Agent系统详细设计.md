# 自创先进多 Agent 协作系统 - 详细设计文档

> 版本：1.0
> 日期：2026-03-07
> 状态：**历史设计文档，不代表当前运行代码**
>
> 当前状态提示（2026-06-02）：当前 Agent 主流程已收敛为 `taizi -> hubu -> zhongshu -> bingbu -> menxia` 的顺序返回值驱动流程；`ShangshuAgent`、`LibuAgent`、`PERMISSION_MATRIX`、消息总线路由和 `KnowledgeRetrievalService` 不在当前索引代码中。

---

## 一、现状分析与目标

### 1.1 现状

当前系统采用单体 `PipelineOrchestrator` 编排整个写作流程，主要特点：

- **单一入口**：`generate_chapter()` 方法处理所有逻辑
- **紧耦合**：70+ 服务模块直接调用，职责边界模糊
- **同步执行**：阶段按顺序执行，部分并行优化
- **阶段划分**：通过 `_emit_stage()` 标记进度

**现有阶段划分**：
```
starting → resolve_config → prepare_project_context → collect_history_context 
→ build_mission_inputs → prepare_context → build_generation_prompt 
→ generate_scene_by_scene → persist_versions → completed
```

### 1.2 目标

将单体流水线拆分为独立的 Agent 协作系统：

1. **解耦**：每个 Agent 独立运行，可单独扩展
2. **可观测**：Agent 间通过消息传递，流程清晰可追踪
3. **可配置**：可根据需求选择不同 Agent 组合
4. **可扩展**：新增 Agent 不影响现有流程

---

## 二、Agent 架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用户请求入口                                   │
│                    (writer.py /advanced/generate)                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         WritingAgentSystem                              │
│                        (Agent 协调中枢)                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐         │
│  │ 需求解析智能体   │───▶│ 规划智能体    │───▶│ 协调智能体    │───▶│ 审核智能体    │         │
│  │ Taizi   │    │ Zhongshu │    │ Shangshu │    │ Menxia   │         │
│  │ Agent   │    │ Agent    │    │ Agent    │    │ Agent    │         │
│  └─────────┘    └──────────┘    └──────────┘    └──────────┘         │
│       │              │               │               ▲                 │
│       │              │               ├───────────────┤                 │
│       │              │               ▼               │                 │
│       │              │        ┌──────────┐           │                 │
│       │              │        │ 技能智能体      │           │                 │
│       │              │        │ Hubu     │           │                 │
│       │              │        │ Agent    │           │                 │
│       │              │        └──────────┘           │                 │
│       │              │               │               │                 │
│       │              │        ┌──────────┐           │                 │
│       │              │        │ 一致性智能体      │           │                 │
│       │              │        │ Libu     │           │                 │
│       │              │        │ Agent    │           │                 │
│       │              │        └──────────┘           │                 │
│       │              │               │               │                 │
│       │              │        ┌──────────┐           │                 │
│       │              │        │ 生成智能体      │           │                 │
│       │              │        │ Bingbu   │───────────┘                 │
│       │              │        │ Agent    │                             │
│       │              │        └──────────┘                             │
│       │              │                                                │
│       │              │                                                │
│  需求分拣            规划中枢                    调度协同 ──────────────┘
│  (新 Agent)         (现有逻辑)                  (重构自 PipelineOrchestrator)
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AgentMessageBus (消息总线)                          │
│                  (Redis Pub/Sub + 持久化队列)                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Agent 职责定义

| Agent | 名称 | 职责 | 对应原流水线阶段 |
|-------|------|------|-----------------|
| **Taizi** | 需求解析智能体 | 需求解析、指令分拣 | 新增 |
| **Zhongshu** | 规划智能体 | 策略规划、上下文组装 | build_mission_inputs |
| **Shangshu** | 协调智能体 | 任务分发、结果汇总 | 调度层 |
| **Bingbu** | 生成智能体 | 章节核心生成 | generate_scene_by_scene |
| **Hubu** | 技能智能体 | 技能系统、技能调度 | 技能执行 |
| **Libu** | 一致性智能体 | 角色管理、人物一致性 | consistency_service |
| **Menxia** | 审核智能体 | 质量审核、最终把关 | gatekeeper_review |

### 2.3 Agent 权限矩阵

```
       Taizi  Zhongshu  Shangshu  Menxia  Hubu  Libu  Bingbu
Taizi    -       ✓         -        -      -     -      -
Zhongshu ✓        -         ✓        ✓     -     -      -
Shangshu ✓        ✓         -        -      ✓     ✓      ✓
Menxia   ✓        ✓         -        -      -     -      -
Hubu      -        -         ✓        -      -     -      -
Libu      -        -         ✓        -      -     -      -
Bingbu    -        -         ✓        -      -     -      -
```

---

## 三、消息协议设计

### 3.1 消息格式

```python
class AgentMessage(BaseModel):
    """Agent 间消息格式"""
    
    # 消息唯一标识
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    
    # 发送者 Agent ID
    sender: str
    
    # 接收者 Agent ID (* 表示广播)
    recipient: str
    
    # 消息类型
    message_type: AgentMessageType
    
    # 消息内容
    payload: Dict[str, Any]
    
    # 关联的写作任务
    task_id: Optional[str] = None
    project_id: Optional[str] = None
    chapter_number: Optional[int] = None
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # 时间戳
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentMessageType(str, Enum):
    """消息类型枚举"""
    
    # 任务流转
    TASK_STARTED = "task_started"           # 任务开始
    TASK_DELEGATED = "task_delegated"       # 任务委托
    TASK_COMPLETED = "task_completed"        # 任务完成
    TASK_FAILED = "task_failed"              # 任务失败
    
    # 章节生成
    CHAPTER_GENERATE_REQUEST = "chapter_generate_request"
    CHAPTER_GENERATE_RESPONSE = "chapter_generate_response"
    CHAPTER_VERSION_READY = "chapter_version_ready"
    
    # 审核流程
    REVIEW_REQUEST = "review_request"
    REVIEW_RESPONSE = "review_response"
    
    # 技能调用
    SKILL_APPLY_REQUEST = "skill_apply_request"
    SKILL_APPLY_RESPONSE = "skill_apply_response"
    
    # 上下文请求
    CONTEXT_REQUEST = "context_request"
    CONTEXT_RESPONSE = "context_response"
```

### 3.2 通道设计

```python
class AgentChannel:
    """Agent 消息通道"""
    
    # 任务级别通道
    TASK_PREFIX = "agent.task"           # agent.task.{task_id}
    
    # Agent 级别通道
    AGENT_PREFIX = "agent"                # agent.{agent_name}
    
    # 系统广播通道
    SYSTEM_BROADCAST = "agent.broadcast"
    
    # 任务状态通道
    TASK_STATUS = "agent.status"          # agent.status.{task_id}
```

---

## 四、Agent 详细设计

### 4.1 基类设计 (base.py)

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class AgentCapability(BaseModel):
    """Agent 能力定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


class AgentContext(BaseModel):
    """Agent 执行上下文"""
    task_id: str
    project_id: str
    chapter_number: Optional[int] = None
    
    # 输入数据
    user_input: Optional[str] = None
    mission: Optional[Dict[str, Any]] = None
    blueprint: Optional[Dict[str, Any]] = None
    
    # 上下文数据
    history_context: Optional[Dict[str, Any]] = None
    rag_results: Optional[List[Dict[str, Any]]] = None
    skill_context: Optional[Dict[str, Any]] = None
    
    # 配置
    config: Dict[str, Any] = Field(default_factory=dict)
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Agent 执行结果"""
    status: str  # "completed", "failed", "delegated", "waiting"
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    next_agent: Optional[str] = None  # 委托给下一个 Agent
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """Agent 基类"""
    
    AGENT_NAME: str = "base"
    AGENT_VERSION: str = "1.0.0"
    
    def __init__(self, agent_id: str, session: AsyncSession):
        self.agent_id = agent_id
        self.session = session
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)
        self.message_bus: Optional[AgentMessageBus] = None
        
        # 能力注册
        self._capabilities: Dict[str, AgentCapability] = {}
        self._register_capabilities()
    
    @abstractmethod
    async def process(self, context: AgentContext) -> AgentResult:
        """处理任务（子类必须实现）"""
        pass
    
    async def initialize(self) -> None:
        """初始化 Agent"""
        logger.info(f"Initializing agent: {self.AGENT_NAME}")
        await self._load_prompts()
        await self._load_config()
    
    async def cleanup(self) -> None:
        """清理资源"""
        logger.info(f"Cleaning up agent: {self.AGENT_NAME}")
    
    # ========== 消息发送 ==========
    
    async def send_message(
        self,
        recipient: str,
        message_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        """发送消息给其他 Agent"""
        if not self._can_send_to(recipient):
            raise PermissionError(
                f"Agent {self.AGENT_NAME} cannot send message to {recipient}"
            )
        
        message = AgentMessage(
            sender=self.AGENT_NAME,
            recipient=recipient,
            message_type=message_type,
            payload=payload,
            task_id=task_id,
            project_id=project_id,
        )
        
        await self.message_bus.publish(
            channel=f"agent.{recipient}",
            message=message.model_dump()
        )
        logger.debug(f"Message sent: {self.AGENT_NAME} -> {recipient}")
    
    async def broadcast(
        self,
        message_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> None:
        """广播消息"""
        message = AgentMessage(
            sender=self.AGENT_NAME,
            recipient="*",
            message_type=message_type,
            payload=payload,
            task_id=task_id,
        )
        
        await self.message_bus.publish(
            channel="agent.broadcast",
            message=message.model_dump()
        )
    
    # ========== 权限检查 ==========
    
    def _can_send_to(self, target: str) -> bool:
        """检查是否可以发送消息给目标 Agent"""
        from .system import WritingAgentSystem
        return target in WritingAgentSystem.PERMISSION_MATRIX.get(self.AGENT_NAME, [])
    
    def _register_capabilities(self) -> None:
        """注册 Agent 能力（子类可重写）"""
        pass
    
    async def _load_prompts(self) -> None:
        """加载提示词模板"""
        pass
    
    async def _load_config(self) -> None:
        """加载配置"""
        pass
```

### 4.2 需求解析智能体 Agent (taizi_agent.py)

```python
class TaiziAgent(BaseAgent):
    """
    需求解析 Agent - 需求分拣
    
    职责：
    1. 解析用户写作指令
    2. 识别章节类型和情绪目标
    3. 提取关键写作要求
    4. 转发给规划智能体
    """
    
    AGENT_NAME = "taizi"
    
    async def process(self, context: AgentContext) -> AgentResult:
        # 1. 解析用户指令
        parsed = await self._parse_command(context.user_input or "")
        
        # 2. 识别章节类型
        chapter_type = await self._identify_chapter_type(
            parsed,
            context.blueprint
        )
        
        # 3. 提取情绪目标
        emotion_target = await self._extract_emotion_target(
            parsed,
            context.blueprint
        )
        
        # 4. 提取写作偏好
        writing_preferences = await self._extract_writing_preferences(parsed)
        
        # 5. 转发给规划智能体
        await self.send_message(
            recipient="zhongshu",
            message_type=AgentMessageType.TASK_DELEGATED,
            payload={
                "parsed_command": parsed,
                "chapter_type": chapter_type,
                "emotion_target": emotion_target,
                "writing_preferences": writing_preferences,
            },
            task_id=context.task_id,
            project_id=context.project_id,
        )
        
        return AgentResult(
            status="delegated",
            output={"chapter_type": chapter_type},
            next_agent="zhongshu"
        )
    
    async def _parse_command(self, user_input: str) -> Dict[str, Any]:
        """解析用户指令"""
        prompt = await self.prompt_service.get_prompt("taizi_command_parser")
        if not prompt:
            # 回退到简单解析
            return self._simple_parse(user_input)
        
        filled = prompt.format(user_input=user_input)
        result = await self.llm_service.generate(
            filled,
            max_tokens=500,
            temperature=0.3,
        )
        
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return self._simple_parse(user_input)
    
    async def _identify_chapter_type(
        self,
        parsed: Dict[str, Any],
        blueprint: Optional[Dict[str, Any]]
    ) -> str:
        """识别章节类型"""
        # 类型：铺垫章/高潮章/转折章/过渡章/结局章
        # 基于用户输入和蓝图中的章节位置判断
        
        if blueprint and blueprint.get("chapter_outline"):
            # 根据章节位置推断
            pass
        
        return parsed.get("chapter_type", "normal")
    
    async def _extract_emotion_target(
        self,
        parsed: Dict[str, Any],
        blueprint: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """提取情绪目标"""
        return {
            "primary_emotion": parsed.get("emotion", "平稳"),
            "intensity": parsed.get("intensity", 5),  # 1-10
            "target_feeling": parsed.get("target_feeling", ""),
        }
    
    async def _extract_writing_preferences(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """提取写作偏好"""
        return {
            "style": parsed.get("style", "default"),
            "pacing": parsed.get("pacing", "balanced"),
            "dialogue_ratio": parsed.get("dialogue_ratio", 0.3),
            "description_style": parsed.get("description_style", "immersive"),
        }
```

### 4.3 规划智能体 Agent (zhongshu_agent.py)

```python
class ZhongshuAgent(BaseAgent):
    """
    规划智能体 Agent - 规划中枢
    
    职责：
    1. 接收需求解析智能体解析结果
    2. 收集项目上下文（蓝图、历史、RAG）
    3. 构建写作任务 Mission
    4. 转发给协调智能体
    """
    
    AGENT_NAME = "zhongshu"
    
    async def process(self, context: AgentContext) -> AgentResult:
        # 1. 收集上下文
        context_data = await self._collect_context(context)
        
        # 2. 构建 Mission
        mission = await self._build_mission(
            context=context,
            context_data=context_data
        )
        
        # 3. 生成写作提示词
        writing_prompt = await self._generate_writing_prompt(mission, context_data)
        
        # 4. 转发给协调智能体
        await self.send_message(
            recipient="shangshu",
            message_type=AgentMessageType.CHAPTER_GENERATE_REQUEST,
            payload={
                "mission": mission,
                "writing_prompt": writing_prompt,
                "context_data": context_data,
            },
            task_id=context.task_id,
            project_id=context.project_id,
        )
        
        return AgentResult(
            status="delegated",
            output={"mission_id": mission.get("id")},
            next_agent="shangshu"
        )
    
    async def _collect_context(self, context: AgentContext) -> Dict[str, Any]:
        """收集项目上下文"""
        from ..services.novel_service import NovelService
        from ..services.chapter_context_service import ChapterContextService
        
        novel_service = NovelService(self.session)
        context_service = ChapterContextService(self.session)
        
        # 获取项目信息
        project = await novel_service.get_project(context.project_id)
        
        # 获取蓝图
        blueprint = context.blueprint
        
        # 获取历史上下文
        history_context = await context_service.collect_history(
            project_id=context.project_id,
            chapter_number=context.chapter_number,
        )
        
        # 获取 RAG 上下文
        rag_results = await self._get_rag_context(context)
        
        return {
            "project": project,
            "blueprint": blueprint,
            "history_context": history_context,
            "rag_results": rag_results,
        }
    
    async def _build_mission(
        self,
        context: AgentContext,
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建写作任务 Mission"""
        # 复用现有 PipelineOrchestrator 的 mission 生成逻辑
        # 将其封装为 ZhongshuAgent 的方法
        pass
    
    async def _get_rag_context(self, context: AgentContext) -> List[Dict[str, Any]]:
        """获取 RAG 上下文"""
        from ..services.knowledge_retrieval_service import KnowledgeRetrievalService
        
        retrieval_service = KnowledgeRetrievalService(self.session)
        results = await retrieval_service.retrieve(
            project_id=context.project_id,
            query=context.mission.get("query", ""),
            top_k=5,
        )
        return results
```

### 4.4 协调智能体 Agent (shangshu_agent.py)

```python
class ShangshuAgent(BaseAgent):
    """
    协调智能体 Agent - 调度协调
    
    职责：
    1. 接收规划智能体的写作任务
    2. 协调生成智能体、一致性智能体、技能智能体执行
    3. 汇总结果
    4. 转发给审核智能体审核
    """
    
    AGENT_NAME = "shangshu"
    
    async def process(self, context: AgentContext) -> AgentResult:
        mission = context.mission
        writing_prompt = context.metadata.get("writing_prompt")
        
        # 1. 调度章节生成章节
        await self._dispatch_bingbu(context, writing_prompt)
        
        # 2. 等待生成智能体完成（通过消息回调）
        # 这里使用等待队列实现
        
        # 3. 获取生成结果
        chapter_versions = await self._wait_for_versions(context.task_id)
        
        # 4. 如需后处理，调度一致性智能体
        if context.config.get("enable_post_processing"):
            await self._dispatch_libu(context, chapter_versions)
        
        # 5. 汇总结果
        result = await self._aggregate_results(chapter_versions)
        
        # 6. 转发给审核智能体审核
        await self.send_message(
            recipient="menxia",
            message_type=AgentMessageType.REVIEW_REQUEST,
            payload={"chapter": result},
            task_id=context.task_id,
            project_id=context.project_id,
        )
        
        return AgentResult(
            status="delegated",
            output={"versions": chapter_versions},
            next_agent="menxia"
        )
    
    async def _dispatch_bingbu(
        self,
        context: AgentContext,
        writing_prompt: str
    ) -> None:
        """调度章节生成章节"""
        await self.send_message(
            recipient="bingbu",
            message_type=AgentMessageType.CHAPTER_GENERATE_REQUEST,
            payload={
                "writing_prompt": writing_prompt,
                "version_count": context.config.get("version_count", 3),
            },
            task_id=context.task_id,
            project_id=context.project_id,
        )
```

### 4.5 生成智能体 Agent (bingbu_agent.py)

```python
class BingbuAgent(BaseAgent):
    """
    生成智能体 Agent - 核心章节生成
    
    职责：
    1. 调用 LLM 生成章节内容
    2. 支持多版本生成
    3. 完成后通知协调智能体
    """
    
    AGENT_NAME = "bingbu"
    
    async def process(self, context: AgentContext) -> AgentResult:
        writing_prompt = context.metadata.get("writing_prompt")
        version_count = context.metadata.get("version_count", 3)
        
        # 调用现有的章节生成逻辑
        versions = await self._generate_versions(
            prompt=writing_prompt,
            count=version_count,
            context=context
        )
        
        # 通知协调智能体
        await self.send_message(
            recipient="shangshu",
            message_type=AgentMessageType.CHAPTER_VERSION_READY,
            payload={
                "versions": versions,
                "task_id": context.task_id,
            },
            task_id=context.task_id,
            project_id=context.project_id,
        )
        
        return AgentResult(
            status="completed",
            output={"versions": versions}
        )
    
    async def _generate_versions(
        self,
        prompt: str,
        count: int,
        context: AgentContext
    ) -> List[Dict[str, Any]]:
        """生成多个版本"""
        # 复用 PipelineOrchestrator 的生成逻辑
        # 可以直接调用现有的 generate_scene_by_scene 方法
        pass
```

### 4.6 技能智能体 Agent (hubu_agent.py)

```python
class HubuAgent(BaseAgent):
    """
    技能智能体 Agent - 技能系统
    
    职责：
    1. 管理技能注册
    2. 执行技能处理
    3. 提供技能上下文
    """
    
    AGENT_NAME = "hubu"
    
    async def process(self, context: AgentContext) -> AgentResult:
        action = context.metadata.get("action")
        
        if action == "apply_skill":
            return await self._apply_skill(context)
        elif action == "list_skills":
            return await self._list_skills(context)
        elif action == "get_skill_context":
            return await self._get_skill_context(context)
        else:
            return AgentResult(
                status="failed",
                error=f"Unknown action: {action}"
            )
    
    async def _apply_skill(self, context: AgentContext) -> AgentResult:
        """应用技能"""
        skill_id = context.metadata.get("skill_id")
        content = context.metadata.get("content")
        
        from ..services.skill_service import SkillService
        skill_service = SkillService(self.session)
        
        result = await skill_service.apply_skill(
            skill_id=skill_id,
            content=content,
            params=context.metadata.get("params", {})
        )
        
        return AgentResult(
            status="completed",
            output={"result": result}
        )
```

### 4.7 一致性智能体 Agent (libu_agent.py)

```python
class LibuAgent(BaseAgent):
    """
    一致性智能体 Agent - 角色管理
    
    职责：
    1. 角色一致性检查
    2. 角色档案管理
    3. 角色关系维护
    """
    
    AGENT_NAME = "libu"
    
    async def process(self, context: AgentContext) -> AgentResult:
        action = context.metadata.get("action")
        
        if action == "check_consistency":
            return await self._check_consistency(context)
        elif action == "get_character_profile":
            return await self._get_character_profile(context)
        else:
            return AgentResult(
                status="failed",
                error=f"Unknown action: {action}"
            )
    
    async def _check_consistency(self, context: AgentContext) -> AgentResult:
        """检查角色一致性"""
        from ..services.consistency_service import ConsistencyService
        
        consistency_service = ConsistencyService(self.session)
        
        issues = await consistency_service.check_chapter(
            project_id=context.project_id,
            chapter_number=context.chapter_number,
            content=context.metadata.get("content", ""),
        )
        
        return AgentResult(
            status="completed",
            output={"issues": issues}
        )
```

### 4.8 审核智能体 Agent (menxia_agent.py)

```python
class MenxiaAgent(BaseAgent):
    """
    审核智能体 Agent - 质量审核
    
    职责：
    1. 章节质量审核
    2. 多维度评审
    3. 审核结果反馈
    """
    
    AGENT_NAME = "menxia"
    
    async def process(self, context: AgentContext) -> AgentResult:
        message_type = context.metadata.get("message_type")
        
        if message_type == AgentMessageType.REVIEW_REQUEST:
            return await self._handle_review_request(context)
        else:
            return AgentResult(
                status="failed",
                error=f"Unknown message type: {message_type}"
            )
    
    async def _handle_review_request(self, context: AgentContext) -> AgentResult:
        """处理审核请求"""
        chapter = context.metadata.get("chapter")
        
        # 调用 Gatekeeper Review
        from ..services.gatekeeper_review_service import GatekeeperReviewService
        
        review_service = GatekeeperReviewService(self.session)
        review_result = await review_service.review(
            project_id=context.project_id,
            chapter_number=context.chapter_number,
            content=chapter.get("content", ""),
        )
        
        if review_result.get("passed"):
            return AgentResult(
                status="completed",
                output={"review": review_result}
            )
        else:
            # 审核不通过，可能需要返回修改
            return AgentResult(
                status="failed",
                output={"review": review_result},
                error="Review not passed"
            )
```

---

## 五、消息总线设计

### 5.1 AgentMessageBus

```python
class AgentMessageBus:
    """Agent 消息总线"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._pubsub: Optional[Redis] = None
        self._publisher: Optional[Redis] = None
        self._handlers: Dict[str, List[Callable]] = {}
        self._task_queues: Dict[str, asyncio.Queue] = {}
    
    async def initialize(self) -> None:
        """初始化连接"""
        self._publisher = Redis.from_url(self.redis_url)
        self._pubsub = Redis.from_url(self.redis_url)
    
    async def publish(self, channel: str, message: Dict[str, Any]) -> None:
        """发布消息"""
        # 持久化到任务队列
        task_id = message.get("task_id")
        if task_id:
            await self._persist_to_queue(task_id, message)
        
        # 发布到 Redis 频道
        await self._publisher.publish(
            channel=channel,
            message=json.dumps(message)
        )
    
    async def subscribe(self, agent_name: str, handler: Callable) -> None:
        """订阅消息"""
        channel = f"agent.{agent_name}"
        
        if channel not in self._handlers:
            self._handlers[channel] = []
            # 启动订阅协程
            asyncio.create_task(self._subscription_loop(channel))
        
        self._handlers[channel].append(handler)
    
    async def wait_for_message(
        self,
        task_id: str,
        timeout: float = 300
    ) -> Optional[Dict[str, Any]]:
        """等待特定任务的消息"""
        if task_id not in self._task_queues:
            self._task_queues[task_id] = asyncio.Queue()
        
        try:
            return await asyncio.wait_for(
                self._task_queues[task_id].get(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return None
    
    async def _persist_to_queue(self, task_id: str, message: Dict) -> None:
        """持久化消息到任务队列"""
        if task_id not in self._task_queues:
            self._task_queues[task_id] = asyncio.Queue()
        
        await self._task_queues[task_id].put(message)
    
    async def _subscription_loop(self, channel: str) -> None:
        """订阅循环"""
        pubsub = self._pubsub.pubsub()
        await pubsub.subscribe(channel)
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                
                # 触发所有处理器
                for handler in self._handlers.get(channel, []):
                    try:
                        await handler(data)
                    except Exception as e:
                        logger.error(f"Handler error: {e}")
```

### 5.2 WritingAgentSystem (系统入口)

```python
class WritingAgentSystem:
    """Agent 系统入口"""
    
    AGENT_REGISTRY: Dict[str, Type[BaseAgent]] = {
        "taizi": TaiziAgent,
        "zhongshu": ZhongshuAgent,
        "shangshu": ShangshuAgent,
        "bingbu": BingbuAgent,
        "hubu": HubuAgent,
        "libu": LibuAgent,
        "menxia": MenxiaAgent,
    }
    
    PERMISSION_MATRIX = {
        "taizi": ["zhongshu"],
        "zhongshu": ["taizi", "menxia", "shangshu"],
        "menxia": ["taizi", "zhongshu"],
        "shangshu": ["taizi", "zhongshu", "hubu", "libu", "bingbu"],
        "hubu": ["shangshu"],
        "libu": ["shangshu"],
        "bingbu": ["shangshu"],
    }
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.message_bus = AgentMessageBus()
        self._agents: Dict[str, BaseAgent] = {}
    
    async def initialize(self) -> None:
        """初始化系统"""
        await self.message_bus.initialize()
        
        # 创建所有 Agent 实例
        for name, agent_class in self.AGENT_REGISTRY.items():
            agent = agent_class(
                agent_id=f"{name}_{uuid4().hex[:8]}",
                session=self.session
            )
            agent.message_bus = self.message_bus
            await agent.initialize()
            self._agents[name] = agent
    
    async def execute_chapter_generation(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_input: Optional[str] = None,
        writing_notes: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """执行章节生成（主入口）"""
        
        # 1. 创建任务
        task_id = str(uuid4())
        
        # 2. 启动需求解析智能体
        taizi = self._agents["taizi"]
        context = AgentContext(
            task_id=task_id,
            project_id=project_id,
            chapter_number=chapter_number,
            user_input=user_input,
            writing_notes=writing_notes,
            config=config or {},
        )
        
        result = await taizi.process(context)
        
        # 3. 等待最终结果
        final_result = await self.message_bus.wait_for_message(
            task_id=task_id,
            timeout=600  # 10分钟超时
        )
        
        return final_result
```

---

## 六、与现有系统对接

### 6.1 对接策略

采用**渐进式迁移**策略：

1. **第一阶段**：实现 Agent 框架和消息总线
2. **第二阶段**：将现有服务封装为 Agent
3. **第三阶段**：切换入口，逐步分流流量

### 6.2 服务封装映射

| 现有服务 | 封装为 | 说明 |
|---------|--------|------|
| PipelineOrchestrator | ShangshuAgent | 核心调度 |
| ChapterContextService | ZhongshuAgent | 上下文 |
| SkillService | HubuAgent | 技能 |
| ConsistencyService | LibuAgent | 角色 |
| GatekeeperReviewService | MenxiaAgent | 审核 |
| 章节生成逻辑 | BingbuAgent | 核心生成 |

### 6.3 共存策略

```python
class HybridExecutor:
    """混合执行器：新旧系统共存"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.agent_system: Optional[WritingAgentSystem] = None
        self.legacy_orchestrator = PipelineOrchestrator(session)
    
    async def generate_chapter(self, *, use_agent: bool = False, **kwargs):
        """选择使用 Agent 系统或传统流水线"""
        
        if use_agent and self.agent_system:
            return await self.agent_system.execute_chapter_generation(**kwargs)
        else:
            return await self.legacy_orchestrator.generate_chapter(**kwargs)
```

---

## 七、文件结构

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
└── menxia_agent.py          # 审核智能体
```

---

## 八、实施计划

### 阶段一：框架搭建 (5天)

1. 创建 `agents/` 目录结构
2. 实现 `BaseAgent` 基类
3. 实现 `AgentMessageBus` 消息总线
4. 实现 `WritingAgentSystem` 系统入口
5. 编写单元测试

### 阶段二：核心 Agent 实现 (10天)

1. 实现 TaiziAgent（需求解析）
2. 实现 ZhongshuAgent（上下文组装）
3. 实现 ShangshuAgent（调度协调）
4. 实现 BingbuAgent（章节生成）
5. 实现 HubuAgent（技能系统）
6. 实现 LibuAgent（角色管理）
7. 实现 MenxiaAgent（质量审核）

### 阶段三：集成测试 (5天)

1. 与现有 PipelineOrchestrator 对接
2. 端到端流程测试
3. 性能基准测试
4. 降级策略验证

### 阶段四：灰度发布 (3天)

1. 内部用户灰度
2. 监控系统部署
3. 问题修复迭代

**总工作量：约 23 天**

---

## 九、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| Agent 通信延迟 | 响应时间增加 | 消息队列超时控制，本地缓存 |
| 状态一致性 | 多 Agent 状态不同步 | 事务性消息投递，补偿机制 |
| 循环依赖 | Agent 间死锁 | 权限矩阵严格控制 |
| 调试困难 | 问题定位复杂 | 完整的日志和追踪系统 |

---

## 十、附录

### A. 消息类型完整列表

```python
class AgentMessageType(str, Enum):
    # 生命周期
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    
    # 委托
    TASK_DELEGATED = "task_delegated"
    TASK_RETRY = "task_retry"
    
    # 章节生成
    CHAPTER_GENERATE_REQUEST = "chapter_generate_request"
    CHAPTER_GENERATE_RESPONSE = "chapter_generate_response"
    CHAPTER_VERSION_READY = "chapter_version_ready"
    CHAPTER_VERSION_SELECTED = "chapter_version_selected"
    
    # 审核
    REVIEW_REQUEST = "review_request"
    REVIEW_RESPONSE = "review_response"
    REVIEW_RETRY = "review_retry"
    
    # 技能
    SKILL_APPLY_REQUEST = "skill_apply_request"
    SKILL_APPLY_RESPONSE = "skill_apply_response"
    
    # 上下文
    CONTEXT_REQUEST = "context_request"
    CONTEXT_RESPONSE = "context_response"
    
    # 监控
    HEALTH_CHECK = "health_check"
    HEALTH_RESPONSE = "health_response"
```

### B. 配置项

```python
class AgentSystemConfig:
    """Agent 系统配置"""
    
    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # 超时配置
    TASK_TIMEOUT: int = 600  # 10分钟
    MESSAGE_TIMEOUT: int = 30  # 30秒
    
    # 并发配置
    MAX_CONCURRENT_TASKS: int = 10
    MAX_RETRY_COUNT: int = 3
    
    # 开关
    ENABLE_AGENT_SYSTEM: bool = False  # 默认关闭
    FALLBACK_TO_LEGACY: bool = True  # 失败时回退
```
