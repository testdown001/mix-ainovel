# -*- coding: utf-8 -*-
# AIMETA P=LLM工具_大模型调用辅助|R=请求构建_响应解析|NR=不含业务逻辑|E=LLMTool|X=internal|A=工具类|D=httpx|S=net|RD=./README.ai
"""OpenAI / Anthropic / Gemini / OpenAI Responses 兼容型 LLM 工具封装。"""

import json as _json
import logging
import os
from dataclasses import asdict, dataclass
from typing import AsyncGenerator, Dict, List, Optional

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_CLAUDE_CLI_UA = "claude-cli/2.1.38 (external, cli)"

_CLAUDE_CODE_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": _CLAUDE_CLI_UA,
    "X-Stainless-Arch": "x64",
    "X-Stainless-Lang": "js",
    "X-Stainless-OS": "Linux",
    "X-Stainless-Package-Version": "0.73.0",
    "X-Stainless-Retry-Count": "0",
    "X-Stainless-Runtime": "node",
    "X-Stainless-Runtime-Version": "v24.3.0",
    "X-Stainless-Timeout": "3000",
    "anthropic-beta": (
        "claude-code-20250219,"
        "prompt-caching-scope-2026-01-05,"
        "effort-2025-11-24,"
        "adaptive-thinking-2026-01-28"
    ),
    "anthropic-dangerous-direct-browser-access": "true",
    "anthropic-version": "2023-06-01",
    "x-app": "cli",
    "Accept-Encoding": "gzip, deflate, br, zstd",
}


def _make_logging_hooks() -> Dict:
    """创建 httpx event hooks，记录实际发出的 HTTP 请求和收到的响应。"""

    async def log_request(request: httpx.Request):
        body_preview = ""
        if request.content:
            try:
                body_preview = request.content.decode("utf-8")[:2000]
            except Exception:
                body_preview = f"<binary {len(request.content)} bytes>"
        logger.info(
            "HTTP请求 >> %s %s headers=%s body=%s",
            request.method,
            request.url,
            dict(request.headers),
            body_preview,
        )

    async def log_response(response: httpx.Response):
        request = response.request
        resp_body = ""
        if response.status_code >= 400:
            try:
                await response.aread()
                resp_body = response.text[:2000]
            except Exception:
                resp_body = "<无法读取响应体>"
        logger.info(
            "HTTP响应 << %s %s status=%d headers=%s body=%s",
            request.method,
            request.url,
            response.status_code,
            dict(response.headers),
            resp_body,
        )

    return {"request": [log_request], "response": [log_response]}


def _build_http_client() -> httpx.AsyncClient:
    """构建共享的 httpx 客户端配置。"""
    return httpx.AsyncClient(
        event_hooks=_make_logging_hooks(),
        headers={
            "User-Agent": _BROWSER_UA,
            "Accept": "application/json, text/event-stream",
        },
        timeout=httpx.Timeout(connect=75.0, read=1500.0, write=150.0, pool=150.0),
        limits=httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10,
            keepalive_expiry=60,
        ),
    )


@dataclass
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


