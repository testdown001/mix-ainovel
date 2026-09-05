# AIMETA P=人味化服务_AI指纹扫描与修复|R=静态分析_LLM定向修复|NR=不含API路由|E=HumanizationService|X=internal|A=人味化|D=re|S=compute|RD=./README.ai
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..services.llm_service import LLMService
from ..services.prompt_service import PromptService
from ..utils.json_utils import is_probable_chapter_plain_text, sanitize_chapter_plain_text

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
    # 总结类
    "总之", "因此", "总的来说", "一切都", "这就是",
    # 修饰冗余类
    "某种程度上", "在这一刻", "仿佛在诉说", "似乎在暗示",
    "不禁", "缓缓地", "默默地",
]

# 层2: 转折词列表
TRANSITION_WORDS: List[str] = ["然而", "但是", "不过", "却"]

# 规则级替换表（无 LLM）：AI 高频词 → 更自然的替代，或空串表示可删。
# 两条硬约束（tests/test_humanization_rules_cleanup.py 程序化锁定）：
# 1. 替换产物一律不得命中 AI_LEXICAL_PATTERNS（否则替换完再扫仍扣分，自我抵消，
#    如旧表「显而易见→显然」「总而言之→总之」）；
# 2. 空串（删除类）仅在句首/行首/标点后等安全位置生效（见 _delete_at_safe_positions），
#    不做全文盲删。删除在任何位置都会破坏句法的词（「一切都」删掉丢主语，
#    「仿佛在诉说」「似乎在暗示」删掉悬空宾语）不进本表，仅保留扣分。
LEXICAL_REPLACEMENTS: Dict[str, str] = {
    "显而易见": "一眼就能看出",
    "综上所述": "",
    "值得注意的是": "",
    "不仅如此": "而且",
    "与此同时": "同时",
    "换句话说": "",
    "毫无疑问": "当然",
    "不言而喻": "",
    "事实上": "其实",
    "从某种意义上说": "可以说",
    "换言之": "",
    "由此可见": "",
    "正因如此": "所以",
    "总而言之": "说到底",
    "需要指出的是": "",
    "不难发现": "",
    "众所周知": "",
    "某种程度上": "",
    "在这一刻": "",
    "不禁": "",
    "缓缓地": "缓缓",
    "默默地": "默默",
    "因此": "所以",
    "总的来说": "",
    "这就是": "这便是",
}

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
    re.compile(r"(?:风|雨|夜色|月光|灯光|影子|黑暗|火焰|烟雾|钟声|沉默).{0,15}(?:仿佛|似乎|好像|像是|宛如|犹如).{0,15}(?:回应|呼应)"),
    re.compile(r"(?:有什么|某种).{0,10}(?:正在|悄然|开始).{0,10}(?:苏醒|萌芽|觉醒|改变|生长|蠕动|涌动|震颤)"),
    re.compile(r"(?:随着|跟着|伴着).{0,10}(?:心跳|呼吸|脉搏|决心|意志).{0,15}(?:震颤|跳动|涌动|苏醒|燃烧)"),
    re.compile(r"(?:在|而).{0,6}(?:黑暗|风声|夜色|沉默|寂静).{0,6}(?:中|里).{0,15}(?:悄然|似乎|仿佛).{0,12}(?:苏醒|蔓延|等待|注视|回应|发酵)"),
    re.compile(r".{0,10}(?:像是在为|仿佛在为|似乎在为).{0,15}(?:送行|倒计时|预告|宣告|铺路)"),
    re.compile(r"(?:命运|时代|历史).{0,10}(?:齿轮|车轮|洪流).{0,12}(?:转动|滚动|启动|开始)"),
    re.compile(r"(?:风暴|浪潮|序幕|大幕).{0,12}(?:即将|将要|正在|已经|才).{0,10}(?:来临|逼近|拉开|掀起)"),
    re.compile(r"(?:故事|一切|真正的.{0,8}).{0,10}(?:才刚刚开始|只是开始|即将开始)"),
    re.compile(r"(?:种子|火种|裂缝).{0,12}(?:埋下|萌芽|燃起|蔓延|生根)"),
    re.compile(r"(?:风|雨|夜色|月光|灯光|影子|黑暗|沉默|火焰|烟雾).{0,18}(?:仿佛|似乎|像是).{0,18}(?:预告|宣告|见证|吞没|回应|等待)"),
]

