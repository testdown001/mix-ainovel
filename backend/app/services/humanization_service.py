# AIMETA P=人味化服务_AI指纹扫描与修复|R=静态分析_LLM定向修复|NR=不含API路由|E=HumanizationService|X=internal|A=人味化|D=re|S=compute|RD=./README.ai
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..services.llm_service import LLMService
from ..services.prompt_service import PromptService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 层1: 词汇级 AI 高频词库
# ---------------------------------------------------------------------------
AI_LEXICAL_PATTERNS: List[str] = [
    # 连接词类
    "显而易见", "综上所述", "值得注意的是", "不仅如此", "与此同时",
    "换句话说", "毫无疑问", "不言而喻", "事实上", "从某种意义上说",
    "换言之", "由此可见", "正因如此", "总而言之", "需要指出的是",
    "不难发现", "显然", "众所周知",
    # 情绪判断类（全知叙述标志）
    "他知道", "他明白", "他意识到", "他感觉到", "他决定", "他清楚",
    "她知道", "她明白", "她意识到", "她感觉到", "她决定", "她清楚",
    # 总结类
    "总之", "因此", "总的来说", "一切都", "这就是",
    # 修饰冗余类
    "某种程度上", "在这一刻", "仿佛在诉说", "似乎在暗示",
    "不禁", "缓缓地", "默默地",
]

# 层2: 转折词列表
TRANSITION_WORDS: List[str] = ["然而", "但是", "不过", "却"]

# 层2: 对称句式正则
SYMMETRIC_PATTERNS: List[re.Pattern] = [
    re.compile(r"一边.{2,15}一边.{2,15}"),
    re.compile(r"既.{2,15}又.{2,15}"),
    re.compile(r"不但.{2,15}而且.{2,15}"),
    re.compile(r"不仅.{2,15}还.{2,15}"),
    re.compile(r"虽然.{2,15}但.{2,15}"),
]

# 层2: 章末环境隐喻收束正则
AI_ENDING_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?:仿佛|似乎|好像|像是|宛如|犹如).{0,15}(?:在回应|在呼应|回应着|呼应着)"),
    re.compile(r"(?:有什么|某种).{0,10}(?:正在|悄然|开始).{0,10}(?:苏醒|萌芽|觉醒|改变|生长|蠕动|涌动|震颤)"),
    re.compile(r"(?:随着|跟着|伴着).{0,10}(?:心跳|呼吸|脉搏|决心|意志).{0,15}(?:震颤|跳动|涌动|苏醒|燃烧)"),
    re.compile(r"(?:在|而).{0,6}(?:黑暗|风声|夜色|沉默|寂静).{0,6}(?:中|里).{0,15}(?:悄然|正在|似乎|仿佛)"),
    re.compile(r".{0,10}(?:像是在为|仿佛在为|似乎在为).{0,15}(?:送行|倒计时|预告|宣告|铺路)"),
]



# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class HumanizationIssue:
    """单项检测问题。"""
    layer: str          # lexical / structural / statistical
    category: str       # 具体分类
    description: str    # 人可读描述
    severity: int       # 扣分值
    location: str = ""  # 可选位置信息


