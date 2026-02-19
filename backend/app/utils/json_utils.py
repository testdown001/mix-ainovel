# AIMETA P=JSON工具_JSON解析和修复|R=安全解析_格式修复|NR=不含业务逻辑|E=parse_json_safely|X=internal|A=工具函数|D=json|S=none|RD=./README.ai
import json
import re


def remove_think_tags(raw_text: str) -> str:
    """移除 <think></think> 标签，避免污染结果。"""
    if not raw_text:
        return raw_text
    return re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()


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
    """尝试修复常见的 JSON 格式错误，如缺少逗号、尾部逗号、未闭合括号等。"""
    if not text:
        return text

    # 先尝试直接解析，如果成功就不需要修复
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # 1. 移除行尾注释 (// ...)
    text = re.sub(r'(?<!:)//[^\n"]*$', '', text, flags=re.MULTILINE)

    # 2. 修复缺少逗号的情况：}" 或 ]" 或 数字/字符串/true/false/null 后直接跟 " 或 { 或 [
    # 例如: "key1": "val1"\n"key2" → "key1": "val1",\n"key2"
    text = re.sub(r'(")\s*\n(\s*")', r'\1,\n\2', text)
    text = re.sub(r'(})\s*\n(\s*\{)', r'\1,\n\2', text)
    text = re.sub(r'(])\s*\n(\s*\[)', r'\1,\n\2', text)
    text = re.sub(r'(})\s*\n(\s*")', r'\1,\n\2', text)
    text = re.sub(r'(])\s*\n(\s*")', r'\1,\n\2', text)
    text = re.sub(r'(\btrue)\s*\n(\s*")', r'\1,\n\2', text)
    text = re.sub(r'(\bfalse)\s*\n(\s*")', r'\1,\n\2', text)
    text = re.sub(r'(\bnull)\s*\n(\s*")', r'\1,\n\2', text)
    text = re.sub(r'(\d)\s*\n(\s*")', r'\1,\n\2', text)

    # 3. 移除尾部逗号 (trailing comma before } or ])
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # 4. 尝试闭合未闭合的括号
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    if open_braces > 0 or open_brackets > 0:
        text = text.rstrip()
        # 移除末尾可能的不完整逗号
        text = text.rstrip(',')
        text += ']' * max(0, open_brackets) + '}' * max(0, open_braces)

    return text


def sanitize_chapter_plain_text(raw_text: str) -> str:
    """清理章节正文中的 Markdown 标签，确保输出为纯文本叙事。"""
    if not raw_text:
        return raw_text

    text = raw_text

    # 先移除代码块围栏标记（保留内部文本）
    text = re.sub(r"(?m)^\s*```(?:\w+)?\s*$", "", text)

    # 移除标题和分隔线
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*(?:---+|\*\*\*+|___+)\s*$", "", text)

    # 移除列表前缀
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)

    # 去掉粗体/斜体标记
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text, flags=re.DOTALL)

    # 收敛多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
