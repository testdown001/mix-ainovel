# AIMETA P=生成阶段类型化共享状态|R=预收集上下文的类型化建模与序列化|NR=不含业务逻辑|E=PreCollectedContext|X=internal|A=数据模型|D=dataclasses|S=none|RD=./README.ai
"""生成管线的类型化共享状态（借鉴 LangGraph typed state 思想）。

背景：`pre_collected_context` 历史上是一个 stringly-typed dict，用魔法字符串 key
跨组件传递（中书省 zhongshu → system flow_config → PipelineOrchestrator / 证据阶段），
读取处散落 `.get("history_context")`/`.get("rag_context")` 等，键名拼写错误无法静态发现。

本模块用强类型 dataclass 建模这份跨阶段共享状态，并保留 `from_dict/to_dict` 序列化边界：
- 线上 wire 格式仍是 dict（flow_config 会被 JSON 序列化给 Go worker），不破坏契约；
- 组件内部用类型化字段访问，IDE/类型检查可发现拼写错误；
- `extra` 兜底未知键，round-trip 不丢字段（前向兼容）。

注意：只借"状态建模"，不引入图运行时；编排仍是确定性线性 pipeline。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# pre_collected_context 的已知键（与各 producer/consumer 对齐）
_KNOWN_KEYS = (
    "history_context",
    "blueprint",
    "context_plan",
    "rag_context",
    "rag_stats",
    "foreshadowing_data",
    "chapter_state_context",
    "power_system",
    "relationship_context",
    "retrieval_evidence_summary",
    "agentic_tool_history",
)


@dataclass
class PreCollectedContext:
    """跨阶段/跨组件预收集上下文的类型化模型。

    字段均带默认值（多为可选），未知键统一收进 extra 以保证序列化 round-trip 不丢数据。
    """

    history_context: Optional[Dict[str, Any]] = None
    blueprint: Optional[Dict[str, Any]] = None
    context_plan: Optional[Dict[str, Any]] = None  # ContextPlan.to_dict() 序列化结果
    rag_context: Optional[Dict[str, Any]] = None
    rag_stats: Optional[Dict[str, Any]] = None
    foreshadowing_data: Optional[Dict[str, Any]] = None
    chapter_state_context: Optional[str] = None
    power_system: Optional[str] = None
    relationship_context: Optional[str] = None
    retrieval_evidence_summary: Any = None
    agentic_tool_history: Any = None
    # 兜底未知键，保证 from_dict→to_dict 不丢字段
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "PreCollectedContext":
        data = data or {}
        if not isinstance(data, dict):
            return cls()
        known = {k: data.get(k) for k in _KNOWN_KEYS if k in data}
        extra = {k: v for k, v in data.items() if k not in _KNOWN_KEYS}
        return cls(**known, extra=extra)

    def to_dict(self) -> Dict[str, Any]:
        """序列化回 dict（wire 格式）。仅输出非 None 的已知键 + extra，保持紧凑。"""
        out: Dict[str, Any] = {}
        for key in _KNOWN_KEYS:
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        out.update(self.extra or {})
        return out
