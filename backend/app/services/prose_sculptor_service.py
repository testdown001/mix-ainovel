# AIMETA P=文字雕塑服务_节奏与密度重写|R=节奏雕塑_信息密度_关键时刻增强|NR=不含API路由|E=ProseSculptorService|X=internal|A=雕塑|D=none|S=net|RD=./README.ai
"""
ProseSculptorService: 文字雕塑服务

替代原有的补丁式 optimizer，采用两遍聚焦重写：
1. 节奏雕塑：调整句子长短、段落呼吸、删除赘余连接词
2. 信息密度雕塑：砍掉过度解释、补充留白、打破对话的"太配合"

另外提供 Golden Paragraph 增强：识别 1-2 个峰值段落，用高温度重写。

每遍重写只聚焦一个维度，LLM 执行质量远高于"同时优化 5 个维度"。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ..core.config import settings
from ..utils.json_utils import remove_think_tags

logger = logging.getLogger(__name__)

RHYTHM_SCULPT_SYSTEM = "你是一个文字节奏师。你的唯一工作：调整文字的呼吸节奏，让它读起来像一流网文作者写的——有快有慢、有轻有重、有松有紧。"

RHYTHM_SCULPT_PROMPT = """以下章节的故事内容完全不变，但需要重新调整文字节奏。

你要做的：
1. 找到所有"匀速"段落（每段差不多长、每句差不多长），打破它们的均匀
2. 关键动作/冲击瞬间用短句砸（≤10字），氛围/心理铺开用长句（30-50字）
3. 紧张场景段落变短变密，松弛场景段落变长变舒展
4. 删掉所有不必要的连接词（然而、但是、不过、于是、因此）——用句子本身的转折代替连接词
5. 在最关键的 1-2 个瞬间，让句式本身制造冲击力（短句独立成段、不完整句、破折号截断）
6. 确保全文有至少1个超短段（≤2句话，砸关键瞬间）和至少1个长段（200+字，沉浸铺陈）

你不要做的：
- 不改事件、不改对话内容、不改角色行为
- 不加新的剧情
- 不改变字数（±5%以内）
- 不加 Markdown 标记

[原文]
{chapter_content}

直接输出调整后的全文，不要任何说明。"""

DENSITY_SCULPT_SYSTEM = "你是一个信息密度控制师。你的唯一工作：让文字该密则密、该疏则疏，砍掉读者不需要的解释，补上读者需要的留白。"

DENSITY_SCULPT_PROMPT = """以下章节需要调整信息密度分布。

你要做的：
1. 找到"什么都说了"的段落（铺了因果、解释了动机、交代了背景），砍掉30%的显式信息——让读者自己脑补
2. 找到"一笔带过"但其实是关键时刻的地方，展开它（加体感、加细节、加停顿）
3. 对话中删掉"太配合"的回答——有时角色应该答非所问、沉默、或岔开话题
4. 至少制造 1 处"省略"——用一个动作或沉默代替本可以写出来的情绪/解释
5. 把连续超过100字的纯设定/纯解释段落打散成角色能感知的小细节
6. 如果有"他知道/他明白/他意识到"这类叙述者替角色总结的句子，改为角色自己的反应或行动

你不要做的：
- 不改事件走向、不删关键对话
- 不改变字数（±8%以内）
- 不加 Markdown 标记

[原文]
{chapter_content}

直接输出调整后的全文，不要任何说明。"""

GOLDEN_PARA_SYSTEM = "你是一个只专注关键瞬间的写手。你要把一个普通段落改写成让读者记住一整天的段落。追求'一巴掌打在读者脸上'的力度。"

GOLDEN_PARA_PROMPT = """以下是本章的一个关键时刻（高潮/转折/情感峰值），需要你重写这几段话。

要求：
- 可以大幅改动句式、节奏、用词、段落划分
- 不改事件内容和对话语义
- 让这段话成为整章最有力度、最有记忆点的部分
- 可以用不完整句、省略、短句独立成段、感官冲击等任何手法
- 字数可以±20%浮动

[上文片段]
{context_before}

[需要重写的段落]
{peak_text}

[下文片段]
{context_after}

