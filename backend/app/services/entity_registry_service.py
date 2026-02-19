# AIMETA P=实体注册服务_实体注册消歧检测|R=注册_消歧_别名匹配_置信度评分|NR=不含LLM生成|E=EntityRegistryService|X=internal|A=实体管理|D=sqlalchemy|S=db|RD=./README.ai
"""
实体注册服务 (EntityRegistryService)

提供：
1. 从蓝图自动注册实体（confidence=1.0）
2. 从章节内容自动检测并注册新实体
3. 别名消歧：编辑距离匹配 + 别名表查询
4. 置信度评分：>=0.8 自动注册，0.5-0.8 标记 warning，<0.5 疑似幻觉
"""
import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.entity_registry import EntityAlias, EntityRegistry

logger = logging.getLogger(__name__)


class EntityRegistryService:
    """实体注册/消歧/检测服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def register_entity(
        self,
        *,
        project_id: str,
        entity_type: str,
        canonical_name: str,
        description: Optional[str] = None,
        first_chapter: Optional[int] = None,
        source: str = "auto_detected",
        confidence: float = 1.0,
        properties: Optional[dict] = None,
        aliases: Optional[List[str]] = None,
    ) -> EntityRegistry:
        """注册一个新实体，如果已存在同名实体则更新。"""
        existing = await self._find_by_name(project_id, canonical_name)
        if existing:
            if confidence > existing.confidence:
                existing.confidence = confidence
            if description and not existing.description:
                existing.description = description
            if properties:
                existing.properties = {**(existing.properties or {}), **properties}
            await self.session.flush()
            if aliases:
                await self._add_aliases(existing.id, aliases)
            return existing

        entity = EntityRegistry(
            project_id=project_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            description=description,
            first_chapter=first_chapter,
            source=source,
            confidence=confidence,
            properties=properties or {},
            is_active=True,
        )
        self.session.add(entity)
        await self.session.flush()

        if aliases:
            await self._add_aliases(entity.id, aliases)

        logger.info(
            "注册实体: project=%s type=%s name=%s confidence=%.2f source=%s",
            project_id, entity_type, canonical_name, confidence, source,
        )
        return entity

    async def register_from_blueprint(
        self,
        project_id: str,
        blueprint: dict,
    ) -> List[EntityRegistry]:
        """从蓝图自动注册角色、地点等实体，confidence=1.0。"""
        registered: List[EntityRegistry] = []

        for char in blueprint.get("characters", []):
            name = char.get("name")
            if not name:
                continue
            aliases = []
            if char.get("nickname"):
                aliases.append(char["nickname"])
            if char.get("title"):
                aliases.append(char["title"])
            entity = await self.register_entity(
                project_id=project_id,
                entity_type="character",
                canonical_name=name,
                description=char.get("description") or char.get("role"),
                source="blueprint",
                confidence=1.0,
                properties={
                    k: v for k, v in char.items()
                    if k not in ("name", "description", "role", "nickname", "title") and v
                },
                aliases=aliases,
            )
            registered.append(entity)

        for loc in blueprint.get("locations", []):
            name = loc.get("name")
            if not name:
                continue
            entity = await self.register_entity(
                project_id=project_id,
                entity_type="location",
                canonical_name=name,
                description=loc.get("description"),
                source="blueprint",
                confidence=1.0,
            )
            registered.append(entity)

        for org in blueprint.get("organizations", []):
            name = org.get("name")
            if not name:
                continue
            entity = await self.register_entity(
                project_id=project_id,
                entity_type="organization",
                canonical_name=name,
                description=org.get("description"),
                source="blueprint",
                confidence=1.0,
            )
            registered.append(entity)

        await self.session.commit()
        logger.info("从蓝图注册实体完成: project=%s count=%d", project_id, len(registered))
        return registered

    async def get_all_entities(
        self,
        project_id: str,
        entity_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[EntityRegistry]:
        """获取项目的所有实体。"""
        stmt = select(EntityRegistry).where(EntityRegistry.project_id == project_id)
        if entity_type:
            stmt = stmt.where(EntityRegistry.entity_type == entity_type)
        if active_only:
            stmt = stmt.where(EntityRegistry.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def resolve_alias(
        self,
        project_id: str,
        name: str,
    ) -> Optional[str]:
        """将别名解析为正式名称。先精确匹配别名表，再尝试编辑距离模糊匹配。"""
        entity = await self._find_by_name(project_id, name)
        if entity:
            return entity.canonical_name

        alias_result = await self.session.execute(
            select(EntityAlias)
            .join(EntityRegistry)
            .where(
                EntityRegistry.project_id == project_id,
                EntityAlias.alias == name,
                EntityRegistry.is_active == True,
            )
        )
        alias_record = alias_result.scalars().first()
        if alias_record:
            entity_result = await self.session.execute(
                select(EntityRegistry).where(EntityRegistry.id == alias_record.entity_id)
            )
            entity = entity_result.scalars().first()
            if entity:
                return entity.canonical_name

        all_entities = await self.get_all_entities(project_id)
        best_match = None
        best_distance = float("inf")
        threshold = max(2, len(name) // 3)

        for entity in all_entities:
            dist = self._edit_distance(name, entity.canonical_name)
            if dist < best_distance and dist <= threshold:
                best_distance = dist
                best_match = entity.canonical_name

            for alias_obj in (entity.aliases or []):
                dist = self._edit_distance(name, alias_obj.alias)
                if dist < best_distance and dist <= threshold:
                    best_distance = dist
                    best_match = entity.canonical_name

        return best_match

    async def build_alias_map(self, project_id: str) -> Dict[str, str]:
        """构建别名→正式名映射表，供批量处理使用。"""
        entities = await self.get_all_entities(project_id)
        alias_map: Dict[str, str] = {}
        for entity in entities:
            alias_map[entity.canonical_name] = entity.canonical_name
            for alias_obj in (entity.aliases or []):
                alias_map[alias_obj.alias] = entity.canonical_name
        return alias_map

    async def detect_unregistered_names(
        self,
        project_id: str,
        text: str,
        known_names: Optional[Set[str]] = None,
    ) -> List[Dict]:
        """检测文本中可能未注册的实体名称。"""
        if known_names is None:
            entities = await self.get_all_entities(project_id)
            known_names = set()
            for e in entities:
                known_names.add(e.canonical_name)
                for a in (e.aliases or []):
                    known_names.add(a.alias)

        name_pattern = re.compile(
            r"(?:[\u4e00-\u9fff]{2,4}(?:老|师|哥|弟|姐|妹|爷|奶|叔|婶|先生|女士|大人|殿下|陛下)?)"
        )
        candidates = set(name_pattern.findall(text))

        common_words = {
            "他们", "她们", "我们", "自己", "大家", "所有", "这个", "那个",
            "什么", "怎么", "如何", "为什么", "因为", "所以", "但是", "然而",
            "虽然", "虽说", "不过", "可是", "而且", "并且", "或者", "还是",
            "一个", "两个", "三个", "一些", "许多", "很多", "非常", "十分",
        }
        candidates -= common_words
        candidates -= known_names

        unregistered = []
        for name in candidates:
            resolved = await self.resolve_alias(project_id, name)
            if resolved:
                continue
            unregistered.append({
                "name": name,
                "occurrences": text.count(name),
            })

        return sorted(unregistered, key=lambda x: x["occurrences"], reverse=True)

    async def _find_by_name(self, project_id: str, name: str) -> Optional[EntityRegistry]:
        result = await self.session.execute(
            select(EntityRegistry).where(
                EntityRegistry.project_id == project_id,
                EntityRegistry.canonical_name == name,
            )
        )
        return result.scalars().first()

    async def _add_aliases(self, entity_id: int, aliases: List[str]) -> None:
        existing_result = await self.session.execute(
            select(EntityAlias.alias).where(EntityAlias.entity_id == entity_id)
        )
        existing_aliases = {row[0] for row in existing_result}
        for alias in aliases:
            if alias and alias not in existing_aliases:
                self.session.add(EntityAlias(
                    entity_id=entity_id,
                    alias=alias,
                    alias_type="alias",
                ))

    @staticmethod
    def _edit_distance(s1: str, s2: str) -> int:
        """计算两个字符串的编辑距离（Levenshtein）。"""
        if len(s1) < len(s2):
            return EntityRegistryService._edit_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        return prev_row[-1]
