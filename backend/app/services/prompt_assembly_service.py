from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from ..core.constants import (
    ALL_HARD_RULES,
    CHAPTER_MAX_WORDS,
    CHAPTER_MIN_WORDS,
    CHAPTER_RECOMMENDED_WORDS,
    CHAPTER_WORD_COUNT_RULE,
)
from ..utils.json_utils import remove_think_tags

logger = logging.getLogger(__name__)


class PromptAssemblyService:
    """统一承载 Prompt 规则构建与 section 组装。"""

    def __init__(self, prompt_service, llm_service):
        self.prompt_service = prompt_service
        self.llm_service = llm_service

    @staticmethod
    def build_word_count_rule(
        chapter_word_count_min: Optional[int],
        chapter_word_count_max: Optional[int],
        chapter_target_word_count: Optional[int],
    ) -> str:
        try:
            min_words = int(chapter_word_count_min or CHAPTER_MIN_WORDS)
            max_words = int(chapter_word_count_max or CHAPTER_MAX_WORDS)
            if min_words < 1:
                min_words = CHAPTER_MIN_WORDS
            if max_words < min_words:
                max_words = min_words

            fallback_target = min_words + (max_words - min_words) // 2
            target_words = int(chapter_target_word_count or fallback_target)
            target_words = max(min_words, min(max_words, target_words))
            if target_words < 1:
                target_words = CHAPTER_RECOMMENDED_WORDS

            return (
                f"【硬性要求】本章正文必须控制在 {min_words} 到 {max_words} 字之间，"
                f"目标约 {target_words} 字。超过 {max_words} 字即为不合格，必须精简。"
                f"宁可少写一个场景细节，也绝对不要超过 {max_words} 字。"
                "冲突/动作段可用短句提速，铺垫/心理段可用长句展开；长短句必须交替变化，"
                "禁止整章单一句式。不要为凑字数硬加空描写，也不要因压字数跳过关键动作与情绪递进。"
            )
        except (TypeError, ValueError):
            return CHAPTER_WORD_COUNT_RULE

    @staticmethod
    def build_emotion_expression_brief(completed_chapters: List[Dict[str, Any]]) -> str:
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
                "怒意优先通过“行为后果”体现：例如改策略、压冲动、转移目标、反制行动，而非只写身体反应。",
                "允许写生理反应，但每次只保留一个短动作，并与场景细节绑定，禁止连续堆叠“握拳+指节+目光”套装。",
                "同段中相近情绪句式不得重复；如果上一段写了怒，下一段改用对话节奏、环境压力或决策代价呈现。",
            ]
        )

    @staticmethod
    def extract_mission_patterns(selected_version) -> Dict[str, str]:
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
    def build_pattern_differentiation(completed_chapters: List[Dict[str, Any]]) -> str:
        if not completed_chapters:
            return ""

        sorted_chapters = sorted(completed_chapters, key=lambda c: c["chapter_number"])
        constraints: List[str] = []
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

        recent_5 = sorted_chapters[-5:]
        sat_types = [
            c["chapter_mission_patterns"].get("satisfaction_type", "")
            for c in recent_5
            if c.get("chapter_mission_patterns")
        ]
        sat_types = [t for t in sat_types if t and t != "无（蓄力中）"]
        if len(sat_types) >= 3:
            most_common_type, most_common_count = Counter(sat_types).most_common(1)[0]
            if most_common_count >= 3:
                constraints.append(f"最近5章中「{most_common_type}」爽感出现{most_common_count}次，本章应尝试不同类型的爽感设计。")

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

    async def generate_mission_brief(
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
            brief_prompt = await self.prompt_service.get_prompt("mission_brief")
            if not brief_prompt:
                logger.info("未配置 mission_brief 提示词，将使用原始 JSON")
                return None

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
    def build_blueprint_digest(writer_blueprint: Any) -> str:
        """把世界蓝图 dict 压缩为逐行的结构化中文摘要（替代 json.dumps 全量注入）。

        每条信息占一行：预算超限时按行截断，不会再产出残破 JSON；
        字段缺失逐项跳过，异常时回退为紧凑 JSON（保底不阻断生成）。
        """
        try:
            blueprint = writer_blueprint or {}
            lines: List[str] = []

            title = str(blueprint.get("title") or "").strip()
            if title:
                lines.append(f"书名：{title}")
            meta_bits = [
                f"{label}：{str(blueprint.get(key)).strip()}"
                for label, key in (
                    ("类型", "genre"),
                    ("风格", "style"),
                    ("基调", "tone"),
                    ("目标读者", "target_audience"),
                )
                if str(blueprint.get(key) or "").strip()
            ]
            if meta_bits:
                lines.append(" / ".join(meta_bits))
            one_line = str(blueprint.get("one_sentence_summary") or "").strip()
            if one_line:
                lines.append(f"一句话主线：{one_line}")

            world = blueprint.get("world_setting") or {}
            if isinstance(world, dict):
                core_rules = str(world.get("core_rules") or "").strip()
                if core_rules:
                    lines.append("世界观核心设定：")
                    for rule in core_rules.splitlines():
                        rule = rule.strip().lstrip("-").strip()
                        if rule:
                            lines.append(f"- {rule}")
                locations = [item for item in (world.get("key_locations") or []) if isinstance(item, dict)]
                if locations:
                    lines.append("关键地点：")
                    for item in locations[:8]:
                        name = str(item.get("name") or "").strip()
                        desc = str(item.get("description") or "").strip()
                        if name:
                            lines.append(f"- {name}：{desc}" if desc else f"- {name}")
                factions = [item for item in (world.get("factions") or []) if isinstance(item, dict)]
                if factions:
                    lines.append("势力格局：")
                    for item in factions[:8]:
                        name = str(item.get("name") or "").strip()
                        desc = str(item.get("description") or "").strip()
                        if name:
                            lines.append(f"- {name}：{desc}" if desc else f"- {name}")
                # 非标准键（自由扩展的世界观字段）：标量直接收录；嵌套结构压缩为单行紧凑 JSON，
                # 截 200 字防膨胀——绝不整体丢弃（修炼体系/时间线等常存于此类键）
                known_world_keys = {"core_rules", "key_locations", "factions"}
                for key, value in world.items():
                    if key in known_world_keys:
                        continue
                    if isinstance(value, (str, int, float)):
                        value_text = str(value).strip()
                    else:
                        try:
                            value_text = json.dumps(value, ensure_ascii=False)
                        except (TypeError, ValueError):
                            value_text = str(value)
                        value_text = value_text.strip()
                        if len(value_text) > 200:
                            value_text = value_text[:200] + "…"
                    if value_text:
                        lines.append(f"{key}：{value_text}")

            golden = blueprint.get("golden_finger")
            if isinstance(golden, dict):
                g_name = str(golden.get("name") or "").strip()
                g_desc = str(golden.get("description") or "").strip()
                if g_name or g_desc:
                    g_type = str(golden.get("type") or "").strip()
                    g_limit = str(golden.get("limitations") or "").strip()
                    bits = [f"金手指：{g_name or '（未命名）'}"]
                    if g_type:
                        bits.append(f"（{g_type}）")
                    if g_desc:
                        bits.append(f"——{g_desc}")
                    if g_limit:
                        bits.append(f"；限制：{g_limit}")
                    lines.append("".join(bits))

            characters = [item for item in (blueprint.get("characters") or []) if isinstance(item, dict)]
            if characters:
                lines.append("主要角色：")
                for item in characters[:10]:
                    name = str(item.get("name") or "").strip()
                    if not name:
                        continue
                    desc = "；".join(
                        str(item.get(key) or "").strip()
                        for key in ("identity", "personality", "abilities", "relationship_to_protagonist", "goals")
                        if str(item.get(key) or "").strip()
                    )
                    lines.append(f"- {name}：{desc}" if desc else f"- {name}")

            relationships = [item for item in (blueprint.get("relationships") or []) if isinstance(item, dict)]
            rel_lines = []
            for item in relationships[:10]:
                src = str(item.get("from") or item.get("character_from") or "").strip()
                dst = str(item.get("to") or item.get("character_to") or "").strip()
                desc = str(item.get("description") or "").strip()
                if src and dst:
                    rel_lines.append(f"- {src} → {dst}：{desc}" if desc else f"- {src} → {dst}")
            if rel_lines:
                lines.append("角色关系：")
                lines.extend(rel_lines)

            foreshadowings = [
                item for item in (blueprint.get("foreshadowings") or []) if isinstance(item, dict)
            ]
            fs_lines = []
            for item in foreshadowings[:10]:
                content = str(item.get("description") or item.get("name") or "").strip()
                if not content:
                    continue
                planted = item.get("planted_chapter")
                target = item.get("target_chapter")
                if planted and target:
                    span = f"（第{planted}章埋 → 第{target}章收）"
                elif planted:
                    span = f"（第{planted}章埋）"
                else:
                    span = ""
                fs_lines.append(f"- {content}{span}")
            if fs_lines:
                lines.append("蓝图伏笔：")
                lines.extend(fs_lines)

            return "\n".join(lines) if lines else "（蓝图为空）"
        except Exception:
            # 极端异常兜底：退回紧凑 JSON（旧行为），不阻断生成
            return json.dumps(writer_blueprint, ensure_ascii=False)

    def build_prompt_sections(
        self,
        *,
        writer_blueprint: Dict[str, Any],
        previous_summary: str,
        previous_tail: str,
        chapter_mission: Optional[dict],
        mission_brief_text: Optional[str],
        rag_context: Optional[Dict[str, Any]],
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
        user_style_rules: Optional[str] = None,
        chapter_word_count_min: Optional[int] = None,
        chapter_word_count_max: Optional[int] = None,
        chapter_target_word_count: Optional[int] = None,
        chapter_state_context: Optional[str] = None,
        coolpoint_rhythm_directive: Optional[str] = None,
        writing_strategy: Optional[Any] = None,
        power_system_context: Optional[str] = None,
        relationship_context: Optional[str] = None,
        trajectory_context: Optional[str] = None,
        outline_revision_context: Optional[str] = None,
        volume_replan_context: Optional[str] = None,
        significance_context: Optional[str] = None,
        volume_summary_context: Optional[str] = None,
        book_summary_context: Optional[str] = None,
        name_lock_text: Optional[str] = None,
    ) -> List[Tuple[str, str]]:
        blueprint_text = self.build_blueprint_digest(writer_blueprint)
        forbidden_text = json.dumps(forbidden_characters, ensure_ascii=False) if forbidden_characters else "无"

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

        sections.append(
            (
                "[章节字数要求]",
                self.build_word_count_rule(
                    chapter_word_count_min=chapter_word_count_min,
                    chapter_word_count_max=chapter_word_count_max,
                    chapter_target_word_count=chapter_target_word_count,
                ),
            )
        )

        if foreshadowing_urgency_brief:
            sections.append(("[高优先级伏笔提醒](必须在本章处理的伏笔)", foreshadowing_urgency_brief))
        if chapter_state_context:
            sections.append(("[角色当前状态](数据库实时查询，零幻觉)", chapter_state_context))
        if coolpoint_rhythm_directive:
            sections.append(("[节奏纠偏指令](系统级强制)", coolpoint_rhythm_directive))
        if power_system_context:
            sections.append(("[力量体系约束](角色能力上限，严禁超阶)", power_system_context))
        if relationship_context:
            sections.append(("[角色关系网](已确定的角色关系，行为需符合关系逻辑)", relationship_context))
        if story_skeleton:
            sections.append(("[故事骨架](三层压缩：近章详细/中距摘要/远距关键事件)", story_skeleton))

        sections.extend(
            [
                ("[上一章摘要]", previous_summary or "暂无（这是第一章）"),
                ("[上一章结尾]", previous_tail or "暂无（这是第一章）"),
                ("[世界蓝图](结构化摘要，已按可见性裁剪)", blueprint_text),
            ]
        )
        if name_lock_text:
            sections.append(("[人设锁](亦称指向同一人，正文用正式名)", name_lock_text))

        # 分层长程记忆：全书脉络（最宏观）→ 卷级前情（最近数卷）→ 项目长期记忆
        if book_summary_context:
            sections.append(("[全书脉络](全书主线/角色弧光/跨卷悬念)", book_summary_context))
        if volume_summary_context:
            sections.append(("[卷级前情](最近数卷的结构化摘要)", volume_summary_context))
        if project_memory_text:
            sections.append(("[项目长期记忆](摘要/剧情线)", project_memory_text))
        if memory_context:
            sections.append(("[记忆层上下文]", memory_context))
        if rag_context:
            rag_chunks_text = "\n\n".join(rag_context.get("chunks", [])) or "未检索到章节片段"
            rag_summaries_text = "\n".join(rag_context.get("summaries", [])) or "未检索到章节摘要"
            sections.append(("[检索到的剧情上下文](Markdown)", rag_chunks_text))
            sections.append(("[检索到的章节摘要](Markdown)", rag_summaries_text))
        if hook_continuity_brief:
            sections.append(("[追更钩子连续性](上一章未兑现的钩子)", hook_continuity_brief))

        style_weight = writing_strategy.style_weight if writing_strategy else 1.0
        ref_weight = writing_strategy.reference_weight if writing_strategy else 1.0
        genre_weight = writing_strategy.genre_weight if writing_strategy else 1.0
        warnings = writing_strategy.warnings if writing_strategy else []
        if warnings:
            sections.insert(1, ("[策略协调提醒]", "\n".join(f"- {warning}" for warning in warnings)))

        if trajectory_context:
            sections.append(("[故事轨迹分析](基于历史章节的节奏建议)", trajectory_context))

        if significance_context:
            # 紧跟角色状态之后：事实说「他是什么状态」，意义说「这对他意味着什么」，
            # 两段挨着读才成立。标题里就点明「不得直接写出」，避免模型把底色当台词。
            sections.append((
                "[人物意义层](人物此刻的底色——只可通过选择与反应体现，不得直接写出)",
                significance_context,
            ))
        if volume_replan_context:
            # 放在章级修订提示之前：卷级是更大尺度的方向校正，先定方向再谈本章微调
            sections.append(("[卷级重规划](上一卷复盘后对本卷方向的修订)", volume_replan_context))
        if outline_revision_context:
            sections.append(("[大纲修订提示](前文实际走向与本章原大纲的偏差，参考调整)", outline_revision_context))
        if genre_prompt_injection and genre_weight > 0:
            sections.append(("[题材写作约束]", genre_prompt_injection))
        if fingerprint_context and ref_weight > 0:
            sections.append(("[作者风格指纹]", fingerprint_context))
        if platinum_rhythm_brief:
            sections.append(("[白金节奏控制](Quest/Fire/Constellation)", platinum_rhythm_brief))
        if emotion_expression_brief:
            sections.append(("[情绪表达去模板化约束](重点减少怒意句式重复)", emotion_expression_brief))
        if user_style_rules and style_weight > 0:
            if style_weight >= 0.8:
                style_label = "[用户写作风格](用户级全局约束，必须严格遵守)"
            elif style_weight >= 0.5:
                style_label = "[用户写作风格](参考约束，适度遵守)"
            else:
                style_label = "[用户写作风格](参考建议，非强制)"
            sections.append((style_label, user_style_rules))
        sections.append(("[写作硬性约束](必须严格遵守)", ALL_HARD_RULES))
        if platinum_writing_brief:
            sections.append(("[白金写作准则](硬约束)", platinum_writing_brief))
        sections.append(("[禁止角色](本章不允许提及)", forbidden_text))

        return sections