直接输出重写后的段落，不要任何说明。"""


class ProseSculptorService:
    """文字雕塑服务：节奏雕塑 + 信息密度雕塑 + Golden Paragraph。"""

    def __init__(self, llm_service):
        self.llm_service = llm_service

    async def sculpt_rhythm(
        self, chapter_content: str, *, user_id: int, max_word_count: int = 0,
    ) -> Tuple[str, Dict[str, Any]]:
        prompt = RHYTHM_SCULPT_PROMPT.replace("{chapter_content}", chapter_content)
        _rhythm_max_tokens = int(max_word_count * 1.5) if max_word_count else settings.writer_max_tokens
        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=RHYTHM_SCULPT_SYSTEM,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.6,
                user_id=user_id,
                timeout=60.0,
                response_format=None,
                max_tokens=_rhythm_max_tokens,
            )
            result = (remove_think_tags(response) or response).strip()
            if len(result) < len(chapter_content) * 0.6:
                logger.warning("节奏雕塑结果过短 (%d→%d)，保留原文", len(chapter_content), len(result))
                return chapter_content, {"applied": False, "reason": "result_too_short"}
            return result, {"applied": True, "original_len": len(chapter_content), "sculpted_len": len(result)}
        except Exception as e:
            logger.error("节奏雕塑失败: %s", e)
            return chapter_content, {"applied": False, "error": str(e)}

    async def sculpt_density(
        self, chapter_content: str, *, user_id: int, max_word_count: int = 0,
    ) -> Tuple[str, Dict[str, Any]]:
        prompt = DENSITY_SCULPT_PROMPT.replace("{chapter_content}", chapter_content)
        _density_max_tokens = int(max_word_count * 1.5) if max_word_count else settings.writer_max_tokens
        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=DENSITY_SCULPT_SYSTEM,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.6,
                user_id=user_id,
                timeout=60.0,
                response_format=None,
                max_tokens=_density_max_tokens,
            )
            result = (remove_think_tags(response) or response).strip()
            if len(result) < len(chapter_content) * 0.6:
                logger.warning("密度雕塑结果过短 (%d→%d)，保留原文", len(chapter_content), len(result))
                return chapter_content, {"applied": False, "reason": "result_too_short"}
            return result, {"applied": True, "original_len": len(chapter_content), "sculpted_len": len(result)}
        except Exception as e:
            logger.error("密度雕塑失败: %s", e)
            return chapter_content, {"applied": False, "error": str(e)}

    async def enhance_peak_moments(
        self, chapter_content: str, *, user_id: int, chapter_mission: Optional[dict] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        peaks = self._identify_peak_paragraphs(chapter_content, chapter_mission)
        if not peaks:
            return chapter_content, {"applied": False, "reason": "no_peaks_identified"}

        result = chapter_content
        enhanced_count = 0
        for peak_info in peaks[:1]:
            para_text = peak_info["text"]
            para_start = peak_info["start"]

            ctx_before = result[max(0, para_start - 300):para_start].strip()
            para_end = para_start + len(para_text)
            ctx_after = result[para_end:para_end + 300].strip()

            prompt = GOLDEN_PARA_PROMPT.replace("{context_before}", ctx_before or "(章节开头)")
            prompt = prompt.replace("{peak_text}", para_text)
            prompt = prompt.replace("{context_after}", ctx_after or "(章节结尾)")

            try:
                response = await self.llm_service.get_llm_response(
                    system_prompt=GOLDEN_PARA_SYSTEM,
                    conversation_history=[{"role": "user", "content": prompt}],
                    temperature=0.9,
                    user_id=user_id,
                    timeout=45.0,
                    response_format=None,
                    max_tokens=4096,
                )
                rewrite = (remove_think_tags(response) or response).strip()
                if rewrite and len(rewrite) > len(para_text) * 0.4:
                    result = result[:para_start] + rewrite + result[para_end:]
                    enhanced_count += 1
            except Exception as e:
                logger.warning("Golden Paragraph 增强失败: %s", e)

        return result, {"applied": enhanced_count > 0, "peaks_found": len(peaks), "enhanced": enhanced_count}

    @staticmethod
    def _identify_peak_paragraphs(
        chapter_content: str,
        chapter_mission: Optional[dict] = None,
    ) -> List[Dict[str, Any]]:
        paragraphs = [p for p in chapter_content.split("\n") if p.strip()]
        if len(paragraphs) < 5:
            return []

        scored: List[Dict[str, Any]] = []
        for i, para in enumerate(paragraphs):
            offset = chapter_content.index(para)
            score = 0.0

            position_ratio = i / max(1, len(paragraphs) - 1)
            if 0.55 <= position_ratio <= 0.85:
                score += 2.0

            intensity_markers = ["！", "——", "……", "？！", "!"]
            score += sum(0.5 for m in intensity_markers if m in para)

            short_sentences = re.findall(r'[^。！？…]{1,8}[。！？…]', para)
            if len(short_sentences) >= 2:
                score += 1.0

            dialogue_count = para.count("\u201c") + para.count("\u300c")
            action_words = sum(1 for w in ["一拳", "一剑", "一刀", "爆发", "冲", "砸", "撞", "断", "碎"]
                             if w in para)
            if action_words >= 2:
                score += 1.5
            if dialogue_count >= 2 and len(para) > 100:
                score += 1.0

            if len(para) > 80:
                scored.append({"text": para, "start": offset, "score": score, "index": i})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:2]
