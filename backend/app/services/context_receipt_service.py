"""Deterministic receipts from the actual model boundary, not planner intentions.

Only bounded evidence excerpts and hashes are persisted, never complete prompts.
This module performs no I/O and never invokes a model.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

_SOURCE_KEYS = {"project_id", "chapter_id", "chapter_number", "source_version_id", "source_content_hash",
                "adoption_revision_id", "narrative_base", "index_revision_id", "contributing_sources"}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def collect_receipt_sources(rag: Any, history: Any = None) -> list[dict]:
    sources = []
    if isinstance(rag, dict):
        for key, text_key, kind in (("chunk_records", "content", "retrieved_chunk"),
                                    ("summary_records", "summary", "retrieved_summary")):
            for record in rag.get(key) or []:
                if not isinstance(record, dict):
                    continue
                metadata = record.get("metadata") or {}
                metadata = metadata if isinstance(metadata, dict) else {}
                provenance = metadata.get("source_ref") or metadata
                provenance = provenance if isinstance(provenance, dict) else {}
                sources.append({"kind": kind, "chapter_number": record.get("chapter_number"),
                    "source_ref": {key: value for key, value in provenance.items() if key in _SOURCE_KEYS},
                    "text": record.get(text_key) or ""})
    if isinstance(history, dict):
        for item in history.get("completed_chapters") or []:
            if isinstance(item, dict):
                sources.append({"kind": item.get("summary_kind", "history"),
                    "chapter_number": item.get("chapter_number"), "source_ref": item.get("source_ref") or {},
                    "text": item.get("summary") or ""})
    return sources


def build_context_receipt(*, system_prompt: str, user_prompt: str, project_id: str | None = None,
                          chapter_number: int | None = None, sources: list[dict] | None = None,
                          scope: str = "prose", scene_number: int | None = None) -> dict:
    """Exact literal matching against the submitted prompt, after all budget cuts/retries."""
    evidence = []
    for source in sources or []:
        text = str(source.get("text") or "").strip()
        if not text:
            continue
        included = text in user_prompt
        # Record a partial source only when a substantial literal fragment really remains.
        fragment = text[:min(80, len(text))]
        partial = not included and len(fragment) >= 40 and fragment in user_prompt
        item = {key: value for key, value in source.items() if key != "text"}
        item.update(injection_status="included" if included else "partial" if partial else "omitted",
                    source_text_sha256=_hash(text))
        if included or partial:
            item["evidence_excerpt"] = (text if included else fragment)[:180]
        else:
            item["reason"] = "not_in_final_prompt"
        evidence.append(item)
    counts = {"included": sum(item["injection_status"] == "included" for item in evidence),
              "partial": sum(item["injection_status"] == "partial" for item in evidence),
              "omitted": sum(item["injection_status"] == "omitted" for item in evidence)}
    evidence_details = ([item for item in evidence if item["injection_status"] != "omitted"][:80]
                        + [item for item in evidence if item["injection_status"] == "omitted"][:20])
    headings = list(re.finditer(r"(?m)^(?:\[[^\]\n]{1,120}\]|【[^】\n]{1,120}】|#{1,4} [^\n]{1,120})", user_prompt))
    sections = []
    for index, match in enumerate(headings[:80]):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(user_prompt)
        text = user_prompt[match.start():end]
        sections.append({"title": match.group(), "chars": len(text), "sha256": _hash(text)})
    return {"schema_version": 1, "status": "recorded", "scope": scope,
            "project_id": project_id, "chapter_number": chapter_number,
            **({"scene_number": scene_number} if scene_number else {}),
            "system_prompt_sha256": _hash(system_prompt), "user_prompt_sha256": _hash(user_prompt),
            "system_chars": len(system_prompt), "user_chars": len(user_prompt),
            "observed_sections": sections, "evidence": evidence_details,
            "evidence_details_truncated": len(evidence_details) < len(evidence),
            "actual_injection": counts,
            "limits": "记录发送给模型的上下文，不证明模型实际采用了其中每条材料；无收据的历史步骤为 unknown。"}


def build_execution_receipt(metadata: Any) -> dict:
    metadata = metadata if isinstance(metadata, dict) else {}
    steps = []
    gate = metadata.get("quality_gate")
    if isinstance(gate, dict):
        steps.append({"step": "quality_gate", "status": "report_completed" if gate.get("status") == "verified"
                      else gate.get("status", "unknown"), "text_modified": False})
        steps.append({"step": "narrative_delta", "status": gate.get("narrative_delta_status", "unknown"),
                      "text_modified": False})
    guard = metadata.get("guardrail")
    if isinstance(guard, dict):
        steps.append({"step": "guardrail", "status": "check_completed",
                      "text_modified": guard.get("local_patch_applied") is True})

    for index, checked in enumerate(metadata.get("scene_checks") or []):
        if isinstance(checked, dict):
            steps.append({"step": f"scene_{index + 1}_quality_gate", "status":
                "report_completed" if checked.get("status") == "verified" else checked.get("status", "unknown"),
                "text_modified": False})

    def walk(value, path=""):
        if not isinstance(value, dict):
            return
        explicit_status = value.get("status")
        if path and isinstance(explicit_status, str) and explicit_status in {"scheduled_async", "running", "pending", "skipped_for_budget", "degraded", "failed", "unavailable"}:
            steps.append({"step": path, "status": "budget_skipped" if explicit_status == "skipped_for_budget" else explicit_status,
                          "text_modified": False})
        if "applied" in value or "rolled_back" in value:
            steps.append({"step": path, "status": "rolled_back" if value.get("rolled_back") else
                          "modification_applied" if value.get("applied") is True else "not_applied",
                          "text_modified": value.get("applied") is True and not value.get("rolled_back", False)})
        if path.endswith("time_budget"):
            for skipped in value.get("skipped") or []:
                steps.append({"step": str(skipped), "status": "budget_skipped", "text_modified": False})
        for key, child in value.items():
            if isinstance(child, dict) and key not in {"quality_gate", "context_receipt", "execution_receipt"}:
                walk(child, f"{path}.{key}" if path else key)
    walk(metadata)
    compression = metadata.get("word_count_compression")
    if isinstance(compression, dict):
        steps.append({"step": "word_count_compression", "status": "completed",
            "text_modified": compression.get("original_length") != compression.get("compressed_length")})
    return {"schema_version": 1, "status": "recorded" if steps else "unknown", "steps": steps,
            "limits": "报告完成不等于正文已修改；未记录步骤不可推断为成功。"}
