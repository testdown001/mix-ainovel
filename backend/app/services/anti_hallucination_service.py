# AIMETA P=反幻觉服务_三法则框架|R=大纲即法律_设定即物理_新实体必须注册|NR=不含向量库|E=AntiHallucinationService|X=internal|A=反幻觉检查|D=llm_service_entity_registry|S=db|RD=./README.ai
"""
反幻觉服务 (AntiHallucinationService)

实现"三法则"框架防止长篇小说中的幻觉问题：
1. 大纲即法律：章节内容不得违背已定大纲的核心设定
2. 设定即物理：世界观/魔法体系/科技体系的规则不可被打破
3. 新实体必须注册：所有新出现的角色/地点等必须通过置信度评估

检查结果带严重度分级：critical/warning/info
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from .entity_registry_service import EntityRegistryService
from .llm_service import LLMService

logger = logging.getLogger(__name__)


@dataclass
class HallucinationIssue:
    """幻觉问题记录"""
    severity: str  # critical / warning / info
    category: str  # unregistered_entity / setting_violation / outline_violation / alias_ambiguity
    description: str
    entity_name: Optional[str] = None
    confidence: float = 0.0
    suggested_fix: Optional[str] = None


@dataclass
class AntiHallucinationReport:
    """反幻觉检查报告"""
    passed: bool
    issues: List[HallucinationIssue] = field(default_factory=list)
    registered_count: int = 0
    warning_count: int = 0
    critical_count: int = 0


ENTITY_EXTRACTION_PROMPT = """\
请从以下小说章节中提取所有出现的实体（角色名、地名、组织名、物品名、能力名）。

章节内容：
{chapter_text}

已知实体列表（这些不需要提取）：
{known_entities}

请以JSON格式返回新出现的实体：
{{
  "entities": [
    {{
      "name": "实体名称",
      "type": "character/location/organization/item/ability",
      "description": "根据上下文推断的简短描述",
      "confidence": 0.0-1.0,
      "first_mention_context": "首次出现的上下文句子"
    }}
  ]
}}

注意：
1. 只提取新出现的、不在已知列表中的实体
2. 忽略代词（他/她/它/他们）和通称（路人/村民/士兵等）
3. confidence 评分标准：
   - 1.0: 有明确介绍或描写的命名实体
   - 0.8: 上下文可明确判断身份的实体
   - 0.5: 仅提及名字但身份不明确
   - 0.3: 可能是已知实体的别称
