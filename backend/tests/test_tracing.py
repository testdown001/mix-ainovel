"""轻量 tracing/span 工具与 telemetry 集成测试。"""
import asyncio
import json
import logging

import pytest

from app.utils import tracing
from app.services.generation_telemetry_service import GenerationTelemetryService


class _CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def spans(self):
        out = []
        for r in self.records:
            msg = r.getMessage()
            if msg.startswith("span "):
                out.append(json.loads(msg[len("span "):]))
        return out


@pytest.fixture
def capture_spans():
    handler = _CaptureHandler()
    logger = logging.getLogger("arboris.trace")
    prev_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(prev_level)


def test_emit_span_basic(capture_spans):
    tracing.emit_span(name="stage_a", duration_ms=12, trace_id="t1",
                      attributes={"project_id": "p1", "empty": None})
    spans = capture_spans.spans()
    assert len(spans) == 1
    s = spans[0]
    assert s["span"] == "stage_a"
    assert s["duration_ms"] == 12
    assert s["trace_id"] == "t1"
    assert s["status"] == "ok"
    assert s["project_id"] == "p1"
    assert "empty" not in s  # None 属性被剔除


def test_span_context_manager_ok_and_attrs(capture_spans):
    with tracing.span("work", trace_id="t2") as sp:
        sp.set("count", 3)
    spans = capture_spans.spans()
    assert spans[-1]["span"] == "work"
    assert spans[-1]["status"] == "ok"
    assert spans[-1]["count"] == 3
    assert spans[-1]["trace_id"] == "t2"
    assert spans[-1]["duration_ms"] >= 0


def test_span_context_manager_records_error_and_reraises(capture_spans):
    with pytest.raises(RuntimeError):
        with tracing.span("boom", trace_id="t3"):
            raise RuntimeError("x")
    spans = capture_spans.spans()
    assert spans[-1]["span"] == "boom"
    assert spans[-1]["status"] == "error"


def test_nested_span_parent_linkage(capture_spans):
    with tracing.span("outer", trace_id="t4"):
        with tracing.span("inner"):
            pass
    spans = {s["span"]: s for s in capture_spans.spans()}
    assert spans["inner"]["parent_id"] is not None
    # inner 继承了 outer 的 trace_id
    assert spans["inner"]["trace_id"] == "t4"
    assert spans["outer"]["parent_id"] is None


def test_telemetry_mark_stage_emits_span(capture_spans):
    async def _noop_stream(event, payload=None):
        return None

    tele = GenerationTelemetryService(_noop_stream)
    tele.set_trace_context(project_id="proj9", chapter_number=2)
    import time
    start = time.perf_counter()
    tele.mark_stage("resolve_config", start)
    tele.mark_stage("generate", start)

    spans = capture_spans.spans()
    names = [s["span"] for s in spans]
    assert "resolve_config" in names and "generate" in names
    rc = next(s for s in spans if s["span"] == "resolve_config")
    assert rc["trace_id"] == tele.trace_id
    assert rc["project_id"] == "proj9"
    assert rc["chapter_number"] == 2
    assert rc["seq"] == 0
    gen = next(s for s in spans if s["span"] == "generate")
    assert gen["seq"] == 1
    # 同一 trace 下耗时记录也已写入
    assert "resolve_config" in tele.stage_timings_ms
