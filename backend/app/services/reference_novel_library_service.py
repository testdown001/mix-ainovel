# AIMETA P=参考小说库服务_持久化与分析|R=参考小说CRUD_分析流程|NR=不含API|E=ReferenceNovelLibraryService|X=internal|A=业务服务|D=sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ReferenceNovel, User
from ..schemas.reference_novel import BeatLibrary, MemoryCard
from ..utils.json_utils import (
    remove_think_tags,
    repair_json,
    sanitize_json_like_text,
    unwrap_markdown_json,
)
from .llm_service import LLMService
from .prompt_service import PromptService
from .web_search_service import WebSearchService

logger = logging.getLogger(__name__)


class ReferenceNovelLibraryService:
    _STATUS_PENDING = "pending"
    _STATUS_ANALYZING = "analyzing"
    _STATUS_READY = "ready"
    _STATUS_FAILED = "failed"

    def __init__(self, session: AsyncSession):
        self.session = session
        self.prompt_service = PromptService(session)
        self.llm_service = LLMService(session)
        self.search_service = WebSearchService(session)

    async def list_all(self, search: Optional[str] = None) -> List[ReferenceNovel]:
        stmt = select(ReferenceNovel).order_by(ReferenceNovel.created_at.desc())
        if search:
            stmt = stmt.where(ReferenceNovel.title.ilike(f"%{search}%"))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, novel_id: int) -> Optional[ReferenceNovel]:
        return await self.session.get(ReferenceNovel, novel_id)

    async def get_by_ids(self, novel_ids: List[int]) -> List[ReferenceNovel]:
        if not novel_ids:
            return []
        stmt = select(ReferenceNovel).where(ReferenceNovel.id.in_(novel_ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_title(self, title: str) -> Optional[ReferenceNovel]:
        stmt = select(ReferenceNovel).where(ReferenceNovel.title == title.strip())
        result = await self.session.execute(stmt)
        return result.scalars().one_or_none()

    async def create(self, user_id: int, title: str, author: Optional[str] = None, genre: Optional[str] = None) -> ReferenceNovel:
        normalized_title = title.strip()
        if not normalized_title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="参考小说标题不能为空")
        existing = await self.get_by_title(normalized_title)
        if existing:
            # 如果已存在，更新作者和题材信息
            if (author or genre) and (existing.author != author or existing.genre != genre):
                existing.author = author or existing.author
                existing.genre = genre or existing.genre
                await self.session.commit()
                await self.session.refresh(existing)
            return existing
        novel = ReferenceNovel(
            title=normalized_title,
            user_id=user_id,
            status=self._STATUS_PENDING,
            author=author,
            genre=genre
        )
        self.session.add(novel)
        try:
            await self.session.commit()
            await self.session.refresh(novel)
        except IntegrityError:
            await self.session.rollback()
            existing = await self.get_by_title(normalized_title)
            if existing:
                return existing
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="参考小说已存在")
        return novel

    async def update(self, novel_id: int, user: User, payload: Dict[str, Any]) -> ReferenceNovel:
        novel = await self.get_by_id(novel_id)
        if not novel:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="参考小说不存在")
        if novel.user_id != user.id and not user.is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="无权修改该参考小说")

        if "memory_card" in payload:
            payload["memory_card"] = self._normalize_memory_card_payload(payload["memory_card"])

        for key, value in payload.items():
            if hasattr(novel, key):
                setattr(novel, key, value)

        await self.session.commit()
        await self.session.refresh(novel)
        return novel

    async def delete(self, novel_id: int, user: User) -> None:
        novel = await self.get_by_id(novel_id)
        if not novel:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="参考小说不存在")
        if novel.user_id != user.id and not user.is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="无权删除该参考小说")

        await self.session.delete(novel)
        await self.session.commit()

    async def analyze(self, novel_id: int, user_id: int) -> ReferenceNovel:
        novel = await self.get_by_id(novel_id)
        if not novel:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="参考小说不存在")

        novel.status = self._STATUS_ANALYZING
        novel.error_message = None
        await self.session.commit()
        await self.session.refresh(novel)

        try:
            # 多维度检索：每路抽取吃自己需要的维度，而不是全部吃同一段百科式摘要。
            # 单维度失败降级（combine_dimension_texts 会回退到可用维度），全失败才抛。
            dimension_results = await self.search_service.search_novel_dimensions(novel_name=novel.title)
            combine = self.search_service.combine_dimension_texts
            outline_context = combine(dimension_results, "plot", "characters")
            style_context = combine(dimension_results, "craft", "plot")
            memory_card_context = combine(dimension_results, "pacing", "craft", "plot")
            beats_context = combine(dimension_results, "beats", "pacing", "plot")

            outline_prompt = await self.prompt_service.get_prompt("reference_outline_extraction")
            style_prompt = await self.prompt_service.get_prompt("reference_style_extraction")
            memory_card_prompt = await self.prompt_service.get_prompt("reference_memory_card_extraction")
            beats_prompt = await self.prompt_service.get_prompt("reference_beat_extraction")
            search_llm_config = await self.llm_service._resolve_search_llm_config()

            outline, style, memory_card, beat_library = await asyncio.gather(
                self._extract_outline(
                    novel.title,
                    outline_context,
                    user_id,
                    prompt_template=outline_prompt,
                    llm_config=search_llm_config,
                ),
                self._extract_style(
                    novel.title,
                    style_context,
                    user_id,
                    prompt_template=style_prompt,
                    llm_config=search_llm_config,
                ),
                self._extract_memory_card(
                    novel.title,
                    memory_card_context,
                    user_id,
                    prompt_template=memory_card_prompt,
                    llm_config=search_llm_config,
                ),
                self._extract_beat_library(
                    novel.title,
                    beats_context,
                    user_id,
                    prompt_template=beats_prompt,
                    llm_config=search_llm_config,
                ),
            )

            novel.outline_content = outline
            novel.style_samples_content = style
            novel.memory_card = memory_card
            novel.beat_library = beat_library
            novel.status = self._STATUS_READY
            novel.error_message = None
            await self.session.commit()
            await self.session.refresh(novel)
            return novel

        except Exception as exc:  # pragma: no cover - 保障状态回退
            novel.status = self._STATUS_FAILED
            novel.error_message = str(exc)
            await self.session.commit()
            logger.exception("分析参考小说失败: %s", exc)
            raise

    async def _extract_outline(
        self,
        novel_title: str,
        search_results: str,
        user_id: int,
        *,
        prompt_template: Optional[str] = None,
        llm_config: Optional[Dict[str, Optional[str]]] = None,
    ) -> str:
        prompt = prompt_template or await self.prompt_service.get_prompt("reference_outline_extraction")
        if not prompt:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="缺失大纲提取提示词")
        filled = self.prompt_service.render_prompt(
            prompt,
            novel_title=novel_title,
            search_results=search_results,
        )
        generated = await self.llm_service.get_search_llm_response(
            system_prompt="你是专业的小说分析助手，擅长从搜索结果中提取和整理小说大纲与人物档案。",
            conversation_history=[{"role": "user", "content": filled}],
            temperature=0.3,
            max_tokens=1600,
            config_override=llm_config,
        )
        return remove_think_tags(generated)

    async def _extract_style(
        self,
        novel_title: str,
        search_results: str,
        user_id: int,
        *,
        prompt_template: Optional[str] = None,
        llm_config: Optional[Dict[str, Optional[str]]] = None,
    ) -> str:
        prompt = prompt_template or await self.prompt_service.get_prompt("reference_style_extraction")
        if not prompt:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="缺失风格提取提示词")
        filled = self.prompt_service.render_prompt(
            prompt,
            novel_title=novel_title,
            search_results=search_results,
        )
        generated = await self.llm_service.get_search_llm_response(
            system_prompt="你是专业的小说风格分析师，擅长从搜索结果中提取和模仿小说的写作风格。",
            conversation_history=[{"role": "user", "content": filled}],
            temperature=0.3,
            max_tokens=1200,
            config_override=llm_config,
        )
        return remove_think_tags(generated)

    async def _extract_memory_card(
        self,
        novel_title: str,
        search_results: str,
        user_id: int,
        *,
        prompt_template: Optional[str] = None,
        llm_config: Optional[Dict[str, Optional[str]]] = None,
    ) -> Optional[dict]:
        prompt = prompt_template or await self.prompt_service.get_prompt("reference_memory_card_extraction")
        if not prompt:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="缺失记忆卡提取提示词")
        filled = self.prompt_service.render_prompt(
            prompt,
            novel_title=novel_title,
            search_results=search_results,
        )
        generated = await self.llm_service.get_search_llm_response(
            system_prompt="你是专业的小说分析助手，擅长从搜索结果中提取小说的核心创作记忆卡。请以合法 JSON 格式回复。",
            conversation_history=[{"role": "user", "content": filled}],
            temperature=0.3,
            max_tokens=1200,
            config_override=llm_config,
        )
        payload = remove_think_tags(generated).strip()
        if not payload:
            return None

        normalized = unwrap_markdown_json(payload)
        sanitized = sanitize_json_like_text(normalized)
        repaired = repair_json(sanitized)
        try:
            parsed = json.loads(repaired)
        except json.JSONDecodeError:
            logger.warning("记忆卡 JSON 解析失败，尝试修复: %s", payload[:200])
            return None

        memory_card = self._normalize_memory_card_payload(parsed)
        if memory_card is None:
            logger.warning("记忆卡 JSON 缺少有效字段，已忽略: %s", payload[:200])
        return memory_card

    async def _extract_beat_library(
        self,
        novel_title: str,
        search_results: str,
        user_id: int,
        *,
        prompt_template: Optional[str] = None,
        llm_config: Optional[Dict[str, Optional[str]]] = None,
    ) -> Optional[dict]:
        """抽取桥段库：情境→手法的可检索条目 + 全书级结构手法。

        软失败：桥段是增量能力，抽不出来不应让整次分析失败（老三样照旧可用），
        但要记日志——静默的空库和「分析成功」看起来一样，排查时得知道是这里没料。
        """
        prompt = prompt_template or await self.prompt_service.get_prompt("reference_beat_extraction")
        if not prompt:
            logger.warning("缺失 reference_beat_extraction 提示词，跳过桥段库抽取")
            return None
        filled = self.prompt_service.render_prompt(
            prompt,
            novel_title=novel_title,
            search_results=search_results,
        )

        async def _search_channel_responder(p: str, system_prompt: str) -> str:
            return await self.llm_service.get_search_llm_response(
                system_prompt=system_prompt,
                conversation_history=[{"role": "user", "content": p}],
                temperature=0.3,
                max_tokens=3200,
                config_override=llm_config,
            )

        library = await self.llm_service.generate_structured(
            prompt=filled,
            schema=BeatLibrary,
            user_id=user_id,
            responder=_search_channel_responder,
            default=BeatLibrary(),
        )
        beats = [beat for beat in library.beats if beat.situation.strip()]
        if not beats:
            logger.warning("参考小说《%s》桥段库抽取为空（资料不足或解析失败）", novel_title)
            structure = library.structure.model_dump(exclude_defaults=True)
            return {"beats": [], "structure": structure} if structure else None
        return BeatLibrary(beats=beats, structure=library.structure).model_dump()

    @staticmethod
    def _normalize_memory_card_key(key: str) -> str:
        normalized = key.strip().replace("-", "_").replace(" ", "_")
        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        return normalized.lower().strip("_")

    @classmethod
    def _normalize_memory_card_payload(cls, payload: Any) -> Optional[dict]:
        if not isinstance(payload, dict):
            return None

        candidates: List[dict] = [payload]
        for wrapper_key in ("memory_card", "memoryCard", "card", "data", "result"):
            wrapped = payload.get(wrapper_key)
            if isinstance(wrapped, dict):
                candidates.append(wrapped)

        for candidate in candidates:
            normalized_candidate = {
                cls._normalize_memory_card_key(str(key)): value
                for key, value in candidate.items()
            }
            normalized = MemoryCard.model_validate(normalized_candidate).model_dump(exclude_defaults=True)
            if normalized:
                return normalized

        return None

    async def generate_fusion_dna(self, novels: List[ReferenceNovel], user_id: int) -> Dict[str, Any]:
        """从多本参考小说中提炼融合创作DNA。"""
        if not novels:
            return {}
        if len(novels) == 1:
            novel = novels[0]
            mc = novel.memory_card or {}
            return {
                "narrative_strategy": f"以《{novel.title}》为核心参考，借鉴其叙事结构和风格",
                "style_fingerprint": mc.get("dialogue_style", "") or "参考原作风格",
                "structure_references": [{"from": novel.title, "take": "整体叙事框架", "adapt": "结合本作世界观调整"}],
                "avoidance_list": [f"不要照搬《{novel.title}》的标志性设定和桥段"],
                "blended_pacing": mc.get("pacing_traits", "") or "参考原作节奏",
                "dialogue_style": mc.get("dialogue_style", "") or "参考原作对话风格",
                "scene_rhythm": mc.get("emotion_control_pattern", "") or "参考原作场景节奏",
                "key_techniques": mc.get("takeaways", [])[:5] if mc.get("takeaways") else [],
            }

        prompt_template = await self.prompt_service.get_prompt("reference_fusion")
        if not prompt_template:
            logger.warning("缺失 reference_fusion 提示词，回退到简单拼接")
            return self._build_fallback_fusion_dna(novels)

        materials_parts: List[str] = []
        for novel in novels:
            parts = [f"### 《{novel.title}》（{novel.author or '未知作者'}）"]
            if novel.outline_content:
                parts.append(f"**大纲摘要**：\n{novel.outline_content[:800]}")
            if novel.style_samples_content:
                samples = novel.style_samples_content[:600]
                parts.append(f"**风格样本**：\n{samples}")
            if novel.memory_card:
                card_text = json.dumps(novel.memory_card, ensure_ascii=False, indent=2)
                parts.append(f"**创作记忆卡**：\n{card_text[:800]}")
            materials_parts.append("\n".join(parts))

        reference_materials = "\n\n---\n\n".join(materials_parts)
        filled = self.prompt_service.render_prompt(
            prompt_template,
            novel_count=len(novels),
            reference_materials=reference_materials,
        )

        try:
            generated = await self.llm_service.generate(
                filled,
                user_id=user_id,
                max_tokens=2000,
                response_format="json_object",
            )
            payload = remove_think_tags(generated).strip()
            return json.loads(payload)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("融合DNA生成/解析失败: %s, 回退到简单融合", exc)
            return self._build_fallback_fusion_dna(novels)

    @staticmethod
    def _build_fallback_fusion_dna(novels: List[ReferenceNovel]) -> Dict[str, Any]:
        """LLM 不可用时的简单融合回退。"""
        titles = [n.title for n in novels]
        all_takeaways: List[str] = []
        for n in novels:
            mc = n.memory_card or {}
            all_takeaways.extend(mc.get("takeaways", [])[:2])
        return {
            "narrative_strategy": f"融合借鉴{'/'.join(titles)}的各自优势",
            "style_fingerprint": "综合多部参考作品的风格特点",
            "structure_references": [
                {"from": t, "take": "核心叙事结构", "adapt": "结合本作调整"}
                for t in titles
            ],
            "avoidance_list": [f"不要直接复刻《{t}》的标志性设定" for t in titles],
            "blended_pacing": "参考多部作品的节奏优势",
            "dialogue_style": "综合参考",
            "scene_rhythm": "根据场景类型灵活切换",
            "key_techniques": all_takeaways[:5],
        }

    def format_fusion_dna_for_prompt(self, fusion_dna: Optional[Dict[str, Any]]) -> str:
        """将融合DNA格式化为可注入 prompt 的文本。"""
        if not fusion_dna:
            return ""
        parts = []
        if fusion_dna.get("narrative_strategy"):
            parts.append(f"【叙事策略】{fusion_dna['narrative_strategy']}")
        if fusion_dna.get("style_fingerprint"):
            parts.append(f"【风格指纹】{fusion_dna['style_fingerprint']}")
        if fusion_dna.get("blended_pacing"):
            parts.append(f"【节奏策略】{fusion_dna['blended_pacing']}")
        if fusion_dna.get("dialogue_style"):
            parts.append(f"【对话风格】{fusion_dna['dialogue_style']}")
        if fusion_dna.get("scene_rhythm"):
            parts.append(f"【场景节奏】{fusion_dna['scene_rhythm']}")

        refs = fusion_dna.get("structure_references", [])
        if refs:
            ref_lines = []
            for r in refs[:5]:
                ref_lines.append(f"  - 从《{r.get('from', '?')}》借鉴：{r.get('take', '')}（变形：{r.get('adapt', '')}）")
            parts.append("【结构借鉴】\n" + "\n".join(ref_lines))

        avoidance = fusion_dna.get("avoidance_list", [])
        if avoidance:
            parts.append("【禁止复刻】\n  - " + "\n  - ".join(avoidance[:6]))

        techniques = fusion_dna.get("key_techniques", [])
        if techniques:
            parts.append("【核心技法】\n  - " + "\n  - ".join(techniques[:5]))

        return "\n\n".join(parts)

    # 注入 prompt 的每本参考素材截断上限（对齐 generate_fusion_dna 的 800/600/800 风格）：
    # 概念对话每轮都会重注这些素材，零截断会造成 token 膨胀。
    _PROMPT_OUTLINE_CHARS = 800
    _PROMPT_STYLE_SAMPLE_CHARS = 600
    _PROMPT_MEMORY_CARD_CHARS = 800

    def format_for_concept_prompt(self, novels: List[ReferenceNovel]) -> str:
        sections: List[str] = []
        for novel in novels:
            outline = (novel.outline_content or "")[: self._PROMPT_OUTLINE_CHARS]
            sections.append(f"参考小说：{novel.title} ({novel.author or '未知'})\n{outline}")
        return "\n\n".join(sections)

    def format_style_samples_for_prompt(self, novels: List[ReferenceNovel]) -> str:
        samples: List[str] = []
        for novel in novels:
            content = novel.style_samples_content
            if content:
                samples.append(f"=== {novel.title} ===\n{content[: self._PROMPT_STYLE_SAMPLE_CHARS]}")
        return "\n\n".join(samples)

    # 记忆卡注入的字段优先级：剧情思考类在前（冲突模版/爽点/伏笔/悬念），
    # 其后是节奏与写法。此前是整段 JSON dump 再拦腰截 800 字——缩进和引号吃掉
    # 大半预算，截断点落在哪个字段全凭运气，排前面的 genre/target_audience
    # 这类低价值字段反而永远活着。
    _MEMORY_CARD_PROMPT_FIELDS: List[tuple[str, str]] = [
        ("main_conflict_pattern", "主线冲突模版"),
        ("cool_point_patterns", "爽点模式"),
        ("foreshadowing_techniques", "伏笔技法"),
        ("suspense_techniques", "悬念技法"),
        ("pacing_traits", "节奏特点"),
        ("emotion_control_pattern", "情绪控制"),
        ("narrative_pov", "叙述视角"),
        ("dialogue_style", "对话风格"),
        ("takeaways", "可复用要点"),
        ("risks", "风险提醒"),
    ]

    def format_memory_card_for_prompt(self, novels: List[ReferenceNovel]) -> str:
        cards: List[str] = []
        for novel in novels:
            data = novel.memory_card or {}
            lines: List[str] = []
            for key, label in self._MEMORY_CARD_PROMPT_FIELDS:
                value = data.get(key)
                if isinstance(value, list):
                    items = [str(v).strip() for v in value if str(v).strip()]
                    if items:
                        lines.append(f"- {label}：{'；'.join(items[:4])}")
                elif isinstance(value, str) and value.strip():
                    lines.append(f"- {label}：{value.strip()}")
            if not lines:
                continue
            block = f"参考小说：{novel.title}\n" + "\n".join(lines)
            cards.append(block[: self._PROMPT_MEMORY_CARD_CHARS])
        return "\n\n".join(cards)