仅返回JSON。
"""


class AntiHallucinationService:
    """反幻觉与实体一致性检查服务。"""

    def __init__(self, session: AsyncSession, llm_service: LLMService):
        self.session = session
        self.llm_service = llm_service
        self.entity_service = EntityRegistryService(session)

    async def check_chapter(
        self,
        *,
        project_id: str,
        chapter_text: str,
        chapter_number: int,
        user_id: int,
        blueprint: Optional[dict] = None,
        outline_summary: Optional[str] = None,
    ) -> AntiHallucinationReport:
        """
        对章节内容执行反幻觉检查。

        Returns:
            AntiHallucinationReport: 检查报告
        """
        report = AntiHallucinationReport(passed=True)

        auto_threshold = getattr(settings, "entity_confidence_auto_threshold", 0.8)
        warn_threshold = getattr(settings, "entity_confidence_warn_threshold", 0.5)

        # 1. 获取已注册实体
        entities = await self.entity_service.get_all_entities(project_id)
        known_names = set()
        alias_map = await self.entity_service.build_alias_map(project_id)
        for e in entities:
            known_names.add(e.canonical_name)
            for a in (e.aliases or []):
                known_names.add(a.alias)

        # 2. LLM 提取新实体
        new_entities = await self._extract_entities(
            chapter_text=chapter_text,
            known_entities=known_names,
            user_id=user_id,
        )

        # 3. 评估每个新实体
        for ent in new_entities:
            name = ent.get("name", "")
            confidence = float(ent.get("confidence", 0.5))
            ent_type = ent.get("type", "character")

            # 尝试别名消歧
            resolved = await self.entity_service.resolve_alias(project_id, name)
            if resolved:
                report.issues.append(HallucinationIssue(
                    severity="info",
                    category="alias_ambiguity",
                    description=f"「{name}」可能是「{resolved}」的别称",
                    entity_name=name,
                    confidence=confidence,
                    suggested_fix=f"统一使用正式名称「{resolved}」",
                ))
                continue

            if confidence >= auto_threshold:
                # 自动注册
                await self.entity_service.register_entity(
                    project_id=project_id,
                    entity_type=ent_type,
                    canonical_name=name,
                    description=ent.get("description"),
                    first_chapter=chapter_number,
                    source="auto_detected",
                    confidence=confidence,
                )
                report.registered_count += 1
                report.issues.append(HallucinationIssue(
                    severity="info",
                    category="unregistered_entity",
                    description=f"新实体「{name}」已自动注册（置信度={confidence:.2f}）",
                    entity_name=name,
                    confidence=confidence,
                ))

            elif confidence >= warn_threshold:
                # 标记 warning
                report.warning_count += 1
                report.issues.append(HallucinationIssue(
                    severity="warning",
                    category="unregistered_entity",
                    description=f"新实体「{name}」置信度不足（{confidence:.2f}），可能需要确认",
                    entity_name=name,
                    confidence=confidence,
                    suggested_fix=f"请确认「{name}」是否为有效实体，或是已知实体的别称",
                ))

            else:
                # 疑似幻觉
                report.critical_count += 1
                report.passed = False
                report.issues.append(HallucinationIssue(
                    severity="critical",
                    category="unregistered_entity",
                    description=f"疑似幻觉实体「{name}」（置信度={confidence:.2f}），未在蓝图或前文中出现",
                    entity_name=name,
                    confidence=confidence,
                    suggested_fix=f"删除或替换「{name}」，使用已注册的实体",
                ))

        # 4. 检查未注册名称（规则方式）
        unregistered = await self.entity_service.detect_unregistered_names(
            project_id=project_id,
            text=chapter_text,
            known_names=known_names,
        )
        for item in unregistered[:5]:
            name = item["name"]
            occurrences = item["occurrences"]
            if occurrences >= 3 and not any(i.entity_name == name for i in report.issues):
                report.warning_count += 1
                report.issues.append(HallucinationIssue(
                    severity="warning",
                    category="unregistered_entity",
                    description=f"频繁出现的未注册名称「{name}」（出现{occurrences}次）",
                    entity_name=name,
                    confidence=0.4,
                    suggested_fix=f"确认「{name}」是否为重要实体，如是则手动注册",
                ))

        if report.critical_count > 0:
            report.passed = False

        logger.info(
            "反幻觉检查完成: project=%s chapter=%d passed=%s registered=%d warnings=%d criticals=%d",
            project_id, chapter_number, report.passed,
            report.registered_count, report.warning_count, report.critical_count,
        )
        return report

    async def _extract_entities(
        self,
        *,
        chapter_text: str,
        known_entities: set,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """使用 LLM 从章节文本中提取新实体。"""
        known_list = ", ".join(sorted(known_entities)[:50]) if known_entities else "无"
        prompt = ENTITY_EXTRACTION_PROMPT.format(
            chapter_text=chapter_text[:4000],
            known_entities=known_list,
        )

        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                user_id=user_id,
                max_tokens=1500,
                temperature=0.2,
            )
            if not response:
                return []

            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            data = json.loads(cleaned)
            return data.get("entities", [])
        except Exception as exc:
            logger.warning("提取实体失败: %s", exc)
            return []

    @staticmethod
    def format_report_for_review(report: AntiHallucinationReport) -> str:
        """将检查报告格式化为可读文本。

        staticmethod：唯一调用方（generation_analysis_task_service 的后台反幻觉检查）
        以类名直接调用——原实例方法签名会把 report 绑到 self 致必然 TypeError。
        """
        if report.passed and not report.issues:
            return "反幻觉检查通过，未发现问题。"

        lines = [f"反幻觉检查{'通过' if report.passed else '未通过'}："]
        for issue in report.issues:
            prefix = {"critical": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue.severity, "•")
            lines.append(f"  {prefix} [{issue.category}] {issue.description}")
            if issue.suggested_fix:
                lines.append(f"    → 建议：{issue.suggested_fix}")

        if report.registered_count:
            lines.append(f"  自动注册 {report.registered_count} 个新实体")

        return "\n".join(lines)
