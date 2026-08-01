# AIMETA P=人物意义层|R=从定稿章节抽取信念变化/代价/关系质变/未言明+读侧注入底色|NR=不含事实状态追踪|E=CharacterSignificanceService|X=internal|A=分析器服务|D=db,llm|S=db,net|RD=./README.ai
"""人物意义层

针对最后一条核心缺陷：**事实非意义**。

现有管线注入生成上下文的东西，全是「发生了什么」：
`CharacterState` 的九种类型（位置/情绪/健康/物品/关系/能力/知识/目标/秘密）、
伏笔清单、关系网标签、章节摘要、力量上限……没有任何一项回答
**「这件事对这个人**意味着**什么」**。

于是模型能把事件按正确顺序、不违反任何设定地写出来——「没毛病，但也不重要」。
好小说由意义驱动：同一个动作，因为人物相信什么、失去过什么、和谁之间有什么没说破，
才有分量。

本服务抽取四样东西（刻意都是**会改变后续行为**的，而非情绪快照）：
- `belief_shift` 信念变化：他现在相信/不再相信什么（人物弧光的引擎）
- `cost`       代价：这一章他失去了什么、付出了什么
- `relational` 关系质变：不是「A 是 B 的师兄」这种标签，而是「A 现在把 B 当成什么」
- `unspoken`   未言明：两人之间已经成立、但谁都没说出口的东西（后续潜台词的来源）

⚠️ **最关键的设计约束**：意义只能当**底色**，绝不能被直接写进正文。
若把「他不再相信示好是无偿的」原样注入而不加约束，模型会把这句话当台词或旁白写出来
——那正是 AI 小说最典型的「说破」毛病，比不注入更糟。故读侧文案强制
「只通过选择、反应、迟疑、回避体现，严禁直接陈述」。

存储复用 `CharacterState.extra["significance"]`（该表已按「每章每角色」在写、也已被读进
`[角色当前状态]`），不新建表。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_CONTENT_LIMIT = 6000
_MAX_CHARACTERS = 4        # 只抽主要角色，避免给配角也上一遍意义层（贵且没用）
_BRIEF_MAX_CHARACTERS = 4


class CharacterSignificance(BaseModel):
    """单个角色在本章获得的「意义」（LLM 结构化输出）。"""

    name: str
    belief_shift: str = ""
    cost: str = ""
    relational: str = ""
    unspoken: str = ""

    def is_empty(self) -> bool:
        return not any((self.belief_shift, self.cost, self.relational, self.unspoken))


class SignificanceResult(BaseModel):
    characters: List[CharacterSignificance] = Field(default_factory=list)


class CharacterSignificanceService:
    """人物意义层：写侧抽取并落在角色状态的 extra 上，读侧格式化为底色注入。"""

    # ------------------------------------------------------------------ 写侧
    async def extract_and_store(
        self,
        *,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        character_names: Optional[List[str]],
        session: Any,
        llm_service: Any,
        prompt_service: Any,
        user_id: int = 0,
    ) -> Dict[str, Any]:
        """从定稿章节抽取人物意义并落库。任何前置不满足都以 `{"skipped": 原因}` 返回。"""
        if not chapter_content or not chapter_content.strip():
            return {"skipped": "empty_content"}

        try:
            system_prompt = await prompt_service.get_prompt("character_significance")
            if not system_prompt:
                logger.warning("缺少 character_significance 提示词，跳过意义层抽取")
                return {"skipped": "prompt_missing"}

            names = [n for n in (character_names or []) if n][:_MAX_CHARACTERS]
            user_input = (
                f"[本章正文]\n{chapter_content[:_CONTENT_LIMIT]}\n\n"
                f"[本章涉及角色]\n{'、'.join(names) if names else '（未提供，请自行判断主要角色）'}\n"
            )
            result = await llm_service.generate_structured(
                prompt=user_input,
                schema=SignificanceResult,
                system_prompt=system_prompt,
                temperature=0.3,
                user_id=user_id,
                default=None,
            )
        except Exception as exc:  # noqa: BLE001 - 抽取失败绝不影响主流程
            logger.warning("人物意义层抽取失败（已降级跳过）: %s", exc)
            return {"skipped": f"error:{type(exc).__name__}"}

        if result is None or not result.characters:
            return {"skipped": "no_significance"}

        stored = 0
        for item in result.characters:
            if not item.name or item.is_empty():
                continue
            try:
                await self._attach(session, project_id, chapter_number, item)
                stored += 1
            except Exception as exc:  # noqa: BLE001 - 单角色失败不拖垮整批
                logger.warning("写入人物意义层失败 character=%s: %s", item.name, exc)

        if stored:
            await session.commit()
        logger.info(
            "人物意义层抽取完成 project=%s chapter=%s stored=%d",
            project_id, chapter_number, stored,
        )
        return {"stored": stored}

    @staticmethod
    async def _attach(
        session: Any, project_id: str, chapter_number: int, item: CharacterSignificance
    ) -> None:
        """把意义挂到该角色本章的 CharacterState.extra 上；行不存在则建一条最小行。

        建行是安全的：读侧对没有事实字段的行只渲染成「角色名：无特殊状态」。
        """
        from sqlalchemy import select

        from ..models.memory_layer import CharacterState

        row = (
            await session.execute(
                select(CharacterState).where(
                    CharacterState.project_id == project_id,
                    CharacterState.character_name == item.name,
                    CharacterState.chapter_number == chapter_number,
                )
            )
        ).scalars().first()

        payload = {
            "belief_shift": item.belief_shift,
            "cost": item.cost,
            "relational": item.relational,
            "unspoken": item.unspoken,
        }
        payload = {k: v for k, v in payload.items() if v}

        if row is None:
            row = CharacterState(
                project_id=project_id,
                character_name=item.name,
                chapter_number=chapter_number,
                extra={"significance": payload},
            )
            session.add(row)
            return

        # 先读后并整体重赋值：JSON 列必须换新对象才触发 SQLAlchemy 变更检测
        existing = row.extra if isinstance(row.extra, dict) else {}
        row.extra = {**existing, "significance": payload}

    # ------------------------------------------------------------------ 读侧
    async def build_significance_brief(
        self,
        *,
        project_id: str,
        chapter_number: int,
        involved_characters: Optional[List[str]] = None,
        session: Any = None,
    ) -> Optional[str]:
        """取每个角色**最近一次**的意义层，格式化为 `[人物意义层]` 段文本。

        无数据/异常 → None（不注入）。仅 DB 读，无 LLM。
        """
        try:
            async def _run(sess: Any) -> Optional[str]:
                from sqlalchemy import select

                from ..models.memory_layer import CharacterState

                rows = (
                    await sess.execute(
                        select(CharacterState)
                        .where(
                            CharacterState.project_id == project_id,
                            CharacterState.chapter_number < chapter_number,
                        )
                        .order_by(CharacterState.chapter_number.asc())
                    )
                ).scalars().all()

                # 同名取章号最大的一条（升序遍历后写即覆盖）
                latest: Dict[str, Dict[str, Any]] = {}
                for row in rows:
                    extra = row.extra if isinstance(row.extra, dict) else None
                    payload = (extra or {}).get("significance")
                    if isinstance(payload, dict) and payload:
                        latest[row.character_name] = payload
                if not latest:
                    return None

                names = list(latest)
                if involved_characters:
                    involved = set(involved_characters)
                    names.sort(key=lambda n: (n not in involved, n))
                return self._format_brief({n: latest[n] for n in names[:_BRIEF_MAX_CHARACTERS]})

            if session is not None:
                return await _run(session)

            from ..db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as own_session:
                return await _run(own_session)
        except Exception as exc:  # noqa: BLE001
            logger.warning("人物意义层读取失败（不影响生成）: %s", exc)
            return None

    @staticmethod
    def _format_brief(by_name: Dict[str, Dict[str, Any]]) -> Optional[str]:
        labels = (
            ("belief_shift", "现在相信/不再相信"),
            ("cost", "已付出的代价"),
            ("relational", "如何看待他人"),
            ("unspoken", "没说破的事"),
        )
        blocks: List[str] = []
        for name, payload in by_name.items():
            lines = [f"- **{name}**"]
            for key, label in labels:
                value = payload.get(key)
                if value:
                    lines.append(f"  - {label}：{value}")
            if len(lines) > 1:
                blocks.append("\n".join(lines))
        if not blocks:
            return None

        # ⚠️ 这段告诫是本特性成立的前提：不加约束地注入「意义」，模型会把它当台词
        # 或旁白**原句写出来**，比不注入更糟（AI 小说最典型的「说破」）。
        guard = (
            "以上是人物此刻的**底色**，不是可以写进正文的句子。\n"
            "硬性要求：\n"
            "1. 严禁以任何形式直接陈述上述内容——不得写成心理独白、旁白、台词或总结句；\n"
            "2. 只能通过**选择、反应、迟疑、回避、语气的细微差别**让读者自己感觉到；\n"
            "3. 「没说破的事」尤其不能说破——它的价值恰恰在于没说出口；\n"
            "4. 若本章情节用不上某条，就让它不出现，不要硬塞。"
        )
        return "\n\n".join(["\n\n".join(blocks), guard])
