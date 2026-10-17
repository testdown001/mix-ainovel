"""Server-owned, time- and revision-bounded factual retrieval.

Missing provenance is not permission to use an old point. Legacy indices remain
physically intact, but need a verified rebuild before entering generation context.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class RetrievalScope:
    project_id: str
    before_chapter: int
    canon_manifest: Mapping[int, Mapping[str, Any]] = field(default_factory=dict)

    def accepts(self, chapter_number: int, metadata: Mapping[str, Any] | None,
                *, require_index: bool = True) -> bool:
        """Validate both temporal boundary and immutable adopted source identity."""
        try:
            number = int(chapter_number)
        except (TypeError, ValueError):
            return False
        meta = metadata or {}
        source = meta.get("source_ref") or meta
        if not isinstance(source, Mapping) or not 0 < number < self.before_chapter:
            return False
        expected = self.canon_manifest.get(number)
        if not expected or str(source.get("project_id", "")) != self.project_id:
            return False
        for key in ("source_version_id", "source_content_hash", "adoption_revision_id", "narrative_base"):
            if source.get(key) is None or source.get(key) != expected.get(key):
                return False
        if require_index:
            revision = meta.get("index_revision_id")
            if not revision or revision != expected.get("active_index_revision_id"):
                return False
        return True

    def accepts_aggregate(self, metadata: Mapping[str, Any] | None) -> bool:
        """An aggregate has actual contributing sources, never chapter_number=0 bypass."""
        sources = (metadata or {}).get("contributing_sources")
        return bool(sources) and all(
            isinstance(source, Mapping)
            and self.accepts(source.get("chapter_number"), source, require_index=False)
            for source in sources
        )

    @classmethod
    async def build(cls, session: Any, *, project_id: str, before_chapter: int) -> "RetrievalScope":
        from sqlalchemy import select
        from ..models.novel import Chapter, ChapterVersion
        from .narrative_state_service import digest

        if before_chapter < 1:
            raise ValueError("before_chapter must be positive")
        rows = (await session.execute(
            select(Chapter.chapter_number, Chapter.id, Chapter.revision_id,
                   Chapter.content_hash, Chapter.active_index_revision_id,
                   ChapterVersion.id, ChapterVersion.content)
            .join(ChapterVersion, Chapter.selected_version_id == ChapterVersion.id)
            .where(Chapter.project_id == project_id, Chapter.chapter_number < before_chapter)
            .order_by(Chapter.chapter_number, Chapter.id)
        )).all()
        manifest: dict[int, dict[str, Any]] = {}
        lineage: list[list[Any]] = []
        for number, chapter_id, revision_id, content_hash, index_revision, version_id, content in rows:
            actual_hash = hashlib.sha256((content or "").encode("utf-8")).hexdigest()
            # Do not certify an inconsistent cached hash, or ambiguous legacy duplicate.
            if number in manifest:
                manifest[number] = {}
            elif not content_hash or content_hash == actual_hash:
                manifest[number] = {
                    "project_id": project_id,
                    "chapter_number": number,
                    "chapter_id": chapter_id,
                    "source_version_id": version_id,
                    "source_content_hash": actual_hash,
                    "adoption_revision_id": int(revision_id or 0),
                    "narrative_base": digest(lineage),
                    "active_index_revision_id": index_revision,
                }
            lineage.append([number, version_id, actual_hash])
        return cls(project_id, before_chapter, manifest)


async def build_retrieval_scope(*, project_id: str, before_chapter: int,
                                session: Any = None) -> RetrievalScope:
    if session is not None:
        return await RetrievalScope.build(session, project_id=project_id, before_chapter=before_chapter)
    from ..db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as own_session:
        return await RetrievalScope.build(own_session, project_id=project_id, before_chapter=before_chapter)
