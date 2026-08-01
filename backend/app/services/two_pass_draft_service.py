# AIMETA P=两遍制草稿改写|R=先轻约束写草稿再据规则改写|NR=不含后处理_不含版本评选|E=TwoPassDraftService|X=internal|A=生成策略|D=llm|S=net|RD=./README.ai
"""两遍制：草稿 → 改写

针对「约束堆叠上限」与「防错非求好」两个核心缺陷。

现状：`prompt_assembly_service` 会把 **26 个段落**一次性堆进同一个生成提示，其中
约一半是「不许犯什么错」（硬性约束/禁止角色/力量上限/去模板化/风格指纹/白金准则…）。
模型在单次生成里要同时**把故事写好**和**满足一张长清单**，注意力被后者吃掉——
写出来的东西"没毛病但也没劲"。

两遍制把这两件事拆开：
- **第一遍（草稿）**：只给「发生了什么 / 人物是谁 / 往哪走」这类事实与方向，
  明确告诉模型先不用管文风与禁令，把劲道、情绪和推进写出来；
- **第二遍（改写）**：拿着草稿 + 全部规则做**改写**（不是重写），
  在保住草稿劲道的前提下把违规处修掉。

关键约束：第二遍**只改不续**——不得引入草稿里没有的人物/设定/事件，否则「防错」
会顺手把「求好」也改没，并引入新的幻觉。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

Section = Tuple[str, str]

# 「规则类」段落的标签特征。命中即划归第二遍。
#
# 刻意用**黑名单**而非白名单：将来新增的段落默认进草稿，行为退化回「一次性堆叠」
# 这个已知状态；若默认进约束侧，则可能悄悄饿掉草稿的关键事实——前者可控，后者难查。
_CONSTRAINT_MARKERS: Tuple[str, ...] = (
    "写作硬性约束",
    "白金写作准则",
    "白金节奏控制",
    "禁止角色",
    "力量体系约束",
    "题材写作约束",
    "作者风格指纹",
    "情绪表达去模板化",
    "节奏纠偏指令",
    "故事轨迹分析",
    "叙事差异化约束",
    "写作风格",      # 用户风格规则（标签由 style_label 动态生成）
    "风格参考",
    "库风格样本",
    "创作DNA融合指引",
)

# 第二遍除规则外仍需锚定的少数事实段（防止「改写」改跑题或改掉章节目标）。
# 刻意极少——草稿本身已经承载故事，再把上下文全量重灌就是在第二遍重建堆叠。
_REWRITE_ANCHOR_MARKERS: Tuple[str, ...] = (
    "当前章节目标",
    "角色当前状态",
)


class TwoPassDraftService:
    """两遍制草稿-改写。全程可降级：任一环失败都退回单遍结果。"""

    # ------------------------------------------------------------------ 纯函数
    @staticmethod
    def partition_sections(sections: Sequence[Section]) -> Tuple[List[Section], List[Section]]:
        """把 prompt sections 切成（草稿用的事实/方向, 改写才施加的规则）。"""
        draft: List[Section] = []
        constraints: List[Section] = []
        for label, content in sections:
            if not content:
                continue
            if any(marker in label for marker in _CONSTRAINT_MARKERS):
                constraints.append((label, content))
            else:
                draft.append((label, content))
        return draft, constraints

    @staticmethod
    def _join(sections: Sequence[Section]) -> str:
        return "\n\n".join(f"{label}\n{content}" for label, content in sections if content)

    @classmethod
    def build_draft_input(cls, draft_sections: Sequence[Section]) -> str:
        return cls._join(draft_sections)

    @classmethod
    def build_rewrite_input(
        cls,
        *,
        draft_text: str,
        constraint_sections: Sequence[Section],
        all_sections: Sequence[Section],
    ) -> str:
        """第二遍输入 = 少量事实锚点 + 全部规则 + 草稿全文。"""
        anchors = [
            (label, content)
            for label, content in all_sections
            if any(marker in label for marker in _REWRITE_ANCHOR_MARKERS) and content
        ]
        parts: List[str] = []
        if anchors:
            parts.append(cls._join(anchors))
        if constraint_sections:
            parts.append(cls._join(constraint_sections))
        parts.append(f"[待改写草稿]\n{draft_text}")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------ 编排
    async def rewrite(
        self,
        *,
        draft_text: str,
        sections: Sequence[Section],
        llm_service: Any,
        prompt_service: Any,
        user_id: int,
        target_word_count: Optional[int] = None,
        validator: Optional[Callable[[str], bool]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """第二遍：据规则改写草稿。

        返回 (最终文本, 报告)。任何失败都返回**原草稿**——两遍制绝不能比一遍更差。
        """
        report: Dict[str, Any] = {"applied": False}
        if not draft_text or not draft_text.strip():
            report["reason"] = "empty_draft"
            return draft_text, report

        _, constraint_sections = self.partition_sections(sections)
        if not constraint_sections:
            # 没有任何规则要施加，第二遍纯属浪费一次调用
            report["reason"] = "no_constraints"
            return draft_text, report

        try:
            system_prompt = await prompt_service.get_prompt("two_pass_rewrite")
            if not system_prompt:
                logger.warning("缺少 two_pass_rewrite 提示词，保留草稿")
                report["reason"] = "prompt_missing"
                return draft_text, report

            user_input = self.build_rewrite_input(
                draft_text=draft_text,
                constraint_sections=constraint_sections,
                all_sections=sections,
            )
            if target_word_count:
                user_input += f"\n\n[篇幅要求]\n目标约 {target_word_count} 字，改写后不得明显缩水。"

            revised = await llm_service.get_llm_response(
                system_prompt=system_prompt,
                conversation_history=[{"role": "user", "content": user_input}],
                temperature=0.6,
                user_id=user_id,
                response_format=None,
            )
        except Exception as exc:  # noqa: BLE001 - 改写失败保留草稿
            logger.warning("两遍制改写失败，保留草稿: %s", exc)
            report["reason"] = f"error:{type(exc).__name__}"
            return draft_text, report

        revised = (revised or "").strip()
        if not revised:
            report["reason"] = "empty_response"
            return draft_text, report
        if validator is not None and not validator(revised):
            # 与 optimizer/polish 同口径：产出不像正文就退回上一步文本
            logger.warning("两遍制改写产出未通过正文校验，保留草稿")
            report["reason"] = "validation_failed"
            return draft_text, report

        # 大幅缩水通常意味着模型把"改写"做成了"摘要"，宁可要原草稿
        if len(revised) < len(draft_text) * 0.6:
            logger.warning(
                "两遍制改写后长度不足草稿六成（%d → %d），保留草稿",
                len(draft_text), len(revised),
            )
            report["reason"] = "shrunk_too_much"
            report["draft_len"] = len(draft_text)
            report["revised_len"] = len(revised)
            return draft_text, report

        report.update({
            "applied": True,
            "draft_len": len(draft_text),
            "revised_len": len(revised),
            "constraint_sections": len(constraint_sections),
        })
        return revised, report
