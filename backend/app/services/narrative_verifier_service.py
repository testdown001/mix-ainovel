from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from .context_planner_service import ContextPlan
from .narrative_claim_service import ClaimVerifierService


class NarrativeVerifierService:
    """统一整理生成后的验证结果，形成 Narrative 级验证报告。"""

    def __init__(self, claim_verifier: Optional[ClaimVerifierService] = None):
        self.claim_verifier = claim_verifier or ClaimVerifierService()

    def verify(
        self,
        *,
        plan: ContextPlan,
        chapter_text: str,
        review_summaries: Optional[Dict[str, Any]] = None,
        evidence_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        review = review_summaries or {}
        evidence = evidence_summary or {}

        tasks: List[Dict[str, Any]] = []
        for task_name in plan.verification_tasks:
            tasks.append(
                self._evaluate_task(
                    task_name=task_name,
                    chapter_text=chapter_text,
                    review_summaries=review,
                    evidence_summary=evidence,
                    plan=plan,
                )
            )

        status_counts = {"passed": 0, "warning": 0, "failed": 0, "pending": 0}
        for item in tasks:
            status = str(item.get("status") or "pending")
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "plan_phase": plan.chapter_phase,
            "is_fast_path": plan.is_fast_path,
            "task_count": len(tasks),
            "status_counts": status_counts,
            "tasks": tasks,
            "summary": self._build_summary(tasks, status_counts, evidence),
        }

    def _evaluate_task(
        self,
        *,
        task_name: str,
        chapter_text: str,
        review_summaries: Dict[str, Any],
        evidence_summary: Dict[str, Any],
        plan: ContextPlan,
    ) -> Dict[str, Any]:
        if task_name == "commercial_hook_check":
            return self._evaluate_commercial_hook(chapter_text)
        if task_name == "claim_level_verification":
            return self._evaluate_claim_level_verification(
                chapter_text=chapter_text,
                plan=plan,
                evidence_summary=evidence_summary,
            )
        if task_name == "consistency_check":
            return self._evaluate_consistency(review_summaries.get("consistency"))
        if task_name == "continuity_check":
            return self._evaluate_continuity(review_summaries, chapter_text)
        if task_name == "foreshadowing_check":
            return self._evaluate_foreshadowing(review_summaries, evidence_summary)
        if task_name == "reader_simulation":
            return self._evaluate_structured_task("reader_simulation", review_summaries.get("reader_simulation"))
        if task_name == "self_critique":
            payload = review_summaries.get("self_critique") or review_summaries.get("combined_revision")
            return self._evaluate_structured_task("self_critique", payload)
        if task_name == "six_dimension_review":
            return self._evaluate_structured_task("six_dimension_review", review_summaries.get("six_dimension"))
        if task_name == "skill_policy_check":
            return self._evaluate_skill_policies(plan)
        if task_name.startswith("skill_checker:"):
            return self._evaluate_skill_checker(
                checker_key=task_name.split(":", 1)[1], chapter_text=chapter_text, plan=plan
            )
        return {
            "task": task_name,
            "status": "pending",
            "summary": "尚未接入统一验证器",
            "details": {},
        }

    def _evaluate_claim_level_verification(
        self,
        *,
        chapter_text: str,
        plan: ContextPlan,
        evidence_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        report = self.claim_verifier.verify(
            chapter_text=chapter_text,
            plan=plan,
            evidence_summary=evidence_summary,
        )
        blocking_count = int(report.get("blocking_count") or 0)
        claim_count = int(report.get("claim_count") or 0)
        return {
            "task": "claim_level_verification",
            "status": "failed" if blocking_count else "passed",
            "summary": (
                f"发现 {blocking_count} 条高风险未支撑叙事断言"
                if blocking_count
                else f"叙事断言验证通过，共检查 {claim_count} 条"
            ),
            "details": report,
        }

    def _evaluate_commercial_hook(self, chapter_text: str) -> Dict[str, Any]:
        tail = (chapter_text or "").strip()[-180:]
        if not tail:
            return {
                "task": "commercial_hook_check",
                "status": "warning",
                "summary": "章节内容为空，无法评估断章点",
                "details": {"score": 0.0},
            }

        suspense_hits = sum(
            1
            for token in ("？", "?", "……", "却", "忽然", "下一刻", "与此同时", "门外", "身后")
            if token in tail
        )
        end_bonus = 1 if not tail.endswith(("。", "！", "；")) else 0
        score = min(1.0, suspense_hits * 0.12 + end_bonus * 0.18 + (0.18 if len(tail) >= 60 else 0.06))
        status = "passed" if score >= 0.55 else "warning"
        summary = "结尾存在较明显的追更钩子" if status == "passed" else "结尾钩子偏弱，可考虑增强悬念或情绪抬升"
        return {
            "task": "commercial_hook_check",
            "status": status,
            "summary": summary,
            "details": {"score": round(score, 3), "tail_preview": tail[-80:]},
        }

    def _evaluate_consistency(self, payload: Any) -> Dict[str, Any]:
        if not payload:
            return {
                "task": "consistency_check",
                "status": "pending",
                "summary": "一致性检查未执行",
                "details": {},
            }

        violations = []
        if isinstance(payload, dict):
            violations = payload.get("violations") or payload.get("issues") or []
        if violations:
            status = "warning"
            summary = f"发现 {len(violations)} 项一致性问题"
        else:
            status = "passed"
            summary = "未发现显著一致性问题"
        return {
            "task": "consistency_check",
            "status": status,
            "summary": summary,
            "details": {"violations": violations[:5]},
        }

    def _evaluate_continuity(self, review_summaries: Dict[str, Any], chapter_text: str) -> Dict[str, Any]:
        consistency = self._evaluate_consistency(review_summaries.get("consistency"))
        if consistency["status"] != "pending":
            return {
                "task": "continuity_check",
                "status": consistency["status"],
                "summary": consistency["summary"],
                "details": consistency["details"],
            }

        short_text = len((chapter_text or "").strip()) < 300
        return {
            "task": "continuity_check",
            "status": "warning" if short_text else "passed",
            "summary": "章节过短，连续性判断可信度较低" if short_text else "未见明显连续性异常",
            "details": {"content_length": len((chapter_text or "").strip())},
        }

    def _evaluate_foreshadowing(
        self,
        review_summaries: Dict[str, Any],
        evidence_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = review_summaries.get("foreshadowing")
        if payload:
            return self._evaluate_structured_task("foreshadowing_check", payload)

        symbolic_count = int((evidence_summary.get("category_counts") or {}).get("symbolic_items") or 0)
        if symbolic_count > 0:
            return {
                "task": "foreshadowing_check",
                "status": "warning",
                "summary": "存在符号级证据/伏笔线索，但尚无显式伏笔验证结果",
                "details": {"symbolic_items": symbolic_count},
            }
        return {
            "task": "foreshadowing_check",
            "status": "passed",
            "summary": "当前未检测到需要重点处理的伏笔验证项",
            "details": {"symbolic_items": symbolic_count},
        }

    def _evaluate_structured_task(self, task_name: str, payload: Any) -> Dict[str, Any]:
        if not payload:
            return {
                "task": task_name,
                "status": "pending",
                "summary": f"{task_name} 未执行",
                "details": {},
            }
        if isinstance(payload, dict):
            if payload.get("status") == "scheduled_async":
                return {
                    "task": task_name,
                    "status": "pending",
                    "summary": f"{task_name} 已异步排队",
                    "details": payload,
                }
            score = payload.get("overall_score") or payload.get("score") or payload.get("final_score")
            if isinstance(score, (int, float)):
                status = "passed" if score >= 75 else "warning"
                return {
                    "task": task_name,
                    "status": status,
                    "summary": f"{task_name} 得分 {score}",
                    "details": payload,
                }
        return {
            "task": task_name,
            "status": "passed",
            "summary": f"{task_name} 已执行",
            "details": payload if isinstance(payload, dict) else {"value": payload},
        }

    def _evaluate_skill_policies(self, plan: ContextPlan) -> Dict[str, Any]:
        if not plan.skill_policies:
            return {
                "task": "skill_policy_check",
                "status": "passed",
                "summary": "未启用技能策略，无需校验",
                "details": {"skill_count": 0},
            }
        return {
            "task": "skill_policy_check",
            "status": "passed",
            "summary": f"已加载 {len(plan.skill_policies)} 条技能策略",
            "details": {"skills": [policy.skill_id for policy in plan.skill_policies]},
        }

    def _evaluate_skill_checker(self, *, checker_key: str, chapter_text: str, plan: ContextPlan) -> Dict[str, Any]:
        """Run safe, deterministic checker keys and retain text-range evidence.

        Checker keys are allow-listed here; skill versions can request a key but
        cannot execute arbitrary code stored in the database.
        """
        text = chapter_text or ""
        evidence: List[Dict[str, Any]] = []

        def add_match(match: re.Match[str], reason: str, severity: str = "warning") -> None:
            start, end = match.span()
            evidence.append({
                "char_start": start,
                "char_end": end,
                "excerpt": text[max(0, start - 24):min(len(text), end + 40)],
                "reason": reason,
                "severity": severity,
            })

        if checker_key == "limited_pov":
            for pattern in (r"殊不知", r"他不知道的是", r"与此同时，[^。！？]{0,36}的内心", r"作者认为"):
                for match in re.finditer(pattern, text):
                    add_match(match, "疑似越过当前视角直接解释未知信息")
        elif checker_key in {"rhetoric_density", "adjective_stack"}:
            if checker_key == "rhetoric_density":
                for match in re.finditer(r"仿佛|如同|宛如|像是|似乎", text):
                    add_match(match, "检测到可能以比喻替代具体行动")
            else:
                # 连续三个以上“X的Y”结构是可解释的保守告警，不直接判定为错误。
                for match in re.finditer(r"(?:[^，。！？\n]{1,8}的){3,}[^，。！？\n]{1,12}", text):
                    add_match(match, "连续修饰结构较密，建议删减形容词")
        elif checker_key in {"natural_ending", "omniscient_summary"}:
            tail_start = max(0, len(text) - 260)
            tail = text[tail_start:]
            patterns = (r"这一刻", r"从此", r"命运", r"注定", r"仿佛", r"如同", r"无人知道")
            for pattern in patterns:
                for match in re.finditer(pattern, tail):
                    # 将尾部相对位置转换为全文位置，避免把证据锚到错误段落。
                    start = tail_start + match.start()
                    end = tail_start + match.end()
                    evidence.append({
                        "char_start": start,
                        "char_end": end,
                        "excerpt": text[max(0, start - 24):min(len(text), end + 40)],
                        "reason": "结尾疑似使用旁白总结或象征性升华",
                        "severity": "warning",
                    })
        else:
            return {
                "task": f"skill_checker:{checker_key}",
                "status": "pending",
                "summary": "该技能检查器尚未接入安全检查器白名单",
                "details": {"checker_key": checker_key, "evidence": []},
            }

        # 同一命中最多保留 12 条，报告可直接用于前端定位且不会膨胀上下文。
        evidence = evidence[:12]
        status = "warning" if evidence else "passed"
        labels = {
            "limited_pov": "视角边界",
            "rhetoric_density": "比喻密度",
            "adjective_stack": "修饰堆叠",
            "natural_ending": "自然收束",
            "omniscient_summary": "全知旁白",
        }
        return {
            "task": f"skill_checker:{checker_key}",
            "status": status,
            "summary": f"{labels.get(checker_key, checker_key)}检查发现 {len(evidence)} 条提示" if evidence else f"{labels.get(checker_key, checker_key)}检查通过",
            "details": {"checker_key": checker_key, "hit_count": len(evidence), "evidence": evidence},
        }

    def _build_summary(
        self,
        tasks: Sequence[Dict[str, Any]],
        status_counts: Dict[str, int],
        evidence_summary: Dict[str, Any],
    ) -> str:
        if status_counts.get("failed"):
            return "存在必须关注的验证失败项"
        if status_counts.get("warning"):
            return "验证完成，但仍有需要人工关注的风险"
        if status_counts.get("pending"):
            return "验证部分已完成，仍有异步或未启用项"
        total_items = int(evidence_summary.get("total_items") or 0)
        return f"验证通过，参考了 {total_items} 条证据"
