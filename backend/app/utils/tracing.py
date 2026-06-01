# AIMETA P=轻量分布式追踪|R=结构化span发射_trace上下文|NR=不含业务逻辑|E=span,emit_span,new_trace_id|X=internal|A=工具|D=logging|S=none|RD=./README.ai
"""轻量级 tracing / span 工具（借鉴 OpenAI Agents SDK 默认 tracing 思想）。

目标：为生成主路径提供低成本可观测性——每个阶段一条结构化 span 日志
(trace_id / span 名 / 耗时 / 状态 / 上下文属性)，便于排障与后续接入
Langfuse 等。零重依赖，仅复用标准 logging（写入 `arboris.trace` logger）。

用法：
    # 1) 显式 span（支持嵌套，自动记录耗时与异常状态）
    with span("retrieve_rag", attributes={"project_id": pid}) as s:
        s.set("chunks", len(chunks))

    # 2) 已知耗时直接发射（用于已有 mark_stage 这类事后计时点）
    emit_span(name="resolve_config", duration_ms=12, trace_id=tid)
"""
from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Optional

trace_logger = logging.getLogger("arboris.trace")

# 当前 trace / span 上下文（用于 span() 的嵌套 parent 关联）
_current_trace: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "arboris_trace_id", default=None
)
_current_span: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "arboris_span_id", default=None
)


_UNSET = object()


def new_trace_id() -> str:
    """生成一个 trace id（一次生成任务一个）。"""
    return uuid.uuid4().hex[:16]


def emit_span(
    *,
    name: str,
    duration_ms: int,
    trace_id: Optional[str] = None,
    parent_id: Any = _UNSET,
    status: str = "ok",
    attributes: Optional[Dict[str, Any]] = None,
) -> None:
    """发射一条结构化 span 日志（单行 JSON，便于检索/采集）。

    parent_id 未显式提供时回退到当前上下文 span；显式传入（含 None）则原样使用。
    """
    record: Dict[str, Any] = {
        "trace_id": trace_id or _current_trace.get() or "-",
        "parent_id": _current_span.get() if parent_id is _UNSET else parent_id,
        "span": name,
        "duration_ms": duration_ms,
        "status": status,
    }
    if attributes:
        for k, v in attributes.items():
            if v is not None:
                record[k] = v
    try:
        trace_logger.info("span %s", json.dumps(record, ensure_ascii=False, default=str))
    except Exception:  # 追踪绝不能影响主流程
        pass


class SpanHandle:
    """span() 上下文内用于挂载属性的句柄。"""

    __slots__ = ("attributes",)

    def __init__(self, attributes: Dict[str, Any]):
        self.attributes = attributes

    def set(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def update(self, **kwargs: Any) -> None:
        self.attributes.update(kwargs)


@contextmanager
def span(
    name: str,
    *,
    trace_id: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
):
    """同步上下文管理器：自动记录耗时、异常状态与父子关系。

    既可包同步代码，也可包 `await`（在 `with` 体内 await 即可，CM 本身同步）。
    """
    tid = trace_id or _current_trace.get()
    sid = uuid.uuid4().hex[:8]
    parent = _current_span.get()

    token_trace = _current_trace.set(tid) if tid is not None else None
    token_span = _current_span.set(sid)
    start = time.perf_counter()
    status = "ok"
    handle = SpanHandle(dict(attributes or {}))
    try:
        yield handle
    except Exception:
        status = "error"
        raise
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        emit_span(
            name=name,
            duration_ms=duration_ms,
            trace_id=tid,
            parent_id=parent,
            status=status,
            attributes=handle.attributes,
        )
        _current_span.reset(token_span)
        if token_trace is not None:
            _current_trace.reset(token_trace)
