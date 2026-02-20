# AIMETA P=流水线提示词Mixin|R=情感表达_任务模式_提示词拼接|NR=不含API路由|E=PipelinePromptMixin|X=internal|A=Mixin|D=none|S=none|RD=./README.ai
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from ..core.constants import CHAPTER_WORD_COUNT_RULE
from ..utils.json_utils import remove_think_tags

logger = logging.getLogger(__name__)


class PipelinePromptMixin:
    """流水线提示词构建相关方法。"""

    @staticmethod
    def _build_emotion_expression_brief(completed_chapters: List[Dict[str, Any]]) -> str:
        """构建情绪表达去模板化约束，减少"愤怒=握拳+指节发白"等重复句式。"""
        recent_chapters = sorted(
            completed_chapters or [],
            key=lambda item: item.get("chapter_number", 0),
        )[-6:]
        observed_pool = "\n".join(
            [
                (item.get("opening_excerpt") or "") + "\n" + (item.get("ending_excerpt") or "") + "\n" + (item.get("summary") or "")
                for item in recent_chapters
            ]
        )
        phrase_bank = (
            "握紧拳头",
            "指节发白",
            "目光死死",
            "死死盯",
            "咬紧牙关",
            "胸腔发麻",
            "掌心",
            "血痕",
            "青筋暴起",
            "怒火中烧",
            "太阳穴突突",
        )
        observed = [phrase for phrase in phrase_bank if phrase and phrase in observed_pool]
        observed_text = "、".join(observed[:8]) if observed else "近期未检测到固定短语，但仍需主动避免模板化怒意描写"
        return "\n".join(
            [
                "同一情绪必须用不同表达路径，不得复用固定模板。",
                f"近期疑似高频表达：{observed_text}。",
                "怒意优先通过\u201c行为后果\u201d体现：例如改策略、压冲动、转移目标、反制行动，而非只写身体反应。",
                "允许写生理反应，但每次只保留一个短动作，并与场景细节绑定，禁止连续堆叠\u201c握拳+指节+目光\u201d套装。",
                "同段中相近情绪句式不得重复；如果上一段写了怒，下一段改用对话节奏、环境压力或决策代价呈现。",
            ]
        )

    @staticmethod
    def _extract_mission_patterns(selected_version) -> Dict[str, str]:
        """从 version metadata 中提取 opening_hook_type、chapter_end_style、satisfaction_design.type。"""
        if not selected_version:
            return {}
        metadata = getattr(selected_version, "metadata_", None) or {}
        mission = metadata.get("chapter_mission") or {}
        if not mission:
            return {}
        result: Dict[str, str] = {}
        if mission.get("opening_hook_type"):
            result["opening_hook_type"] = mission["opening_hook_type"]
        if mission.get("chapter_end_style"):
            result["chapter_end_style"] = mission["chapter_end_style"]
        sat = mission.get("satisfaction_design")
        if isinstance(sat, dict) and sat.get("type"):
            result["satisfaction_type"] = sat["type"]
        return result

    @staticmethod
    def _build_pattern_differentiation(completed_chapters: List[Dict[str, Any]]) -> str:
        """分析最近章节的开头/结尾/爽感模式，生成差异化约束文本。"""
        if not completed_chapters:
            return ""

        sorted_chapters = sorted(completed_chapters, key=lambda c: c["chapter_number"])
        constraints: List[str] = []

        # 分析最近3章的开头类型和结尾类型
        recent_3 = sorted_chapters[-3:]
        opening_types = [
            c["chapter_mission_patterns"].get("opening_hook_type", "")
            for c in recent_3
            if c.get("chapter_mission_patterns")
        ]
        opening_types = [t for t in opening_types if t]
        if len(opening_types) >= 2 and len(set(opening_types)) == 1:
            constraints.append(f"最近{len(opening_types)}章开头均为「{opening_types[0]}」类型，本章必须使用不同的开头类型。")

        ending_types = [
            c["chapter_mission_patterns"].get("chapter_end_style", "")
            for c in recent_3
            if c.get("chapter_mission_patterns")
        ]
        ending_types = [t for t in ending_types if t]
        if len(ending_types) >= 2 and len(set(ending_types)) == 1:
            constraints.append(f"最近{len(ending_types)}章结尾均为「{ending_types[0]}」风格，本章必须使用不同的结尾风格。")

        # 分析最近5章的爽感模式
        recent_5 = sorted_chapters[-5:]
        sat_types = [
            c["chapter_mission_patterns"].get("satisfaction_type", "")
            for c in recent_5
            if c.get("chapter_mission_patterns")
        ]
        sat_types = [t for t in sat_types if t and t != "无（蓄力中）"]
        if len(sat_types) >= 3:
            from collections import Counter
            counter = Counter(sat_types)
            most_common_type, most_common_count = counter.most_common(1)[0]
            if most_common_count >= 3:
                constraints.append(f"最近5章中「{most_common_type}」爽感出现{most_common_count}次，本章应尝试不同类型的爽感设计。")

        # 对比最近3章开头摘录，检测开头模式雷同
        opening_excerpts = [
            c.get("opening_excerpt", "")[:80]
            for c in recent_3
            if c.get("opening_excerpt")
        ]
        if opening_excerpts:
            constraints.append(
                "近期章节开头摘录供参考（避免相似开头）：\n"
                + "\n".join(f"- 第{c['chapter_number']}章：「{c.get('opening_excerpt', '')[:80]}…」" for c in recent_3 if c.get("opening_excerpt"))
            )

        if not constraints:
            return ""

        return "[模式差异化约束]\n" + "\n".join(constraints)

    async def _generate_mission_brief(
        self,
        *,
        chapter_mission: dict,
        previous_summary: str,
        previous_tail: str,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        introduced_characters: List[str],
        forbidden_characters: List[str],
        user_id: int,
    ) -> Optional[str]:
        """将 ChapterMission JSON 转换为人类可读的创作任务书。"""
        brief_prompt = await self.prompt_service.get_prompt("mission_brief")
        if not brief_prompt:
            logger.info("未配置 mission_brief 提示词，将使用原始 JSON")
            return None

        brief_input = f"""[章节导演脚本]
{json.dumps(chapter_mission, ensure_ascii=False, indent=2)}

[上一章摘要]
{previous_summary}

[上一章结尾]
{previous_tail}

[当前章节目标]
标题：{outline_title}
摘要：{outline_summary}
写作要求：{writing_notes}

[已登场角色]
{", ".join(introduced_characters) if introduced_characters else "暂无"}

[禁止角色]
{", ".join(forbidden_characters) if forbidden_characters else "无"}"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=brief_prompt,
                conversation_history=[{"role": "user", "content": brief_input}],
                temperature=0.3,
                user_id=user_id,
                timeout=120.0,
            )
            cleaned = remove_think_tags(response)
            if not cleaned or not cleaned.strip():
                logger.warning("创作任务书生成结果为空，回退原始 JSON")
                return None
            logger.info("创作任务书生成完成 (len=%d)", len(cleaned))
            return cleaned.strip()
        except Exception as exc:
            logger.warning("生成创作任务书失败，将回退原始 JSON: %s", exc)
            return None

    @staticmethod
    def _build_prompt_sections(
        *,
        writer_blueprint: Dict[str, Any],
        previous_summary: str,
        previous_tail: str,
        chapter_mission: Optional[dict],
        mission_brief_text: Optional[str],
        rag_context: Optional[Dict[str, Any]],
        knowledge_context: Optional[str],
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        forbidden_characters: List[str],
        project_memory_text: Optional[str],
        memory_context: Optional[str],
        platinum_writing_brief: Optional[str],
        platinum_rhythm_brief: Optional[str],
        foreshadowing_urgency_brief: Optional[str],
        hook_continuity_brief: Optional[str],
        emotion_expression_brief: Optional[str],
        story_skeleton: Optional[str] = None,
        genre_prompt_injection: Optional[str] = None,
        fingerprint_context: Optional[str] = None,
        prediction_text: Optional[str] = None,
    ) -> List[Tuple[str, str]]:
        blueprint_text = json.dumps(writer_blueprint, ensure_ascii=False, indent=2)
        forbidden_text = json.dumps(forbidden_characters, ensure_ascii=False) if forbidden_characters else "无"

        # --- TIER 1: 核心指令（利用首因效应，放在最前面）---
        sections: List[Tuple[str, str]] = [
            ("[当前章节目标]", f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}"),
        ]
        if prediction_text:
            sections.append(("[剧情推演](AI预分析的章节要点与约束，请参考执行)", prediction_text))

        if mission_brief_text:
            sections.append(("[创作任务书](本章写作的核心执行指南，必须严格遵循)", mission_brief_text))
        elif chapter_mission:
            mission_text = json.dumps(chapter_mission, ensure_ascii=False, indent=2)
            sections.append(("[章节导演脚本](JSON)", mission_text))

        sections.append(("[章节字数要求]", CHAPTER_WORD_COUNT_RULE))

        # --- TIER 2: 上下文参考（中间位置）---
        if story_skeleton:
            sections.append(("[故事骨架](前情关键节点采样，帮助你把握全局走向)", story_skeleton))

        sections.extend(
            [
                ("[上一章摘要]", previous_summary or "暂无（这是第一章）"),
                ("[上一章结尾]", previous_tail or "暂无（这是第一章）"),
                ("[世界蓝图](JSON，已裁剪)", blueprint_text),
            ]
        )

        if project_memory_text:
            sections.append(("[项目长期记忆](摘要/剧情线)", project_memory_text))
        if memory_context:
            sections.append(("[记忆层上下文]", memory_context))

        if knowledge_context:
            sections.append(("[RAG精筛上下文](含POV裁剪)", knowledge_context))

        if rag_context:
            rag_chunks_text = "\n\n".join(rag_context.get("chunks", [])) or "未检索到章节片段"
            rag_summaries_text = "\n".join(rag_context.get("summaries", [])) or "未检索到章节摘要"
            sections.append(("[检索到的剧情上下文](Markdown)", rag_chunks_text))
            sections.append(("[检索到的章节摘要](Markdown)", rag_summaries_text))

        # --- TIER 3: 补充约束（利用近因效应，放在最后面）---
        if genre_prompt_injection:
            sections.append(("[题材写作约束]", genre_prompt_injection))
        if fingerprint_context:
            sections.append(("[作者风格指纹]", fingerprint_context))
        if platinum_rhythm_brief:
            sections.append(("[白金节奏控制](Quest/Fire/Constellation)", platinum_rhythm_brief))
        if foreshadowing_urgency_brief:
            sections.append(("[高优先级伏笔提醒]", foreshadowing_urgency_brief))
        if hook_continuity_brief:
            sections.append(("[追更钩子连续性]", hook_continuity_brief))
        if emotion_expression_brief:
            sections.append(("[情绪表达去模板化约束](重点减少怒意句式重复)", emotion_expression_brief))
        if platinum_writing_brief:
            sections.append(("[白金写作准则](硬约束)", platinum_writing_brief))
        sections.append(("[禁止角色](本章不允许提及)", forbidden_text))

        return sections
