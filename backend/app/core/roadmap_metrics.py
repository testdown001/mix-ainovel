# AIMETA P=路线图领域观测_低耦合结构化事件|R=记录领域事件|NR=不含指标后端实现|E=emit_roadmap_metric|X=internal|A=观测工具|D=logging|S=none|RD=../../../../docs/standards/telemetry.md
"""M0 路线图指标事件。

先以结构化日志统一事件语义，现有日志/追踪管道可直接采集；不在业务层引入另一套
指标基础设施。字段设计见 ``docs/standards/telemetry.md``。
"""
from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

logger = logging.getLogger("arboris.metrics")


class RoadmapMetric(StrEnum):
    VOLUME_SYNCED = "volume.synced"
    WORLD_STATE_SNAPSHOT_CREATED = "world_state.snapshot_created"
    WORLD_STATE_SEED_LOADED = "world_state.seed_loaded"
    CHAPTER_SAVE_SUCCEEDED = "chapter.save_succeeded"
    CHAPTER_SAVE_CONFLICT = "chapter.save_conflict"
    CHAPTER_VERSION_RESTORED = "chapter.version_restored"
    MANUSCRIPT_EXPORTED = "manuscript.exported"
    AI_SUGGESTION_ACCEPTED = "ai.suggestion_accepted"
    DIAGNOSTIC_COMPLETED = "diagnostic.completed"


def emit_roadmap_metric(event: RoadmapMetric, /, **fields: Any) -> None:
    """输出机器可读事件；严禁调用方传递正文、提示词或密钥。"""
    safe_fields = {key: value for key, value in fields.items() if value is not None}
    logger.info("roadmap_metric event=%s fields=%s", event, safe_fields)
