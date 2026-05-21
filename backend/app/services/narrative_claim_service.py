from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Sequence


@dataclass
class NarrativeClaim:
    claim_id: str
    claim_type: str
    text: str
    subject: str = ""
    evidence_required: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NarrativeClaimExtractor:
    """Extracts machine-checkable narrative claims from a generated chapter."""

    _POWER_PATTERN = re.compile(r"([\u4e00-\u9fa5]{2,6})(?:突破|晋升|达到|升入)([\u4e00-\u9fa5A-Za-z0-9]{1,12}(?:境|阶|级|层)?)")
    _FORESHADOWING_TOKENS = ("伏笔", "线索", "预兆", "暗示", "埋下", "回收", "应验")

    def extract(self, *, chapter_text: str, plan: Any) -> List[NarrativeClaim]:
        text = chapter_text or ""
        claims: List[NarrativeClaim] = []
        intent = getattr(plan, "intent", {}) or {}

        for name in intent.get("character_focus") or []:
            if name and str(name) in text:
                claims.append(
                    NarrativeClaim(
                        claim_id=f"character:{name}",
                        claim_type="character_presence",
                        text=f"重点人物「{name}」在本章登场或被明确提及",
                        subject=str(name),
                        evidence_required=["state_items", "local_plot"],
                    )
                )

        for index, match in enumerate(self._POWER_PATTERN.finditer(text), start=1):
            claims.append(
                NarrativeClaim(
                    claim_id=f"power:{index}",
                    claim_type="power_state_change",
                    text=f"{match.group(1)}发生力量等级变化：{match.group(2)}",
                    subject=match.group(1),
                    evidence_required=["symbolic_items", "state_items"],
                    metadata={"target_level": match.group(2)},
                )
            )

        for token in self._FORESHADOWING_TOKENS:
            if token in text:
                claims.append(
                    NarrativeClaim(
                        claim_id=f"foreshadowing:{token}",
                        claim_type="foreshadowing_operation",
                        text=f"本章包含伏笔/线索操作信号：{token}",
                        subject=token,
                        evidence_required=["symbolic_items", "local_plot"],
                    )
                )

        for node in getattr(plan, "scene_plan", []) or []:
            goal = getattr(node, "goal", "") or ""
            if goal:
                claims.append(
                    NarrativeClaim(
                        claim_id=f"scene:{getattr(node, 'scene_id', '') or len(claims) + 1}",
                        claim_type="scene_objective",
                        text=goal,
                        subject=getattr(node, "scene_id", ""),
                        evidence_required=list(getattr(node, "required_evidence", []) or []),
                        metadata={"target_words": getattr(node, "target_words", None)},
                    )
                )

        return claims


class ClaimVerifierService:
    """Verifies narrative claims against retrieved evidence and the chapter text."""

    def __init__(self, extractor: NarrativeClaimExtractor | None = None):
        self.extractor = extractor or NarrativeClaimExtractor()

    def verify(self, *, chapter_text: str, plan: Any, evidence_summary: Dict[str, Any]) -> Dict[str, Any]:
        claims = self.extractor.extract(chapter_text=chapter_text, plan=plan)
        evidence_text = self._evidence_text(evidence_summary)
        category_counts = evidence_summary.get("category_counts") or {}
        results = [
            self._verify_claim(
                claim=claim,
                chapter_text=chapter_text or "",
                evidence_text=evidence_text,
                category_counts=category_counts,
            )
            for claim in claims
        ]
        status_counts: Dict[str, int] = {}
        for item in results:
            status = item["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        blocking = [
            item for item in results
            if item["status"] in {"unsupported", "contradicted"}
            and item["severity"] in {"high", "critical"}
        ]
        return {
            "status": "failed" if blocking else "passed",
            "claim_count": len(results),
            "status_counts": status_counts,
            "blocking_count": len(blocking),
            "claims": results,
        }

    def _verify_claim(
        self,
        *,
        claim: NarrativeClaim,
        chapter_text: str,
        evidence_text: str,
        category_counts: Dict[str, Any],
    ) -> Dict[str, Any]:
        required_sources = claim.evidence_required or []
        available_required = [
            source for source in required_sources
            if int(category_counts.get(source, 0) or 0) > 0 or source in evidence_text
        ]

        status = "supported"
        severity = "low"
        reason = "claim is directly supported by generation context"

        if claim.claim_type in {"power_state_change", "foreshadowing_operation"}:
            if not available_required:
                status = "unsupported"
                severity = "high"
                reason = "high-impact narrative operation lacks matching retrieved evidence"
            elif claim.subject and claim.subject not in evidence_text and claim.subject not in chapter_text:
                status = "unsupported"
                severity = "medium"
                reason = "claim subject is missing from retrieved evidence"
        elif claim.claim_type == "scene_objective":
            keywords = self._keywords(claim.text)
            if keywords and not any(keyword in chapter_text for keyword in keywords[:4]):
                status = "weakly_supported"
                severity = "low"
                reason = "scene objective is planned but exact objective terms are not visible in chapter text"
        elif claim.subject and claim.subject not in chapter_text:
            status = "unsupported"
            severity = "medium"
            reason = "claim subject is absent from chapter text"

        payload = claim.to_dict()
        payload.update(
            {
                "status": status,
                "severity": severity,
                "reason": reason,
                "available_required_sources": available_required,
            }
        )
        return payload

    @staticmethod
    def _evidence_text(evidence_summary: Dict[str, Any]) -> str:
        samples = evidence_summary.get("evidence_samples") or []
        parts: List[str] = []
        for item in samples:
            if isinstance(item, dict):
                parts.append(str(item.get("title") or ""))
                parts.append(str(item.get("content") or ""))
        parts.extend(str(item) for item in (evidence_summary.get("top_titles") or []))
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _keywords(text: str) -> List[str]:
        tokens = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", text or "")
        stopwords = {"本章", "场景", "目标", "推进", "读者", "具体", "动作"}
        return [token for token in tokens if token not in stopwords]
