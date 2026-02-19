# AIMETA P=作者风格指纹服务_跨章风格一致性|R=指纹提取_注入|NR=不含API路由|E=AuthorFingerprintService|X=internal|A=风格指纹|D=re|S=compute|RD=./README.ai
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class AuthorFingerprint:
    """作者风格指纹，纯统计提取。"""

    # 句长分布
    sentence_length_median: float = 0.0
    sentence_length_std: float = 0.0

    # 段落长度分布（四分位数）
    paragraph_length_q1: float = 0.0
    paragraph_length_median: float = 0.0
    paragraph_length_q3: float = 0.0

    # 高频动词/形容词 (top-10 字)
    top_verbs_adjectives: List[str] = field(default_factory=list)

    # 对话占比
    dialogue_ratio: float = 0.0

    # 开头模式分布
    opening_action_pct: float = 0.0    # 动作开头
    opening_dialogue_pct: float = 0.0  # 对话开头
    opening_description_pct: float = 0.0  # 描写开头
    opening_other_pct: float = 0.0     # 其他

    # 标点使用习惯
    ellipsis_per_1000: float = 0.0     # 省略号频率
    dash_per_1000: float = 0.0         # 破折号频率
    exclamation_per_1000: float = 0.0  # 感叹号频率

    # 元数据
    chapter_count: int = 0             # 基于多少章提取

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sentence_length_median": round(self.sentence_length_median, 1),
            "sentence_length_std": round(self.sentence_length_std, 1),
            "paragraph_length_q1": round(self.paragraph_length_q1, 1),
            "paragraph_length_median": round(self.paragraph_length_median, 1),
            "paragraph_length_q3": round(self.paragraph_length_q3, 1),
            "top_verbs_adjectives": self.top_verbs_adjectives,
            "dialogue_ratio": round(self.dialogue_ratio, 2),
            "opening_action_pct": round(self.opening_action_pct, 2),
            "opening_dialogue_pct": round(self.opening_dialogue_pct, 2),
            "opening_description_pct": round(self.opening_description_pct, 2),
            "opening_other_pct": round(self.opening_other_pct, 2),
            "ellipsis_per_1000": round(self.ellipsis_per_1000, 2),
            "dash_per_1000": round(self.dash_per_1000, 2),
            "exclamation_per_1000": round(self.exclamation_per_1000, 2),
            "chapter_count": self.chapter_count,
        }


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"[。！？…]+", text)
    return [s.strip() for s in parts if s.strip()]


def _split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in text.split("\n") if p.strip()]


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2
    return s[mid]


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct
    f = int(k)
    c = f + 1 if f + 1 < len(s) else f
    d = k - f
    return s[f] + d * (s[c] - s[f])


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance ** 0.5


