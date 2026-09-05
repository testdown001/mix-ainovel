# AIMETA P=流水线审查Mixin|R=AI评审_修订_自我批评_读者模拟_一致性_优化_扩写_质量检测|NR=不含API路由|E=PipelineReviewMixin|X=internal|A=Mixin|D=sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from ..core.constants import CHAPTER_RECOMMENDED_WORDS, CHAPTER_MIN_WORDS
from ..services.ai_review_service import AIReviewService
from ..services.consistency_service import ConsistencyService, ViolationSeverity
from ..services.enrichment_service import EnrichmentService
from ..utils.json_utils import (
    is_probable_chapter_plain_text,
    remove_think_tags,
    repair_json,
    sanitize_chapter_plain_text,
    unwrap_markdown_json,
)

from .emotional_editing_service import (
    QUALITY_DETECTION_PROMPT_TEMPLATE, EMOTIONAL_REVIEW_RULES, RevisionPlan,
    apply_revision_plan, mission_brief, preservation_hint, review_chapter_quality,
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
        """One existing review call produces grounded feedback and bounded replacements."""
        if not (critical_flaws or refinement_suggestions or enable_self_critique):
            return chapter_content, {"applied": False, "reason": "no_feedback_no_critique"}
        context = context or {}
        protected = context.get("protected_passages") or []
        prompt = f"""审校并提出局部修订，禁止重写整章。先识别要保留的精彩段落，再修真正的问题。
{EMOTIONAL_REVIEW_RULES}
除情感之外，核查反馈中有原文依据的因果、人设、视角和冗余问题；反馈不一定正确。
edits 最多6处，before 为原文中唯一出现的连续片段（不超过800字），after 为替换文本。
各处不重叠，总替换范围不超过原文35%，优先只改一句。不得修改 protected_passages。
前文证据不足的问题只作记录，不添加新经历、设定或关系事实。没有可落实的问题就返回空 edits。
保留含蓄表达、口语、长短句变化，不把停顿补成心理解释，不为评分强塞高潮。
字数上限：{max_word_count or '保持原有规模'}。
{preservation_hint(protected)}
[章节意图]
{mission_brief(chapter_mission)}
[反馈]
{critical_flaws}
{refinement_suggestions}
[角色参考]
{str(context.get('character_profiles') or '')[:10000]}
[前文摘要（仅供因果参考）]
{str(context.get('previous_summary') or '')[:6000]}
[原文]
{chapter_content}"""
        try:
            plan = await self.llm_service.generate_structured(
                prompt=prompt, schema=RevisionPlan,
                system_prompt="你是尊重作者声音的连载小说编辑，只输出有原文定位的修订计划。",
                temperature=0.3, user_id=user_id, timeout=180.0,
                max_tokens=6000, max_validation_retries=0,
            )
            return apply_revision_plan(chapter_content, plan, max_word_count=max_word_count,
                                       protected_passages=protected)
        except Exception as exc:
            logger.warning("局部修订失败，保留原文: %s", exc)
            return chapter_content, {"applied": False, "reason": "revision_unavailable"}

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
        protected_passages: Optional[List[dict]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """使用综合优化 prompt 一次性优化多个维度（对话/环境/心理/节奏/爽点）。

        当 *include_polish* 为 True 时，同时执行文学性润色，减少一次 LLM 调用。
        当 *include_density* 为 True 时，同时执行信息密度压缩，减少一次 LLM 调用。
        """
        extra_dimensions = ""
        next_dim = 6
        if include_polish:
            extra_dimensions += f"""
{next_dim}. **文学性润色**：优化遣词造句，保留必要画面；删去装饰性修辞和重复感官描写，打磨对话个性"""
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
2. **环境描写**：只保留会影响动作、判断或冲突的场景细节，删除天气/光影替人物抒情的段落
3. **心理描写**：简单情绪允许直陈；优先通过选择、台词和行为后果体现，同一情绪节拍最多一个身体反应
4. **节奏优化**：调整段落长短、松紧交替，确保铺垫→爆发→余韵的节奏感
5. **爽点强化**：识别并强化爽点结构（30%铺垫/40%兑现/30%微反转），增加信息差和情绪张力{extra_dimensions}

**核心原则：**
- 保持情节走向、人物关系、对话内容完全不变
{word_count_principle}
- 优化要自然融入，不能有明显修补痕迹
- 优先精确名词和动词；一个句子只留一个主要意象，一个自然段原则上不超过一次比喻
- 严格保持当前 POV，只写其可感知、可回忆或有证据可推断的信息，不确认其他角色内心或幕后事实
- 最后两段删除总结、未来预告和命运/环境象征，保留由具体事件形成的自然尾钩
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
                conversation_history=[{"role": "user", "content": preservation_hint(protected_passages) +  optimize_prompt}],
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
            return chapter_content, {"steps": [], "applied": False, "error": str(exc)}

    async def _run_polish(self, chapter_content: str, *, user_id: int, max_word_count: int = 0, protected_passages: Optional[List[dict]] = None) -> Tuple[str, Dict[str, Any]]:
        """使用独立配置的润色模型对章节进行文学性润色。"""
        polish_prompt = f"""你是一位文学功底深厚的网文润色编辑。请对以下章节内容进行润色优化。

**润色原则：**
1. 保持情节走向、人物关系、对话内容完全不变
2. 提升准确性：优先精确名词和动词，删除不提供新信息的形容词、副词和装饰性句子
3. 克制感官描写：只保留会影响人物动作、判断或冲突的细节；一个自然段原则上不超过一次比喻
4. 润色对话：使角色语言更有个性和感染力
5. 打磨节奏：优化段落过渡和叙事节奏
6. 保持原文字数规模，总字数不得超过 {max_word_count} 字，不增删情节
7. 禁止输出分析任务、原文本分析、人物分析、氛围分析、优化说明、标题或任何编辑备注
8. 简单情绪允许直陈；同一情绪节拍最多一个身体反应，禁止心跳、冷汗、喉结、指尖、胸腔、目光成套堆叠
9. 严格保持当前 POV，不确认其他角色内心、幕后行动或未来结果
10. 最后两段不得新增或保留总结、未来预告、环境/命运隐喻；尾钩必须来自具体事件

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
                conversation_history=[{"role": "user", "content": preservation_hint(protected_passages) +  polish_prompt}],
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

    async def _run_density_compression(self, chapter_content: str, *, user_id: int, max_word_count: int = 0, protected_passages: Optional[List[dict]] = None) -> Tuple[str, Dict[str, Any]]:
        """执行信息密度压缩 (Chain of Density)"""
        prompt = await self.prompt_service.get_prompt("density_compression")
        if not prompt:
            logger.warning("未找到 density_compression prompt，跳过密度压缩")
            return chapter_content, {"applied": False, "reason": "missing_prompt"}

        try:
            _density_max_tokens = int(max_word_count * 1.2) if max_word_count else None
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一位擅长高信息密度写作的网文编辑。任务是压缩和提纯文字。",
                conversation_history=[{"role": "user", "content": preservation_hint(protected_passages) + f"{prompt}\n\n[原章节内容]\n{chapter_content}"}],
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
        """Read-only full-chapter review, shared with background Stage B."""
        try:
            return await review_chapter_quality(
                self.llm_service, chapter_content, chapter_mission=chapter_mission,
                recent_patterns="\n".join(previous_chapters_openings[-3:]), user_id=user_id,
            )
        except Exception as exc:
            logger.warning("质量检测失败: %s", exc)
            return {"status": "unavailable", "error": str(exc), "coolpoint_score": -1, "repetition_score": -1}