# 描写密度信号：不把单次正常使用判错，只在千字密度或同一套身体反应反复出现时扣分。
FIGURATIVE_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?<![画影肖图好])像(?!素|样|章|机)"),
    re.compile(r"仿佛|似乎|好像|宛如|犹如"),
]

BODY_REACTION_PATTERNS: Dict[str, re.Pattern] = {
    "心跳/心脏": re.compile(r"心(?:跳|脏|口).{0,8}(?:加快|狂跳|骤停|一紧|发紧|擂鼓|收缩|沉下)"),
    "呼吸/胸腔": re.compile(r"(?:呼吸|胸腔|胸口).{0,8}(?:一滞|发紧|起伏|发闷|收紧|堵|压|窒)"),
    "手指/指尖/掌心": re.compile(r"(?:手指|指尖|指节|掌心).{0,8}(?:发白|发抖|颤|冰凉|出汗|沁出|攥|收紧|僵)"),
    "喉咙/喉结": re.compile(r"(?:喉咙|喉头|喉结).{0,8}(?:发紧|滚动|干涩|一动|堵|哽)"),
    "冷汗/汗毛": re.compile(r"(?:冷汗|汗毛|后颈).{0,8}(?:冒|沁|竖|凉|发麻|发紧)"),
    "目光/眼神": re.compile(r"(?:目光|眼神).{0,8}(?:一凝|发冷|死死|锐利|闪烁|复杂|深邃)"),
}

