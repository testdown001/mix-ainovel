from __future__ import annotations

import logging
import re

from ..utils.json_utils import remove_think_tags, sanitize_chapter_plain_text, unwrap_markdown_json

logger = logging.getLogger(__name__)


class TextCompressionService:
    """统一处理章节压缩与硬截断。"""

    def __init__(self, llm_service):
        self.llm_service = llm_service

    @staticmethod
    def strip_compression_preamble(text: str) -> str:
        lines = text.split("\n")

        skip_count = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                skip_count += 1
                continue
            if re.match(
                r'^(可以|好的|当然|没问题|下面是|以下是|精简后|精简版|控制在|保留|压缩|'
                r'我已经|我已为|我为您|我把|以上是|以上为|根据您|按照您|'
                r'这是|我来|让我|我先)',
                stripped,
            ):
                skip_count += 1
                continue
            if re.match(r'^#{1,4}\s+.*(精简版|精简|压缩版|缩写版)', stripped):
                skip_count += 1
                continue
            if re.match(r'^[\(（].*字.*[\)）][：:]?\s*$', stripped):
                skip_count += 1
                continue
            break
        if skip_count > 0:
            lines = lines[skip_count:]

        tail_skip = 0
        for line in reversed(lines):
            stripped = line.strip()
            if not stripped:
                tail_skip += 1
                continue
            if re.match(
                r'^(您需要|需要我|希望我|如果您|如有需要|如需|是否需要|'
                r'我已经为您|我已为您|以上是|以上就是|以上为|'
                r'如果你|你需要|要我|还是继续)',
                stripped,
            ):
                tail_skip += 1
                continue
            if re.search(r'\d+\s*字(左右|以内|以上|之间|范围)', stripped):
                if len(stripped) < 80:
                    tail_skip += 1
                    continue
            break
        if tail_skip > 0:
            lines = lines[:-tail_skip]

        return "\n".join(lines).strip()

    async def compress_overlength(
        self,
        chapter_text: str,
        *,
        target_max: int,
        user_id: int,
    ) -> str:
        target_min = int(target_max * 0.85)
        over_compress_floor = int(target_max * 0.6)
        system_prompt = (
            "你是一个精炼大师。你的任务是将给定的小说章节精简到指定字数范围内，"
            "同时保留核心剧情、角色对话、关键动作和情绪转折。\n"
            "精简策略：\n"
            "1. 只删除明显冗余的环境描写和重复的内心戏\n"
            "2. 适度压缩过渡段落，不要过度删减\n"
            "3. 精简对话中的废话，保留有性格的台词\n"
            "4. 不要删除关键剧情节点和伏笔\n"
            "5. 保持开头和结尾的质量\n\n"
            "【绝对禁止】\n"
            "- 禁止输出任何前言、说明、注释、标题或元信息\n"
            "- 禁止写「可以」「下面是」「精简版」「我已经为您」等任何非正文内容\n"
            "- 禁止添加章节标题或「精简版」标记\n"
            "- 禁止在末尾添加任何总结、询问或对话（如「需要我帮您...」「希望...」）\n"
            "- 你的输出第一个字必须是小说正文的第一个字\n"
            "- 你的输出最后一个字必须是小说正文的最后一个字\n"
            "只输出精简后的纯小说正文，没有任何其他内容。"
        )

        current_text = chapter_text
        max_attempts = 2
        for attempt in range(max_attempts):
            user_prompt = (
                f"将以下 {len(current_text)} 字章节正文精简到 {target_min}~{target_max} 字之间。"
                f"注意：不要过度精简，字数必须保持在 {target_min} 字以上。"
                f"直接输出精简后的纯正文，第一个字就是小说内容。\n\n"
                f"{current_text}"
            )
            try:
                response = await self.llm_service.get_llm_response(
                    system_prompt=system_prompt,
                    conversation_history=[{"role": "user", "content": user_prompt}],
                    temperature=0.3,
                    user_id=user_id,
                    timeout=180.0,
                    max_tokens=int(target_max * 1.2),
                )
                cleaned = remove_think_tags(response)
                result = sanitize_chapter_plain_text(unwrap_markdown_json(cleaned or response))
                if result:
                    result = self.strip_compression_preamble(result)

                if not result or len(result) >= len(current_text):
                    logger.warning("压缩结果无效（更长或为空），保留当前文本 (attempt=%d)", attempt + 1)
                    break
                if len(result) < over_compress_floor:
                    logger.warning(
                        "压缩结果过短 (%d < %d，目标下限的60%%)，丢弃压缩结果保留原文 (attempt=%d)",
                        len(result), over_compress_floor, attempt + 1,
                    )
                    break

                logger.info(
                    "超字数压缩完成 (attempt=%d): %d -> %d 字 (目标 %d~%d)",
                    attempt + 1, len(current_text), len(result), target_min, target_max,
                )
                current_text = result
                if len(current_text) <= target_max:
                    break
            except Exception as exc:
                logger.warning("超字数压缩失败 (attempt=%d)，保留当前文本: %s", attempt + 1, exc)
                break

        if len(current_text) > target_max:
            logger.warning("压缩重试耗尽仍超限 (%d > %d)，触发硬截断", len(current_text), target_max)
            current_text = self.hard_trim_to_limit(current_text, target_max)
        return current_text

    @staticmethod
    def hard_trim_to_limit(text: str, max_chars: int) -> str:
        if not text or len(text) <= max_chars:
            return text

        # 章尾钩子是提示词铁律：始终保留最后一段；剩余预算从开头顺序装入前部段落，
        # 装不下的第一段按句号截取——被牺牲的是"中部"而非开头或结尾。
        # （旧的"从倒数第二段向前整段删"在首段超限+短末段时会把整章删到只剩几十字末段；
        #  max_chars 是下游三条 flow 依赖的硬上限契约，任何分支都不允许超限返回。）
        paragraphs = text.split("\n\n")
        tail = paragraphs[-1]
        if len(tail) > max_chars:
            # 末段自身超限：段内保末句护钩子，头部按句号回填；末句仍超限则硬切守住上限
            last_sentence = tail
            for index in range(len(tail) - 2, -1, -1):
                if tail[index] in "。！？":
                    last_sentence = tail[index + 1:]
                    break
            if len(last_sentence) > max_chars:
                return last_sentence[:max_chars]
            head_budget = max_chars - len(last_sentence)
            head = tail[:head_budget]
            for index in range(len(head) - 1, -1, -1):
                if head[index] in "。！？":
                    return head[: index + 1] + last_sentence
            return last_sentence

        budget = max_chars - len(tail) - 2  # 预留 "\n\n" 连接符
        head_parts: list[str] = []
        used = 0
        for para in paragraphs[:-1]:
            need = len(para) + (2 if head_parts else 0)
            if used + need <= budget:
                head_parts.append(para)
                used += need
                continue
            # 装不下的第一段：句号边界截取填满剩余预算后停止（中部丢弃）
            remaining = budget - used - (2 if head_parts else 0)
            if remaining > 0:
                snippet = para[:remaining]
                for index in range(len(snippet) - 1, -1, -1):
                    if snippet[index] in "。！？":
                        head_parts.append(snippet[: index + 1])
                        break
            break
        head = "\n\n".join(head_parts)
        return (head + "\n\n" + tail) if head else tail