# ---------------------------------------------------------------------------
# 主服务
# ---------------------------------------------------------------------------
class AuthorFingerprintService:
    """从已生成的章节中提取作者风格指纹，在后续章节提示词中注入。

    纯 Python 计算，零 LLM 成本。
    """

    # 内存缓存: project_id -> (chapter_count_at_extraction, fingerprint)
    _cache: Dict[str, tuple] = {}

    def extract_fingerprint(self, chapters: List[str]) -> AuthorFingerprint:
        """从多章文本中提取统计风格指纹。"""
        fp = AuthorFingerprint(chapter_count=len(chapters))
        if not chapters:
            return fp

        combined = "\n\n".join(chapters)
        all_sentences = _split_sentences(combined)
        all_paragraphs = _split_paragraphs(combined)

        # 句长分布
        if all_sentences:
            sent_lens = [float(len(s)) for s in all_sentences]
            fp.sentence_length_median = _median(sent_lens)
            fp.sentence_length_std = _std(sent_lens)

        # 段落长度分布
        if all_paragraphs:
            para_lens = [float(len(p)) for p in all_paragraphs]
            fp.paragraph_length_q1 = _percentile(para_lens, 0.25)
            fp.paragraph_length_median = _median(para_lens)
            fp.paragraph_length_q3 = _percentile(para_lens, 0.75)

        # 对话占比
        total_lines = len(all_paragraphs)
        if total_lines > 0:
            dialogue_lines = sum(
                1 for p in all_paragraphs
                if p.startswith("\u201c") or p.startswith("\u300c") or p.startswith('"')
            )
            fp.dialogue_ratio = dialogue_lines / total_lines

        # 高频用字（双字组合，模拟动词/形容词）
        bigrams = re.findall(r"[\u4e00-\u9fff]{2}", combined)
        if bigrams:
            counter = Counter(bigrams)
            # 排除过于常见的虚词
            stopwords = {"的是", "了他", "他的", "是一", "一个", "不是", "没有", "这个", "那个",
                         "就是", "我们", "他们", "她的", "自己", "什么", "可以", "已经", "因为",
                         "所以", "但是", "如果", "这是", "那是", "有些", "一些"}
            for sw in stopwords:
                counter.pop(sw, None)
            fp.top_verbs_adjectives = [w for w, _ in counter.most_common(10)]

        # 开头模式统计
        if all_paragraphs:
            action_count = 0
            dialogue_count = 0
            description_count = 0
            other_count = 0
            for p in all_paragraphs:
                first_char = p[0] if p else ""
                if first_char in "\u201c\u300c\"'":
                    dialogue_count += 1
                elif re.match(r"^[\u4e00-\u9fff]{1,2}(了|着|过|起|去|来|出|下|上)", p):
                    action_count += 1
                elif re.match(r"^(天空|阳光|月光|风|雨|夜|晨|空气|四周|远处|身旁)", p):
                    description_count += 1
                else:
                    other_count += 1
            n = len(all_paragraphs)
            fp.opening_action_pct = action_count / n
            fp.opening_dialogue_pct = dialogue_count / n
            fp.opening_description_pct = description_count / n
            fp.opening_other_pct = other_count / n

        # 标点使用习惯
        text_len = len(combined)
        if text_len > 0:
            factor = 1000 / text_len
            fp.ellipsis_per_1000 = combined.count("…") * factor
            fp.dash_per_1000 = combined.count("——") * factor
            fp.exclamation_per_1000 = combined.count("！") * factor

        return fp

    def build_fingerprint_context(self, fingerprint: AuthorFingerprint) -> str:
        """将指纹转为可注入提示词的文本段落。"""
        if fingerprint.chapter_count == 0:
            return ""

        lines: List[str] = []

        # 句长
        low = max(5, int(fingerprint.sentence_length_median - fingerprint.sentence_length_std))
        high = int(fingerprint.sentence_length_median + fingerprint.sentence_length_std)
        lines.append(f"- 你的句子长度通常在 {low}-{high} 字之间波动，中位数约 {int(fingerprint.sentence_length_median)} 字")

        # 段落
        q1 = int(fingerprint.paragraph_length_q1)
        q3 = int(fingerprint.paragraph_length_q3)
        if q1 > 0 and q3 > 0:
            lines.append(f"- 段落长短交替，短段 {q1} 字左右，长段 {q3} 字左右")

        # 高频词
        if fingerprint.top_verbs_adjectives:
            words = "、".join(fingerprint.top_verbs_adjectives[:8])
            lines.append(f"- 你偏好使用的高频词：{words}")

        # 对话占比
        pct = int(fingerprint.dialogue_ratio * 100)
        lines.append(f"- 对话约占全文 {pct}%，对话与叙述交替出现")

        # 开头模式
        parts = []
        if fingerprint.opening_action_pct > 0.05:
            parts.append(f"动作开头 {int(fingerprint.opening_action_pct * 100)}%")
        if fingerprint.opening_dialogue_pct > 0.05:
            parts.append(f"对话开头 {int(fingerprint.opening_dialogue_pct * 100)}%")
        if fingerprint.opening_description_pct > 0.05:
            parts.append(f"描写开头 {int(fingerprint.opening_description_pct * 100)}%")
        if parts:
            lines.append(f"- 你的段落开头多样：{'、'.join(parts)}")

        # 标点习惯
        punct_parts = []
        if fingerprint.ellipsis_per_1000 > 0.5:
            punct_parts.append("省略号表犹豫")
        if fingerprint.dash_per_1000 > 0.3:
            punct_parts.append("破折号表转折")
        if fingerprint.exclamation_per_1000 > 1.0:
            punct_parts.append("感叹号增强语气")
        if punct_parts:
            lines.append(f"- 偶尔使用{'，'.join(punct_parts)}")

        return "\n".join(lines)

    def get_or_extract(
        self,
        project_id: str,
        chapter_texts: List[str],
        *,
        refresh_interval: int = 5,
    ) -> Optional[str]:
        """获取缓存的指纹上下文，或在需要时重新提取。

        - 需要至少 3 章才会提取
        - 每 refresh_interval 章更新一次
        """
        if len(chapter_texts) < 3:
            return None

        cached = self._cache.get(project_id)
        if cached:
            cached_count, cached_fp = cached
            # 仅当章节数变化超过 refresh_interval 时才重新提取
            if abs(len(chapter_texts) - cached_count) < refresh_interval:
                return self.build_fingerprint_context(cached_fp)

        fp = self.extract_fingerprint(chapter_texts)
        self._cache[project_id] = (len(chapter_texts), fp)
        return self.build_fingerprint_context(fp)