EMPTY_INTENSIFIERS: List[str] = [
    "极其", "极为", "无比", "格外", "异常地", "非常", "十分", "尤其地", "愈发", "越发",
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
    missing_human_deduction: int = 0
    issues: List[HumanizationIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "lexical_deduction": self.lexical_deduction,
            "structural_deduction": self.structural_deduction,
            "statistical_deduction": self.statistical_deduction,
            "missing_human_deduction": self.missing_human_deduction,
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


_DELETE_BOUNDARY_CHARS = "。！？…；：，、\n"


def _delete_at_safe_positions(text: str, word: str) -> str:
    """仅在文首/行首/标点后删除 word（连带其后紧跟的逗号/顿号）。

    避免全文盲删破坏句法（如「一切都变了」被截成「变了」）；
    非安全位置的出现保持原样，由 LLM 定向修复兜底。
    """
    pattern = re.compile(
        r"(^|[" + re.escape(_DELETE_BOUNDARY_CHARS) + r"])" + re.escape(word) + r"[，、]?"
    )
    return pattern.sub(r"\1", text)


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
        self._scan_missing_human_elements(text, report)

        report.score = max(0, min(100, 100
                                  - report.lexical_deduction
                                  - report.structural_deduction
                                  - report.statistical_deduction
                                  - report.missing_human_deduction))
        return report

    def apply_rule_fixes(self, text: str, report: Optional[HumanizationReport] = None) -> str:
        """纯规则替换，零 LLM 成本。根据 report 中的 lexical 问题做词汇替换；若未传入 report 则先 scan。"""
        if report is None:
            report = self.scan(text)
        result = text
        # 只处理 lexical 层的 ai_vocabulary 问题
        for issue in report.issues:
            if issue.layer != "lexical" or issue.category != "ai_vocabulary":
                continue
            # 从描述中提取词：AI 高频词「X」出现 N 次
            m = re.search(r"「([^」]+)」", issue.description)
            if not m:
                continue
            word = m.group(1)
            replacement = LEXICAL_REPLACEMENTS.get(word)
            if replacement is None:
                continue
            if replacement == "":
                # 删除类：仅在句首/行首/标点后等安全位置删除，避免破坏句法
                result = _delete_at_safe_positions(result, word)
            else:
                # 替换所有出现（整词，避免误伤）
                result = result.replace(word, replacement)
        # 清理替换产生的多余标点（含段落首的残留逗号）
        result = re.sub(r"[，]{2,}", "，", result)
        result = re.sub(r"[。]{2,}", "。", result)
        result = re.sub(r"(^|\n)[，、]\s*", r"\1", result)
        return result.strip() if result.strip() else text

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
                max_tokens=int(len(text) * 1.2),
                fail_on_truncation=True,
            )
            result = sanitize_chapter_plain_text(response.strip()) if response else ""
            if not result or not is_probable_chapter_plain_text(result):
                logger.warning("人味化修复结果不是有效章节正文，保留原文")
                return text
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

        # 2f: 比喻/类比标记密度。单次修辞不扣分，连续堆叠才判 AI 式过度描写。
        text_k = max(1.0, len(text) / 1000)
        figurative_count = sum(len(pattern.findall(text)) for pattern in FIGURATIVE_PATTERNS)
        figurative_density = figurative_count / text_k
        if figurative_density > 6:
            d = 10 if figurative_density > 10 else 6
            total_deduction += d
            report.issues.append(HumanizationIssue(
                layer="structural",
                category="figurative_density",
                description=f"比喻/类比标记过密 ({figurative_density:.1f}/千字，建议≤6)，应只保留真正解释信息的意象",
                severity=d,
            ))

        # 2g: 模板化身体反应。既看总密度，也看同一种反应是否反复出现。
        body_counts = {label: len(pattern.findall(text)) for label, pattern in BODY_REACTION_PATTERNS.items()}
        body_total = sum(body_counts.values())
        body_density = body_total / text_k
        repeated_body = {label: count for label, count in body_counts.items() if count >= 3}
        if body_density > 5 or repeated_body:
            d = 10 if body_density > 8 or repeated_body else 6
            total_deduction += d
            repeated_text = "、".join(f"{label}{count}次" for label, count in repeated_body.items())
            detail = f"；重复项：{repeated_text}" if repeated_text else ""
            report.issues.append(HumanizationIssue(
                layer="structural",
                category="body_reaction_stack",
                description=f"身体反应描写过密 ({body_density:.1f}/千字){detail}，同一情绪节拍只留一个",
                severity=d,
            ))

        # 2h: 空泛程度副词密度。
        intensifier_count = sum(text.count(word) for word in EMPTY_INTENSIFIERS)
        intensifier_density = intensifier_count / text_k
        if intensifier_density > 4:
            d = 8 if intensifier_density > 7 else 5
            total_deduction += d
            report.issues.append(HumanizationIssue(
                layer="structural",
                category="modifier_density",
                description=f"程度副词过密 ({intensifier_density:.1f}/千字)，应改用精确名词、动词或直接删除",
                severity=d,
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

    # -----------------------------------------------------------------------
    # 层4: 表达留白检测（保留旧报表字段，不按对白或残句配额扣分）
    # -----------------------------------------------------------------------
    def _scan_missing_human_elements(self, text: str, report: HumanizationReport) -> None:
        """检测过度解释；没有对白或残句本身不是人味缺失。"""
        total_deduction = 0
        max_deduction = 20
        explanation_markers = ["因为", "所以", "原来是", "这才明白", "这意味着", "换句话说", "也就是说"]
        explanation_count = sum(text.count(m) for m in explanation_markers)
        text_k = max(1, len(text) / 1000)
        explanation_density = explanation_count / text_k
        if explanation_density > 2.5:
            d = min(8, int(explanation_density - 2.0) * 3)
            total_deduction += d
            report.issues.append(HumanizationIssue(
                layer="missing_human",
                category="over_explanation",
                description=f"因果解释密度偏高({explanation_density:.1f}/千字)——真人作者更多用动作和暗示代替显式解释，应增加留白",
                severity=d,
            ))

        # 独立记账：不并入 structural 桶（旧实现 += 会让 structural 实际可达 60，穿透其 40 上限，
        # to_dict 分层归因失真）
        report.missing_human_deduction = min(total_deduction, max_deduction)
