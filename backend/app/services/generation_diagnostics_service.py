"""Admin-only, bounded generation failure diagnostics; never store draft manuscripts."""
import asyncio
import json
import logging
import re
import traceback
import uuid
from datetime import datetime, timezone

from .cache_service import CacheService

logger = logging.getLogger(__name__)
TTL = 30 * 86400
LIMIT = 100


def redact(value: str, limit: int = 20000) -> str:
    value = re.sub(r"(?i)(Bearer\s+)[\w.\-]+", r"\1[REDACTED]", value)
    value = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", value)
    value = re.sub(r"(?i)((?:api[_-]?key|password|secret|token|authorization)[\"']?\s*[:=]\s*[\"']?)[^\s,\"'&}]+", r"\1[REDACTED]", value)
    value = re.sub(r"(https?://)[^/\s@]+@", r"\1[REDACTED]@", value)
    return value[:limit]


def build_diagnostic(req, error: BaseException, stage: str = "") -> dict:
    # Whitelist review issues: do not serialize exception attributes, prompts or partial_text.
    issues = []
    cause = error
    seen = set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        report = getattr(cause, "report", None)
        if isinstance(report, dict):
            for issue in (report.get("issues") or [])[:12]:
                if isinstance(issue, dict):
                    issues.append({key: redact(str(issue.get(key, "")), 1000)
                                   for key in ("category", "severity", "evidence", "explanation")})
        cause = cause.__cause__ or cause.__context__
    return {
        "id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
        "task_id": req.task_id, "execution_id": req.execution_id,
        "chapter_number": req.chapter_number, "task_type": req.task_type,
        "stage": redact(stage, 200), "error_type": type(error).__name__,
        "message": redact(str(error), 2000), "issues": issues[:12],
        "traceback": redact("".join(traceback.format_exception(type(error), error, error.__traceback__))),
    }


async def record_failure(req, error: BaseException, stage: str = "") -> None:
    record = build_diagnostic(req, error, stage)
    # Structured log fallback survives Redis outages; excludes full manuscript and secrets.
    logger.error("generation_diagnostic %s", json.dumps(record, ensure_ascii=False))
    try:
        async with asyncio.timeout(3):
            redis = await CacheService()._get_redis()
            key = f"arboris:generation_diagnostics:{req.project_id}"
            async with redis.pipeline(transaction=True) as pipe:
                pipe.lpush(key, json.dumps(record, ensure_ascii=False))
                pipe.ltrim(key, 0, LIMIT - 1)
                pipe.expire(key, TTL)
                await pipe.execute()
    except Exception:
        logger.warning("Generation diagnostics storage unavailable; see structured server logs")


async def list_failures(project_id: str) -> list[dict]:
    async with asyncio.timeout(3):
        redis = await CacheService()._get_redis()
        rows = await redis.lrange(f"arboris:generation_diagnostics:{project_id}", 0, LIMIT - 1)
    cutoff = datetime.now(timezone.utc).timestamp() - TTL
    return [record for row in rows if
            (record := json.loads(row)) and datetime.fromisoformat(record["created_at"]).timestamp() >= cutoff]
