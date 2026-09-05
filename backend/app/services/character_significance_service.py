# AIMETA P=人物意义层|R=版本溯源_持续心结与承诺_相关检索_化解追踪|NR=不含事实状态追踪|E=CharacterSignificanceService|X=internal|A=分析器服务|D=db,llm|S=db,net|RD=./README.ai
"""从采用的正文抽取意义事件。新变化不覆盖旧心结，化解必须有正文依据。"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import case, select

from ..models.memory_layer import CharacterState
from ..models.novel import Chapter, ChapterVersion

logger = logging.getLogger(__name__)
_LABELS = {"belief_shift": "信念变化", "cost": "付出的代价", "relational": "关系变化",
           "unspoken": "没说破的事", "promise": "心结与承诺"}
_GUARD = (
    "以下是人物的历史底色，不是台词或旁白。严禁照抄、替读者总结心理；"
    "优先通过选择、反应、迟疑、回避和行为后果呈现。"
    "历史判断不等于永久人设；本章有充分铺垫时允许改变，没说破的事不能被无依据地说破。"
    "与本章无关的记忆不必出现。"
)


class SignificanceMemory(BaseModel):
    kind: Literal["belief_shift", "cost", "relational", "unspoken", "promise"]
    meaning: str = Field(default="", max_length=300)
    evidence: str = Field(default="", max_length=300, description="本章正文中连续原文，不改写")
    trigger: str = Field(default="", max_length=160, description="什么人物、处境或物件会重新触发")
    related_characters: List[str] = Field(default_factory=list, max_length=4)
    action: Literal["create", "revise", "resolve"] = "create"
    target_id: str = Field(default="", max_length=64, description="修改或化解既有记忆时原样复制其 ID")


class CharacterSignificance(BaseModel):
    name: str = Field(max_length=100)
    memories: List[SignificanceMemory] = Field(default_factory=list, max_length=4)
    # 兼容历史输出；没有逐条原文依据的旧字段不再作为新记忆写入。
    belief_shift: str = ""
    cost: str = ""
    relational: str = ""
    unspoken: str = ""

    def is_empty(self) -> bool:
        return not self.memories and not any((self.belief_shift, self.cost, self.relational, self.unspoken))


class SignificanceResult(BaseModel):
    characters: List[CharacterSignificance] = Field(default_factory=list, max_length=4)


class CharacterSignificanceService:
    @staticmethod
    async def _sources(session: Any, project_id: str, before: int, only_chapter: Optional[int] = None) -> dict:
        # 读侧只取不可变版本的 hash；旧版本没有 hash 才回退正文，避免每次读全书。
        content_column = ChapterVersion.content if only_chapter is not None else case(
            (ChapterVersion.content_hash.is_(None), ChapterVersion.content), else_="")
        query = (
            select(Chapter.id, Chapter.chapter_number, ChapterVersion.id, ChapterVersion.content_hash, content_column,
                   case((Chapter.real_summary.is_not(None) & (Chapter.real_summary != ""), 1), else_=0),
                   Chapter.word_count, Chapter.status)
            .join(ChapterVersion, Chapter.selected_version_id == ChapterVersion.id)
            .where(Chapter.project_id == project_id, Chapter.chapter_number < before)
            .order_by(Chapter.id.asc())
        )
        if only_chapter is not None:
            query = query.where(Chapter.chapter_number == only_chapter)
        rows = (await session.execute(query)).all()
        sources, ranks = {}, {}
        for cid, number, vid, content_hash, content, has_summary, word_count, status in rows:
            # 与 ChapterPostProcessor 的 canonical 选择一致，兼容历史重复章节行。
            rank = (has_summary, int((word_count or 0) > 0),
                    int((status or "").strip() not in ("", "not_generated")), -cid)
            if number in ranks and rank <= ranks[number]:
                continue
            ranks[number] = rank
            sources[number] = {"chapter_id": cid, "version_id": vid, "content_hash": content_hash or hashlib.sha256(
                (content or "").encode("utf-8")).hexdigest(), "content": content or ""}
        return sources

    @staticmethod
    def _source_matches(stored: dict, current: dict) -> bool:
        return bool(current) and all(stored.get(k) == current.get(k)
                                    for k in ("chapter_id", "version_id", "content_hash"))

    async def _active_memories(self, session: Any, project_id: str, before: int) -> List[dict]:
        sources = await self._sources(session, project_id, before)
        rows = (await session.execute(
            select(CharacterState.character_name, CharacterState.chapter_number, CharacterState.extra)
            .where(CharacterState.project_id == project_id, CharacterState.chapter_number < before)
            .order_by(CharacterState.chapter_number.asc(), CharacterState.id.asc())
        )).all()
        active: Dict[str, dict] = {}
        legacy: Dict[tuple, dict] = {}
        for name, number, extra in rows:
            extra = extra if isinstance(extra, dict) else {}
            ledger = extra.get("significance_v2")
            if isinstance(ledger, dict):
                if not self._source_matches(ledger.get("source") or {}, sources.get(number) or {}):
                    continue
                for event in ledger.get("events") or []:
                    if not isinstance(event, dict) or event.get("kind") not in _LABELS:
                        continue
                    target = event.get("target_id")
                    if event.get("action") in ("resolve", "revise"):
                        previous = active.get(target)
                        if not previous or previous["name"] != name or previous["kind"] != event["kind"]:
                            continue
                        active.pop(target, None)
                    if event.get("action") != "resolve":
                        active[event["id"]] = {**event, "name": name, "chapter": number,
                                              "version_id": ledger["source"]["version_id"]}
                continue
            payload = extra.get("significance")
            if isinstance(payload, dict):
                # 旧记录按字段累计且标记待核对，不允许自动化解无依据的历史推断。
                for kind in _LABELS:
                    value = payload.get(kind)
                    if isinstance(value, str) and value.strip():
                        legacy[(name, kind)] = {"id": "", "name": name, "kind": kind,
                            "meaning": value[:300], "chapter": number, "legacy": True}
        return list(active.values()) + list(legacy.values())

    @staticmethod
    def _rank(memories: List[dict], involved: Optional[List[str]], text: str) -> List[dict]:
        names = set(involved or [])
        def relevance(item: dict) -> tuple:
            related = set(item.get("related_characters") or [])
            trigger = item.get("trigger") or ""
            terms = {trigger[i:i + 2] for i in range(max(0, len(trigger) - 1))}
            score = (6 if item["name"] in names else 0) + 3 * len(related & names)
            score += 4 if item["name"] in text else 0
            score += min(4, sum(term in text for term in terms)) if text else 0
            return score, not item.get("legacy", False), item["chapter"]
        return sorted(memories, key=relevance, reverse=True)

    async def extract_and_store(
        self, *, project_id: str, chapter_number: int, chapter_content: str,
        character_names: Optional[List[str]], session: Any, llm_service: Any,
        prompt_service: Any, user_id: int = 0,
    ) -> Dict[str, Any]:
        if not chapter_content or not chapter_content.strip():
            return {"skipped": "empty_content"}
        try:
            source = (await self._sources(session, project_id, chapter_number + 1, chapter_number)).get(chapter_number)
            if not source or source["content"] != chapter_content:
                return {"skipped": "not_current_selected_version"}
            rows = (await session.execute(select(CharacterState).where(
                CharacterState.project_id == project_id, CharacterState.chapter_number == chapter_number,
            ))).scalars().all()
            if any(self._source_matches((r.extra or {}).get("significance_v2", {}).get("source", {}), source)
                   for r in rows if isinstance(r.extra, dict)):
                return {"skipped": "already_extracted"}
            system_prompt = await prompt_service.get_prompt("character_significance")
            if not system_prompt:
                return {"skipped": "prompt_missing"}
            names = [n for n in (character_names or []) if n][:4]
            history = await self._active_memories(session, project_id, chapter_number)
            relevant = self._rank(history, names, chapter_content)[:16]
            known = {m["id"]: m for m in relevant if m["id"]}
            excerpt = chapter_content if len(chapter_content) <= 10000 else (
                chapter_content[:5000] + "\n[中段省略]\n" + chapter_content[-5000:])
            result = await llm_service.generate_structured(
                prompt=f"[本章正文]\n{excerpt}\n[主要角色]\n{'、'.join(names)}\n"
                       f"[既有意义记录，仅可引用有 ID 的记录]\n{json.dumps(relevant, ensure_ascii=False)}",
                schema=SignificanceResult, system_prompt=system_prompt,
                temperature=0.3, user_id=user_id, default=None,
            )
            if result is None:
                return {"skipped": "no_result"}
            current = (await self._sources(session, project_id, chapter_number + 1, chapter_number)).get(chapter_number)
            if not self._source_matches(source, current or {}):
                return {"skipped": "source_changed"}
            by_name: Dict[str, list] = {}
            for character in result.characters[:4]:
                name = character.name.strip()
                if not name or name not in chapter_content or (names and name not in names):
                    continue
                events = by_name.setdefault(name, [])
                for item in character.memories[:4]:
                    evidence = item.evidence.strip()
                    if len(evidence) < 4 or evidence not in excerpt or evidence not in chapter_content or not item.meaning.strip():
                        continue
                    if item.action != "create":
                        target = known.get(item.target_id)
                        if not target or target["name"] != name or target["kind"] != item.kind:
                            continue
                    payload = item.model_dump()
                    payload["evidence"] = evidence
                    payload["id"] = hashlib.sha256(
                        f"{project_id}:{source['version_id']}:{source['content_hash']}:{name}:{json.dumps(payload, sort_keys=True, ensure_ascii=False)}".encode()
                    ).hexdigest()[:24]
                    events.append(payload)
            stored_source = {k: v for k, v in source.items() if k != "content"}
            for row in rows:
                extra = dict(row.extra or {})
                extra.pop("significance", None)
                extra.pop("significance_v2", None)
                row.extra = extra
            stored = 0
            for name, events in by_name.items():
                if not events:
                    continue
                row = next((r for r in rows if r.character_name == name), None)
                if row is None:
                    row = CharacterState(project_id=project_id, chapter_number=chapter_number, character_name=name)
                    session.add(row)
                row.extra = {**(row.extra or {}), "significance_v2": {"source": stored_source, "events": events}}
                stored += 1
            if not stored and names:
                row = next((r for r in rows if r.character_name == names[0]), None)
                if row is None:
                    row = CharacterState(project_id=project_id, chapter_number=chapter_number, character_name=names[0])
                    session.add(row)
                row.extra = {**(row.extra or {}), "significance_v2": {"source": stored_source, "events": []}}
            await session.commit()
            return {"stored": stored}
        except Exception as exc:
            logger.warning("人物意义层抽取失败（不影响正文）: %s", exc)
            await session.rollback()
            return {"skipped": f"error:{type(exc).__name__}"}

    async def build_significance_brief(
        self, *, project_id: str, chapter_number: int, involved_characters: Optional[List[str]] = None,
        chapter_context: str = "", session: Any = None,
    ) -> Optional[str]:
        async def run(sess: Any) -> Optional[str]:
            ranked = self._rank(await self._active_memories(sess, project_id, chapter_number),
                                involved_characters, chapter_context)
            lines = [_GUARD]
            counts: Dict[str, int] = {}
            for item in ranked:
                name = item["name"]
                if (name not in counts and len(counts) >= 4) or counts.get(name, 0) >= 3:
                    continue
                origin = f"第{item['chapter']}章"
                origin += "，旧记录待核对" if item.get("legacy") else f"，版本{item['version_id']}"
                line = f"- {name}｜{_LABELS[item['kind']]}（{origin}）：{item['meaning'][:200]}"
                if item.get("trigger"):
                    line += f"；触发：{item['trigger'][:80]}"
                if item.get("evidence"):
                    line += f"；原文依据：「{item['evidence'][:100]}」"
                if sum(map(len, lines)) + len(line) > 2600:
                    continue
                lines.append(line)
                counts[name] = counts.get(name, 0) + 1
            return "\n".join(lines) if len(lines) > 1 else None
        try:
            if session is not None:
                return await run(session)
            from ..db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as own:
                return await run(own)
        except Exception as exc:
            logger.warning("人物意义层读取失败: %s", exc)
            return None

    @staticmethod
    def _format_brief(by_name: Dict[str, Dict[str, Any]]) -> Optional[str]:
        lines = [f"- {name}｜{label}：{payload[kind]}" for name, payload in by_name.items()
                 for kind, label in _LABELS.items() if payload.get(kind)]
        return "\n".join([_GUARD, *lines]) if lines else None
