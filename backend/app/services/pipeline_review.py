# AIMETA P=流水线审查Mixin|R=AI评审_修订_自我批评_读者模拟_一致性_优化_扩写_质量检测|NR=不含API路由|E=PipelineReviewMixin|X=internal|A=Mixin|D=sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from ..core.constants import CHAPTER_RECOMMENDED_WORDS, CHAPTER_MIN_WORDS
from ..services.ai_review_service import AIReviewService
from ..services.consistency_service import ConsistencyService, ViolationSeverity
from ..services.enrichment_service import EnrichmentService
from ..services.reader_simulator_service import ReaderSimulatorService, ReaderType
from ..services.self_critique_service import CritiqueDimension, SelfCritiqueService
from ..utils.json_utils import (
    is_probable_chapter_plain_text,
    remove_think_tags,
    repair_json,
    sanitize_chapter_plain_text,
    unwrap_markdown_json,
)

logger = logging.getLogger(__name__)


class PipelineReviewMixin:
    """流水线审查与优化相关方法。"""

    async def _run_ai_review(
        self,
        *,
        versions: List[Dict[str, Any]],
        chapter_mission: Optional[dict],
        user_id: int,
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        if len(versions) <= 1:
            return 0, None

        contents = [v.get("content", "") for v in versions]
        try:
            ai_review_service = AIReviewService(self.llm_service, self.prompt_service)
            ai_review_result = await ai_review_service.review_versions(
                versions=contents,
                chapter_mission=chapter_mission,
                user_id=user_id,
            )
        except Exception as exc:
            logger.warning("AI 评审失败，跳过: %s", exc)
            return 0, None

        if not ai_review_result:
            return 0, None

        for idx, variant in enumerate(versions):
            variant.setdefault("metadata", {})["ai_review"] = {
                "is_best": idx == ai_review_result.best_version_index,
                "scores": ai_review_result.scores,
                "evaluation": ai_review_result.overall_evaluation if idx == ai_review_result.best_version_index else None,
                "flaws": ai_review_result.critical_flaws if idx == ai_review_result.best_version_index else None,
                "suggestions": ai_review_result.refinement_suggestions if idx == ai_review_result.best_version_index else None,
            }

        return ai_review_result.best_version_index, {
            "best_version_index": ai_review_result.best_version_index,
            "scores": ai_review_result.scores,
            "evaluation": ai_review_result.overall_evaluation,
            "flaws": ai_review_result.critical_flaws,
            "suggestions": ai_review_result.refinement_suggestions,
        }

    async def _revise_with_review_feedback(
        self,
        chapter_content: str,
        *,
        critical_flaws: List[str],
        refinement_suggestions: str,
        chapter_mission: Optional[dict],
        user_id: int,
        max_word_count: int = 0,
    ) -> Tuple[str, Dict[str, Any]]:
        """利用 AI 评审的 critical_flaws 和 refinement_suggestions 做定向修订。"""
        if not critical_flaws and not refinement_suggestions:
            return chapter_content, {"applied": False, "reason": "no_feedback"}

        flaws_text = "\n".join(f"- {flaw}" for flaw in critical_flaws) if critical_flaws else "无"
        mission_hint = ""
        if chapter_mission:
            macro_beat = chapter_mission.get("macro_beat_description", "")
            if macro_beat:
                mission_hint = f"\n本章核心任务：{macro_beat}"

        revision_prompt = f"""你是一位资深网文编辑。以下章节已经由评审员指出了关键问题和改进建议。
请根据这些反馈对章节进行定向修订。

**修订原则：**
1. 只修改评审指出的问题，不改变整体情节走向和结构
2. 保持原有字数规模，总字数不得超过 {max_word_count} 字
3. 修改要自然融入，不能有明显修补痕迹
4. 保持原文的叙事风格和语气{mission_hint}

[关键缺陷]
{flaws_text}

[改进建议]
{refinement_suggestions or "无"}

[原章节内容]
{chapter_content}

直接输出修改后的完整章节，不要输出其他内容。"""

        try:
            _revision_max_tokens = int(max_word_count * 1.2) if max_word_count else None
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一位擅长根据编辑反馈精修文章的网文作者。",
                conversation_history=[{"role": "user", "content": revision_prompt}],
                temperature=0.5,
                user_id=user_id,
                timeout=180.0,
                max_tokens=_revision_max_tokens,
            )
            cleaned = remove_think_tags(response)
            if not cleaned or not cleaned.strip():
                logger.warning("审查反馈修订结果为空，保留原文")
                return chapter_content, {"applied": False, "reason": "empty_response"}

            final = sanitize_chapter_plain_text(cleaned.strip())
            logger.info("审查反馈修订完成: flaws=%d, original_len=%d, revised_len=%d",
                        len(critical_flaws), len(chapter_content), len(final))
            return final, {
                "applied": True,
                "flaws_count": len(critical_flaws),
                "has_suggestions": bool(refinement_suggestions),
            }
        except Exception as exc:
            logger.warning("审查反馈修订失败，保留原文: %s", exc)
            return chapter_content, {"applied": False, "reason": str(exc)}

    async def _run_combined_revision(
        self,
        chapter_content: str,
        *,
        critical_flaws: List[str],
        refinement_suggestions: str,
        enable_self_critique: bool,
        chapter_mission: Optional[dict],
        user_id: int,
        context: Optional[Dict[str, Any]] = None,
        max_word_count: int = 0,
    ) -> Tuple[str, Dict[str, Any]]:
        """合并 AI 评审反馈修订 + 自我批评为一次 LLM 调用，减少串行延迟。"""
        has_review_feedback = bool(critical_flaws or refinement_suggestions)
        if not has_review_feedback and not enable_self_critique:
            return chapter_content, {"applied": False, "reason": "no_feedback_no_critique"}

        flaws_text = "\n".join(f"- {flaw}" for flaw in critical_flaws) if critical_flaws else "无"
        suggestions_text = refinement_suggestions or "无"

        mission_hint = ""
        if chapter_mission:
            macro_beat = chapter_mission.get("macro_beat_description", "")
            if macro_beat:
                mission_hint = f"\n本章核心任务：{macro_beat}"

        character_context = ""
        if context and context.get("character_profiles"):
            character_context = f"\n\n[角色档案参考]\n{context['character_profiles']}"

        previous_summary_context = ""
        if context and context.get("previous_summary"):
            previous_summary_context = f"\n\n[前文摘要参考]\n{context['previous_summary']}"

        # 构建合并 prompt
        review_section = ""
        if has_review_feedback:
            review_section = f"""
## 一、AI 评审反馈（需优先修复）

[关键缺陷]
{flaws_text}

[改进建议]
{suggestions_text}
"""

        critique_section = ""
        if enable_self_critique:
            critique_section = """
## """ + ("二" if has_review_feedback else "一") + """、自我批评维度（需同步检查并修正）

请从以下 5 个维度审视章节，发现问题后在修订中一并修正：
1. **逻辑一致性**：情节逻辑是否自洽，时间线和因果关系是否合理
2. **人设一致性**：角色言行是否符合人设，性格特征是否前后一致
3. **文笔质量**：遣词造句是否恰当，是否存在重复表达或生硬措辞
4. **节奏控制**：叙事松紧是否得当，铺垫和爆发是否合理分配
5. **对话质量**：台词是否自然有个性，是否符合角色身份和语境
"""

        combined_prompt = f"""你是一位资深网文编辑，兼具批评眼光和修稿能力。请对以下章节进行一次性综合修订。

**修订原则：**
1. 只修改存在问题的部分，不改变整体情节走向和结构
2. 保持原有字数规模，总字数不得超过 {max_word_count} 字
3. 修改要自然融入，不能有明显修补痕迹
4. 保持原文的叙事风格和语气{mission_hint}
{review_section}{critique_section}{character_context}{previous_summary_context}

[原章节内容]
{chapter_content}

直接输出修改后的完整章节，不要输出其他内容。"""

        try:
            _max_tokens = int(max_word_count * 1.2) if max_word_count else None
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一位擅长根据多维度反馈精修网文章节的资深编辑。综合所有反馈一次性完成修订。",
                conversation_history=[{"role": "user", "content": combined_prompt}],
                temperature=0.5,
                user_id=user_id,
                timeout=180.0,
                max_tokens=_max_tokens,
                fail_on_truncation=True,
            )
            cleaned = remove_think_tags(response)
            if not cleaned or not cleaned.strip():
                logger.warning("合并修订结果为空，保留原文")
                return chapter_content, {"applied": False, "reason": "empty_response"}

            final = sanitize_chapter_plain_text(cleaned.strip())
            if not final or not is_probable_chapter_plain_text(final):
                logger.warning("合并修订结果不是有效章节正文，保留原文")
                return chapter_content, {"applied": False, "reason": "invalid_chapter_response"}
            if len(final) < len(chapter_content) * 0.5:
                logger.warning("合并修订后字数过少 (原%d, 现%d)，保留原文", len(chapter_content), len(final))
                return chapter_content, {"applied": False, "reason": "too_short"}
            logger.info(
                "合并修订完成: has_review=%s, self_critique=%s, flaws=%d, original_len=%d, revised_len=%d",
                has_review_feedback, enable_self_critique, len(critical_flaws),
                len(chapter_content), len(final),
            )
            return final, {
                "applied": True,
                "has_review_feedback": has_review_feedback,
                "flaws_count": len(critical_flaws),
                "has_suggestions": bool(refinement_suggestions),
                "self_critique_included": enable_self_critique,
            }
        except Exception as exc:
            logger.warning("合并修订失败，保留原文: %s", exc)
            return chapter_content, {"applied": False, "reason": str(exc)}

    async def _run_self_critique(
        self,
        chapter_content: str,
        *,
        user_id: int,
        context: Optional[Dict[str, Any]] = None,
        max_iterations: int = 1,
        max_word_count: int = 0,
    ) -> Tuple[str, Dict[str, Any]]:
        service = SelfCritiqueService(self.session, self.llm_service, self.prompt_service)
        _critique_max_tokens = int(max_word_count * 1.2) if max_word_count else None
        critique = await service.critique_and_revise_loop(
            chapter_content=chapter_content,
            max_iterations=max_iterations,
            target_score=80.0,
            dimensions=[
                CritiqueDimension.LOGIC,
                CritiqueDimension.CHARACTER,
                CritiqueDimension.WRITING,
                CritiqueDimension.PACING,
                CritiqueDimension.DIALOGUE,
            ],
            context=context,
            user_id=user_id,
            max_tokens=_critique_max_tokens,
        )
        return critique.get("final_content", chapter_content), {
            "iterations": len(critique.get("iterations", [])),
            "final_score": critique.get("final_score", 0),
            "improvement": critique.get("improvement", 0),
            "status": critique.get("status", "unknown"),
        }

    async def _run_reader_simulation(
        self,
        chapter_content: str,
        *,
        chapter_number: int,
        previous_summary: Optional[str],
        user_id: int,
    ) -> Dict[str, Any]:
        service = ReaderSimulatorService(self.session, self.llm_service, self.prompt_service)
        return await service.simulate_reading_experience(
            chapter_content=chapter_content,
            chapter_number=chapter_number,
            reader_types=[ReaderType.THRILL_SEEKER, ReaderType.CRITIC, ReaderType.CASUAL],
            previous_summary=previous_summary,
            user_id=user_id,
        )

    async def _run_consistency_check(
        self,
        *,
        project_id: str,
        chapter_text: str,
        user_id: int,
    ) -> Tuple[str, Dict[str, Any]]:
        service = ConsistencyService(self.session, self.llm_service)
        result = await service.check_consistency(project_id, chapter_text, user_id, include_foreshadowing=True)
        report = {
            "is_consistent": result.is_consistent,
            "summary": result.summary,
            "check_time_ms": result.check_time_ms,
            "violations": [
                {
                    "severity": v.severity.value if hasattr(v.severity, "value") else v.severity,
                    "category": v.category,
                    "description": v.description,
                    "location": v.location,
                    "suggested_fix": v.suggested_fix,
                    "confidence": v.confidence,
                }
                for v in result.violations
            ],
        }

        needs_fix = any(
            v.severity in (ViolationSeverity.CRITICAL, ViolationSeverity.MAJOR)
            for v in result.violations
        )
        if needs_fix:
            fixed = await service.auto_fix(project_id, chapter_text, result.violations, user_id)
            if fixed:
                report["auto_fix_applied"] = True
                return fixed, report

        report["auto_fix_applied"] = False
        return chapter_text, report

    async def _run_optimizer(
        self, chapter_content: str, *, user_id: int, include_polish: bool = False, include_density: bool = False, max_word_count: int = 0,
    ) -> Tuple[str, Dict[str, Any]]:
        """使用综合优化 prompt 一次性优化多个维度（对话/环境/心理/节奏/爽点）。

        当 *include_polish* 为 True 时，同时执行文学性润色，减少一次 LLM 调用。
        当 *include_density* 为 True 时，同时执行信息密度压缩，减少一次 LLM 调用。
        """
        extra_dimensions = ""
        next_dim = 6
        if include_polish:
            extra_dimensions += f"""
{next_dim}. **文学性润色**：优化遣词造句，增强画面感和沉浸感，强化感官描写，打磨对话个性"""
            next_dim += 1
        if include_density:
            extra_dimensions += f"""
{next_dim}. **信息密度优化**：删除冗余描写、重复表达和水词，在不丢失关键信息的前提下提高每句话的信息含量，适当压缩篇幅"""

        word_count_principle = "- 保持原文字数规模（±10%），不增删情节"
        if include_density:
            word_count_principle = "- 在不丢失关键情节的前提下适当压缩篇幅，目标字数不超过原文的95%"

        optimize_prompt = f"""你是一位精通网络小说写作的多维度优化专家。请对以下章节内容进行综合优化。

**优化维度（同时处理）：**
1. **对话优化**：让角色台词更有个性、更符合身份，增强潜台词和冲突感
2. **环境描写**：补充视觉、听觉、触觉等感官细节，增强沉浸感
3. **心理描写**：用生理反应替代抽象情绪词（"他很愤怒"→具体生理反应），深化内心冲突
4. **节奏优化**：调整段落长短、松紧交替，确保铺垫→爆发→余韵的节奏感
5. **爽点强化**：识别并强化爽点结构（30%铺垫/40%兑现/30%微反转），增加信息差和情绪张力{extra_dimensions}

**核心原则：**
- 保持情节走向、人物关系、对话内容完全不变
{word_count_principle}
- 优化要自然融入，不能有明显修补痕迹
- optimized_content 字段必须只填写小说正文，禁止包含分析任务、原文本分析、人物分析、氛围分析、优化说明、标题或任何编辑备注
- optimization_notes 字段只填写简短优化说明，不得混入 optimized_content

[原章节内容]
{chapter_content}

请以 JSON 格式输出：
{{
  "optimized_content": "优化后的完整章节内容",
  "optimization_notes": "列出每个维度的具体优化点"
}}"""

        try:
            _optimizer_max_tokens = int(max_word_count * 1.2) if max_word_count else None
            response = await self.llm_service.get_llm_response(
                system_prompt=(
                    "你是一位擅长多维度同步优化网文章节的资深编辑。"
                    "只输出JSON。optimized_content 只能是小说正文，禁止输出分析任务、原文本分析或编辑说明。"
                ),
                conversation_history=[{"role": "user", "content": optimize_prompt}],
                temperature=0.7,
                user_id=user_id,
                timeout=180.0,
                max_tokens=_optimizer_max_tokens,
                fail_on_truncation=True,
            )
            cleaned = remove_think_tags(response)
            if not cleaned:
                cleaned = response
            normalized = unwrap_markdown_json(cleaned)
            try:
                parsed = json.loads(normalized)
            except json.JSONDecodeError:
                try:
                    parsed = json.loads(repair_json(normalized))
                except json.JSONDecodeError:
                    parsed = None
            dimension_label = "comprehensive"
            if include_polish:
                dimension_label += "+polish"
            if include_density:
                dimension_label += "+density"
            optimized_raw = parsed.get("optimized_content", cleaned) if parsed else cleaned
            optimized_text = optimized_raw if isinstance(optimized_raw, str) else ""
            optimized_content = sanitize_chapter_plain_text(optimized_text.strip())
            if not optimized_content or not is_probable_chapter_plain_text(optimized_content):
                logger.warning("综合优化结果不是有效章节正文，保留原文")
                return chapter_content, {
                    "steps": [{
                        "dimension": dimension_label,
                        "notes": "优化结果不是有效章节正文，已保留原文",
                    }],
                    "applied": False,
                    "reason": "invalid_chapter_response",
                }
            if parsed:
                return optimized_content, {
                    "steps": [{
                        "dimension": dimension_label,
                        "notes": parsed.get("optimization_notes", "综合优化完成"),
                    }],
                }
            else:
                return optimized_content, {"steps": [{"dimension": dimension_label, "notes": "优化完成（响应格式非标准JSON）"}]}
        except Exception as exc:
            logger.warning("综合优化失败: %s", exc)
            return chapter_content, {"steps": []}

    async def _run_polish(self, chapter_content: str, *, user_id: int, max_word_count: int = 0) -> Tuple[str, Dict[str, Any]]:
        """使用独立配置的润色模型对章节进行文学性润色。"""
        polish_prompt = f"""你是一位文学功底深厚的网文润色编辑。请对以下章节内容进行润色优化。

**润色原则：**
1. 保持情节走向、人物关系、对话内容完全不变
2. 提升文学性：优化遣词造句，增强画面感和沉浸感
3. 强化感官描写：视觉、听觉、触觉等多感官细节
4. 润色对话：使角色语言更有个性和感染力
5. 打磨节奏：优化段落过渡和叙事节奏
6. 保持原文字数规模，总字数不得超过 {max_word_count} 字，不增删情节
7. 禁止输出分析任务、原文本分析、人物分析、氛围分析、优化说明、标题或任何编辑备注

[原章节内容]
{chapter_content}

直接输出润色后的完整章节正文。第一个字必须是小说正文的第一个字，不要输出任何非正文内容。"""

        try:
            _polish_max_tokens = int(max_word_count * 1.2) if max_word_count else None
            response = await self.llm_service.get_optimize_llm_response(
                system_prompt=(
                    "你是一位擅长小说润色的文学编辑。"
                    "只输出润色后的小说正文，禁止输出分析任务、原文本分析、人物分析、氛围分析或编辑说明。"
                ),
                conversation_history=[{"role": "user", "content": polish_prompt}],
                temperature=0.75,
                timeout=180.0,
                max_tokens=_polish_max_tokens,
                fail_on_truncation=True,
            )
            cleaned = remove_think_tags(response)
            if not cleaned or not cleaned.strip():
                logger.warning("独立模型润色结果为空，保留原文")
                return chapter_content, {"applied": False, "reason": "empty_response"}

            final = sanitize_chapter_plain_text(cleaned.strip())
            if not final or not is_probable_chapter_plain_text(final):
                logger.warning("独立模型润色结果不是有效章节正文，保留原文")
                return chapter_content, {"applied": False, "reason": "invalid_chapter_response"}
            logger.info(
                "独立模型润色完成: original_len=%d, polished_len=%d",
                len(chapter_content), len(final),
            )
            return final, {
                "applied": True,
                "original_len": len(chapter_content),
                "polished_len": len(final),
            }
        except Exception as exc:
            logger.warning("独立模型润色失败，保留原文: %s", exc)
            return chapter_content, {"applied": False, "reason": str(exc)}

    async def _run_enrichment(
        self,
        chapter_content: str,
        *,
        user_id: int,
        target_word_count: int = CHAPTER_RECOMMENDED_WORDS,
        min_word_count: int = CHAPTER_MIN_WORDS,
        max_word_count: int = 0,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        service = EnrichmentService(self.session, self.llm_service)
        target_word_count = max(target_word_count, min_word_count)
        curent_word_count = len(chapter_content or "")

        # 上限检查：如果当前字数已达到或超过上限，跳过扩写避免进一步膨胀
        if max_word_count and curent_word_count >= max_word_count:
            logger.info("章节字数已达上限 (%d >= %d)，跳过扩写", curent_word_count, max_word_count)
            return chapter_content, None

        # 接近目标检查：字数已达目标的 95% 时，无需扩写
        if curent_word_count >= target_word_count * 0.95:
            logger.info("章节字数已接近目标 (%d >= %d * 0.95)，跳过扩写", curent_word_count, target_word_count)
            return chapter_content, None

        # 先做下限兜底：低于最小字数时直接走迭代扩写，避免章节明显偏短
        if curent_word_count < min_word_count:
            min_recovery_target = max(min_word_count + 200, target_word_count)
            enriched_text = await service.enrich_to_target(
                chapter_text=chapter_content,
                target_word_count=min_recovery_target,
                user_id=user_id,
                max_iterations=2,
            )
            enriched_count = len(enriched_text or "")
            if enriched_text and enriched_count > curent_word_count:
                return enriched_text, {
                    "original_word_count": curent_word_count,
                    "enriched_word_count": enriched_count,
                    "enrichment_ratio": (enriched_count / curent_word_count) if curent_word_count > 0 else 1.0,
                    "enrichment_type": "min_length_recovery",
                }

        dynamic_threshold = max(0.82, min(0.95, min_word_count / target_word_count))
        result = await service.check_and_enrich(
            chapter_text=chapter_content,
            target_word_count=target_word_count,
            user_id=user_id,
            threshold=dynamic_threshold,
        )
        if not result:
            return chapter_content, None

        return result.enriched_content, {
            "original_word_count": result.original_word_count,
            "enriched_word_count": result.enriched_word_count,
            "enrichment_ratio": result.enrichment_ratio,
            "enrichment_type": result.enrichment_type,
        }

    async def _run_density_compression(self, chapter_content: str, *, user_id: int, max_word_count: int = 0) -> Tuple[str, Dict[str, Any]]:
        """执行信息密度压缩 (Chain of Density)"""
        prompt = await self.prompt_service.get_prompt("density_compression")
        if not prompt:
            logger.warning("未找到 density_compression prompt，跳过密度压缩")
            return chapter_content, {"applied": False, "reason": "missing_prompt"}

        try:
            _density_max_tokens = int(max_word_count * 1.2) if max_word_count else None
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一位擅长高信息密度写作的网文编辑。任务是压缩和提纯文字。",
                conversation_history=[{"role": "user", "content": f"{prompt}\n\n[原章节内容]\n{chapter_content}"}],
                temperature=0.3, # 较低的温度保证不乱加戏
                user_id=user_id,
                timeout=180.0,
                max_tokens=_density_max_tokens,
                fail_on_truncation=True,
            )
            cleaned = remove_think_tags(response)
            if not cleaned or not cleaned.strip():
                logger.warning("密度压缩结果为空，保留原文")
                return chapter_content, {"applied": False, "reason": "empty_response"}

            final = sanitize_chapter_plain_text(cleaned.strip())
            
            # 安全检查：如果压缩后字数骤降（低于原来的50%），可能破坏了情节，放弃压缩
            if len(final) < len(chapter_content) * 0.5:
                logger.warning("密度压缩后字数过少 (原%d, 现%d)，放弃应用", len(chapter_content), len(final))
                return chapter_content, {"applied": False, "reason": "too_short"}
                
            logger.info(
                "密度压缩完成: original_len=%d, compressed_len=%d",
                len(chapter_content), len(final),
            )
            return final, {
                "applied": True,
                "original_len": len(chapter_content),
                "compressed_len": len(final),
                "compression_ratio": round(len(final) / len(chapter_content), 2) if len(chapter_content) > 0 else 1.0,
            }
        except Exception as exc:
            logger.warning("密度压缩失败，保留原文: %s", exc)
            return chapter_content, {"applied": False, "reason": str(exc)}

    async def _run_quality_detection(
        self,
        chapter_content: str,
        *,
        chapter_number: int,
        chapter_mission: Optional[dict],
        previous_chapters_openings: List[str],
        user_id: int,
    ) -> Dict[str, Any]:
        """分析爽点密度和模式重复，返回质量诊断报告（不修改内容）。"""
        opening_300 = chapter_content[:300] if len(chapter_content) > 300 else chapter_content
        ending_300 = chapter_content[-300:] if len(chapter_content) > 300 else chapter_content

        recent_patterns = ""
        if previous_chapters_openings:
            recent_patterns = "\n".join(
                f"第{i+1}个近期章节开头：{op[:200]}"
                for i, op in enumerate(previous_chapters_openings[-3:])
            )

        expected_beat = ""
        if chapter_mission:
            expected_beat = chapter_mission.get("macro_beat_description", "")
            sat_type = chapter_mission.get("satisfaction_design", {}).get("type", "")
            if sat_type:
                expected_beat += f"（爽感类型：{sat_type}）"

        detection_prompt = f"""你是一位资深网文质量分析师。请分析以下章节的三个维度，输出JSON。\r
\r
## 分析维度\r
\r
### 1. 爽点密度\r
检查本章是否有足够的张力/冲突/反转/情绪高潮时刻。\r
- coolpoint_score (0-10)：爽点密度评分\r
- coolpoint_moments：列出识别到的爽点/张力时刻（最多5个，每个一句话描述）\r
- coolpoint_issue：如果评分<6，指出具体问题\r
\r
### 2. 模式重复\r
对比本章开头/结尾与近期章节是否存在套路化重复。\r
- repetition_score (0-10)：独特性评分（10=完全独特，0=严重套路化）\r
- repetition_issues：发现的重复模式（如"连续3章都以对话开头"、"结尾都用身体反应收束"）\r
- within_chapter_repetition：章节内部的句式/词汇重复\r
\r
### 3. 阶段性胜利 (Milestone Victory)\r
判断本章是否包含"改变主角地位、能力层级或势力格局的决定性事件"。\r
- milestone_victory_detected (true/false)：是否存在阶段性胜利\r
- milestone_description：如果存在，一句话描述该阶段性胜利的内容\r
\r
[本章开头300字]\r
{opening_300}\r
\r
[本章结尾300字]\r
{ending_300}\r
\r
[本章预期]\r
{expected_beat or "无特定预期"}\r
\r
[近期章节开头对比]\r
{recent_patterns or "无（这是前几章）"}\r
\r
输出严格JSON格式：\r
{{"coolpoint_score": 0, "coolpoint_moments": [], "coolpoint_issue": "", "repetition_score": 0, "repetition_issues": [], "within_chapter_repetition": [], "milestone_victory_detected": false, "milestone_description": ""}}"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一位擅长量化分析网文质量的编辑。只输出JSON，不要其他内容。",
                conversation_history=[{"role": "user", "content": detection_prompt}],
                temperature=0.2,
                user_id=user_id,
                timeout=60.0,
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned or response)
            try:
                result = json.loads(normalized)
            except json.JSONDecodeError:
                result = json.loads(repair_json(normalized))

            logger.info(
                "质量检测完成: chapter=%d coolpoint=%s repetition=%s",
                chapter_number,
                result.get("coolpoint_score"),
                result.get("repetition_score"),
            )
            return result
        except Exception as exc:
            logger.warning("质量检测失败: %s", exc)
            return {"error": str(exc), "coolpoint_score": -1, "repetition_score": -1}