@dataclass
class HumanizationReport:
    """扫描报告。"""
    score: int = 100
    lexical_deduction: int = 0
    structural_deduction: int = 0
    statistical_deduction: int = 0
    issues: List[HumanizationIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "lexical_deduction": self.lexical_deduction,
            "structural_deduction": self.structural_deduction,
            "statistical_deduction": self.statistical_deduction,
            "issues": [
                {
                    "layer": i.layer,
                    "category": i.category,
                    "description": i.description,
                    "severity": i.severity,
                    "location": i.location,
                }
                for i in self.issues
            ],
        }

    def summary_for_prompt(self) -> str:
        """生成给 LLM 看的问题摘要。"""
        if not self.issues:
            return "无检测问题。"
        lines: List[str] = []
        for idx, issue in enumerate(self.issues, 1):
            loc = f"（{issue.location}）" if issue.location else ""
            lines.append(f"{idx}. [{issue.category}] {issue.description}{loc}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def _split_sentences(text: str) -> List[str]:
    """按中文句末标点切分句子。"""
    parts = re.split(r"[。！？…]+", text)
    return [s.strip() for s in parts if s.strip()]


def _split_paragraphs(text: str) -> List[str]:
    """按换行切分段落。"""
    return [p.strip() for p in text.split("\n") if p.strip()]


def _compute_std(values: List[float]) -> float:
    """计算标准差。"""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance ** 0.5


def _compute_cv(values: List[float]) -> float:
    """计算变异系数 (CV = std / mean)。"""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    return _compute_std(values) / mean


# ---------------------------------------------------------------------------
# 主服务
# ---------------------------------------------------------------------------
class HumanizationService:
    """AI 指纹扫描 + 定向修复服务。

    scan() 用纯 Python 静态分析，零 LLM 成本。
    humanize() 仅在分数低于阈值时调用 LLM 做定向修复。
    """

    def __init__(self, session: AsyncSession, llm_service: LLMService):
        self.session = session
        self.llm_service = llm_service
        self.prompt_service = PromptService(session)

    # -----------------------------------------------------------------------
    # 公开接口
    # -----------------------------------------------------------------------
    def scan(self, text: str) -> HumanizationReport:
        """零 LLM 成本的静态扫描，返回 0-100 人味分数 + 具体问题列表。"""
        report = HumanizationReport()

        self._scan_lexical(text, report)
        self._scan_structural(text, report)
        self._scan_statistical(text, report)

        report.score = max(0, min(100, 100 - report.lexical_deduction - report.structural_deduction - report.statistical_deduction))
        return report

    async def humanize(
        self,
        text: str,
        report: HumanizationReport,
        *,
        user_id: int,
    ) -> str:
        """根据 scan 报告，调用 LLM 做定向修复。返回修复后的文本。"""
        system_prompt = await self.prompt_service.get_prompt("humanize")
        if not system_prompt:
            logger.warning("未配置 humanize 提示词模板，跳过人味化修复")
            return text

        # 填充模板变量
        filled_prompt = system_prompt.replace("{{scan_report}}", report.summary_for_prompt())
        filled_prompt = filled_prompt.replace("{{original_text}}", text)

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一位文字打磨师，专门修正文本中的 AI 痕迹，让文字读起来像真人作家写的。",
                conversation_history=[{"role": "user", "content": filled_prompt}],
                temperature=0.7,
                user_id=user_id,
                timeout=300.0,
                response_format=None,
            )
            result = response.strip() if response else text
            # 基本校验：修复后文本不应过短
            if len(result) < len(text) * 0.5:
                logger.warning("人味化修复后文本过短 (%d → %d)，保留原文", len(text), len(result))
                return text
            return result
        except Exception as e:
            logger.error("人味化修复失败: %s", e)
            return text

    # -----------------------------------------------------------------------
    # 层1: 词汇级检测
    # -----------------------------------------------------------------------
    def _scan_lexical(self, text: str, report: HumanizationReport) -> None:
        total_deduction = 0
        max_deduction = 30
        found_words: List[str] = []

        for word in AI_LEXICAL_PATTERNS:
            count = text.count(word)
            if count > 0:
                deduction = min(count * 2, 6)  # 单词上限 6 分
                total_deduction += deduction
                found_words.append(word)
                report.issues.append(HumanizationIssue(
                    layer="lexical",
                    category="ai_vocabulary",
                    description=f"AI 高频词「{word}」出现 {count} 次",
                    severity=deduction,
                ))

        report.lexical_deduction = min(total_deduction, max_deduction)

    # -----------------------------------------------------------------------
    # 层2: 结构级检测
    # -----------------------------------------------------------------------
    def _scan_structural(self, text: str, report: HumanizationReport) -> None:
        total_deduction = 0
        max_deduction = 40
        paragraphs = _split_paragraphs(text)

        # 2a: 段落长度均匀度
        if len(paragraphs) >= 4:
            lengths = [float(len(p)) for p in paragraphs]
            cv = _compute_cv(lengths)
            if cv < 0.25:
                d = 10 if cv < 0.15 else 5
                total_deduction += d
                report.issues.append(HumanizationIssue(
                    layer="structural",
                    category="uniform_paragraphs",
                    description=f"段落长度过于均匀 (CV={cv:.2f}，合格线≥0.25)",
                    severity=d,
                ))

        # 2b: 句式开头重复
        if len(paragraphs) >= 3:
            consecutive_same = 1
            max_consecutive = 1
            for i in range(1, len(paragraphs)):
                prev_start = paragraphs[i - 1][:2]
                curr_start = paragraphs[i][:2]
                if prev_start == curr_start and len(prev_start) >= 2:
                    consecutive_same += 1
                    max_consecutive = max(max_consecutive, consecutive_same)
                else:
                    consecutive_same = 1
            if max_consecutive >= 3:
                d = 10
                total_deduction += d
                report.issues.append(HumanizationIssue(
                    layer="structural",
                    category="repetitive_openings",
                    description=f"连续 {max_consecutive} 段以相同方式开头",
                    severity=d,
                ))

        # 2c: 转折词密度
        text_len = len(text)
        if text_len > 0:
            transition_count = sum(text.count(w) for w in TRANSITION_WORDS)
            per_500 = transition_count / (text_len / 500) if text_len >= 500 else transition_count
            if per_500 > 3:
                d = 10 if per_500 > 5 else 5
                total_deduction += d
                report.issues.append(HumanizationIssue(
                    layer="structural",
                    category="transition_density",
                    description=f"转折词密度过高 (每500字 {per_500:.1f} 个，合格线≤3)",
                    severity=d,
                ))

        # 2d: 对称句式连续出现
        symmetric_count = 0
        for pattern in SYMMETRIC_PATTERNS:
            symmetric_count += len(pattern.findall(text))
        if symmetric_count >= 3:
            d = 10 if symmetric_count >= 5 else 5
            total_deduction += d
            report.issues.append(HumanizationIssue(
                layer="structural",
                category="symmetric_structure",
                description=f"并列对称句式过多 ({symmetric_count} 组)",
                severity=d,
            ))

        # 2e: 章末环境隐喻收束检测
        tail_text = text[-300:] if len(text) > 300 else text
        ending_hits = 0
        for pattern in AI_ENDING_PATTERNS:
            ending_hits += len(pattern.findall(tail_text))
        if ending_hits > 0:
            d = min(ending_hits * 8, 15)
            total_deduction += d
            report.issues.append(HumanizationIssue(
                layer="structural",
                category="ai_metaphor_ending",
                description=f"章末检测到 {ending_hits} 处环境隐喻收束模式，疑似 AI 式结尾",
                severity=d,
                location="最后300字",
            ))

        report.structural_deduction = min(total_deduction, max_deduction)

    # -----------------------------------------------------------------------
    # 层3: 统计级检测
    # -----------------------------------------------------------------------
    def _scan_statistical(self, text: str, report: HumanizationReport) -> None:
        total_deduction = 0
        max_deduction = 30
        sentences = _split_sentences(text)
        paragraphs = _split_paragraphs(text)

        # 3a: 句长标准差
        if len(sentences) >= 5:
            sent_lengths = [float(len(s)) for s in sentences]
            std = _compute_std(sent_lengths)
            if std < 5:
                d = 10 if std < 3 else 5
                total_deduction += d
                report.issues.append(HumanizationIssue(
                    layer="statistical",
                    category="uniform_sentence_length",
                    description=f"句子长度过于均匀 (标准差={std:.1f}，合格线≥5)",
                    severity=d,
                ))

        # 3b: 段落长度标准差
        if len(paragraphs) >= 4:
            para_lengths = [float(len(p)) for p in paragraphs]
            std = _compute_std(para_lengths)
            if std < 20:
                d = 10 if std < 10 else 5
                total_deduction += d
                report.issues.append(HumanizationIssue(
                    layer="statistical",
                    category="uniform_paragraph_length",
                    description=f"段落长度标准差过低 (std={std:.1f}，合格线≥20)",
                    severity=d,
                ))

        # 3c: 词汇丰富度 (简化 TTR)
        # 使用字级别的 TTR，对中文更合适
        chars = re.findall(r"[\u4e00-\u9fff]", text)
        if len(chars) >= 100:
            unique_chars = set(chars)
            # 为避免长文本 TTR 天然降低，使用滑动窗口平均
            window_size = 200
            if len(chars) <= window_size:
                ttr = len(unique_chars) / len(chars)
            else:
                ttrs = []
                for i in range(0, len(chars) - window_size + 1, window_size):
                    window = chars[i:i + window_size]
                    ttrs.append(len(set(window)) / len(window))
                ttr = sum(ttrs) / len(ttrs) if ttrs else 0.5
            if ttr < 0.4:
                d = 10 if ttr < 0.3 else 5
                total_deduction += d
                report.issues.append(HumanizationIssue(
                    layer="statistical",
                    category="low_lexical_diversity",
                    description=f"用字丰富度偏低 (TTR={ttr:.2f}，合格线≥0.4)",
                    severity=d,
                ))

        report.statistical_deduction = min(total_deduction, max_deduction)