class LLMClient:
    """OpenAI 兼容接口的异步流式调用封装。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("缺少 OPENAI_API_KEY 配置，请在数据库或环境变量中补全。")

        self._base_url = base_url or os.environ.get("OPENAI_API_BASE")
        self._client = AsyncOpenAI(
            api_key=key,
            base_url=self._base_url,
            http_client=_build_http_client(),
            default_headers={"User-Agent": _BROWSER_UA},
        )

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        response_format: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: int = 120,
        **kwargs,
    ) -> AsyncGenerator[Dict[str, str], None]:
        payload = {
            "model": model or os.environ.get("MODEL", "gpt-3.5-turbo"),
            "messages": [msg.to_dict() for msg in messages],
            "stream": True,
            "timeout": timeout,
            **kwargs,
        }
        if response_format:
            payload["response_format"] = {"type": response_format}
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        msg_summary = [
            {"role": m.role, "content_length": len(m.content)} for m in messages
        ]
        log_payload = {k: v for k, v in payload.items() if k != "messages"}
        logger.info(
            "LLM请求(OpenAI) >> base_url=%s model=%s params=%s messages=%s",
            self._base_url, payload.get("model"), log_payload, msg_summary,
        )

        try:
            stream = await self._client.chat.completions.create(**payload)
        except Exception as exc:
            resp_body = ""
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    resp_body = response.text[:2000] if hasattr(response, "text") else ""
                except Exception:
                    resp_body = "<无法读取响应体>"
            logger.error(
                "LLM请求失败(OpenAI) >> base_url=%s model=%s error_type=%s error=%s response_body=%s",
                self._base_url, payload.get("model"),
                type(exc).__name__, exc, resp_body,
                exc_info=True,
            )
            raise

        collected_content = ""
        collected_reasoning = ""
        final_finish_reason = None
        _chunk_count = 0
        _first_chunk_logged = False
        _reasoning_field_name: Optional[str] = None  # 记录代理使用的 thinking 字段名

        try:
            async for chunk in stream:
                _chunk_count += 1
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]

                # 调试：记录第一个 chunk 的结构
                if not _first_chunk_logged:
                    _first_chunk_logged = True
                    delta_extra = {}
                    if choice.delta:
                        delta_extra = getattr(choice.delta, "model_extra", {}) or {}
                        if not delta_extra:
                            delta_extra = getattr(choice.delta, "__pydantic_extra__", {}) or {}
                    logger.info(
                        "OpenAI stream first chunk: model=%s finish_reason=%s "
                        "role=%s delta_extra_keys=%s",
                        getattr(chunk, "model", None),
                        choice.finish_reason,
                        getattr(choice.delta, "role", None),
                        list(delta_extra.keys()) if delta_extra else [],
                    )

                # ------ 提取 reasoning_content（thinking 阶段） ------
                if choice.delta:
                    extra = getattr(choice.delta, "model_extra", {}) or {}
                    if not extra:
                        extra = getattr(choice.delta, "__pydantic_extra__", {}) or {}
                    for key in ("reasoning_content", "thinking", "reasoning"):
                        val = extra.get(key)
                        if val:
                            if not _reasoning_field_name:
                                _reasoning_field_name = key
                                logger.info(
                                    "OpenAI 代理使用 '%s' 字段传输 thinking 内容", key,
                                )
                            collected_reasoning += val

                # ------ 提取 content（正文阶段） ------
                text = choice.delta.content if choice.delta else None
                if text:
                    collected_content += text

                if choice.finish_reason:
                    final_finish_reason = choice.finish_reason
                yield {
                    "content": text,
                    "finish_reason": choice.finish_reason,
                }

            # 流结束后：如果 content 为空但 reasoning 有内容，
            # 说明代理将所有内容（含最终回答）都放在了 reasoning 字段，
            # 将 reasoning 作为最终内容补发给上层
            if not collected_content and collected_reasoning:
                logger.info(
                    "content 为空但 reasoning 有内容（%d 字符），将 reasoning 作为响应内容",
                    len(collected_reasoning),
                )
                yield {
                    "content": collected_reasoning,
                    "finish_reason": final_finish_reason or "stop",
                }
        finally:
            total_content_len = len(collected_content) or len(collected_reasoning)
            logger.info(
                "LLM响应(OpenAI) << base_url=%s model=%s finish_reason=%s "
                "content_len=%d reasoning_len=%d chunks=%d preview=%.200s",
                self._base_url, payload.get("model"),
                final_finish_reason, len(collected_content),
                len(collected_reasoning), _chunk_count,
                (collected_content or collected_reasoning)[:200],
            )

    async def aclose(self):
        """关闭底层 HTTP 客户端连接。"""
        await self._client.close()


class AnthropicLLMClient:
    """原生 Anthropic Messages API (/v1/messages) 的异步流式调用封装，使用 x-api-key 认证。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("缺少 API Key 配置。")

        self._api_key = key
        raw_base = base_url or os.environ.get("OPENAI_API_BASE") or "https://api.anthropic.com/v1"
        self._base_url = raw_base.rstrip("/")
        self._client = httpx.AsyncClient(
            event_hooks=_make_logging_hooks(),
            headers={
                "User-Agent": _BROWSER_UA,
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "anthropic-version": "2023-06-01",
                "x-api-key": key,
            },
            timeout=httpx.Timeout(connect=75.0, read=1500.0, write=150.0, pool=150.0),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=60,
            ),
        )

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        response_format: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: int = 600,
        **kwargs,
    ) -> AsyncGenerator[Dict[str, str], None]:
        # 拆分 system 消息
        system_parts: List[str] = []
        api_messages: List[Dict[str, str]] = []
        for msg in messages:
            if msg.role == "system":
                system_parts.append(msg.content)
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        system_text = "\n\n".join(system_parts)

        if response_format == "json_object":
            system_text += (
                "\n\n[IMPORTANT] You MUST reply in pure JSON format only. "
                "Do not include markdown code block markers (```) or any non-JSON content. "
                "/ 你必须以纯 JSON 格式回复，不要包含 markdown 代码块标记或其他非 JSON 内容。"
            )

        thinking_budget = kwargs.pop("thinking_budget", None)

        # 检测 thinking 模型（opus-4 系列、claude-3-7-sonnet），自动启用 thinking
        _model_name = (model or "").lower()
        _is_thinking_model = any(
            kw in _model_name for kw in ("opus-4", "claude-3-7")
        )

        payload: Dict = {
            "model": model or "claude-sonnet-4-20250514",
            "max_tokens": max_tokens or 8192,
            "stream": True,
            "messages": api_messages,
        }
        if system_text:
            payload["system"] = system_text

        if thinking_budget:
            payload["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
            # thinking 模式不兼容 temperature/top_p
        elif _is_thinking_model:
            payload["thinking"] = {"type": "enabled", "budget_tokens": 10000}
            logger.info("Anthropic thinking 模型自动启用 thinking: model=%s budget=10000", model)
            # thinking 模式不兼容 temperature/top_p
        else:
            if temperature is not None:
                payload["temperature"] = temperature
            if top_p is not None:
                payload["top_p"] = top_p

        msg_summary = [{"role": m.role, "content_length": len(m.content)} for m in messages]
        log_payload = {k: v for k, v in payload.items() if k not in ("messages", "system")}
        logger.info(
            "LLM请求(Anthropic) >> url=%s/messages model=%s params=%s system_len=%d messages=%s",
            self._base_url, payload.get("model"), log_payload,
            len(system_text), msg_summary,
        )

        url = f"{self._base_url}/messages"
        async for chunk in self._do_stream(url, payload, timeout):
            yield chunk

    async def _do_stream(
        self, url: str, payload: Dict, timeout: int,
    ) -> AsyncGenerator[Dict[str, str], None]:
        """公共 SSE 流式解析。"""
        collected_content = ""
        final_finish_reason = None
        _current_block_type: Optional[str] = None
        _event_counts: Dict[str, int] = {}
        _block_types_seen: List[str] = []
        _total_lines = 0
        _thinking_len = 0
        _thinking_text = ""
        _tool_use_input = ""

        try:
            async with self._client.stream(
                "POST", url, json=payload, timeout=timeout,
            ) as response:
                if response.status_code >= 400:
                    error_body = (await response.aread()).decode("utf-8", errors="replace")[:2000]
                    logger.error(
                        "LLM请求失败(Anthropic) >> %s status=%d body=%s",
                        url, response.status_code, error_body,
                    )
                    raise httpx.HTTPStatusError(
                        f"Anthropic API error (HTTP {response.status_code}): {error_body}",
                        request=response.request,
                        response=response,
                    )

                _sse_event_type = ""  # 跟踪 SSE event: 行的事件类型

                async for line in response.aiter_lines():
                    _total_lines += 1
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("event:"):
                        _sse_event_type = line[6:].strip()
                        continue
                    if not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        final_finish_reason = final_finish_reason or "stop"
                        yield {"content": None, "finish_reason": "stop"}
                        break

                    try:
                        data = _json.loads(data_str)
                    except _json.JSONDecodeError:
                        logger.debug("SSE JSON解析失败: %.200s", data_str)
                        continue

                    # 优先使用 data 中的 type 字段，回退到 SSE event: 行
                    event_type = data.get("type") or _sse_event_type or "unknown"
                    _event_counts[event_type] = _event_counts.get(event_type, 0) + 1

                    if event_type == "content_block_start":
                        block = data.get("content_block", {})
                        _current_block_type = block.get("type")
                        _block_types_seen.append(_current_block_type or "unknown")
                        logger.debug(
                            "SSE content_block_start: index=%s type=%s",
                            data.get("index"), _current_block_type,
                        )
                    elif event_type == "content_block_stop":
                        logger.debug(
                            "SSE content_block_stop: index=%s block_type_was=%s",
                            data.get("index"), _current_block_type,
                        )
                        _current_block_type = None
                    elif event_type == "content_block_delta":
                        if _current_block_type == "thinking":
                            delta = data.get("delta", {})
                            thinking_text = delta.get("thinking", "")
                            _thinking_len += len(thinking_text)
                            _thinking_text += thinking_text
                            continue
                        if _current_block_type == "tool_use":
                            # tool_use 块的 input JSON 片段，累积但不作为正文输出
                            delta = data.get("delta", {})
                            partial_json = delta.get("partial_json", "")
                            if partial_json:
                                _tool_use_input += partial_json
                            continue
                        delta = data.get("delta", {})
                        text = delta.get("text", "")
                        if text:
                            collected_content += text
                            yield {"content": text, "finish_reason": None}
                    elif event_type == "message_delta":
                        stop_reason = data.get("delta", {}).get("stop_reason")
                        if stop_reason:
                            final_finish_reason = stop_reason
                            yield {"content": None, "finish_reason": stop_reason}
                    elif event_type == "message_stop":
                        final_finish_reason = final_finish_reason or "stop"
                        yield {"content": None, "finish_reason": "stop"}
                    elif event_type == "error":
                        error_info = data.get("error", {})
                        error_msg = error_info.get("message", str(error_info))
                        logger.error("Anthropic stream error event: %s", error_info)
                        raise RuntimeError(f"Anthropic stream error: {error_msg}")

            # 流结束后补救：
            # 1. thinking 有内容但 content 为空 → 将 thinking 作为响应
            if not collected_content and _thinking_text:
                logger.info(
                    "content 为空但 thinking 有内容（%d 字符），将 thinking 作为响应内容",
                    len(_thinking_text),
                )
                yield {
                    "content": _thinking_text,
                    "finish_reason": final_finish_reason or "stop",
                }
            # 2. 模型返回了 tool_use 而非 text → 提取 tool_use input 作为响应
            elif not collected_content and _tool_use_input:
                logger.warning(
                    "模型返回 tool_use 而非 text（%d 字符），将 tool_use input 作为响应内容。"
                    "这通常意味着代理/模型误将文本放入了 tool call。",
                    len(_tool_use_input),
                )
                yield {
                    "content": _tool_use_input,
                    "finish_reason": final_finish_reason or "stop",
                }

        except httpx.HTTPStatusError:
            raise
        except Exception as exc:
            if not isinstance(exc, (httpx.RemoteProtocolError, httpx.ReadError, httpx.ReadTimeout)):
                logger.error(
                    "LLM请求异常(Anthropic) >> url=%s model=%s error_type=%s error=%s",
                    url, payload.get("model"), type(exc).__name__, exc,
                    exc_info=True,
                )
            raise
        finally:
            total_content_len = len(collected_content) or len(_thinking_text) or len(_tool_use_input)
            logger.info(
                "LLM响应(Anthropic) << url=%s model=%s finish_reason=%s "
                "len=%d thinking_len=%d tool_use_len=%d total_sse_lines=%d events=%s blocks=%s preview=%.500s",
                url, payload.get("model"),
                final_finish_reason, total_content_len,
                _thinking_len, len(_tool_use_input), _total_lines, _event_counts,
                _block_types_seen,
                (collected_content or _thinking_text or _tool_use_input)[:500],
            )
            if not collected_content and not _thinking_text and not _tool_use_input and final_finish_reason:
                logger.warning(
                    "LLM响应为空但流已结束 >> url=%s model=%s finish_reason=%s "
                    "thinking_len=%d events=%s blocks=%s — "
                    "可能原因: temperature与thinking冲突/代理拒绝请求",
                    url, payload.get("model"), final_finish_reason,
                    _thinking_len, _event_counts, _block_types_seen,
                )

    async def aclose(self):
        """关闭底层 HTTP 客户端连接。"""
        await self._client.aclose()


class AnyRouterLLMClient:
    """Claude Code 兼容代理的异步流式调用封装（anyrouter 等），使用 Bearer 认证 + 固定 system。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("缺少 API Key 配置。")

        self._api_key = key
        raw_base = base_url or os.environ.get("OPENAI_API_BASE") or "https://api.anthropic.com/v1"
        self._base_url = raw_base.rstrip("/")
        self._client = httpx.AsyncClient(
            event_hooks=_make_logging_hooks(),
            headers={
                **_CLAUDE_CODE_HEADERS,
                "Authorization": f"Bearer {key}",
            },
            timeout=httpx.Timeout(connect=75.0, read=1500.0, write=150.0, pool=150.0),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=60,
            ),
        )

    # Claude Code 固定 system prompt（代理校验用）
    _FIXED_SYSTEM = [
        {
            "type": "text",
            "text": "You are Claude Code, Anthropic's official CLI for Claude.",
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                "\nYou are an interactive CLI tool that helps users with software engineering tasks. "
                "Use the instructions below and the tools available to you to assist the user.\n\n"
                "IMPORTANT: Assist with authorized security testing, defensive security, CTF challenges, "
                "and educational contexts. Refuse requests for destructive techniques, DoS attacks, mass "
                "targeting, supply chain compromise, or detection evasion for malicious purposes. Dual-use "
                "security tools (C2 frameworks, credential testing, exploit development) require clear "
                "authorization context: pentesting engagements, CTF competitions, security research, or "
                "defensive use cases.\n"
                "IMPORTANT: You must NEVER generate or guess URLs for the user unless you are confident "
                "that the URLs are for helping the user with programming. You may use URLs provided by "
                "the user in their messages or local files.\n\n"
                "If the user asks for help or wants to give feedback inform them of the following:\n"
                "- /help: Get help with using Claude Code\n"
                "- To give feedback, users should report the issue at "
                "https://github.com/anthropics/claude-code/issues\n\n"
                "# Tone and style\n"
                "- Only use emojis if the user explicitly requests it. Avoid using emojis in all "
                "communication unless asked.\n"
                "- Your output will be displayed on a command line interface. Your responses should be "
                "short and concise. You can use Github-flavored markdown for formatting, and will be "
                "rendered in a monospace font using the CommonMark specification.\n"
                "- Output text to communicate with the user; all text you output outside of tool use is "
                "displayed to the user. Only use tools to complete tasks. Never use tools like Bash or "
                "code comments as means to communicate with the user during the session.\n"
                "- NEVER create files unless they're absolutely necessary for achieving your goal. ALWAYS "
                "prefer editing an existing file to creating a new one. This includes markdown files.\n"
                "- Do not use a colon before tool calls. Your tool calls may not be shown directly in the "
                'output, so text like "Let me read the file:" followed by a read tool call should just be '
                '"Let me read the file." with a period.\n\n'
                "# Professional objectivity\n"
                "Prioritize technical accuracy and truthfulness over validating the user's beliefs. Focus "
                "on facts and problem-solving, providing direct, objective technical info without any "
                "unnecessary superlatives, praise, or emotional validation. It is best for the user if "
                "Claude honestly applies the same rigorous standards to all ideas and disagrees when "
                "necessary, even if it may not be what the user wants to hear. Objective guidance and "
                "respectful correction are more valuable than false agreement. Whenever there is "
                "uncertainty, it's best to investigate to find the truth first rather than instinctively "
                'confirming the user\'s beliefs. Avoid using over-the-top validation or excessive praise '
                'when responding to users such as "You\'re absolutely right" or similar phrases.\n\n'
                "# No time estimates\n"
                "Never give time estimates or predictions for how long tasks will take, whether for your "
                "own work or for users planning their projects. Avoid phrases like "
                '"this will take me a few minutes," "should be done in about 5 minutes," '
                '"this is a quick fix," "this will take 2-3 weeks," or "we can do this later." '
                "Focus on what needs to be done, not how long it might take. Break work into actionable "
                "steps and let users judge timing for themselves.\n\n"
                "# Asking questions as you work\n\n"
                "You have access to the AskUserQuestion tool to ask the user questions when you need "
                "clarification, want to validate assumptions, or need to make a decision you're unsure "
                "about. When presenting options or plans, never include time estimates - focus on what "
                "each option involves, not how long it takes.\n\n"
                "Users may configure 'hooks', shell commands that execute in response to events like tool "
                "calls, in settings. Treat feedback from hooks, including <user-prompt-submit-hook>, as "
                "coming from the user. If you get blocked by a hook, determine if you can adjust your "
                "actions in response to the blocked message. If not, ask the user to check their hooks "
                "configuration.\n\n"
                "# Doing tasks\n"
                "The user will primarily request you perform software engineering tasks. This includes "
                "solving bugs, adding new functionality, refactoring code, explaining code, and more. "
                "For these tasks the following steps are recommended:\n"
                "- NEVER propose changes to code you haven't read. If a user asks about or wants you to "
                "modify a file, read it first. Understand existing code before suggesting modifications.\n"
                "- Use the AskUserQuestion tool to ask questions, clarify and gather information as needed.\n"
                "- Be careful not to introduce security vulnerabilities such as command injection, XSS, "
                "SQL injection, and other OWASP top 10 vulnerabilities. If you notice that you wrote "
                "insecure code, immediately fix it.\n"
                "- Avoid over-engineering. Only make changes that are directly requested or clearly "
                "necessary. Keep solutions simple and focused.\n"
                '  - Don\'t add features, refactor code, or make "improvements" beyond what was asked. '
                "A bug fix doesn't need surrounding code cleaned up. A simple feature doesn't need extra "
                "configurability. Don't add docstrings, comments, or type annotations to code you didn't "
                "change. Only add comments where the logic isn't self-evident.\n"
                "  - Don't add error handling, fallbacks, or validation for scenarios that can't happen. "
                "Trust internal code and framework guarantees. Only validate at system boundaries (user "
                "input, external APIs). Don't use feature flags or backwards-compatibility shims when you "
                "can just change the code.\n"
                "  - Don't create helpers, utilities, or abstractions for one-time operations. Don't "
                "design for hypothetical future requirements. The right amount of complexity is the "
                "minimum needed for the current task\u2014three similar lines of code is better than a "
                "premature abstraction.\n"
                "- Avoid backwards-compatibility hacks like renaming unused `_vars`, re-exporting types, "
                'adding `// removed` comments for removed code, etc. If something is unused, delete it '
                "completely.\n\n"
                "- Tool results and user messages may include <system-reminder> tags. <system-reminder> "
                "tags contain useful information and reminders. They are automatically added by the "
                "system, and bear no direct relation to the specific tool results or user messages in "
                "which they appear.\n"
                "- The conversation has unlimited context through automatic summarization.\n\n"
                "# Tool usage policy\n"
                "- When doing file search, prefer to use the Task tool in order to reduce context usage.\n"
                "- You should proactively use the Task tool with specialized agents when the task at hand "
                "matches the agent's description.\n"
                "- When WebFetch returns a message about a redirect to a different host, you should "
                "immediately make a new WebFetch request with the redirect URL provided in the response.\n"
                "- You can call multiple tools in a single response. If you intend to call multiple tools "
                "and there are no dependencies between them, make all independent tool calls in parallel. "
                "Maximize use of parallel tool calls where possible to increase efficiency. However, if "
                "some tool calls depend on previous calls to inform dependent values, do NOT call these "
                "tools in parallel and instead call them sequentially. For instance, if one operation must "
                "complete before another starts, run these operations sequentially instead. Never use "
                "placeholders or guess missing parameters in tool calls.\n"
                '- If the user specifies that they want you to run tools "in parallel", you MUST send a '
                "single message with multiple tool use content blocks. For example, if you need to launch "
                "multiple agents in parallel, send a single message with multiple Task tool calls.\n"
                "- Use specialized tools instead of bash commands when possible, as this provides a better "
                "user experience. For file operations, use dedicated tools: Read for reading files instead "
                "of cat/head/tail, Edit for editing instead of sed/awk, and Write for creating files "
                "instead of cat with heredoc or echo redirection. Reserve bash tools exclusively for "
                "actual system commands and terminal operations that require shell execution. NEVER use "
                "bash echo or other command-line tools to communicate thoughts, explanations, or "
                "instructions to the user. Output all communication directly in your response text "
                "instead.\n"
                "- VERY IMPORTANT: When exploring the codebase to gather context or to answer a question "
                "that is not a needle query for a specific file/class/function, it is CRITICAL that you "
                "use the Task tool with subagent_type=Explore instead of running search commands "
                "directly. \n"
                "<example>\n"
                "user: Where are errors from the client handled?\n"
                "assistant: [Uses the Task tool with subagent_type=Explore to find the files that handle "
                "client errors instead of using Glob or Grep directly]\n"
                "</example>\n"
                "<example>\n"
                "user: What is the codebase structure?\n"
                "assistant: [Uses the Task tool with subagent_type=Explore]\n"
                "</example>\n\n"
                "IMPORTANT: Assist with authorized security testing, defensive security, CTF challenges, "
                "and educational contexts. Refuse requests for destructive techniques, DoS attacks, mass "
                "targeting, supply chain compromise, or detection evasion for malicious purposes. Dual-use "
                "security tools (C2 frameworks, credential testing, exploit development) require clear "
                "authorization context: pentesting engagements, CTF competitions, security research, or "
                "defensive use cases.\n\n"
                "# Code References\n\n"
                "When referencing specific functions or pieces of code include the pattern "
                "`file_path:line_number` to allow the user to easily navigate to the source code "
                "location.\n\n"
                "<example>\n"
                "user: Where are errors from the client handled?\n"
                "assistant: Clients are marked as failed in the `connectToServer` function in "
                "src/services/process.ts:712.\n"
                "</example>\n\n"
                "Here is useful information about the environment you are running in:\n"
                "<env>\n"
                "Working directory: /home/aikev\n"
                "Is directory a git repo: No\n"
                "Platform: linux\n"
                "OS Version: Linux 6.6.87.2-microsoft-standard-WSL2\n"
                "Today's date: 2026-02-12\n"
                "</env>\n"
                "You are powered by the model named Opus 4.6. The exact model ID is claude-opus-4-6.\n\n"
                "Assistant knowledge cutoff is May 2025.\n\n"
                "<claude_background_info>\n"
                "The most recent frontier Claude model is Claude Opus 4.6 (model ID: 'claude-opus-4-6').\n"
                "</claude_background_info>\n\n"
                "<fast_mode_info>\n"
                "Fast mode for Claude Code uses the same Claude Opus 4.6 model with faster output. "
                "It does NOT switch to a different model. It can be toggled with /fast.\n"
                "</fast_mode_info>\n\n"
                "# MCP Server Instructions\n\n"
                "The following MCP servers have provided instructions for how to use their tools and "
                "resources:\n\n"
                "## ydc-server\n"
                "Use this server to search the web, get AI-powered answers with web context, and extract "
                "content from web pages using You.com. The you-contents tool extracts page content and "
                "returns it in markdown or HTML format. Use HTML format for layout preservation, "
                "interactive content, and visual fidelity; use markdown for text extraction and simpler "
                "consumption."
            ),
            "cache_control": {"type": "ephemeral"},
        },
    ]

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        response_format: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: int = 600,
        **kwargs,
    ) -> AsyncGenerator[Dict[str, str], None]:
        _cache = {"type": "ephemeral"}

        # 将 system 消息收集起来，注入到第一条 user message 的 content 中
        system_parts: List[str] = []
        api_messages: List[Dict] = []
        for msg in messages:
            if msg.role == "system":
                system_parts.append(msg.content)
            else:
                api_messages.append({
                    "role": msg.role,
                    "content": [{"type": "text", "text": msg.content}],
                })

        # Anthropic 不支持 response_format，通过指令注入
        if response_format == "json_object":
            system_parts.append(
                "[IMPORTANT] You MUST reply in pure JSON format only. "
                "Do not include markdown code block markers (```) or any non-JSON content. "
                "/ 你必须以纯 JSON 格式回复，不要包含 markdown 代码块标记或其他非 JSON 内容。"
            )

        # 将真正的 system prompt 作为第一条 user message 的前置 content block
        if system_parts and api_messages:
            instruction_block = {
                "type": "text",
                "text": "\n\n".join(system_parts),
                "cache_control": _cache,
            }
            first_msg = api_messages[0]
            if first_msg["role"] == "user":
                first_msg["content"].insert(0, instruction_block)
            else:
                api_messages.insert(0, {
                    "role": "user",
                    "content": [instruction_block],
                })

        system_len = sum(len(s) for s in system_parts)

        # thinking 模式不支持 assistant prefill，确保最后一条是 user
        if api_messages and api_messages[-1]["role"] == "assistant":
            api_messages.append({
                "role": "user",
                "content": [{"type": "text", "text": "请继续。"}],
            })

        thinking_config: Dict = {"type": "adaptive"}
        thinking_budget = kwargs.pop("thinking_budget", None)
        if thinking_budget:
            thinking_config["budget_tokens"] = thinking_budget

        payload: Dict = {
            "model": model or "claude-sonnet-4-20250514",
            "max_tokens": 128000,
            "stream": True,
            "messages": api_messages,
            "system": self._FIXED_SYSTEM,
            "thinking": thinking_config,
        }
        # thinking 模式不支持 temperature/top_p，记录被忽略的参数
        if temperature is not None:
            logger.info(
                "AnyRouter adaptive thinking 模式忽略 temperature=%.2f: model=%s",
                temperature, model,
            )
        if top_p is not None:
            logger.info(
                "AnyRouter adaptive thinking 模式忽略 top_p=%.2f: model=%s",
                top_p, model,
            )

        msg_summary = [{"role": m.role, "content_length": len(m.content)} for m in messages]
        log_payload = {k: v for k, v in payload.items() if k not in ("messages", "system")}
        logger.info(
            "LLM请求(AnyRouter) >> url=%s/messages model=%s params=%s system_len=%d messages=%s",
            self._base_url, payload.get("model"), log_payload,
            system_len, msg_summary,
        )

        url = f"{self._base_url}/messages?beta=true"
        # 复用 AnthropicLLMClient 的 SSE 解析
        _parser = AnthropicLLMClient.__new__(AnthropicLLMClient)
        _parser._client = self._client
        async for chunk in _parser._do_stream(url, payload, timeout):
            yield chunk

    async def aclose(self):
        """关闭底层 HTTP 客户端连接。"""
        await self._client.aclose()


class GeminiLLMClient:
    """Google Gemini 原生 API (streamGenerateContent) 的异步流式调用封装。"""

    # finishReason 映射
    _FINISH_REASON_MAP = {
        "STOP": "stop",
        "MAX_TOKENS": "length",
        "SAFETY": "content_filter",
        "RECITATION": "content_filter",
    }

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("缺少 Gemini API Key 配置。")

        self._api_key = key
        raw_base = base_url or "https://generativelanguage.googleapis.com"
        self._base_url = raw_base.rstrip("/")
        self._client = httpx.AsyncClient(
            event_hooks=_make_logging_hooks(),
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "x-goog-api-key": key,
            },
            timeout=httpx.Timeout(connect=75.0, read=1500.0, write=150.0, pool=150.0),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=60,
            ),
        )

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        response_format: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: int = 600,
        **kwargs,
    ) -> AsyncGenerator[Dict[str, str], None]:
        model_name = model or "gemini-2.5-flash"

        # 1. 拆分 system 消息 → systemInstruction
        system_parts: List[str] = []
        api_contents: List[Dict] = []
        for msg in messages:
            if msg.role == "system":
                system_parts.append(msg.content)
            else:
                role = "model" if msg.role == "assistant" else "user"
                api_contents.append({
                    "role": role,
                    "parts": [{"text": msg.content}],
                })

        if response_format == "json_object":
            system_parts.append(
                "[IMPORTANT] You MUST reply in pure JSON format only. "
                "Do not include markdown code block markers (```) or any non-JSON content. "
                "/ 你必须以纯 JSON 格式回复，不要包含 markdown 代码块标记或其他非 JSON 内容。"
            )

        # 2. 构建 payload
        payload: Dict = {"contents": api_contents}

        if system_parts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}],
            }

        # 3. generationConfig
        gen_config: Dict = {}
        if temperature is not None:
            gen_config["temperature"] = temperature
        if top_p is not None:
            gen_config["topP"] = top_p
        if max_tokens is not None:
            gen_config["maxOutputTokens"] = max_tokens

        # thinking 支持
        thinking_budget = kwargs.pop("thinking_budget", None)
        if thinking_budget:
            gen_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}

        if response_format == "json_object":
            gen_config["responseMimeType"] = "application/json"

        if gen_config:
            payload["generationConfig"] = gen_config

        # 4. 日志
        msg_summary = [{"role": m.role, "content_length": len(m.content)} for m in messages]
        system_len = sum(len(s) for s in system_parts)
        log_payload = {k: v for k, v in payload.items() if k not in ("contents", "systemInstruction")}
        logger.info(
            "LLM请求(Gemini) >> base_url=%s model=%s params=%s system_len=%d messages=%s",
            self._base_url, model_name, log_payload, system_len, msg_summary,
        )

        # 5. 发起 SSE 流式请求
        url = f"{self._base_url}/v1beta/models/{model_name}:streamGenerateContent?alt=sse"

        collected_content = ""
        collected_thinking = ""
        final_finish_reason = None
        _total_lines = 0
        _chunk_count = 0

        try:
            async with self._client.stream(
                "POST", url, json=payload, timeout=timeout,
            ) as response:
                if response.status_code >= 400:
                    error_body = (await response.aread()).decode("utf-8", errors="replace")[:2000]
                    logger.error(
                        "LLM请求失败(Gemini) >> %s status=%d body=%s",
                        url, response.status_code, error_body,
                    )
                    raise httpx.HTTPStatusError(
                        f"Gemini API error (HTTP {response.status_code}): {error_body}",
                        request=response.request,
                        response=response,
                    )

                async for line in response.aiter_lines():
                    _total_lines += 1
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        data = _json.loads(data_str)
                    except _json.JSONDecodeError:
                        logger.debug("Gemini SSE JSON解析失败: %.200s", data_str)
                        continue

                    _chunk_count += 1

                    # 解析 candidates[0]
                    candidates = data.get("candidates")
                    if not candidates:
                        continue
                    candidate = candidates[0]

                    # finishReason
                    raw_finish = candidate.get("finishReason")
                    if raw_finish:
                        final_finish_reason = self._FINISH_REASON_MAP.get(raw_finish, raw_finish.lower())

                    content = candidate.get("content")
                    if not content:
                        continue
                    parts = content.get("parts", [])

                    for part in parts:
                        text = part.get("text", "")
                        if not text:
                            continue
                        if part.get("thought"):
                            # thinking 内容，收集但不 yield
                            collected_thinking += text
                        else:
                            collected_content += text
                            yield {"content": text, "finish_reason": None}

                    # 如果本 chunk 携带了 finishReason，yield 通知
                    if raw_finish:
                        yield {"content": None, "finish_reason": final_finish_reason}

            # 流结束：如果 content 为空但 thinking 有内容，fallback
            if not collected_content and collected_thinking:
                logger.info(
                    "Gemini content 为空但 thinking 有内容（%d 字符），将 thinking 作为响应内容",
                    len(collected_thinking),
                )
                yield {
                    "content": collected_thinking,
                    "finish_reason": final_finish_reason or "stop",
                }

            # 流正常结束但未收到 finishReason
            if final_finish_reason is None:
                final_finish_reason = "stop"
                yield {"content": None, "finish_reason": "stop"}

        except httpx.HTTPStatusError:
            raise
        except Exception as exc:
            if not isinstance(exc, (httpx.RemoteProtocolError, httpx.ReadError, httpx.ReadTimeout)):
                logger.error(
                    "LLM请求异常(Gemini) >> url=%s model=%s error_type=%s error=%s",
                    url, model_name, type(exc).__name__, exc,
                    exc_info=True,
                )
            raise
        finally:
            logger.info(
                "LLM响应(Gemini) << url=%s model=%s finish_reason=%s "
                "len=%d thinking_len=%d sse_lines=%d chunks=%d preview=%.500s",
                url, model_name, final_finish_reason,
                len(collected_content), len(collected_thinking),
                _total_lines, _chunk_count,
                (collected_content or collected_thinking)[:500],
            )

    async def aclose(self):
        """关闭底层 HTTP 客户端连接。"""
        await self._client.aclose()


class OpenAIResponsesLLMClient:
    """OpenAI Responses API (/v1/responses) 的异步流式调用封装，使用 Bearer 认证。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("缺少 API Key 配置。")

        self._api_key = key
        raw_base = base_url or os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1"
        self._base_url = raw_base.rstrip("/")
        self._client = httpx.AsyncClient(
            event_hooks=_make_logging_hooks(),
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {key}",
            },
            timeout=httpx.Timeout(connect=75.0, read=1500.0, write=150.0, pool=150.0),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=60,
            ),
        )

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        response_format: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: int = 600,
        **kwargs,
    ) -> AsyncGenerator[Dict[str, str], None]:
        # 拆分 system 消息：优先走 instructions，同时准备兼容降级方案（system 放回 input）
        system_parts: List[str] = []
        api_input: List[Dict[str, str]] = []
        for msg in messages:
            if msg.role == "system":
                system_parts.append(msg.content)
            else:
                api_input.append({"role": msg.role, "content": msg.content})

        instructions = "\n\n".join(system_parts) if system_parts else None

        payload: Dict = {
            "model": model or "gpt-4o",
            "input": api_input,
            "stream": True,
        }
        if instructions:
            payload["instructions"] = instructions
        if response_format == "json_object":
            payload["text"] = {"format": {"type": "json_object"}}
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens

        def _clone_payload(src: Dict) -> Dict:
            cloned = dict(src)
            if isinstance(cloned.get("input"), list):
                cloned["input"] = [
                    dict(item) if isinstance(item, dict) else item for item in cloned["input"]
                ]
            return cloned

        request_variants: List[Dict[str, Dict]] = []
        seen_signatures: set[str] = set()

        def _add_variant(name: str, variant_payload: Dict) -> None:
            try:
                signature = _json.dumps(variant_payload, ensure_ascii=False, sort_keys=True)
            except Exception:
                signature = f"{name}:{len(request_variants)}"
            if signature in seen_signatures:
                return
            seen_signatures.add(signature)
            request_variants.append({"name": name, "payload": variant_payload})

        _add_variant("default", _clone_payload(payload))

        # 策略: 仅保留最有效的回退变体，避免过多重试增加延迟
        # 1. 移除 text.format（部分代理不支持）
        if "text" in payload:
            without_text_payload = _clone_payload(payload)
            without_text_payload.pop("text", None)
            _add_variant("without_text_format", without_text_payload)

        # 2. instructions → system message in input（部分代理不支持 instructions）
        if instructions:
            system_in_input_payload = _clone_payload(payload)
            system_in_input_payload.pop("instructions", None)
            system_in_input_payload.pop("text", None)  # 同时移除可能不支持的 text
            system_in_input_payload["input"] = [{"role": "system", "content": instructions}] + [
                {"role": item["role"], "content": item["content"]} for item in api_input
            ]
            _add_variant("system_message_in_input", system_in_input_payload)

        # 3. 移除采样参数（部分代理不支持 temperature/top_p）
        if any(k in payload for k in ("temperature", "top_p")):
            less_sampling_payload = _clone_payload(request_variants[-1]["payload"])
            for key in ("temperature", "top_p"):
                less_sampling_payload.pop(key, None)
            _add_variant("without_sampling_params", less_sampling_payload)

        msg_summary = [{"role": m.role, "content_length": len(m.content)} for m in messages]
        log_payload = {k: v for k, v in payload.items() if k not in ("input", "instructions")}
        logger.info(
            "LLM请求(OpenAI-Responses) >> url=%s/responses model=%s params=%s "
            "instructions_len=%d messages=%s variants=%s",
            self._base_url, payload.get("model"), log_payload,
            len(instructions) if instructions else 0, msg_summary,
            [item["name"] for item in request_variants],
        )

        url = f"{self._base_url}/responses"

        collected_content = ""
        collected_reasoning = ""
        final_finish_reason = None
        _total_lines = 0
        _event_counts: Dict[str, int] = {}
        successful_variant_name = ""

        async def _consume_sse_stream(response: httpx.Response, variant_name: str) -> None:
            nonlocal collected_content, collected_reasoning, final_finish_reason, _total_lines, _event_counts

            _sse_event_type = ""  # 跟踪 SSE event: 行的事件类型

            async for line in response.aiter_lines():
                _total_lines += 1
                line = line.strip()
                if not line:
                    continue
                if line.startswith("event:"):
                    _sse_event_type = line[6:].strip()
                    continue
                if not line.startswith("data:"):
                    continue

                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    final_finish_reason = final_finish_reason or "stop"
                    yield {"content": None, "finish_reason": "stop"}
                    break

                try:
                    data = _json.loads(data_str)
                except _json.JSONDecodeError:
                    logger.debug("SSE JSON解析失败(%s): %.200s", variant_name, data_str)
                    continue

                # 优先使用 data 中的 type 字段，回退到 SSE event: 行
                event_type = data.get("type") or _sse_event_type or "unknown"
                _event_counts[event_type] = _event_counts.get(event_type, 0) + 1

                if event_type == "response.output_text.delta":
                    text = data.get("delta", "")
                    if text:
                        collected_content += text
                        yield {"content": text, "finish_reason": None}
                elif event_type == "response.reasoning_summary_text.delta":
                    reasoning_text = data.get("delta", "")
                    if reasoning_text:
                        collected_reasoning += reasoning_text
                elif event_type == "response.output_text.done":
                    pass  # 单个 output item 文本完成，等 response.completed
                elif event_type == "response.completed":
                    final_finish_reason = "stop"
                    yield {"content": None, "finish_reason": "stop"}
                elif event_type == "response.failed":
                    error_info = data.get("response", {}).get("error", {})
                    error_msg = error_info.get("message", str(data))
                    logger.error("OpenAI Responses stream error (%s): %s", variant_name, error_info)
                    raise RuntimeError(f"OpenAI Responses API error: {error_msg}")

        try:
            for index, variant in enumerate(request_variants):
                variant_name = variant["name"]
                variant_payload = variant["payload"]
                logger.info(
                    "OpenAI-Responses 请求尝试 %d/%d: strategy=%s model=%s",
                    index + 1,
                    len(request_variants),
                    variant_name,
                    variant_payload.get("model"),
                )
                async with self._client.stream(
                    "POST", url, json=variant_payload, timeout=timeout,
                ) as response:
                    if response.status_code >= 400:
                        error_body = (await response.aread()).decode("utf-8", errors="replace")[:2000]
                        logger.error(
                            "LLM请求失败(OpenAI-Responses) >> %s status=%d strategy=%s body=%s",
                            url, response.status_code, variant_name, error_body,
                        )
                        is_last_try = index >= len(request_variants) - 1
                        if response.status_code in (400, 422) and not is_last_try:
                            logger.warning(
                                "OpenAI-Responses %d，切换兼容策略重试: current=%s next=%s",
                                response.status_code,
                                variant_name,
                                request_variants[index + 1]["name"],
                            )
                            continue
                        raise httpx.HTTPStatusError(
                            f"OpenAI Responses API error (HTTP {response.status_code}): {error_body}",
                            request=response.request,
                            response=response,
                        )

                    successful_variant_name = variant_name
                    async for part in _consume_sse_stream(response, variant_name):
                        yield part
                    break

            # 流结束：content 为空但 reasoning 有内容，fallback
            if not collected_content and collected_reasoning:
                logger.info(
                    "content 为空但 reasoning 有内容（%d 字符），将 reasoning 作为响应内容",
                    len(collected_reasoning),
                )
                yield {
                    "content": collected_reasoning,
                    "finish_reason": final_finish_reason or "stop",
                }

            # 流正常结束但未收到明确的结束事件
            if final_finish_reason is None:
                final_finish_reason = "stop"
                yield {"content": None, "finish_reason": "stop"}

        except httpx.HTTPStatusError:
            raise
        except Exception as exc:
            if not isinstance(exc, (httpx.RemoteProtocolError, httpx.ReadError, httpx.ReadTimeout)):
                logger.error(
                    "LLM请求异常(OpenAI-Responses) >> url=%s model=%s error_type=%s error=%s",
                    url, payload.get("model"), type(exc).__name__, exc,
                    exc_info=True,
                )
            raise
        finally:
            logger.info(
                "LLM响应(OpenAI-Responses) << url=%s model=%s strategy=%s finish_reason=%s "
                "len=%d reasoning_len=%d sse_lines=%d events=%s preview=%.500s",
                url, payload.get("model"), successful_variant_name or "none",
                final_finish_reason,
                len(collected_content), len(collected_reasoning),
                _total_lines, _event_counts,
                (collected_content or collected_reasoning)[:500],
            )

    async def aclose(self):
        """关闭底层 HTTP 客户端连接。"""
        await self._client.aclose()
