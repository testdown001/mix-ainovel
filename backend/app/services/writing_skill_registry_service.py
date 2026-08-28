# AIMETA P=版本化写作技能注册服务_发布_回滚_指标|R=技能治理业务逻辑|NR=不执行数据库外代码|E=WritingSkillRegistryService|X=internal|A=服务|D=py,sqlalchemy|S=db
"""Registry and governance service for versioned writing skills.

Only declarative policy data is persisted and injected into prompts.  Runtime
transformers remain the small, audited Python modules in ``app.skills``.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import NovelProject, WritingSkill, WritingSkillUsage, WritingSkillVersion


DEFAULT_SKILL_CARDS: tuple[dict[str, Any], ...] = (
    {
        "skill_key": "platinum_style", "name": "白金作家文风", "description": "专业小说家的写作风格，使文字更加老练、有质感",
        "category": "style", "icon": "👑", "execution_mode": "transform", "runtime": True,
        "rules": ["句式有变化，叙述具体克制", "优先呈现场景和行动"], "prohibitions": ["避免空泛的华丽辞藻"],
        "prompt_hints": ["成熟叙事声音", "具体可感的细节"], "verify_hints": ["文风一致性检查"],
    },
    {
        "skill_key": "dialogue_polish", "name": "对话润色", "description": "优化角色对话，使对白更贴合角色性格和场景",
        "category": "dialogue", "icon": "💬", "execution_mode": "transform", "runtime": True,
        "rules": ["每句对白都应有角色意图", "用动作和停顿承载潜台词"], "prohibitions": ["避免所有角色使用同一种口吻"],
        "retrieval_hints": ["角色对白样本", "声纹一致性"], "prompt_hints": ["角色口头禅", "对白节奏稳定性"], "verify_hints": ["对白风格漂移检查"],
    },
    {
        "skill_key": "rhythm_control", "name": "节奏控制", "description": "调整章节节奏，使叙事张弛有度",
        "category": "rhythm", "icon": "🎵", "execution_mode": "transform", "runtime": True,
        "rules": ["场景必须产生信息或行动增量", "紧张段落减少无效铺陈"], "prohibitions": ["避免连续多个段落停留在同一情绪"],
        "retrieval_hints": ["近5章节奏分布", "爽点密度"], "prompt_hints": ["节奏配额", "场景推进速度"], "verify_hints": ["节奏目标达成度"],
    },
    {
        "skill_key": "foreshadowing", "name": "伏笔管理", "description": "处理伏笔埋设与回收，增强故事连贯性",
        "category": "foreshadowing", "icon": "🎯", "execution_mode": "transform", "runtime": True,
        "rules": ["伏笔服务于人物行动和因果链"], "prohibitions": ["避免为了神秘感硬塞隐喻"],
        "retrieval_hints": ["未回收伏笔", "相关章节片段"], "prompt_hints": ["本章伏笔处理清单"], "verify_hints": ["伏笔埋设/强化/回收状态"],
    },
    {
        "skill_key": "emotion_boost", "name": "情绪增强", "description": "提升情感张力，让情绪表达更强烈",
        "category": "emotion", "icon": "💖", "execution_mode": "transform", "runtime": True,
        "rules": ["情绪通过选择、动作和后果呈现"], "prohibitions": ["避免反复直白解释人物感受"],
        "prompt_hints": ["情绪递进", "动作化表达"], "verify_hints": ["情绪转折有效性"],
    },
    {
        "skill_key": "consistency_check", "name": "一致性检查", "description": "检查前后情节、人物设定的一致性",
        "category": "consistency", "icon": "🔍", "execution_mode": "transform", "runtime": True,
        "rules": ["人物、时间线和设定以项目事实为准"], "prohibitions": ["发现冲突时不得擅自改写既定事实"],
        "retrieval_hints": ["角色状态", "时间线", "硬性设定边界"], "prompt_hints": ["设定冲突警戒"], "verify_hints": ["一致性冲突扫描"],
    },
    {
        "skill_key": "limited_pov", "name": "有限视角控制", "description": "锁定单一人物感知范围，避免上帝视角泄露未知信息",
        "category": "narrative", "icon": "◉", "execution_mode": "policy", "runtime": False,
        "phase": "pre_prompt", "rules": ["只写当前视角人物能观察、听见、回忆或合理推断的内容", "未知信息通过行动、对白或线索呈现"],
        "prohibitions": ["禁止直接进入其他人物未表现出的内心", "禁止作者替读者解释真相"], "checker_keys": ["limited_pov"],
        "prompt_hints": ["视角锚定", "感知边界"], "verify_hints": ["视角越界扫描"],
    },
    {
        "skill_key": "restrained_prose", "name": "少修辞与克制表达", "description": "减少形容词堆叠和抽象抒情，让叙述回到具体行动",
        "category": "style", "icon": "Aa", "execution_mode": "policy", "runtime": False, "phase": "pre_prompt",
        "rules": ["优先使用动词、名词和可验证的感官细节", "同一对象连续修饰词不超过两个", "每段至少包含一个具体行动或结果"],
        "prohibitions": ["禁止连续堆叠近义形容词", "禁止用密集比喻替代事实和动作", "禁止反复使用‘仿佛/如同’制造氛围"],
        "checker_keys": ["rhetoric_density", "adjective_stack"], "prompt_hints": ["少形容词", "少比喻", "动作优先"], "verify_hints": ["修辞密度检查"],
    },
    {
        "skill_key": "natural_closing", "name": "自然收束", "description": "用人物行动、对白或具体信息结束章节，避免作者式总结和空泛隐喻",
        "category": "rhythm", "icon": "↘", "execution_mode": "policy", "runtime": False, "phase": "verify",
        "rules": ["结尾优先落在一个可见动作、对白或新信息上", "留下问题但不替读者解释意义"],
        "prohibitions": ["禁止上帝视角概括人物命运", "禁止连续使用象征、隐喻或金句收尾", "禁止用‘这一刻/从此/命运’类旁白强行升华"],
        "checker_keys": ["natural_ending", "omniscient_summary"], "prompt_hints": ["具体动作收尾", "留问题不总结"], "verify_hints": ["章节结尾自然度"],
    },
)


def _checksum(payload: dict[str, Any]) -> str:
    clean = {key: payload.get(key) for key in ("phase", "rules", "prohibitions", "checker_keys", "retrieval_hints", "prompt_hints", "verify_hints")}
    return hashlib.sha256(json.dumps(clean, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _list(value: Any) -> list[str]:
    return [str(item).strip() for item in (value or []) if str(item).strip()]


class WritingSkillRegistryService:
    """CRUD and policy resolution for versioned skills."""

    async def ensure_defaults(self, session: AsyncSession) -> None:
        """Idempotently seed the nine safe, built-in skill cards."""
        for card in DEFAULT_SKILL_CARDS:
            existing = await session.scalar(select(WritingSkill).where(WritingSkill.skill_key == card["skill_key"]))
            skill = existing
            if not skill:
                skill = WritingSkill(
                    skill_key=card["skill_key"], name=card["name"], description=card["description"],
                    category=card.get("category", "style"), icon=card.get("icon", "✨"), scope="system",
                    is_builtin=True, execution_mode=card.get("execution_mode", "policy"),
                )
                session.add(skill)
                await session.flush()
            if await self._active_version(session, skill.id):
                continue
            payload = self._version_payload(card)
            session.add(WritingSkillVersion(
                skill_id=skill.id, version_number=1, version_label="v1.0.0", status="published",
                source="builtin", change_note="初始内置版本", published_at=datetime.now(timezone.utc),
                **payload, checksum=_checksum(payload),
            ))
        await session.flush()

    @staticmethod
    def _version_payload(data: dict[str, Any]) -> dict[str, Any]:
        return {
            "phase": str(data.get("phase") or "pre_prompt"), "rules": _list(data.get("rules")),
            "prohibitions": _list(data.get("prohibitions")), "checker_keys": _list(data.get("checker_keys")),
            "retrieval_hints": _list(data.get("retrieval_hints")), "prompt_hints": _list(data.get("prompt_hints")),
            "verify_hints": _list(data.get("verify_hints")),
        }

    @staticmethod
    def _version_dict(version: WritingSkillVersion) -> dict[str, Any]:
        return {
            "id": version.id, "version_number": version.version_number, "version_label": version.version_label,
            "status": version.status, "phase": version.phase, "rules": _list(version.rules),
            "prohibitions": _list(version.prohibitions), "checker_keys": _list(version.checker_keys),
            "retrieval_hints": _list(version.retrieval_hints), "prompt_hints": _list(version.prompt_hints),
            "verify_hints": _list(version.verify_hints), "change_note": version.change_note,
            "source": version.source, "parent_version_id": version.parent_version_id,
            "checksum": version.checksum, "created_at": version.created_at.isoformat() if version.created_at else None,
            "published_at": version.published_at.isoformat() if version.published_at else None,
        }

    async def _active_version(self, session: AsyncSession, skill_id: int) -> Optional[WritingSkillVersion]:
        return await session.scalar(
            select(WritingSkillVersion).where(
                WritingSkillVersion.skill_id == skill_id, WritingSkillVersion.status == "published"
            ).order_by(WritingSkillVersion.version_number.desc()).limit(1)
        )

    async def catalog(self, session: AsyncSession, *, user_id: Optional[int] = None, project_id: Optional[str] = None) -> list[dict[str, Any]]:
        await self.ensure_defaults(session)
        query = select(WritingSkill).order_by(WritingSkill.category, WritingSkill.id)
        skills = list((await session.scalars(query)).all())
        result: list[dict[str, Any]] = []
        usages = list((await session.scalars(select(WritingSkillUsage))).all())
        grouped: dict[str, list[WritingSkillUsage]] = defaultdict(list)
        for usage in usages:
            grouped[usage.skill_key].append(usage)
        for skill in skills:
            if skill.scope == "author" and skill.owner_user_id != user_id:
                continue
            if skill.scope == "project" and skill.project_id != project_id:
                continue
            active = await self._active_version(session, skill.id)
            records = grouped.get(skill.skill_key, [])
            accepted = [r for r in records if r.accepted is not None]
            changed = [r for r in records if r.changed is not None]
            result.append({
                "id": skill.skill_key, "skill_id": skill.id, "name": skill.name, "description": skill.description,
                "category": skill.category, "icon": skill.icon, "scope": skill.scope, "is_builtin": skill.is_builtin,
                "execution_mode": skill.execution_mode, "version": active.version_label if active else None,
                "version_id": active.id if active else None, "status": active.status if active else "unpublished",
                "version_snapshot": self._version_dict(active) if active else None,
                "capabilities": ([{"name": skill.name, "description": skill.description}] if skill.execution_mode == "transform" else []),
                "config": {"intensity": ["subtle", "moderate", "strong"], "default": "moderate", "preserve_original": True},
                "metrics": {
                    "usage_count": len(records), "accepted_count": sum(1 for r in accepted if r.accepted),
                    "acceptance_rate": round(sum(1 for r in accepted if r.accepted) / len(accepted), 4) if accepted else None,
                    "changed_rate": round(sum(1 for r in changed if r.changed) / len(changed), 4) if changed else None,
                    "avg_before_score": self._avg(r.before_score for r in records), "avg_after_score": self._avg(r.after_score for r in records),
                },
            })
        return result

    @staticmethod
    def _avg(values: Iterable[Optional[float]]) -> Optional[float]:
        nums = [float(v) for v in values if v is not None]
        return round(sum(nums) / len(nums), 3) if nums else None

    async def get_skill(self, session: AsyncSession, skill_key: str) -> Optional[WritingSkill]:
        await self.ensure_defaults(session)
        return await session.scalar(select(WritingSkill).where(WritingSkill.skill_key == skill_key))

    async def list_versions(self, session: AsyncSession, skill_key: str) -> list[dict[str, Any]]:
        skill = await self.get_skill(session, skill_key)
        if not skill:
            return []
        versions = await session.scalars(select(WritingSkillVersion).where(WritingSkillVersion.skill_id == skill.id).order_by(WritingSkillVersion.version_number.desc()))
        return [self._version_dict(item) for item in versions.all()]

    async def resolve_selection(self, session: AsyncSession, selected_skills: Iterable[dict[str, Any]], *, project_id: Optional[str] = None, user_id: Optional[int] = None) -> list[dict[str, Any]]:
        """Resolve IDs to the currently published immutable snapshot.

        Drafts are intentionally invisible to generation.  This is the guard
        that makes AI improvement safe until a human publishes it.
        """
        await self.ensure_defaults(session)
        resolved: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in selected_skills:
            if not isinstance(item, dict):
                continue
            key = str(item.get("skill_id") or item.get("skill_key") or "").strip()
            if not key or key in seen:
                continue
            skill = await self.get_skill(session, key)
            if not skill or (skill.scope == "project" and skill.project_id != project_id) or (skill.scope == "author" and skill.owner_user_id != user_id):
                continue
            version = await self._active_version(session, skill.id)
            if not version:
                continue
            seen.add(key)
            entry = dict(item)
            entry["skill_id"] = skill.skill_key
            entry["version_id"] = version.id
            entry["version_snapshot"] = self._version_dict(version)
            entry["execution_mode"] = skill.execution_mode
            entry["skill_name"] = skill.name
            resolved.append(entry)
        return resolved

    async def create_draft(self, session: AsyncSession, skill_key: str, *, user_id: int, payload: Optional[dict[str, Any]] = None, source: str = "author", change_note: Optional[str] = None) -> dict[str, Any]:
        skill = await self.get_skill(session, skill_key)
        if not skill:
            raise ValueError("技能不存在")
        if skill.scope == "system" and not payload:
            raise PermissionError("系统技能需要提供改进草稿内容")
        current = await self._active_version(session, skill.id)
        data = dict(payload or (self._version_dict(current) if current else {}))
        latest = await session.scalar(select(WritingSkillVersion).where(WritingSkillVersion.skill_id == skill.id).order_by(WritingSkillVersion.version_number.desc()).limit(1))
        number = (latest.version_number if latest else 0) + 1
        version_payload = self._version_payload(data)
        version = WritingSkillVersion(
            skill_id=skill.id, version_number=number, version_label=f"v1.{number - 1}.0",
            status="draft", source=source, change_note=change_note or "待人工审核的技能改进草稿", parent_version_id=current.id if current else None,
            created_by_user_id=user_id, checksum=_checksum(version_payload), **version_payload,
        )
        session.add(version)
        await session.flush()
        return self._version_dict(version)

    async def publish(self, session: AsyncSession, skill_key: str, version_id: int, *, user_id: int, is_admin: bool = False) -> dict[str, Any]:
        skill = await self.get_skill(session, skill_key)
        version = await session.get(WritingSkillVersion, version_id)
        if not skill or not version or version.skill_id != skill.id:
            raise ValueError("技能版本不存在")
        if (skill.scope == "system" and not is_admin) or (skill.scope != "system" and skill.owner_user_id != user_id and not is_admin):
            raise PermissionError("无权发布该技能")
        if version.status == "published":
            return self._version_dict(version)
        current = await self._active_version(session, skill.id)
        if current and current.id != version.id:
            current.status = "retired"
        version.status = "published"
        version.published_by_user_id = user_id
        version.published_at = datetime.now(timezone.utc)
        await session.flush()
        return self._version_dict(version)

    async def rollback(self, session: AsyncSession, skill_key: str, target_version_id: int, *, user_id: int, is_admin: bool = False) -> dict[str, Any]:
        skill = await self.get_skill(session, skill_key)
        target = await session.get(WritingSkillVersion, target_version_id)
        if not skill or not target or target.skill_id != skill.id:
            raise ValueError("回滚目标不存在")
        if (skill.scope == "system" and not is_admin) or (skill.scope != "system" and skill.owner_user_id != user_id and not is_admin):
            raise PermissionError("无权回滚该技能")
        draft = await self.create_draft(session, skill_key, user_id=user_id, payload=self._version_dict(target), source="rollback", change_note=f"从 {target.version_label} 回滚")
        return await self.publish(session, skill_key, draft["id"], user_id=user_id, is_admin=is_admin)

    async def metrics(self, session: AsyncSession, skill_key: str) -> dict[str, Any]:
        rows = list((await session.scalars(select(WritingSkillUsage).where(WritingSkillUsage.skill_key == skill_key))).all())
        return {
            "skill_key": skill_key, "usage_count": len(rows), "accepted_count": sum(1 for r in rows if r.accepted is True),
            "rejected_count": sum(1 for r in rows if r.accepted is False), "pending_count": sum(1 for r in rows if r.accepted is None),
            "acceptance_rate": round(sum(1 for r in rows if r.accepted is True) / sum(1 for r in rows if r.accepted is not None), 4) if any(r.accepted is not None for r in rows) else None,
            "avg_before_score": self._avg(r.before_score for r in rows), "avg_after_score": self._avg(r.after_score for r in rows),
        }

    async def record_usage(self, session: AsyncSession, *, skill_key: str, version_id: Optional[int], user_id: Optional[int], project_id: Optional[str], chapter_number: Optional[int], source: str, changed: Optional[bool] = None, accepted: Optional[bool] = None, before_score: Optional[float] = None, after_score: Optional[float] = None, feedback: Optional[str] = None, metadata: Optional[dict[str, Any]] = None) -> WritingSkillUsage:
        skill = await self.get_skill(session, skill_key)
        usage = WritingSkillUsage(
            skill_id=skill.id if skill else None, skill_version_id=version_id, skill_key=skill_key, user_id=user_id,
            project_id=project_id, chapter_number=chapter_number, source=source, changed=changed, accepted=accepted,
            before_score=before_score, after_score=after_score, feedback=feedback, metadata_=metadata,
        )
        session.add(usage)
        await session.flush()
        return usage
