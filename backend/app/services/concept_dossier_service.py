# AIMETA P=立项书蒸馏与压力推演|R=对话蒸馏立项书_对抗性推演_高危自动修订_采纳修复|NR=不含蓝图生成|E=ConceptDossierService|X=internal|A=立项质量层|D=llm_service,prompt_service,novel_service|S=db|RD=./README.ai
"""故事立项书服务：灵感对话 → 结构化立项书 → 压力推演 → 修订。

设计要点：
- 全链路软失败：任何 LLM/解析失败都返回 None 并保留既有产物，绝不向上抛
  （立项书是质量增益层，不能反过来阻断「对话→蓝图」主链路）。
- 幂等 + 并发防抖：converse is_complete 的后台蒸馏与确认页 GET 的同步蒸馏
  可能并发，per-project asyncio 锁 + 「已有产物直接返回」保证只跑一次。
- 存储形态（novel_projects.concept_dossier JSON）：
  {"dossier": {...}, "stress_report": {...}, "generated_at": iso, "stress_at": iso,
   "revised": bool}
"""
import asyncio
import copy
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.novel import NovelProject
from ..schemas.concept_dossier import ConceptDossier, PremiseStressReport
from ..utils.json_utils import repair_json, unwrap_markdown_json
from .llm_service import LLMService
from .prompt_service import PromptService

logger = logging.getLogger(__name__)

# 蒸馏输入的对话历史上限（字符）：立项书只需要共识，不需要全部细节
_HISTORY_CHAR_BUDGET = 12000
_DOSSIER_MAX_TOKENS = 4096
_STRESS_MAX_TOKENS = 4096

_dossier_locks: Dict[str, asyncio.Lock] = {}
_dossier_locks_guard = asyncio.Lock()


async def _get_dossier_lock(project_id: str) -> asyncio.Lock:
    async with _dossier_locks_guard:
        if project_id not in _dossier_locks:
            _dossier_locks[project_id] = asyncio.Lock()
        return _dossier_locks[project_id]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# 立项书内部路径 → 确认页中文区块名。毒点「修复建议」常把 JSON 键写进给作者看的句子，
# 必须在展示前替换；最长路径优先，避免 protagonist.identity 被拆成 identity。
_DOSSIER_FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("protagonist.charm_point", "主角代入点"),
    ("protagonist.predicament", "主角开局困境"),
    ("protagonist.identity", "主角身份处境"),
    ("protagonist.desire", "主角欲望"),
    ("protagonist.flaw", "主角缺陷"),
    ("protagonist.name", "主角"),
    ("golden_finger.growth_curve", "金手指成长曲线"),
    ("golden_finger.limitations", "金手指限制与代价"),
    ("golden_finger.mechanism", "金手指机制"),
    ("golden_finger.source", "金手指来源"),
    ("golden_finger.name", "金手指名称"),
    ("anticipation.ten_chapters", "前10章承诺"),
    ("anticipation.fifty_chapters", "前50章承诺"),
    ("anticipation.long_term", "长线承诺"),
    ("core_selling_line", "核心卖点"),
    ("title_candidates", "书名候选"),
    ("coolpoint_chain", "爽点链"),
    ("conflict_engine", "矛盾发动机"),
    ("core_conflict", "核心冲突"),
    ("platform_mode", "平台模式"),
    ("golden_finger", "金手指"),
    ("growth_curve", "金手指成长曲线"),
    ("charm_point", "主角代入点"),
    ("predicament", "主角开局困境"),
    ("limitations", "金手指限制与代价"),
    ("mechanism", "金手指机制"),
    ("anticipation", "期待感承诺"),
    ("identity", "主角身份处境"),
    ("audience", "目标读者"),
    ("notes", "补充说明"),
    ("genre", "题材"),
)


