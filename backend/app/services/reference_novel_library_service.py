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
from ..schemas.reference_novel import BeatLibrary, MemoryCard, StyleGuide
from ..utils.json_utils import (
    remove_think_tags,
    repair_json,
    sanitize_json_like_text,
    unwrap_markdown_json,
)
from .llm_service import LLMService
from .prompt_service import PromptService
from .web_search_service import WebSearchService
from .reference_reading_contract import FusionDNA, fallback_dna, fusion_materials, is_current, stamp

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
        by_id = {novel.id: novel for novel in result.scalars().all()}
        return [by_id[rid] for rid in dict.fromkeys(novel_ids) if rid in by_id]

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
            memory_card_context = combine(dimension_results, "pacing", "characters", "beats", "craft", "plot")
            beats_context = combine(dimension_results, "beats", "pacing", "plot")

            outline_prompt = await self.prompt_service.get_prompt("reference_outline_extraction")
            style_prompt = await self.prompt_service.get_prompt("reference_style_extraction")
            memory_card_prompt = await self.prompt_service.get_prompt("reference_memory_card_extraction")
            beats_prompt = await self.prompt_service.get_prompt("reference_beat_extraction")
            style_guide_prompt = await self.prompt_service.get_prompt("reference_style_guide_extraction")
            search_llm_config = await self.llm_service._resolve_search_llm_config()

            outline, style, memory_card, beat_library, style_guide = await asyncio.gather(
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
                self._extract_style_guide(
                    novel.title,
                    style_context,
                    user_id,
                    prompt_template=style_guide_prompt,
                    llm_config=search_llm_config,
                ),
            )

            # 大纲/风格样本都可能因「任务复述」被整份判废（返回空串）——保留旧档案，
            # 不用空值/垃圾覆盖；首次分析没有旧值时保持为空，界面会给提示
            novel.outline_content = outline or novel.outline_content
            novel.style_samples_content = style or novel.style_samples_content
            novel.memory_card = memory_card
            novel.beat_library = beat_library
            novel.style_guide = style_guide
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
        cleaned = remove_think_tags(generated)
        if not self._looks_like_task_echo(cleaned):
            return cleaned

        # 输出是任务复述（「理解任务需求：角色：经验丰富的小说策划编辑…」）
        # → 一次矫正重问，仍复述则返回空串（analyze() 保留旧档案）
        logger.warning("大纲输出疑似任务复述，矫正重问一次: %s", novel_title)
        retry = await self.llm_service.get_search_llm_response(
            system_prompt="你是专业的小说分析助手，擅长从搜索结果中提取和整理小说大纲与人物档案。",
            conversation_history=[
                {"role": "user", "content": filled},
                {"role": "assistant", "content": cleaned[:500]},
                {
                    "role": "user",
                    "content": (
                        "你刚才把任务要求复述了一遍，没有给出大纲。重新输出：\n"
                        "禁止出现「理解任务需求 / 分析请求 / 输出格式要求 / 任务 / 角色定位」等元话语，"
                        "第一行就必须是剧情大纲的内容本身。"
                    ),
                },
            ],
            temperature=0.4,
            max_tokens=1600,
            config_override=llm_config,
        )
        retry_cleaned = remove_think_tags(retry)
        return "" if self._looks_like_task_echo(retry_cleaned) else retry_cleaned

    # 元话语标记：命中任一即判定该段不是样本正文，而是任务复述/分析笔记/写作过程叙述。
    # 「样本/撰写」对虚构正文属罕见词，宁可错杀（10 段里留 3-4 段干净的就够用），
    # 也不能把元话语注入正文生成。
    _STYLE_META_MARKERS = (
        "分析请求", "分析师", "风格样本", "风格分析", "解构", "样本", "撰写",
        "任务：", "任务:", "输入：", "输入:", "输出：", "输出:",
        "要求：", "要求:", "以下是", "如下所示",
    )

    # 大纲任务复述标记：出现在开头即判定整份输出是任务复述而非大纲内容
    _OUTLINE_ECHO_MARKERS = (
        "理解任务需求", "分析请求", "输出格式要求", "任务需求",
        "角色：小说", "角色：经验丰富", "策划编辑", "任务：", "任务:",
    )

    @classmethod
    def _looks_like_task_echo(cls, text: str) -> bool:
        """大纲输出是否是任务复述（「理解任务需求：角色：经验丰富的小说策划编辑…」）。

        大纲的合法形态本来就是结构化 markdown，没法像样本那样按段过滤，
        只看开头 300 字符内是否出现任务复述标记（高置信、低误伤）。
        """
        head = (text or "")[:300]
        return any(marker in head for marker in cls._OUTLINE_ECHO_MARKERS)

    @classmethod
    def _clean_style_samples(cls, raw: str) -> str:
        """剔除 LLM 的任务复述/分析笔记，只保留样本正文段。

        线上实测（2026-08-14，两个变体）：搜索通道模型有时不给样本，而是
        ①复述任务（「分析请求：角色：小说风格分析师。任务：模仿……」），
        ②输出分析笔记/写作计划（「2. 解构《大奉打更人》风格：* 句式：短句为主…」
        「3. 构建10段样本：段1：开局破案/内心吐槽…」）。这类输出一旦入库，
        既在档案页展示垃圾，也会被 format_style_samples_for_prompt 原样注入正文
        生成。按段切分（--- 或空行）后丢弃：含元话语标记的段、markdown 标题/编号
        开头的段（提示词禁止样本带序号）、bullet 列表结构的段、含「段N：」计划的段；
        全部被丢弃则返回空串，由调用方决定重问或保留旧值。
        """
        if not raw or not raw.strip():
            return ""
        segments = [seg.strip() for seg in re.split(r"\n\s*-{3,}\s*\n|\n\s*\n", raw.strip()) if seg.strip()]
        clean: List[str] = []
        for seg in segments:
            if any(marker in seg for marker in cls._STYLE_META_MARKERS):
                continue
            # markdown 标题头或编号开头（提示词明确禁止样本带序号 → 带序号的是计划/说明）
            if re.match(r"^\s*(#{1,6}\s|\d+\s*[.、])", seg):
                continue
            # 段落编号引用（「段1：」「第7段」）与修订箭头：写作过程叙述
            # （thinking 模型把打磨过程写进答案，2026-08-14 线上第三变体）
            if re.search(r"第?\s*\d+\s*段|->|→", seg):
                continue
            # bullet 列表结构（≥2 行以 * - · 开头）是分析笔记，不是叙事正文
            bullet_lines = sum(1 for line in seg.splitlines() if re.match(r"^\s*[*\-·•]\s+", line))
            if bullet_lines >= 2:
                continue
            clean.append(seg)
        return "\n\n---\n\n".join(clean)

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
        cleaned = self._clean_style_samples(remove_think_tags(generated))
        if cleaned:
            return cleaned

        # 整份输出都是任务复述 → 一次矫正重问（与蓝图章纲补齐同款模式），仍不行则
        # 返回空串（analyze() 会保留旧档案，不用垃圾覆盖）
        logger.warning("风格样本输出疑似任务复述，矫正重问一次: %s", novel_title)
        retry = await self.llm_service.get_search_llm_response(
            system_prompt="你是专业的小说风格分析师，擅长从搜索结果中提取和模仿小说的写作风格。",
            conversation_history=[
                {"role": "user", "content": filled},
                {"role": "assistant", "content": remove_think_tags(generated)[:500]},
                {
                    "role": "user",
                    "content": (
                        "你刚才把任务要求复述了一遍，没有给出样本。重新输出：\n"
                        "禁止出现「分析请求 / 任务 / 输入 / 输出 / 要求 / 以下是」等元话语，"
                        "禁止标题与编号；第一行就必须是第一段样本的正文第一个字，段间用 --- 分隔。"
                    ),
                },
            ],
            temperature=0.4,
            max_tokens=1200,
            config_override=llm_config,
        )
        return self._clean_style_samples(remove_think_tags(retry))

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
            max_tokens=1800,
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

    async def _extract_style_guide(
        self,
        novel_title: str,
        search_results: str,
        user_id: int,
        *,
        prompt_template: Optional[str] = None,
        llm_config: Optional[Dict[str, Optional[str]]] = None,
    ) -> Optional[dict]:
        """抽取写法基准（可执行约束）；与桥段库同款软失败——抽不出不拖垮分析。"""
        prompt = prompt_template or await self.prompt_service.get_prompt("reference_style_guide_extraction")
        if not prompt:
            logger.warning("缺失 reference_style_guide_extraction 提示词，跳过写法基准抽取")
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
                max_tokens=1600,
                config_override=llm_config,
            )

        guide = await self.llm_service.generate_structured(
            prompt=filled,
            schema=StyleGuide,
            user_id=user_id,
            responder=_search_channel_responder,
            default=StyleGuide(),
        )
        data = guide.model_dump(exclude_defaults=True)
        if not data:
            logger.warning("参考小说《%s》写法基准抽取为空（资料不足或解析失败）", novel_title)
            return None
        return guide.model_dump()

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
        """单本提炼阅读动力，多本生成有分工、有取舍的统一方案。"""
        if not novels:
            return {}
        prompt_template = await self.prompt_service.get_prompt("reference_fusion")
        if not prompt_template:
            logger.warning("缺失 reference_fusion 提示词，使用临时参考方案")
            return self._build_fallback_fusion_dna(novels)
        filled = self.prompt_service.render_prompt(
            prompt_template,
            novel_count=len(novels),
            reference_materials=fusion_materials(novels),
        )
        try:
            generated = await self.llm_service.generate_structured(
                prompt=filled,
                schema=FusionDNA,
                user_id=user_id,
                max_tokens=4000,
                temperature=0.4,
                default=None,
            )
            if generated is None:
                return self._build_fallback_fusion_dna(novels)
            payload = generated.model_dump(by_alias=True)
            sources = [ref["from"] for ref in payload["structure_references"]]
            if len(sources) != len(novels) or set(sources) != {novel.title for novel in novels}:
                raise ValueError("融合必须覆盖每本参考且不得引入未选择的书")
            return stamp(payload, novels, generated=True)
        except Exception as exc:
            logger.warning("融合DNA生成/校验失败: %s, 使用临时参考方案", exc)
            return self._build_fallback_fusion_dna(novels)

    @staticmethod
    def _build_fallback_fusion_dna(novels: List[ReferenceNovel]) -> Dict[str, Any]:
        return fallback_dna(novels)

    def format_fusion_dna_for_prompt(self, fusion_dna: Optional[Dict[str, Any]]) -> str:
        """将融合DNA格式化为可注入 prompt 的文本。"""
        if not fusion_dna:
            return ""
        if fusion_dna.get("version") == 2:
            from .reference_reading_contract import format_contract
            return format_contract(fusion_dna)
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

    # 概念对话补充素材的每书预算；融合分析另按语义字段独立分配预算。
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
                # 诚实标注：这些样本是 LLM 根据检索印象仿写的，不是原文摘录——
                # 标成「原文」会让下游把仿写误差当成该书的真实语感来学
                samples.append(
                    f"=== 《{novel.title}》语感示例（AI 仿写，非原文摘录）===\n"
                    f"{content[: self._PROMPT_STYLE_SAMPLE_CHARS]}"
                )
        return "\n\n".join(samples)

    # 写法基准注入的字段顺序与中文标签（空字段不注入）
    _STYLE_GUIDE_FIELDS: List[tuple[str, str]] = [
        ("narrative_pov", "叙事视角"),
        ("sentence_rhythm", "句式节奏"),
        ("dialogue_style", "对白"),
        ("description_density", "描写密度"),
        ("paragraphing", "分段"),
        ("emotion_expression", "情绪表达"),
    ]

    def format_style_guide_for_prompt(self, novels: List[ReferenceNovel]) -> str:
        """写法基准 → 可注入文本。多本参考时取**第一本**有基准的（绑定顺序即优先级）：
        可执行约束不能像 fusion_dna 那样「融合」——两套句式节奏拼在一起就都不成立了。
        """
        for novel in novels or []:
            guide = getattr(novel, "style_guide", None)
            if not isinstance(guide, dict):
                continue
            lines: List[str] = []
            for key, label in self._STYLE_GUIDE_FIELDS:
                value = guide.get(key)
                if isinstance(value, str) and value.strip():
                    lines.append(f"- {label}：{value.strip()}")
            devices = [str(v).strip() for v in guide.get("signature_devices") or [] if str(v).strip()]
            if devices:
                lines.append(f"- 标志性手法：{'；'.join(devices[:4])}")
            forbidden = [str(v).strip() for v in guide.get("forbidden") or [] if str(v).strip()]
            if forbidden:
                lines.append(f"- 禁用写法：{'；'.join(forbidden[:5])}")
            if not lines:
                continue
            return (
                f"以下写法基准提炼自《{novel.title}》的写法分析，只约束「怎么写」，"
                "不约束写什么；与本书设定冲突时以本书为准：\n" + "\n".join(lines)
            )
        return ""

    # 记忆卡注入的字段优先级：剧情思考类在前（冲突模版/爽点/伏笔/悬念），
    # 其后是节奏与写法。此前是整段 JSON dump 再拦腰截 800 字——缩进和引号吃掉
    # 大半预算，截断点落在哪个字段全凭运气，排前面的 genre/target_audience
    # 这类低价值字段反而永远活着。
    _MEMORY_CARD_PROMPT_FIELDS: List[tuple[str, str]] = [
        ("reader_expectation", "读者期待"),
        ("payoff_rhythm", "铺垫兑现与余波"),
        ("relationship_pull", "关系牵挂"),
        ("main_conflict_pattern", "主线冲突模版"),
        ("core_selling_point", "核心卖点"),
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

    @staticmethod
    def _join_card_values(value: Any, *, limit: int = 3) -> str:
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            return "；".join(items[:limit])
        if isinstance(value, str):
            return value.strip()
        return ""

    def format_recommend_compass_for_concept(
        self,
        novels: Optional[List[ReferenceNovel]] = None,
        fusion_dna: Optional[Dict[str, Any]] = None,
    ) -> str:
        """概念选择题的推荐罗盘：核心底层逻辑 + 读者最大魅力点。

        给 LLM 一个短、难忽略的约束块——选项可以换题材换人物，但被标「推荐」的那一项
        必须转译这里的发动机和魅力，而不是抄原作人名情节。
        """
        blocks: List[str] = []
        for novel in novels or []:
            card = getattr(novel, "memory_card", None) or {}
            if not isinstance(card, dict):
                card = {}
            engine = self._join_card_values(card.get("main_conflict_pattern"))
            if not engine:
                engine = self._join_card_values(card.get("takeaways"), limit=2)
            charm = self._join_card_values(card.get("core_selling_point"))
            cool = self._join_card_values(card.get("cool_point_patterns"))
            if cool:
                charm = f"{charm}；{cool}" if charm else cool
            if not engine and not charm:
                continue
            title = getattr(novel, "title", None) or "参考小说"
            lines = [f"《{title}》"]
            if engine:
                lines.append(f"- 核心底层逻辑：{engine}")
            if charm:
                lines.append(f"- 读者最大魅力点：{charm}")
            blocks.append("\n".join(lines))

        if isinstance(fusion_dna, dict) and (not blocks or is_current(fusion_dna, novels or [])):
            engine = str(fusion_dna.get("narrative_strategy") or "").strip()
            charm_parts = [
                str(fusion_dna.get("style_fingerprint") or "").strip(),
            ]
            loop = fusion_dna.get("reader_loop") or {}
            charm_parts.extend(str(loop.get(key) or "").strip() for key in ("desire", "promise", "payoff"))
            techniques = fusion_dna.get("key_techniques") or []
            if isinstance(techniques, list):
                charm_parts.append("；".join(str(item).strip() for item in techniques[:3] if str(item).strip()))
            charm = "；".join(part for part in charm_parts if part)
            if engine or charm:
                lines = ["融合创作DNA"]
                if engine:
                    lines.append(f"- 核心底层逻辑：{engine}")
                if charm:
                    lines.append(f"- 读者最大魅力点：{charm}")
                blocks.insert(0, "\n".join(lines))

        if not blocks:
            return ""
        return (
            "## 选项推荐罗盘（绑定了参考小说，必须遵守）\n"
            "出 single_choice 时必须且只能把其中一个选项标 recommended=true，"
            "并写一句不超过 24 字的 recommend_reason。\n"
            "被推荐的选项必须把下面的「核心底层逻辑」转译成当前问题的答案"
            "（换题材、换人物、换世界观都可以），并让读者感到同一类「最大魅力点」。\n"
            "禁止抄原作人名/情节；禁止把「全不满意/自由描述」标成推荐。\n"
            + "\n\n".join(blocks)
        )

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
