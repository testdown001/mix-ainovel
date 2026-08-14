# AIMETA P=提示词预算管理器|R=token预算分配_截断_压缩|NR=不含API路由|E=PromptBudgetManager|X=internal|A=工具类|D=none|S=none
"""
P5 优化: Prompt Token Budget Manager

为每个 prompt section 分配 token 预算，超额时自动截断/压缩，
同时重新排列 section 顺序以利用 LLM Provider 的 Prompt Caching 特性。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 中文约 1.5 字符/token, 英文约 4 字符/token，混合取 ~2 字符/token
_CHARS_PER_TOKEN = 2


def _estimate_tokens(text: str) -> int:
    """粗略估算文本的 token 数量（中英混合取均值）。"""
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """将文本截断到指定 token 数量，在完整段落边界截断。"""
    if _estimate_tokens(text) <= max_tokens:
        return text

    max_chars = max_tokens * _CHARS_PER_TOKEN
    # 尝试在段落边界截断
    truncated = text[:max_chars]
    last_newline = truncated.rfind("\n\n")
    if last_newline > max_chars * 0.6:
        truncated = truncated[:last_newline]
    else:
        # 兜底按行截断：避免把一行（如蓝图摘要的一条设定）拦腰截断
        last_line_break = truncated.rfind("\n")
        if last_line_break > max_chars * 0.6:
            truncated = truncated[:last_line_break]
    return truncated.rstrip() + "\n\n…（已截断，以上为最相关内容）"


@dataclass
class SectionBudget:
    """单个 section 的预算配置。"""
    priority: int  # 1=核心(不截断) 2=重要 3=可选 4=低优先
    max_tokens: int = 0  # 0 = 不限制
    label: str = ""


# 各 section 的默认预算配置（按 section title 的关键字匹配）
# priority: 1=绝不截断 2=重要但可截断 3=可选可压缩 4=低优先级可丢弃
_DEFAULT_BUDGETS: Dict[str, SectionBudget] = {
    # TIER 1: 核心指令 — 不截断
    "当前章节目标": SectionBudget(priority=1),
    "剧情推演": SectionBudget(priority=1),
    "创作任务书": SectionBudget(priority=1),
    "章节导演脚本": SectionBudget(priority=1),
    "章节字数要求": SectionBudget(priority=1),
    "字数与节奏要求": SectionBudget(priority=1),
    "语言风格硬约束": SectionBudget(priority=1),
    "白金写作准则": SectionBudget(priority=1),
    "禁止角色": SectionBudget(priority=1),
    "用户写作风格": SectionBudget(priority=1),
    "写作硬性约束": SectionBudget(priority=1),
    "高优先级伏笔提醒": SectionBudget(priority=1),
    "角色当前状态": SectionBudget(priority=1),
    "节奏纠偏指令": SectionBudget(priority=1),

    # TIER 2: 上下文参考 — 可截断
    "故事骨架": SectionBudget(priority=2, max_tokens=1500),
    "上一章摘要": SectionBudget(priority=2, max_tokens=1000),
    "上一章结尾": SectionBudget(priority=2, max_tokens=800),
    "世界蓝图": SectionBudget(priority=2, max_tokens=1200),
    "项目长期记忆": SectionBudget(priority=2, max_tokens=1500),
    "记忆层上下文": SectionBudget(priority=2, max_tokens=1500),
    "卷级前情": SectionBudget(priority=2, max_tokens=800),
    "全书脉络": SectionBudget(priority=2, max_tokens=600),
    "追更钩子连续性": SectionBudget(priority=2, max_tokens=600),

    # TIER 2.5: RAG 检索 — 可压缩
    "RAG精筛上下文": SectionBudget(priority=2, max_tokens=1500),
    "检索到的剧情上下文": SectionBudget(priority=2, max_tokens=1500),
    "检索到的章节摘要": SectionBudget(priority=3, max_tokens=800),

    # TIER 3: 补充约束 — 可压缩
    "题材写作约束": SectionBudget(priority=3, max_tokens=500),
    "作者风格指纹": SectionBudget(priority=3, max_tokens=800),
    "白金节奏控制": SectionBudget(priority=3, max_tokens=500),
    "情绪表达去模板化约束": SectionBudget(priority=3, max_tokens=400),
    "模式差异化约束": SectionBudget(priority=3, max_tokens=400),
    "风格参考": SectionBudget(priority=3, max_tokens=800),
    "参考桥段": SectionBudget(priority=3, max_tokens=600),
    "写法基准": SectionBudget(priority=2, max_tokens=500),
    "叙事差异化约束": SectionBudget(priority=3, max_tokens=500),

    # Enhanced flow sections
    "角色档案": SectionBudget(priority=2, max_tokens=1500),
    "世界观设定": SectionBudget(priority=2, max_tokens=1000),
    "阵营势力": SectionBudget(priority=3, max_tokens=800),
    "伏笔": SectionBudget(priority=3, max_tokens=600),
}

# 默认总预算上限 (tokens)
DEFAULT_TOTAL_BUDGET = 12000


class PromptBudgetManager:
    """
    Prompt Token Budget Manager.

    根据优先级为每个 prompt section 分配 token 预算，
    超额时自动截断，并重新排列为 Prompt Cache 友好的顺序。
    """

    def __init__(
        self,
        total_budget: int = DEFAULT_TOTAL_BUDGET,
        budgets: Optional[Dict[str, SectionBudget]] = None,
    ):
        self.total_budget = total_budget
        self.budgets = budgets or _DEFAULT_BUDGETS

    def _match_budget(self, title: str) -> SectionBudget:
        """根据 section title 匹配预算配置。"""
        for keyword, budget in self.budgets.items():
            if keyword in title:
                return budget
        # 未匹配的 section 默认为 priority=3, 800 tokens
        return SectionBudget(priority=3, max_tokens=800)

    def apply_budget(
        self,
        sections: List[Tuple[str, str]],
    ) -> List[Tuple[str, str]]:
        """
        对 prompt sections 应用 token 预算。

        1. 计算每个 section 的 token 数
        2. 如果总 token 在预算内，不做截断
        3. 如果超出预算，按优先级从低到高截断
        4. 记录截断日志

        Returns:
            截断后的 sections 列表（保持原顺序）
        """
        if not sections:
            return sections

        # 计算各 section 的 token 数和预算
        section_info = []
        total_tokens = 0
        for title, content in sections:
            tokens = _estimate_tokens(content)
            budget = self._match_budget(title)
            section_info.append({
                "title": title,
                "content": content,
                "tokens": tokens,
                "budget": budget,
            })
            total_tokens += tokens

        # 如果在预算内，不做截断
        if total_tokens <= self.total_budget:
            logger.debug(
                "P5 PromptBudget: total_tokens=%d <= budget=%d, 无需截断",
                total_tokens, self.total_budget,
            )
            return sections

        logger.info(
            "P5 PromptBudget: total_tokens=%d > budget=%d, 开始按优先级截断 (超出 %d tokens)",
            total_tokens, self.total_budget, total_tokens - self.total_budget,
        )

        # 按优先级从低到高排序（priority 4 先截断），同优先级按 token 数降序
        indices_by_priority = sorted(
            range(len(section_info)),
            key=lambda i: (-section_info[i]["budget"].priority, -section_info[i]["tokens"]),
        )

        tokens_to_cut = total_tokens - self.total_budget
        tokens_cut = 0

        for idx in indices_by_priority:
            if tokens_cut >= tokens_to_cut:
                break

            info = section_info[idx]
            budget = info["budget"]

            # Priority 1 的 section 不截断
            if budget.priority == 1:
                continue

            current_tokens = info["tokens"]
            target_tokens = budget.max_tokens if budget.max_tokens > 0 else current_tokens

            if current_tokens <= target_tokens:
                continue

            # 截断到预算
            new_content = _truncate_to_tokens(info["content"], target_tokens)
            saved = current_tokens - _estimate_tokens(new_content)
            tokens_cut += saved

            logger.info(
                "P5 截断: %s %d→%d tokens (节省 %d)",
                info["title"][:30], current_tokens, current_tokens - saved, saved,
            )
            section_info[idx]["content"] = new_content

        # 如果还超预算，对 priority 4 的 section 直接移除
        if tokens_cut < tokens_to_cut:
            for idx in indices_by_priority:
                if tokens_cut >= tokens_to_cut:
                    break
                info = section_info[idx]
                if info["budget"].priority >= 4 and info["content"]:
                    saved = _estimate_tokens(info["content"])
                    tokens_cut += saved
                    section_info[idx]["content"] = ""
                    logger.info("P5 移除低优先级 section: %s (节省 %d tokens)", info["title"][:30], saved)

        logger.info("P5 PromptBudget: 共截断/移除 %d tokens", tokens_cut)

        return [(info["title"], info["content"]) for info in section_info if info["content"]]

    @staticmethod
    def reorder_for_cache(
        sections: List[Tuple[str, str]],
    ) -> List[Tuple[str, str]]:
        """
        重排 prompt sections 以利用 Prompt Caching。

        OpenAI / Anthropic 的 Prompt Caching 基于前缀匹配：
        相同的前缀内容可被缓存复用。因此将跨章节稳定不变的内容
        放在前面，章节特定的内容放在后面。

        稳定内容（放前面）: 写作准则、风格约束、硬性规则、世界蓝图
        变化内容（放后面）: 章节目标、上一章上下文、mission brief
        """
        # 定义稳定 section 的关键字（按顺序）
        _STABLE_KEYWORDS = [
            "白金写作准则",
            "语言风格硬约束",
            "用户写作风格",
            "写法基准",
            "题材写作约束",
            "作者风格指纹",
            "世界蓝图",
            "禁止角色",
        ]

        stable_sections = []
        dynamic_sections = []

        for title, content in sections:
            is_stable = any(kw in title for kw in _STABLE_KEYWORDS)
            if is_stable:
                stable_sections.append((title, content))
            else:
                dynamic_sections.append((title, content))

        # 稳定内容在前（利用缓存），动态内容在后
        return stable_sections + dynamic_sections