def humanize_dossier_jargon(text: str) -> str:
    """把修复建议里的内部字段路径换成立项书中文区块名。"""
    if not isinstance(text, str) or not text:
        return text or ""
    result = text
    for path, label in sorted(_DOSSIER_FIELD_LABELS, key=lambda item: len(item[0]), reverse=True):
        escaped = re.escape(path)
        result = re.sub(rf"[`\"'「]{escaped}[`\"'」]", label, result)
        result = re.sub(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", label, result)
    return result


def humanize_stress_report_dict(report: Dict[str, Any]) -> Dict[str, Any]:
    """清洗推演报告里给作者看的字符串，不改结构。返回副本。"""
    cleaned = copy.deepcopy(report)
    for point in cleaned.get("toxic_points") or []:
        if not isinstance(point, dict):
            continue
        for key in ("fix_suggestion", "reason", "issue"):
            value = point.get(key)
            if isinstance(value, str):
                point[key] = humanize_dossier_jargon(value)
    for section_key in ("conflict_sustainability", "golden_finger_collapse"):
        section = cleaned.get(section_key)
        if not isinstance(section, dict):
            continue
        for key, value in list(section.items()):
            if isinstance(value, str):
                section[key] = humanize_dossier_jargon(value)
    for key in ("summary", "overall_verdict"):
        value = cleaned.get(key)
        if isinstance(value, str):
            cleaned[key] = humanize_dossier_jargon(value)
    return cleaned


def humanize_stress_report(report: PremiseStressReport) -> PremiseStressReport:
    try:
        return PremiseStressReport.model_validate(humanize_stress_report_dict(report.model_dump()))
    except Exception:  # noqa: BLE001 - 清洗失败不阻断推演
        return report


def _compact_history_text(history_records: List[Any]) -> str:
    """把落库对话史压成蒸馏输入文本（user 取 value，assistant 取 ai_message）。"""
    lines: List[str] = []
    for record in history_records:
        role = getattr(record, "role", None)
        content = getattr(record, "content", None) or ""
        if not role or not content:
            continue
        text = ""
        try:
            normalized = unwrap_markdown_json(content)
            try:
                data = json.loads(normalized)
            except json.JSONDecodeError:
                data = json.loads(repair_json(normalized))
            if isinstance(data, dict):
                if role == "user":
                    value = data.get("value")
                    if isinstance(value, str):
                        text = value
                elif role == "assistant":
                    ai_message = data.get("ai_message")
                    if isinstance(ai_message, str):
                        text = ai_message
        except Exception:  # noqa: BLE001 - 坏记录退回截断原文
            text = content[:300]
        if not text.strip():
            continue
        speaker = "作者" if role == "user" else "构思助手"
        lines.append(f"{speaker}：{text.strip()}")
    joined = "\n".join(lines)
    if len(joined) > _HISTORY_CHAR_BUDGET:
        # 头尾保留：开场定调 + 尾部最新共识都是立项书的关键素材
        head = joined[: _HISTORY_CHAR_BUDGET // 3]
        tail = joined[-(_HISTORY_CHAR_BUDGET * 2 // 3):]
        joined = f"{head}\n……（中段对话已截断）……\n{tail}"
    return joined


def format_dossier_for_prompt(dossier: Dict[str, Any]) -> str:
    """把立项书 JSON 压成蓝图 Stage A 的注入文本（最高优先级设定锚点）。"""
    if not isinstance(dossier, dict) or not dossier:
        return ""
    lines: List[str] = ["【故事立项书】（最高优先级设定依据，对话记录仅作细节补充）"]

    def _add(label: str, value: Any) -> None:
        if isinstance(value, str) and value.strip():
            lines.append(f"- {label}：{value.strip()}")

    _add("核心卖点句", dossier.get("core_selling_line"))
    _add("题材", dossier.get("genre"))
    _add("目标读者", dossier.get("audience"))
    _add("平台模式", dossier.get("platform_mode"))

    protagonist = dossier.get("protagonist")
    if isinstance(protagonist, dict):
        parts = []
        for key, label in (
            ("name", "主角"), ("identity", "身份"), ("desire", "欲望"),
            ("flaw", "缺陷"), ("predicament", "困境"), ("charm_point", "代入点"),
        ):
            value = protagonist.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(f"{label}={value.strip()}")
        if parts:
            lines.append("- 主角三件套：" + "；".join(parts))

    _add("核心冲突", dossier.get("core_conflict"))
    _add("矛盾发动机", dossier.get("conflict_engine"))

    golden_finger = dossier.get("golden_finger")
    if isinstance(golden_finger, dict) and (golden_finger.get("name") or "").strip():
        parts = []
        for key, label in (
            ("name", "名称"), ("source", "来源"), ("mechanism", "机制"),
            ("limitations", "限制与代价"), ("growth_curve", "成长曲线"),
        ):
            value = golden_finger.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(f"{label}={value.strip()}")
        if parts:
            lines.append("- 金手指：" + "；".join(parts))

    anticipation = dossier.get("anticipation")
    if isinstance(anticipation, dict):
        parts = []
        for key, label in (
            ("ten_chapters", "前10章"), ("fifty_chapters", "前50章"), ("long_term", "长线"),
        ):
            value = anticipation.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(f"{label}={value.strip()}")
        if parts:
            lines.append("- 期待感承诺：" + "；".join(parts))

    coolpoints = dossier.get("coolpoint_chain")
    if isinstance(coolpoints, list):
        cleaned = [str(c).strip() for c in coolpoints if str(c).strip()]
        if cleaned:
            lines.append("- 爽点链：" + " → ".join(cleaned))

    titles = dossier.get("title_candidates")
    if isinstance(titles, list):
        cleaned = [str(t).strip() for t in titles if str(t).strip()]
        if cleaned:
            lines.append("- 书名候选：" + "、".join(cleaned))

    _add("其余共识", dossier.get("notes"))
    return "\n".join(lines) if len(lines) > 1 else ""


def _hoist_misplaced_stress_fields(report: PremiseStressReport) -> PremiseStressReport:
    """纠正推演报告的字段错嵌（2026-08-15 测试服实测变体）。

    schema 全字段带默认值 + extra=allow 的组合下，思考型模型会把 toxic_points/
    overall_verdict/summary 误嵌进 golden_finger_collapse 等子对象里——顶层校验
    照样通过，但确认页读到的是空报告。顶层为空且子对象里有同名内容时上提。
    """
    data = report.model_dump()
    changed = False
    for container_key in ("golden_finger_collapse", "conflict_sustainability"):
        container = data.get(container_key)
        if not isinstance(container, dict):
            continue
        nested_points = container.get("toxic_points")
        if not data.get("toxic_points") and isinstance(nested_points, list) and nested_points:
            data["toxic_points"] = container.pop("toxic_points")
            changed = True
        for scalar in ("overall_verdict", "summary"):
            nested_value = container.get(scalar)
            if (
                not str(data.get(scalar) or "").strip()
                and isinstance(nested_value, str)
                and nested_value.strip()
            ):
                data[scalar] = container.pop(scalar)
                changed = True
    if not changed:
        return report
    try:
        return PremiseStressReport.model_validate(data)
    except Exception:  # noqa: BLE001 - 纠偏失败保留原报告
        return report


class ConceptDossierService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------
    @staticmethod
    def get_state(project: NovelProject) -> Dict[str, Any]:
        state = project.concept_dossier
        if not isinstance(state, dict):
            return {}
        state = dict(state)
        report = state.get("stress_report")
        if isinstance(report, dict):
            state["stress_report"] = humanize_stress_report_dict(report)
        return state

    # ------------------------------------------------------------------
    # 主入口：确保立项书（+按档位推演）就绪；幂等，全程软失败
    # ------------------------------------------------------------------
    async def ensure_dossier(
        self,
        project_id: str,
        user_id: int,
        *,
        run_stress: bool,
        exclusions: str = "",
    ) -> Dict[str, Any]:
        lock = await _get_dossier_lock(project_id)
        async with lock:
            project = await self.session.get(NovelProject, project_id)
            if project is None:
                return {}
            state = dict(self.get_state(project))

            if not isinstance(state.get("dossier"), dict):
                dossier = await self._distill(project, user_id, exclusions=exclusions)
                if dossier is not None:
                    state["dossier"] = dossier.model_dump()
                    state["generated_at"] = _now_iso()
                    state.pop("stress_report", None)
                    state.pop("stress_at", None)
                    project.concept_dossier = dict(state)
                    await self.session.commit()

            if (
                run_stress
                and await self._stress_platform_enabled()
                and isinstance(state.get("dossier"), dict)
                and not isinstance(state.get("stress_report"), dict)
            ):
                report, revised_dossier = await self._stress_test(
                    state["dossier"], user_id, exclusions=exclusions
                )
                if report is not None:
                    state["stress_report"] = report.model_dump()
                    state["stress_at"] = _now_iso()
                    if revised_dossier is not None:
                        state["dossier"] = revised_dossier.model_dump()
                        state["revised"] = True
                    project.concept_dossier = dict(state)
                    await self.session.commit()

            return state

    async def _stress_platform_enabled(self) -> bool:
        """平台级推演熔断（blueprint.stress_enabled）；与档位无关。"""
        from .blueprint_review_service import STRESS_ENABLED_KEY, read_blueprint_switch

        return await read_blueprint_switch(self.session, STRESS_ENABLED_KEY, True)

    # ------------------------------------------------------------------
    # 分块编辑（确认页 PATCH）：浅合并顶层键，嵌套 dict 再合一层
    # ------------------------------------------------------------------
    async def patch_dossier(self, project: NovelProject, partial: Dict[str, Any]) -> Dict[str, Any]:
        state = dict(self.get_state(project))
        dossier = dict(state.get("dossier") or {})
        for key, value in (partial or {}).items():
            if isinstance(value, dict) and isinstance(dossier.get(key), dict):
                merged = dict(dossier[key])
                merged.update(value)
                dossier[key] = merged
            else:
                dossier[key] = value
        state["dossier"] = dossier
        state["edited_at"] = _now_iso()
        project.concept_dossier = dict(state)
        await self.session.commit()
        return state

    # ------------------------------------------------------------------
    # 采纳修复建议（确认页动作）：把推演报告的全部修复建议应用回立项书
    # ------------------------------------------------------------------
    async def apply_stress_fixes(self, project: NovelProject, user_id: int) -> Optional[Dict[str, Any]]:
        state = dict(self.get_state(project))
        dossier = state.get("dossier")
        report = state.get("stress_report")
        if not isinstance(dossier, dict) or not isinstance(report, dict):
            return None
        toxic_points = [
            p for p in (report.get("toxic_points") or [])
            if isinstance(p, dict) and (p.get("fix_suggestion") or "").strip()
        ]
        if not toxic_points:
            return None
        revised = await self._revise_dossier(dossier, toxic_points, user_id)
        if revised is None:
            return None
        state["dossier"] = revised.model_dump()
        state["revised"] = True
        state["fixes_applied_at"] = _now_iso()
        project.concept_dossier = dict(state)
        await self.session.commit()
        return state

    # ------------------------------------------------------------------
    # 内部：蒸馏
    # ------------------------------------------------------------------
    async def _distill(
        self, project: NovelProject, user_id: int, *, exclusions: str = ""
    ) -> Optional[ConceptDossier]:
        try:
            from .novel_service import NovelService

            history_records = await NovelService(self.session).list_conversations(project.id)
            history_text = _compact_history_text(history_records)
            if not history_text.strip():
                logger.info("项目 %s 立项书蒸馏跳过：无有效对话历史", project.id)
                return None

            system_prompt = await self.prompt_service.get_prompt("concept_dossier")
            if not system_prompt:
                logger.warning("项目 %s 立项书蒸馏跳过：缺少 concept_dossier 提示词", project.id)
                return None

            parts = [f"【灵感对话记录】\n{history_text}"]
            effective_exclusions = (exclusions or project.exclusions or "").strip()
            if effective_exclusions:
                parts.append(f"【创作禁区（立项书任何字段不得触碰）】\n{effective_exclusions}")
            prompt = "\n\n".join(parts)

            dossier = await self.llm_service.generate_structured(
                prompt=prompt,
                schema=ConceptDossier,
                system_prompt=system_prompt,
                temperature=0.4,
                user_id=user_id,
                max_tokens=_DOSSIER_MAX_TOKENS,
                default=None,
            )
            if not (dossier.core_selling_line or "").strip():
                logger.warning("项目 %s 立项书蒸馏产物缺核心卖点句，按失败处理", project.id)
                return None
            logger.info("项目 %s 立项书蒸馏完成", project.id)
            return dossier
        except Exception as exc:  # noqa: BLE001 - 软失败
            logger.warning("项目 %s 立项书蒸馏失败（不阻断主链路）: %s", project.id, exc)
            return None

    # ------------------------------------------------------------------
    # 内部：压力推演（含高危自动修订一轮）
    # ------------------------------------------------------------------
    async def _stress_test(
        self, dossier: Dict[str, Any], user_id: int, *, exclusions: str = ""
    ) -> tuple[Optional[PremiseStressReport], Optional[ConceptDossier]]:
        try:
            system_prompt = await self.prompt_service.get_prompt("premise_stress_test")
            if not system_prompt:
                logger.warning("压力推演跳过：缺少 premise_stress_test 提示词")
                return None, None

            prompt = (
                "【故事立项书】\n"
                + json.dumps(dossier, ensure_ascii=False, indent=1)
                + "\n\n【写修复建议时】只用中文区块名（主角身份处境、金手指限制与代价、矛盾发动机、"
                "爽点链、期待感承诺、补充说明等），不要写英文变量名。"
            )
            report = await self.llm_service.generate_structured(
                prompt=prompt,
                schema=PremiseStressReport,
                system_prompt=system_prompt,
                temperature=0.3,
                user_id=user_id,
                max_tokens=_STRESS_MAX_TOKENS,
                default=None,
            )
            if report is None:
                return None, None
            report = _hoist_misplaced_stress_fields(report)
            report = humanize_stress_report(report)

            revised: Optional[ConceptDossier] = None
            high_risk = [p.model_dump() for p in report.high_risk_points()]
            if high_risk:
                logger.info("立项书推演发现 %d 个高危毒点，触发一轮自动修订", len(high_risk))
                revised = await self._revise_dossier(dossier, high_risk, user_id, exclusions=exclusions)
            return report, revised
        except Exception as exc:  # noqa: BLE001 - 软失败
            logger.warning("立项书压力推演失败（不阻断主链路）: %s", exc)
            return None, None

    # ------------------------------------------------------------------
    # 内部：定向修订（沿用矫正重问模式：原产物 + 硬约束追问）
    # ------------------------------------------------------------------
    async def _revise_dossier(
        self,
        dossier: Dict[str, Any],
        toxic_points: List[Dict[str, Any]],
        user_id: int,
        *,
        exclusions: str = "",
    ) -> Optional[ConceptDossier]:
        try:
            system_prompt = await self.prompt_service.get_prompt("concept_dossier")
            if not system_prompt:
                return None
            issues_lines = []
            for point in toxic_points:
                issues_lines.append(
                    f"- [{point.get('severity', '高危')}] {point.get('issue', '')}："
                    f"{point.get('reason', '')}\n  修复方向：{point.get('fix_suggestion', '')}"
                )
            parts = [
                "【待修订的故事立项书】\n" + json.dumps(dossier, ensure_ascii=False, indent=1),
                "【主编压力推演点名的毒点（必须逐条修掉）】\n" + "\n".join(issues_lines),
                "【修订任务】\n"
                "输出修订后的完整立项书 JSON：只改动与上述毒点直接相关的字段，"
                "其余字段原样保留（允许为保持一致性做最小限度的连带措辞调整）。"
                "修订必须实质解决问题，不许只在措辞上敷衍；核心卖点与既有亮点不得因修订而变平庸。",
            ]
            effective_exclusions = (exclusions or "").strip()
            if effective_exclusions:
                parts.append(f"【创作禁区（修订后仍不得触碰）】\n{effective_exclusions}")
            revised = await self.llm_service.generate_structured(
                prompt="\n\n".join(parts),
                schema=ConceptDossier,
                system_prompt=system_prompt,
                temperature=0.4,
                user_id=user_id,
                max_tokens=_DOSSIER_MAX_TOKENS,
                default=None,
            )
            if not (revised.core_selling_line or "").strip():
                return None
            return revised
        except Exception as exc:  # noqa: BLE001 - 软失败
            logger.warning("立项书修订失败（保留原立项书）: %s", exc)
            return None


async def background_ensure_dossier(project_id: str, user_id: int, *, run_stress: bool) -> None:
    """converse is_complete 后的后台蒸馏入口（safe_create_task 调度，自带会话）。"""
    from ..db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            await ConceptDossierService(session).ensure_dossier(
                project_id, user_id, run_stress=run_stress
            )
    except Exception as exc:  # noqa: BLE001 - 后台任务绝不外抛
        logger.warning("项目 %s 后台立项书蒸馏失败: %s", project_id, exc)
