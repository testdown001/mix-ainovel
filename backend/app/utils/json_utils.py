# AIMETA P=JSON工具_JSON解析和修复|R=安全解析_格式修复|NR=不含业务逻辑|E=parse_json_safely|X=internal|A=工具函数|D=json|S=none|RD=./README.ai
import json
import logging
import re

try:
    import json_repair as _json_repair_lib
except ImportError:
    _json_repair_lib = None

logger = logging.getLogger(__name__)


def remove_think_tags(raw_text: str) -> str:
    """移除模型推理泄漏文本（think 标签、AgentThink 前缀等）。"""
    if not raw_text:
        return raw_text
    text = str(raw_text)

    # 1) 移除常见推理块标签（兼容大小写与属性）
    #    覆盖: think, thinking, thought, analysis, reflection, reasoning
    _TAG_NAMES = r"think|thinking|thought|analysis|reflection|reasoning"
    cleaned = re.sub(
        rf"<\s*(?:{_TAG_NAMES})\b[^>]*>"
        rf".*?"
        rf"<\s*/\s*(?:{_TAG_NAMES})\s*>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 2) 移除残留的单独标签（未闭合场景）
    cleaned = re.sub(
        rf"</?\s*(?:{_TAG_NAMES})\b[^>]*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # 3) 移除常见代理推理前缀行，如: [Agent 3][AgentThink] ...
    cleaned = re.sub(
        r"(?im)^\s*\[agent\s*\d+\]\s*\[agent(?:think|reasoning|analysis)\][^\n]*$",
        "",
        cleaned,
    )

    # 4) 清理多余空行
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()

    # 5) 回退保护：如果清理后为空但原文有实质内容，
    #    说明模型将所有有效内容都放在了推理标签内，提取标签内文本
    if not cleaned and text.strip():
        inner = re.search(
            rf"<\s*(?:{_TAG_NAMES})\b[^>]*>(.*?)"
            rf"<\s*/\s*(?:{_TAG_NAMES})\s*>",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if inner:
            cleaned = inner.group(1).strip()

    return cleaned


def unwrap_markdown_json(raw_text: str) -> str:
    """从 Markdown 或普通文本中提取 JSON 字符串。"""
    if not raw_text:
        return raw_text

    trimmed = raw_text.strip()

    fence_match = re.search(r"```(?:json|JSON)?\s*(.*?)\s*```", trimmed, re.DOTALL)
    if fence_match:
        candidate = fence_match.group(1).strip()
        if candidate:
            return candidate

    json_start_candidates = [idx for idx in (trimmed.find("{"), trimmed.find("[")) if idx != -1]
    if json_start_candidates:
        start_idx = min(json_start_candidates)
        closing_brace = trimmed.rfind("}")
        closing_bracket = trimmed.rfind("]")
        end_idx = max(closing_brace, closing_bracket)
        if end_idx != -1 and end_idx > start_idx:
            candidate = trimmed[start_idx : end_idx + 1].strip()
            if candidate:
                return candidate

    return trimmed


def sanitize_json_like_text(raw_text: str) -> str:
    """对可能含有未转义换行/引号的 JSON 文本进行清洗。"""
    if not raw_text:
        return raw_text

    result = []
    in_string = False
    escape_next = False
    length = len(raw_text)
    i = 0
    while i < length:
        ch = raw_text[i]
        if in_string:
            if escape_next:
                result.append(ch)
                escape_next = False
            elif ch == "\\":
                result.append(ch)
                escape_next = True
            elif ch == '"':
                j = i + 1
                while j < length and raw_text[j] in " \t\r\n":
                    j += 1

                if j >= length or raw_text[j] in "}]":
                    in_string = False
                    result.append(ch)
                elif raw_text[j] in ",:":
                    in_string = False
                    result.append(ch)
                else:
                    result.extend(["\\", '"'])
            elif ch == "\n":
                result.extend(["\\", "n"])
            elif ch == "\r":
                result.extend(["\\", "r"])
            elif ch == "\t":
                result.extend(["\\", "t"])
            else:
                result.append(ch)
        else:
            if ch == '"':
                in_string = True
            result.append(ch)
        i += 1

    return "".join(result)


def repair_json(text: str) -> str:
    """尝试修复常见的 JSON 格式错误，如缺少逗号、尾部逗号、未闭合括号等。

    优先使用 json_repair 库（更健壮），回退到内置的正则修复。
    """
    if not text:
        return text

    # 先尝试直接解析，如果成功就不需要修复
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # ── 策略1：使用 json_repair 库（最佳方案）──
    if _json_repair_lib is not None:
        try:
            repaired = _json_repair_lib.repair_json(text, return_objects=False)
            # 验证修复结果可正常解析
            json.loads(repaired)
            return repaired
        except Exception as exc:
            logger.debug("json_repair 库修复失败，回退到内置修复: %s", exc)

    # ── 策略2：清洗字符串内未转义的特殊字符 ──
    # 1. 移除行尾注释 (// ...)
    text = re.sub(r'(?<!:)//[^\n"]*$', '', text, flags=re.MULTILINE)

    try:
        sanitized = sanitize_json_like_text(text)
        json.loads(sanitized)
        return sanitized
    except (json.JSONDecodeError, Exception):
        pass

    # ── 策略3：正则修复缺少逗号的情况（跨行和同行）──
    # 跨行: "val1"\n"key2" → "val1",\n"key2"
    text = re.sub(r'(")\s*\n(\s*")', r'\1,\n\2', text)
    text = re.sub(r'(})\s*\n(\s*\{)', r'\1,\n\2', text)
    text = re.sub(r'(])\s*\n(\s*\[)', r'\1,\n\2', text)
    text = re.sub(r'(})\s*\n(\s*")', r'\1,\n\2', text)
    text = re.sub(r'(])\s*\n(\s*")', r'\1,\n\2', text)
    text = re.sub(r'(\btrue)\s*\n(\s*")', r'\1,\n\2', text)
    text = re.sub(r'(\bfalse)\s*\n(\s*")', r'\1,\n\2', text)
    text = re.sub(r'(\bnull)\s*\n(\s*")', r'\1,\n\2', text)
    text = re.sub(r'(\d)\s*\n(\s*")', r'\1,\n\2', text)
    # 同行: "val1" "key2" → "val1", "key2"
    text = re.sub(r'(")\s+(")', r'\1, \2', text)
    text = re.sub(r'(})\s+(\{)', r'\1, \2', text)
    text = re.sub(r'(})\s+(")', r'\1, \2', text)
    text = re.sub(r'(])\s+(")', r'\1, \2', text)
    text = re.sub(r'(])\s+(\[)', r'\1, \2', text)
    text = re.sub(r'(\d)\s+(")', r'\1, \2', text)

    # 移除尾部逗号 (trailing comma before } or ])
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # 尝试闭合未闭合的括号
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    if open_braces > 0 or open_brackets > 0:
        text = text.rstrip()
        text = text.rstrip(',')
        text += ']' * max(0, open_brackets) + '}' * max(0, open_braces)

    return text


_UNSET = object()


_TASK_ANALYSIS_PREFIX_RE = re.compile(
    r"^\s*(?:\d+[\.、]\s*)?"
    r"(?:版本内容为|分析任务要求|分析任务|任务分析|需求分析|审题|"
    r"原文本分析|原文分析|文本分析|章节分析|处理思路|润色思路|修改思路)"
    r"[：:]?"
)
_VERSION_CONTENT_MARKER_RE = re.compile(r"^\s*版本内容为[：:]\s*(.*)$")
_TASK_ANALYSIS_LABEL_RE = re.compile(
    r"^\s*(?:[-*+]\s*)?(?:\d+[\.、]\s*)?"
    r"(?:角色|目标|限制|任务|要求|原则|核心原则|润色原则|优化维度|输出格式|输出要求|"
    r"注意事项|字数要求|情节|人物|氛围|需要提升的地方|画面感|感官描写|文学性|"
    r"节奏|对话|场景细节|微表情|声音|触觉|视觉)"
    r"[：:]"
)
_CHAPTER_BODY_MARKER_RE = re.compile(
    r"^\s*(?:\d+[\.、]\s*)?"
    r"(?:润色后(?:的)?(?:完整)?(?:章节|内容|正文)?|修改后(?:的)?(?:完整)?(?:章节|内容|正文)?|"
    r"优化后(?:的)?(?:完整)?(?:章节|内容|正文)?|最终(?:章节|内容|正文)|正文|小说正文|章节正文|完整章节)"
    r"(?:为)?[：:]\s*(.*)$"
)
_ORIGINAL_CONTENT_MARKER_RE = re.compile(r"^\s*\[(?:原章节内容|章节内容|正文|小说正文)\]\s*$")
_NON_CHAPTER_OUTPUT_MARKER_RE = re.compile(
    r"(分析任务|任务分析|原文本分析|原文分析|文本分析|章节分析|润色思路|修改思路|处理思路|"
    r"优化说明|编辑备注|输出要求|角色：|目标：|限制：|原则：|需要提升的地方：|"
    r"画面感：|感官描写：|文学性：|情节：|人物：|氛围：)"
)


def _looks_like_task_analysis_prefix(lines: list[str], start: int) -> bool:
    head_lines = [line.strip() for line in lines[start : start + 8] if line.strip()]
    if not head_lines:
        return False
    head_text = "\n".join(head_lines)
    if _TASK_ANALYSIS_PREFIX_RE.match(head_lines[0]):
        return True
    label_hits = sum(1 for line in head_lines if _TASK_ANALYSIS_LABEL_RE.match(line))
    strong_markers = (
        "分析任务要求",
        "分析任务",
        "文学功底深厚",
        "擅长小说润色",
        "润色编辑",
        "优化专家",
        "原文本分析",
        "提升文字的文学性",
        "直接输出",
        "不要输出其他",
        "不增删情节",
    )
    return label_hits >= 2 and any(marker in head_text for marker in strong_markers)


def _is_task_analysis_line(stripped: str) -> bool:
    if not stripped:
        return True
    if _TASK_ANALYSIS_PREFIX_RE.match(stripped) or _TASK_ANALYSIS_LABEL_RE.match(stripped):
        return True
    if re.match(
        r"^\s*(?:[-*+]\s*)?\d+[\.、]\s*"
        r"(?:保持|提升|强化|润色|打磨|不增删|字数|优化|修改|修订|检查|保留|限制|要求|"
        r"分析任务|原文本分析|原文分析|文本分析)",
        stripped,
    ):
        return True
    if re.match(
        r"^\s*(?:[-*+]\s*)?(?:\d+[\.、]\s*)?[^：:\n]{1,24}[：:].*"
        r"(?:男主|女主|主角|配角|前妻|儿子|女嘉宾|角色|人设|控制狂|懂事|氛围|情节|"
        r"画面感|感官|文学性|节奏|提升|细节|微表情|视觉|听觉|触觉|对话)",
        stripped,
    ):
        return True
    return bool(
        re.match(r"^\s*(?:直接输出|不要输出|禁止输出|请只输出|无其他|字数不得|总字数|不增删情节)", stripped)
    )


def _strip_task_analysis_prefix(text: str) -> str:
    """移除模型把编辑任务拆解当作正文输出的前缀块。"""
    lines = text.split("\n")
    first_content_idx = None
    for idx, line in enumerate(lines):
        if line.strip():
            first_content_idx = idx
            break
    if first_content_idx is None or not _looks_like_task_analysis_prefix(lines, first_content_idx):
        return text

    scan_limit = min(len(lines), first_content_idx + 80)
    for idx in range(first_content_idx, scan_limit):
        stripped = lines[idx].strip()
        if not stripped:
            continue

        version_match = _VERSION_CONTENT_MARKER_RE.match(stripped)
        if version_match:
            remainder = version_match.group(1).strip()
            if remainder and not _TASK_ANALYSIS_PREFIX_RE.match(remainder):
                return "\n".join([remainder] + lines[idx + 1 :]).strip()
            continue

        body_match = _CHAPTER_BODY_MARKER_RE.match(stripped)
        if body_match:
            remainder = body_match.group(1).strip()
            rest = lines[idx + 1 :]
            if remainder:
                rest = [remainder] + rest
            return "\n".join(rest).strip()

        if _ORIGINAL_CONTENT_MARKER_RE.match(stripped):
            return "\n".join(lines[idx + 1 :]).strip()

    skip_to = first_content_idx
    while skip_to < len(lines):
        stripped = lines[skip_to].strip()
        if not _is_task_analysis_line(stripped):
            break
        skip_to += 1

    return "\n".join(lines[skip_to:]).strip()


def is_probable_chapter_plain_text(text: str) -> bool:
    """判断一段文本是否更像小说正文，而不是提示词、任务分析或编辑说明。"""
    stripped = (text or "").strip()
    if not stripped:
        return False

    compact = re.sub(r"\s+", "", stripped)
    if len(compact) < 80:
        return False

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    first_lines = lines[:12]
    head_text = "\n".join(first_lines)

    if first_lines and _looks_like_task_analysis_prefix(lines, 0):
        return False

    marker_hits = len(_NON_CHAPTER_OUTPUT_MARKER_RE.findall(head_text))
    label_lines = sum(1 for line in first_lines if _TASK_ANALYSIS_LABEL_RE.match(line))
    numbered_analysis_lines = sum(
        1
        for line in first_lines
        if re.match(r"^\s*\d+[\.、]\s*(?:分析|原文|任务|角色|目标|限制|原则)", line)
    )
    if marker_hits >= 2 or label_lines >= 3 or numbered_analysis_lines >= 1:
        return False

    # 正文通常含有较多叙事标点；分析提纲常由短标签行组成。
    punctuation_count = sum(compact.count(ch) for ch in "，。！？“”‘’、；")
    if punctuation_count < 8 and len(compact) < 300:
        return False

    return True


def parse_llm_json(raw, default=_UNSET):
    """统一的 LLM JSON 解析入口（对象/数组通用）。

    去思考标签 → 去 Markdown 围栏 → json_repair 修复 → json.loads，
    用以彻底替换全仓散落的脆弱 `content.find('{')..rfind('}')` 切片解析
    （后者在嵌套/多对象/数组/前后缀文本时极易出错）。

    - 成功：返回解析后的 Python 对象（dict / list / 标量）。
    - 失败：default 已提供则返回 default（软失败）；否则抛 ValueError（硬失败）。
    """
    text = raw if isinstance(raw, str) else ("" if raw is None else str(raw))
    cleaned = repair_json(unwrap_markdown_json(remove_think_tags(text)))
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        if default is not _UNSET:
            logger.warning("parse_llm_json 解析失败，返回 default: %s", exc)
            return default
        raise ValueError(f"无法解析 LLM JSON 输出: {exc}") from exc


def sanitize_chapter_plain_text(raw_text: str) -> str:
    """清理章节正文中的 Markdown 标签和 LLM 前言，确保输出为纯文本叙事。"""
    if not raw_text:
        return raw_text

    # 先剥离可能泄漏的推理文本
    text = remove_think_tags(raw_text)
    text = _strip_task_analysis_prefix(text)

    # ── 去除 LLM 对话式前言（安全网） ──
    # 某些 LLM 会在正文前添加 "可以，下面是…" "好的，以下是第X章…" 等回应
    lines = text.split("\n")
    skip_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            skip_count += 1
            continue
        # 检测常见 LLM 对话式前言
        if re.match(
            r'^(可以[，。,.]|好的[，。,.]|当然[，。,.]|没问题[，。,.]|'
            r'下面是|以下是|这是|我来|让我|'
            r'我已经|我已为|我为您|我把|'
            r'精简后|精简版|概要版|缩写版|草稿版|'
            r'如需扩展|如果需要|你(要是|需要|想)|'
            r'我先给你|先给你|给你一版|根据您|按照您)',
            stripped,
        ):
            skip_count += 1
            continue
        if re.match(r'^#{1,4}\s+.*(精简版|精简稿|概要版|草稿|压缩版|缩写版)', stripped):
            skip_count += 1
            continue
        # 带括号的字数说明行：(约2600字)、（控制在4000字以内）
        if re.match(r'^[\(（].*字.*[\)）][：:.]?\s*$', stripped):
            skip_count += 1
            continue
        # 第一个看起来像正文的行，停止
        break
    if skip_count > 0:
        lines = lines[skip_count:]

    # ── 去除 LLM 尾部元对话（安全网） ──
    # 某些 LLM 会在正文后追加 "您需要我帮您…" "希望对您有帮助" 等
    tail_skip = 0
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            tail_skip += 1
            continue
        if re.match(
            r'^(您需要|需要我|希望我|如果您|如有需要|如需|是否需要|'
            r'我已经为您|我已为您|以上是|以上就是|以上为|'
            r'如果你|你需要|要我|还是继续|希望对您|'
            r'直接输出|不要输出|禁止输出|请只输出|输出要求)',
            stripped,
        ):
            tail_skip += 1
            continue
        break
    if tail_skip > 0:
        lines = lines[:-tail_skip]

    text = "\n".join(lines).lstrip("\n")

    # 先移除代码块围栏标记（保留内部文本）
    text = re.sub(r"(?m)^\s*```(?:\w+)?\s*$", "", text)

    # 移除标题和分隔线
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*(?:---+|\*\*\*+|___+)\s*$", "", text)

    # 移除引用块前缀
    text = re.sub(r"(?m)^\s*>\s?", "", text)

    # 移除列表前缀
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)

    # 移除图片标记（保留 alt 文本）
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)

    # 移除链接标记（保留链接文本）
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)

    # 移除行内代码标记
    text = re.sub(r"`([^`]*)`", r"\1", text)

    # 去掉粗体/斜体标记
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)

    # 收敛多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_json(value: object) -> str | None:
    """从 LLM 返回的 JSON 结构中递归提取正文文本。

    支持以下格式：
    - 纯字符串
    - {"content": "..."} / {"chapter_content": "..."} / {"text": "..."} 等
    - 嵌套 dict / list 结构
    """
    if not value:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("content", "chapter_content", "chapter_text", "text", "body", "story"):
            if value.get(key):
                nested = extract_text_from_json(value.get(key))
                if nested:
                    return nested
        return None
    if isinstance(value, list):
        for item in value:
            nested = extract_text_from_json(item)
            if nested:
                return nested
    return None
