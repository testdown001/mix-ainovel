# AIMETA P=LLM服务_大模型调用封装|R=API调用_流式生成|NR=不含业务逻辑|E=LLMService|X=internal|A=服务类|D=openai,httpx|S=net|RD=./README.ai
import asyncio
import base64
import binascii
import hashlib
import inspect
import json
import logging
import os
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type, TypeVar

import httpx
from cachetools import LRUCache
from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

from ..utils.json_utils import remove_think_tags, repair_json, unwrap_markdown_json
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, InternalServerError, PermissionDeniedError, AuthenticationError, NotFoundError, BadRequestError

from ..core.config import settings
from ..db.session import AsyncSessionLocal
from ..repositories.system_config_repository import SystemConfigRepository
from ..repositories.user_repository import UserRepository
from ..services.admin_setting_service import AdminSettingService
from ..services.prompt_service import PromptService
from ..services.usage_service import UsageService
from ..services.api_usage_recorder import record_usage, estimate_tokens, record_call_log
from ..utils.llm_tool import ChatMessage, LLMClient, AnthropicLLMClient, AnyRouterLLMClient, GeminiLLMClient, OpenAIResponsesLLMClient, _build_http_client

logger = logging.getLogger(__name__)

_StructuredT = TypeVar("_StructuredT", bound=BaseModel)


class StructuredOutputError(ValueError):
    """LLM 结构化输出经修复与重试后仍无法通过 Pydantic schema 校验时抛出。"""

    def __init__(self, schema_name: str, raw: str, last_error: Exception):
        self.schema_name = schema_name
        self.raw = raw
        self.last_error = last_error
        super().__init__(
            f"结构化输出校验失败 (schema={schema_name}): {last_error}"
        )


class LLMResponseTruncated(Exception):
    """LLM 输出因 finish_reason=length 被截断（仅 fail_on_truncation=True 时抛出）。

    非通道故障，不触发兜底通道重试；partial_text 保留半截内容供调用方兜底。
    """

    def __init__(self, partial_text: str):
        self.partial_text = partial_text
        super().__init__(
            f"LLM 输出被截断 (finish_reason=length, 已收 {len(partial_text)} 字符)"
        )


try:  # pragma: no cover - 运行环境未安装时兼容
    from ollama import AsyncClient as OllamaAsyncClient
except ImportError:  # pragma: no cover - Ollama 为可选依赖
    OllamaAsyncClient = None


_CONFIG_VALUE_CACHE: Dict[str, tuple] = {}
_CONFIG_VALUE_TTL = 60.0


def invalidate_llm_config_cache() -> None:
    """清空 LLM 配置值缓存，使配置变更即时生效（可选；默认依赖 TTL 自动过期）。"""
    _CONFIG_VALUE_CACHE.clear()


def channel_explicitly_configured(*channel_values: Optional[str]) -> bool:
    """可选通道（润色/搜索/评分）是否被显式配置：四个通道键(api_key/base_url/model/api_format)
    任一非空即算启用——api_key 允许留空以继承 llm.*，只填 model 也是一种合法配置。

    搜索/评分未显式配置时运行时**不会**回退默认通道，而是 503 / 静默跳过，所以后台
    「测试通道」必须用同一判据。曾经不一致：test_channel 只看 api_key，一空就拿默认
    通道的 key 去测，于是一条实际禁用的评分通道在后台显示「✅ 可用」，管理员看到全绿，
    用户那边这个能力压根不存在。    判据只此一处，改这里即三处资源解析同时生效。
    """
    return any(v for v in channel_values)


# 通道未启用时的后果说明——只说「未配置」没用，管理员需要知道少了什么能力
_UNCONFIGURED_CHANNEL_DETAIL = {
    "default": "未配置 API Key，任何生成请求都会直接失败",
    "fallback": "未配置兜底通道，主通道终局失败时无处可退",
    "polish": "未配置 API Key（默认通道也没有），润色会失败",
    "search": "未配置搜索通道（llm_search.*），灵感模式「跨域找料」静默跳过、显式搜索接口 503",
    "grader": "未配置评分通道（llm_grader.*），证据打分静默跳过（不影响生成成败）",
}


class LLMService:
    """封装与大模型交互的所有逻辑，包括配额控制与配置选择。"""

    # 进程级 LLM 客户端缓存（LRU 限制大小，避免无限增长）
    _CLIENT_CACHE: LRUCache = LRUCache(maxsize=32)

    def __init__(self, session):
        self.session = session
        self.system_config_repo = SystemConfigRepository(session)
        self.user_repo = UserRepository(session)
        self.admin_setting_service = AdminSettingService(session)
        self.usage_service = UsageService(session)
        self._embedding_dimensions: Dict[str, int] = {}
        self._db_access_lock = asyncio.Lock()

    @classmethod
    def _get_or_create_client(cls, api_format: str, api_key: str, base_url: Optional[str]) -> Any:
        """从缓存获取或创建 LLM 客户端，避免重复 TLS 握手。"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        cache_key = f"{api_format}|{base_url or ''}|{key_hash}"
        if cache_key in cls._CLIENT_CACHE:
            return cls._CLIENT_CACHE[cache_key]

        if api_format == "anyrouter":
            client = AnyRouterLLMClient(api_key=api_key, base_url=base_url)
        elif api_format == "anthropic":
            client = AnthropicLLMClient(api_key=api_key, base_url=base_url)
        elif api_format == "gemini":
            client = GeminiLLMClient(api_key=api_key, base_url=base_url)
        elif api_format == "openai-responses":
            client = OpenAIResponsesLLMClient(api_key=api_key, base_url=base_url)
        else:
            client = LLMClient(api_key=api_key, base_url=base_url)

        cls._CLIENT_CACHE[cache_key] = client
        return client

    async def get_llm_response(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 1500.0,
        response_format: Optional[str] = "json_object",
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        max_retries: int = 2,
        thinking_budget: Optional[int] = None,
        disable_thinking: bool = False,
        on_chunk: Optional[Callable[[str], Awaitable[None] | None]] = None,
        reasoning_effort: Optional[str] = None,
        config_override: Optional[Dict[str, Optional[str]]] = None,
        fail_on_truncation: bool = False,
    ) -> str:
        # reasoning_effort：按调用覆盖通道默认推理档（minimal/low/medium/high）。
        # 仅对 o系列/gpt-5 的 openai 格式生效，其它模型/格式自动忽略；不传则沿用通道配置。
        # config_override：按调用指定整套通道(模型目录解析出的真实大模型)，覆盖默认 llm.*；
        # 仅作用于主调用，兜底通道仍用 llm_fallback.*。不传则用默认通道。
        # fail_on_truncation：finish_reason=length 时抛 LLMResponseTruncated 而非静默返回半截内容，
        # 供正文生成等不允许截断落库的调用方显式处理。默认 False 保持旧行为。
        messages = [{"role": "system", "content": system_prompt}, *conversation_history]

        # 兜底通道仅在尚未向调用方流出任何增量时才能重试，否则会产生重复输出
        emitted_any_chunk = False
        wrapped_on_chunk = on_chunk
        if on_chunk is not None:
            def _marking_on_chunk(chunk: str):
                nonlocal emitted_any_chunk
                emitted_any_chunk = True
                return on_chunk(chunk)

            wrapped_on_chunk = _marking_on_chunk

        try:
            return await self._stream_and_collect(
                messages,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout,
                response_format=response_format,
                max_tokens=max_tokens,
                top_p=top_p,
                max_retries=max_retries,
                thinking_budget=thinking_budget,
                disable_thinking=disable_thinking,
                on_chunk=wrapped_on_chunk,
                reasoning_effort_override=reasoning_effort,
                config_override=config_override,
                fail_on_truncation=fail_on_truncation,
            )
        except Exception as exc:
            # 429 = 用户每日请求上限（配额问题而非通道故障），不兜底
            if isinstance(exc, HTTPException) and exc.status_code == 429:
                raise
            # 截断 = max_tokens 不足（非通道故障），换兜底通道重试无意义，由调用方处理
            if isinstance(exc, LLMResponseTruncated):
                raise
            if emitted_any_chunk:
                raise
            fallback_config = await self._resolve_fallback_llm_config()
            if not fallback_config:
                raise
            logger.warning(
                "默认 LLM 通道失败，启用兜底通道重试: error=%s fallback_model=%s",
                str(exc)[:200],
                fallback_config.get("model"),
            )
            return await self._stream_and_collect(
                messages,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout,
                config_override=fallback_config,
                response_format=response_format,
                max_tokens=max_tokens,
                top_p=top_p,
                max_retries=max_retries,
                thinking_budget=thinking_budget,
                disable_thinking=disable_thinking,
                on_chunk=wrapped_on_chunk,
                reasoning_effort_override=reasoning_effort,
                api_type="fallback",
                fail_on_truncation=fail_on_truncation,
            )

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 1500.0,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
        top_p: Optional[float] = None,
        fail_on_truncation: bool = False,
    ) -> str:
        """兼容旧版接口的文本生成入口，统一走 get_llm_response。"""
        return await self.get_llm_response(
            system_prompt=system_prompt or "你是一位专业写作助手。",
            conversation_history=[{"role": "user", "content": prompt}],
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
            max_tokens=max_tokens,
            top_p=top_p,
            fail_on_truncation=fail_on_truncation,
        )

    async def generate_image(
        self,
        prompt: str,
        *,
        user_id: Optional[int] = None,
        size: str = "1024x1536",
        quality: str = "medium",
        timeout: float = 300.0,
    ) -> tuple[bytes, str]:
        """通过 OpenAI Images API 生成图片，统一复用系统通道与用户限额。

        可选的 image.api_key / image.base_url / image.model 会覆盖默认 llm.*；未配置时
        只把模型切到 gpt-image-2。返回 PNG/JPEG 原始字节和实际模型名，落盘由业务层负责。
        """
        config = await self._resolve_image_config(user_id)
        model = config["model"] or "gpt-image-2"
        base_url = (config["base_url"] or "https://api.openai.com/v1").rstrip("/")
        endpoint = f"{base_url}/images/generations"
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {config['api_key']}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
                data = body.get("data") if isinstance(body, dict) else None
                item = data[0] if isinstance(data, list) and data else None
                if not isinstance(item, dict):
                    raise ValueError("图片服务未返回有效数据")
                encoded = item.get("b64_json")
                if encoded:
                    image_bytes = base64.b64decode(encoded, validate=True)
                elif item.get("url"):
                    image_response = await client.get(item["url"])
                    image_response.raise_for_status()
                    image_bytes = image_response.content
                else:
                    raise ValueError("图片服务未返回图片内容")
        except httpx.HTTPStatusError as exc:
            detail = "图片生成服务请求失败"
            try:
                error_body = exc.response.json()
                detail = (
                    error_body.get("error", {}).get("message")
                    or error_body.get("message")
                    or detail
                )
            except Exception:
                pass
            logger.warning("Images API 请求失败: status=%s model=%s", exc.response.status_code, model)
            raise HTTPException(status_code=503, detail=str(detail)[:400]) from exc
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.warning("Images API 网络异常: model=%s error=%s", model, exc)
            raise HTTPException(status_code=504, detail="图片生成超时，请稍后重试") from exc
        except (ValueError, binascii.Error, json.JSONDecodeError) as exc:
            logger.warning("Images API 响应异常: model=%s error=%s", model, exc)
            raise HTTPException(status_code=502, detail="图片服务返回了无法识别的内容") from exc

        if len(image_bytes) < 1024 or len(image_bytes) > 30 * 1024 * 1024:
            raise HTTPException(status_code=502, detail="图片服务返回的文件大小异常")
        return image_bytes, model

    async def _resolve_image_config(self, user_id: Optional[int]) -> Dict[str, Optional[str]]:
        """解析图片专用通道；读取默认通道时同时执行既有用户日限额检查。"""
        default = await self._resolve_llm_config(user_id)
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                api_key = await self._get_config_value_for_session(session, "image.api_key")
                base_url = await self._get_config_value_for_session(session, "image.base_url")
                model = await self._get_config_value_for_session(session, "image.model")
        default_base_url = default.get("base_url") or ""
        if not api_key and not base_url and "api.openai.com" not in default_base_url.lower():
            raise HTTPException(
                status_code=503,
                detail=(
                    "图片生成通道尚未配置。当前文本通道不支持 Images API，请设置 "
                    "IMAGE_API_KEY 和 IMAGE_BASE_URL（OpenAI 官方地址为 https://api.openai.com/v1）。"
                ),
            )
        return {
            "api_key": api_key or default.get("api_key"),
            "base_url": self._normalize_base_url(base_url or default.get("base_url")),
            "model": model or "gpt-image-2",
        }

    async def generate_structured(
        self,
        *,
        prompt: str,
        schema: Type[_StructuredT],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        user_id: Optional[int] = None,
        max_tokens: Optional[int] = None,
        max_validation_retries: int = 1,
        default: Optional[_StructuredT] = None,
        responder: Optional[Callable[[str, str], Awaitable[str]]] = None,
    ) -> _StructuredT:
        """Prompt → 经校验的 Pydantic 模型（借鉴 Pydantic AI 的结构化输出范式）。

        在现有 generate(response_format=json_object) + json_utils 修复之上，补齐
        “schema 校验失败 → 把校验错误回喂给模型，要求修正后重答”这一层，
        消除全仓散落的 `repair_json → loads → dict.get(默认值)` 静默腐烂问题。

        - schema: 期望输出的 Pydantic 模型类。其 JSON Schema 会注入 system prompt 引导模型。
        - max_validation_retries: 校验失败后的纠正性重问次数（默认 1，共最多 2 次调用）。
        - default: 若全部尝试仍失败：default 非 None 时返回它（软失败，对齐旧的"取默认值"行为），
          否则抛 StructuredOutputError（硬失败，便于上层显式处理）。
        - responder: 可选的"出口"回调 async (prompt, system_prompt) -> str，用于适配非默认
          LLM 通道（如证据评分专用的 get_grader_llm_response）。默认走 self.generate。
        """
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        base_system = (
            (system_prompt or "你是一个严格输出 JSON 的助手。")
            + "\n\n你必须只输出符合以下 JSON Schema 的合法 JSON 对象，"
            + "不要输出任何解释、Markdown 代码块或多余文字：\n"
            + schema_json
        )

        async def _default_responder(p: str, sys: str) -> str:
            return await self.generate(
                prompt=p,
                system_prompt=sys,
                temperature=temperature,
                user_id=user_id,
                response_format="json_object",
                max_tokens=max_tokens,
            )

        respond = responder or _default_responder

        current_prompt = prompt
        raw = ""
        last_error: Optional[Exception] = None

        for attempt in range(max_validation_retries + 1):
            raw = await respond(current_prompt, base_system)
            cleaned = repair_json(unwrap_markdown_json(remove_think_tags(raw or "")))
            try:
                return schema.model_validate_json(cleaned)
            except (ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "generate_structured 校验失败 (schema=%s, attempt=%d/%d): %s",
                    schema.__name__, attempt + 1, max_validation_retries + 1, exc,
                )
                # 把校验错误与上次原始输出回喂，引导模型自我修正
                current_prompt = (
                    f"{prompt}\n\n———\n你上一次的输出未通过 JSON Schema 校验。\n"
                    f"校验错误：\n{exc}\n\n上次输出（截断）：\n{(raw or '')[:1200]}\n\n"
                    f"请严格按 schema 重新输出**合法且完整**的 JSON 对象。"
                )

        if default is not None:
            logger.warning(
                "generate_structured 最终失败，返回 default (schema=%s)", schema.__name__
            )
            return default
        raise StructuredOutputError(schema.__name__, raw, last_error or ValueError("unknown"))

    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[dict],
        *,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 1500.0,
        max_tokens: Optional[int] = None,
        tool_choice: str = "auto",
    ) -> Dict[str, Any]:
        """Non-streaming LLM call with OpenAI function-calling tool support.

        Returns a dict with:
          - content: Optional text content
          - tool_calls: List of tool call dicts (id, function.name, function.arguments)
          - finish_reason: The finish reason from the API
        """
        config = await self._resolve_llm_config(user_id)
        config["base_url"] = self._normalize_base_url(config.get("base_url"))
        model_name = config.get("model") or ""
        api_format_raw = config.get("api_format")
        api_format = self._resolve_api_format(api_format_raw, config.get("base_url"), model_name)

        if api_format in ("anthropic", "gemini", "openai-responses"):
            raise ValueError(
                f"chat_with_tools 不支持 api_format='{api_format}'。"
                f"智能体循环（Agentic Loop）需要 OpenAI 兼容的 API 端点。"
                f"请将 LLM 配置切换为 openai 格式（如 OpenRouter、OpenAI 官方或兼容代理），"
                f"或将 api_format 设置为 'openai'。"
            )

        api_key = config["api_key"]
        base_url = config.get("base_url")

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=_build_http_client(),
        )

        api_messages = []
        for msg in messages:
            entry: Dict[str, Any] = {"role": msg["role"]}
            if msg.get("content") is not None:
                entry["content"] = msg["content"]
            if msg.get("tool_calls"):
                entry["tool_calls"] = msg["tool_calls"]
            if msg.get("tool_call_id"):
                entry["tool_call_id"] = msg["tool_call_id"]
            if msg.get("name"):
                entry["name"] = msg["name"]
            api_messages.append(entry)

        _is_claude_thinking = self._is_claude_thinking_model(model_name)
        effective_temperature = temperature
        if _is_claude_thinking and temperature != 1.0:
            logger.info("chat_with_tools: 跳过 temperature=%.2f (thinking model %s)", temperature, model_name)
            effective_temperature = 1.0
        elif self._is_openai_reasoning_model(model_name) and temperature != 1.0:
            logger.info("chat_with_tools: 跳过 temperature=%.2f (OpenAI 推理模型 %s)", temperature, model_name)
            effective_temperature = 1.0

        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": api_messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "temperature": effective_temperature,
            "timeout": int(timeout),
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        logger.info(
            "LLM tool-use request: model=%s tools=%d messages=%d format=%s",
            model_name, len(tools), len(api_messages), api_format,
        )

        try:
            response = await client.chat.completions.create(**payload)
        except Exception as exc:
            logger.error("LLM tool-use request failed: %s", exc, exc_info=True)
            raise

        choice = response.choices[0] if response.choices else None
        if not choice:
            return {"content": None, "tool_calls": [], "finish_reason": "error"}

        message = choice.message
        tool_calls_raw = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls_raw.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                })

        return {
            "content": message.content,
            "tool_calls": tool_calls_raw,
            "finish_reason": choice.finish_reason,
        }

    async def get_summary(
        self,
        chapter_content: str,
        *,
        temperature: float = 0.2,
        user_id: Optional[int] = None,
        timeout: float = 900.0,
        system_prompt: Optional[str] = None,
        config_override: Optional[Dict[str, Optional[str]]] = None,
    ) -> str:
        if not system_prompt:
            prompt_service = PromptService(self.session)
            system_prompt = await prompt_service.get_prompt("extraction")
        if not system_prompt:
            logger.error("未配置名为 'extraction' 的摘要提示词，无法生成章节摘要")
            raise HTTPException(status_code=500, detail="未配置摘要提示词，请联系管理员配置 'extraction' 提示词")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chapter_content},
        ]
        return await self._stream_and_collect(messages, temperature=temperature, user_id=user_id, timeout=timeout, config_override=config_override)

    # 网络瞬断类异常，可安全重试
    _RETRYABLE_ERRORS = (
        httpx.RemoteProtocolError,
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadError,
        httpx.ReadTimeout,
        APIConnectionError,
        APITimeoutError,
    )
    # 进程级缓存：记录不支持 response_format 的 provider 组合（base_url|model）
    _UNSUPPORTED_RESPONSE_FORMAT_TARGETS: set[str] = set()
    # 进程级缓存：记录不支持 stream_options.include_usage 的 provider 组合（避免每次先失败再重试）
    _UNSUPPORTED_STREAM_OPTIONS_TARGETS: set[str] = set()
    # 进程级缓存：记录不接受 reasoning_effort 的 provider 组合（普通非推理模型会因未知参数 400）
    _UNSUPPORTED_REASONING_EFFORT_TARGETS: set[str] = set()
    # 辅助（结构化 JSON）调用的默认推理档。取 low 而非 minimal：low 被 o 系列与 gpt-5 同时接受，
    # minimal 只有 gpt-5 认，配错值的代价是一次 400 往返。管理员可在后台改成 minimal/off。
    _DEFAULT_AUX_REASONING_EFFORT = "low"
    _AUX_EFFORT_TTL_SEC = 60.0
    _aux_effort_cache: Optional[str] = None
    _aux_effort_expires_at: float = 0.0

    @staticmethod
    def _normalize_base_url(base_url: Optional[str]) -> Optional[str]:
        """规范化第三方 LLM 地址，自动补全缺失协议。"""
        if base_url is None:
            return None

        normalized = str(base_url).strip()
        if not normalized:
            return None

        # 兼容常见误填：把 https:/host 或 http:/host 修复为双斜杠
        if normalized.lower().startswith("https:/") and not normalized.lower().startswith("https://"):
            normalized = "https://" + normalized[len("https:/"):].lstrip("/")
        elif normalized.lower().startswith("http:/") and not normalized.lower().startswith("http://"):
            normalized = "http://" + normalized[len("http:/"):].lstrip("/")

        lower = normalized.lower()
        has_http_scheme = lower.startswith("http://") or lower.startswith("https://")
        has_any_scheme = "://" in normalized
        if not has_http_scheme and not has_any_scheme:
            host = normalized.split("/", 1)[0].lower()
            is_local = (
                host.startswith("localhost")
                or host.startswith("127.")
                or host.startswith("0.0.0.0")
                or host.startswith("[::1]")
                or host.startswith("::1")
                or host.startswith("192.168.")
                or host.startswith("10.")
                or host.startswith("172.")
            )
            scheme = "http" if is_local else "https"
            normalized = f"{scheme}://{normalized}"

        return normalized.rstrip("/")

    @staticmethod
    def _is_claude_model(model_name: Optional[str]) -> bool:
        """判断模型名称是否为 Claude 系列。"""
        return bool(model_name and model_name.lower().startswith("claude"))

    @staticmethod
    def _extract_provider_error_detail(exc: Exception) -> str:
        """尽可能提取服务商返回的可读错误信息。"""
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    error_data = payload.get("error")
                    if isinstance(error_data, dict):
                        message = error_data.get("message_zh") or error_data.get("message")
                        if isinstance(message, str) and message.strip():
                            return message
                    message = payload.get("message")
                    if isinstance(message, str) and message.strip():
                        return message
            except Exception:
                pass
            try:
                text = response.text
                if isinstance(text, str) and text.strip():
                    return text[:2000]
            except Exception:
                pass
        return str(exc)

    @classmethod
    def _is_response_format_unsupported_error(cls, exc: Exception) -> bool:
        """判断是否为服务商不支持 response_format 的请求错误。"""
        detail = (cls._extract_provider_error_detail(exc) or "").lower()
        # 场景0: 代理/网关吞掉了上游错误详情，返回空消息 400
        # 此时最可能的原因就是 json_object 格式不兼容，重试无害
        if not detail.strip():
            return True
        # 场景1: 消息中不含 "json" 但请求了 json_object 格式
        if "json_object" in detail and "must contain" in detail:
            return True
        if "response_format" not in detail and "response format" not in detail:
            return False
        return any(
            marker in detail
            for marker in (
                "invalid",
                "unsupported",
                "not support",
                "illegal",
                "unknown",
                "不合法",
                "不支持",
                "无效",
            )
        )

    @staticmethod
    def _prefer_openai_responses_model(model_name: Optional[str]) -> bool:
        """判断模型是否更适合优先走 OpenAI Responses API。"""
        normalized = (model_name or "").strip().lower()
        return normalized.startswith("gpt-5")

    @staticmethod
    def _is_endpoint_not_supported_detail(detail: str) -> bool:
        """判断错误详情是否属于网关/上游的端点不兼容。"""
        lowered = (detail or "").strip().lower()
        if not lowered:
            return False
        return any(
            marker in lowered
            for marker in (
                "endpoint not supported",
                "codex channel",
                "convert_request_failed",
                "chat/completions",
                "responses endpoint",
                "unsupported endpoint",
            )
        )

    @staticmethod
    def _is_gemini_model(model_name: Optional[str]) -> bool:
        """判断模型名称是否为 Gemini 系列。"""
        return bool(model_name and model_name.lower().startswith("gemini"))

    @staticmethod
    def _is_claude_thinking_model(model_name: Optional[str]) -> bool:
        """Claude 思考模型（opus-4 / sonnet-4 / claude-3-7 等）。

        其 thinking 模式与 temperature/top_p/response_format 不兼容；当经 OpenAI/Anthropic
        代理调用时代理可能自动开启 thinking，故需在请求侧主动剔除这些参数。
        统一判定，避免在 _stream_and_collect 与 chat_with_tools 两处各维护一份关键词表导致漂移。
        """
        m = (model_name or "").lower()
        return any(kw in m for kw in ("claude-opus", "opus-4", "claude-3-7", "claude-4", "sonnet-4"))

    @staticmethod
    def _is_openai_reasoning_model(model_name: Optional[str]) -> bool:
        """OpenAI o 系列推理模型（o1 / o3 / o4，含 -mini/-preview）。

        这些模型经 chat/completions 调用时仅接受 temperature=1（其余值报 400），
        且不支持 top_p。需在请求侧主动剔除。容忍 "openai/o3-mini" 这类带 provider 前缀的命名。
        """
        m = (model_name or "").strip().lower().split("/")[-1]
        return bool(re.match(r"^o[1-9]([.\-]|$)", m))

    @classmethod
    def _is_temperature_unsupported_error(cls, exc: Exception) -> bool:
        """判断 400 错误是否为"该模型不支持 temperature/top_p"（推理模型常见）。"""
        detail = (cls._extract_provider_error_detail(exc) or "").lower()
        if not detail.strip():
            return False
        mentions_param = "temperature" in detail or "top_p" in detail or "top-p" in detail
        mentions_unsupported = any(
            marker in detail
            for marker in (
                "unsupported value",
                "does not support",
                "not support",
                "only the default",
                "unsupported parameter",
                "is not supported",
                "不支持",
                "无效",
            )
        )
        return mentions_param and mentions_unsupported

    @classmethod
    def _is_stream_options_unsupported_error(cls, exc: Exception) -> bool:
        """判断 400 是否为 provider 不支持 stream_options(.include_usage)。"""
        detail = (cls._extract_provider_error_detail(exc) or "").lower()
        return "stream_options" in detail or "stream options" in detail

    @classmethod
    def _is_reasoning_effort_unsupported_error(cls, exc: Exception) -> bool:
        """判断 400 是否因 reasoning_effort/reasoning 参数不被接受。"""
        return cls._detail_indicates_reasoning_unsupported(
            cls._extract_provider_error_detail(exc) or ""
        )

    @staticmethod
    def _detail_indicates_reasoning_unsupported(detail: str) -> bool:
        """错误详情是否明确指向推理参数不被接受（同时服务 SDK 异常与 httpx 响应体两条路径）。

        必须要求文本里明确提到该参数：不能像 response_format 那样把「空错误体」也算进来，
        否则任何被网关吞掉详情的 400 都会误判成推理参数问题，把真实故障掩盖成一次静默降级。
        """
        detail = (detail or "").lower()
        if "reasoning_effort" in detail or "reasoning effort" in detail:
            return True
        if "reasoning" not in detail:
            return False
        return any(
            marker in detail
            for marker in (
                "unsupported", "not supported", "not support", "unknown",
                "unrecognized", "invalid", "unexpected", "extra field",
            )
        )

    @classmethod
    def _is_max_completion_tokens_error(cls, exc: Exception) -> bool:
        """判断 400 是否要求改用 max_completion_tokens（OpenAI o 系列官方接口）。"""
        detail = (cls._extract_provider_error_detail(exc) or "").lower()
        return "max_completion_tokens" in detail

    def _resolve_api_format(self, api_format_setting: Optional[str], base_url: Optional[str], model_name: Optional[str]) -> str:
        """根据配置决定使用哪种 API 格式。

        返回值：
        - "openai"    → OpenAI 兼容格式 (/v1/chat/completions)
        - "anthropic" → 原生 Anthropic Messages API (/v1/messages, x-api-key 认证)
        - "anyrouter" → Claude Code 兼容代理 (/v1/messages?beta=true, Bearer 认证 + 固定 system)
        - "gemini"    → Google Gemini 原生 API (streamGenerateContent)
        - "openai-responses" → OpenAI Responses API (/v1/responses)
        """
        fmt = (api_format_setting or "auto").strip().lower()
        if fmt in ("openai", "anthropic", "anyrouter", "gemini", "openai-responses"):
            return fmt
        # auto: 按模型名称自动推断
        if self._is_claude_model(model_name):
            return "anthropic"
        if self._is_gemini_model(model_name):
            return "gemini"
        if self._prefer_openai_responses_model(model_name):
            return "openai-responses"
        return "openai"

    @classmethod
    def _build_stream_extra_kwargs(
        cls,
        api_format: str,
        *,
        thinking_budget: Optional[int],
        disable_thinking: bool,
        reasoning_effort: Optional[str] = None,
        model_name: Optional[str] = None,
        enable_usage: bool = False,
        use_max_completion_tokens: bool = False,
        reasoning_effort_supported: bool = True,
    ) -> Dict[str, Any]:
        """按 provider 能力构建可透传的附加参数。"""
        extra_kwargs: Dict[str, Any] = {}

        # 仅 Anthropic/AnyRouter/Gemini 支持 thinking_budget。
        if thinking_budget and api_format in {"anthropic", "anyrouter", "gemini"}:
            extra_kwargs["thinking_budget"] = thinking_budget

        # disable_thinking 当前仅 AnyRouter 客户端实现了显式关闭逻辑。
        if disable_thinking and api_format == "anyrouter":
            extra_kwargs["disable_thinking"] = True

        # reasoning_effort：OpenAI 兼容 / Responses 格式下一律尝试透传，不再按模型名判断。
        # 原先的门槛是「o 系列 or gpt-5」，用意是避免普通模型因未知参数 400；代价是
        # DeepSeek / Grok / GLM 这类同样默认深度思考的模型永远收不到推理档——后台把
        # llm.reasoning_effort 配成 minimal 也毫无作用，实测一次一致性检查为 2504 字的
        # JSON 判定烧掉 8257 个推理 token(≈49s)，且界面上完全看不出开关是失效的。
        # 改为「先试；被上游拒绝就按 base_url|model 记闩、去掉参数重试」，沿用
        # stream_options / response_format 既有的自愈范式：最坏每个上游组合每进程多一次往返。
        effort = (reasoning_effort or "").strip().lower()
        if (
            effort in {"low", "medium", "high", "minimal"}
            and api_format in {"openai", "openai-responses"}
            and reasoning_effort_supported
        ):
            extra_kwargs["reasoning_effort"] = effort

        # 真实 token 用量：请求 OpenAI 流附带 usage（含推理模型的 reasoning token）。
        if enable_usage and api_format == "openai":
            extra_kwargs["enable_usage"] = True

        # o 系列官方接口要求 max_completion_tokens 而非 max_tokens（反应式兜底触发）。
        if use_max_completion_tokens and api_format == "openai":
            extra_kwargs["use_max_completion_tokens"] = True

        return extra_kwargs

    async def _stream_and_collect(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        user_id: Optional[int],
        timeout: float,
        config_override: Optional[Dict[str, Optional[str]]] = None,
        response_format: Optional[str] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        max_retries: int = 2,
        thinking_budget: Optional[int] = None,
        disable_thinking: bool = False,
        on_chunk: Optional[Callable[[str], Awaitable[None] | None]] = None,
        reasoning_effort_override: Optional[str] = None,
        api_type: str = "default",
        fail_on_truncation: bool = False,
        _record_telemetry: bool = True,
    ) -> str:
        """薄包装：为每次真实 LLM 调用记录遥测（通道/模型/延迟/状态/错误），供后台
        「通道诊断」排查生成慢/报错/超时。记录 best-effort，绝不影响生成主流程。
        _record_telemetry=False 用于排除「测试通道」等合成调用，免污染真实流量统计。"""
        import time as _time

        _start = _time.monotonic()
        _meta: Dict[str, Any] = {}
        _status = "error"
        _err_type: Optional[str] = None
        _err_msg: Optional[str] = None
        _http_status: Optional[int] = None
        try:
            result = await self._stream_and_collect_impl(
                messages,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout,
                config_override=config_override,
                response_format=response_format,
                max_tokens=max_tokens,
                top_p=top_p,
                max_retries=max_retries,
                thinking_budget=thinking_budget,
                disable_thinking=disable_thinking,
                on_chunk=on_chunk,
                reasoning_effort_override=reasoning_effort_override,
                api_type=api_type,
                fail_on_truncation=fail_on_truncation,
                _call_meta=_meta,
            )
            _status = "success"
            return result
        except Exception as exc:
            _status, _http_status = self._classify_call_error(exc)
            _err_type = type(exc).__name__
            _err_msg = (str(exc) or "")[:500]
            raise
        finally:
            if _record_telemetry:
                try:
                    _latency = int((_time.monotonic() - _start) * 1000)
                    await self._record_call_log(
                        api_type=api_type,
                        model=_meta.get("model"),
                        host=_meta.get("host"),
                        status=_status,
                        latency_ms=_latency,
                        http_status=_http_status,
                        error_type=_err_type,
                        error_message=_err_msg,
                        prompt_tokens=_meta.get("prompt_tokens", 0),
                        completion_tokens=_meta.get("completion_tokens", 0),
                        user_id=user_id,
                    )
                except Exception:
                    pass

    async def _stream_and_collect_impl(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        user_id: Optional[int],
        timeout: float,
        config_override: Optional[Dict[str, Optional[str]]] = None,
        response_format: Optional[str] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        max_retries: int = 2,
        thinking_budget: Optional[int] = None,
        disable_thinking: bool = False,
        on_chunk: Optional[Callable[[str], Awaitable[None] | None]] = None,
        reasoning_effort_override: Optional[str] = None,
        api_type: str = "default",
        fail_on_truncation: bool = False,
        _call_meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        config = config_override or await self._resolve_llm_config(user_id)
        config["base_url"] = self._normalize_base_url(config.get("base_url"))
        chat_messages = [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]

        model_name = config.get("model") or ""
        api_format_setting = config.get("api_format")
        api_format = self._resolve_api_format(api_format_setting, config.get("base_url"), model_name)

        # Claude thinking 模型不兼容 temperature/top_p/response_format
        # 当通过 OpenAI/Anthropic 代理调用时，代理可能自动开启 thinking，
        # 此时传入 temperature!=1.0 会导致空响应或报错
        # 覆盖: opus-4 系列、sonnet-4 系列、claude-3-7-sonnet、claude-4 系列
        is_claude_thinking = self._is_claude_thinking_model(model_name)
        # OpenAI o 系列推理模型经 chat/completions 调用仅接受 temperature=1，且不支持 top_p
        is_openai_reasoning = api_format == "openai" and self._is_openai_reasoning_model(model_name)
        effective_temperature = temperature
        effective_top_p = top_p
        effective_response_format = response_format
        response_format_target = f"{(config.get('base_url') or '').rstrip('/')}|{model_name}"
        if (
            api_format == "openai"
            and effective_response_format is not None
            and response_format_target in self._UNSUPPORTED_RESPONSE_FORMAT_TARGETS
        ):
            logger.info(
                "已知该服务商组合不支持 response_format，直接跳过: base_url=%s model=%s response_format=%s",
                config.get("base_url"),
                model_name,
                effective_response_format,
            )
            effective_response_format = None
        if is_claude_thinking and api_format != "anyrouter":
            if temperature is not None and temperature != 1.0:
                logger.info(
                    "跳过 temperature=%.2f（Claude thinking 模型不兼容），model=%s format=%s",
                    temperature, model_name, api_format,
                )
                effective_temperature = None
            if top_p is not None:
                logger.info("跳过 top_p=%.2f（Claude thinking 模型不兼容），model=%s", top_p, model_name)
                effective_top_p = None
            if response_format is not None:
                logger.info("跳过 response_format=%s（Claude thinking 模型不兼容），model=%s", response_format, model_name)
                effective_response_format = None
        if is_openai_reasoning:
            if temperature is not None and temperature != 1.0:
                logger.info(
                    "跳过 temperature=%.2f（OpenAI o 系列推理模型仅支持默认值），model=%s",
                    temperature, model_name,
                )
                effective_temperature = None
            if top_p is not None:
                logger.info("跳过 top_p=%.2f（OpenAI o 系列推理模型不支持），model=%s", top_p, model_name)
                effective_top_p = None

        # Gemini 系列模型不支持 response_format，前置跳过避免首次 400 错误
        if "gemini" in model_name.lower() and effective_response_format is not None:
            logger.info(
                "跳过 response_format=%s（Gemini 模型不兼容），model=%s",
                effective_response_format, model_name,
            )
            effective_response_format = None

        # Gemini 系列模型输出上限较高，自动提升 max_tokens 下限
        _GEMINI_MIN_MAX_TOKENS = 65536
        if "gemini" in model_name.lower() and (max_tokens is None or max_tokens < _GEMINI_MIN_MAX_TOKENS):
            logger.info(
                "Gemini 模型检测到，max_tokens 从 %s 提升至 %d: model=%s",
                max_tokens, _GEMINI_MIN_MAX_TOKENS, model_name,
            )
            max_tokens = _GEMINI_MIN_MAX_TOKENS

        logger.info(
            "Streaming LLM response: base_url=%s model=%s user_id=%s messages=%d format=%s",
            config.get("base_url"),
            model_name,
            user_id,
            len(messages),
            api_format,
        )

        if _call_meta is not None:
            _call_meta["model"] = model_name
            _call_meta["host"] = config.get("base_url") or ""

        reasoning_effort = reasoning_effort_override or config.get("reasoning_effort")
        # 辅助调用降档：请求 json_object 的调用是「给机器看的结构化判定」（使命规划、
        # 一致性检查、摘要抽取…），深度思考在这里换不来正文质量，只换来等待——实测标准档
        # 一章 203s 里有约 55s 花在这类调用的推理 token 上。正文创作（无 response_format）
        # 不受影响，仍用通道/模型目录配的推理档，付费档位的差异化不被削弱。
        # 调用方显式传 reasoning_effort_override 时以调用方为准，不做二次干预。
        if response_format == "json_object" and not reasoning_effort_override:
            aux_effort = await self._resolve_aux_reasoning_effort()
            if aux_effort:
                reasoning_effort = aux_effort
        # response_format_target 就是「base_url|model」上游组合键，三个自愈闩共用同一个键
        reasoning_effort_supported = response_format_target not in self._UNSUPPORTED_REASONING_EFFORT_TARGETS
        last_exc = None
        response_format_fallback_applied = False
        responses_endpoint_fallback_applied = False
        temperature_fallback_applied = False
        use_max_completion_tokens = False
        real_usage: Optional[Dict[str, int]] = None
        _active_format: Optional[str] = None
        client = None
        for attempt in range(1, max_retries + 2):  # max_retries + 1 次总尝试
            # P2 优化: 使用客户端缓存，仅当 api_format 变更时切换客户端
            if api_format != _active_format:
                client = self._get_or_create_client(api_format, config["api_key"], config.get("base_url"))
                _active_format = api_format
            full_response = ""
            finish_reason = None
            real_usage = None

            try:
                # 真实 token 用量：仅对未知不支持的 provider 组合启用 stream_options.include_usage
                stream_usage_enabled = response_format_target not in self._UNSUPPORTED_STREAM_OPTIONS_TARGETS
                extra_kwargs = self._build_stream_extra_kwargs(
                    api_format,
                    thinking_budget=thinking_budget,
                    disable_thinking=disable_thinking,
                    reasoning_effort=reasoning_effort,
                    model_name=model_name,
                    enable_usage=stream_usage_enabled,
                    use_max_completion_tokens=use_max_completion_tokens,
                    reasoning_effort_supported=reasoning_effort_supported,
                )
                async for part in client.stream_chat(
                    messages=chat_messages,
                    model=config.get("model"),
                    temperature=effective_temperature,
                    timeout=int(timeout),
                    response_format=effective_response_format,
                    max_tokens=max_tokens,
                    top_p=effective_top_p,
                    **extra_kwargs,
                ):
                    delta = part.get("content")
                    if delta:
                        full_response += delta
                        if on_chunk:
                            try:
                                callback_result = on_chunk(delta)
                                if inspect.isawaitable(callback_result):
                                    await callback_result
                            except Exception as callback_exc:
                                logger.debug("LLM on_chunk 回调异常（已忽略）: %s", callback_exc)
                    if part.get("finish_reason"):
                        finish_reason = part["finish_reason"]
                    if part.get("usage"):
                        real_usage = part["usage"]
                # 流式读取正常完成，跳出重试循环
                break

            except InternalServerError as exc:
                detail = "AI 服务内部错误，请稍后重试"
                response = getattr(exc, "response", None)
                if response is not None:
                    try:
                        payload = response.json()
                        error_data = payload.get("error", {}) if isinstance(payload, dict) else {}
                        detail = error_data.get("message_zh") or error_data.get("message") or detail
                    except Exception:
                        detail = str(exc) or detail
                else:
                    detail = str(exc) or detail

                # OpenAI chat/completions 端点不兼容时，自动切换到 responses 重试
                if (
                    api_format == "openai"
                    and not responses_endpoint_fallback_applied
                    and self._is_endpoint_not_supported_detail(detail)
                ):
                    responses_endpoint_fallback_applied = True
                    api_format = "openai-responses"
                    logger.warning(
                        "OpenAI chat/completions 端点不兼容，自动切换到 Responses API 重试: "
                        "base_url=%s model=%s attempt=%d/%d detail=%s",
                        config.get("base_url"),
                        model_name,
                        attempt,
                        max_retries + 1,
                        detail,
                    )
                    continue

                logger.error(
                    "LLM stream internal error: base_url=%s model=%s user_id=%s detail=%s",
                    config.get("base_url"), model_name, user_id, detail,
                    exc_info=exc,
                )
                raise HTTPException(status_code=503, detail=detail)

            except (PermissionDeniedError, AuthenticationError) as exc:
                detail = "AI 服务鉴权失败：请求被拒绝，请检查 API Key 或服务商权限配置"
                response = getattr(exc, "response", None)
                if response is not None:
                    try:
                        payload = response.json()
                        error_data = payload.get("error", {}) if isinstance(payload, dict) else {}
                        detail = error_data.get("message") or detail
                    except Exception:
                        detail = str(exc) or detail
                else:
                    detail = str(exc) or detail
                logger.error(
                    "LLM鉴权/权限错误: base_url=%s model=%s user_id=%s error_type=%s detail=%s",
                    config.get("base_url"), model_name, user_id,
                    type(exc).__name__, detail,
                    exc_info=exc,
                )
                raise HTTPException(status_code=403, detail=detail) from exc

            except (NotFoundError, BadRequestError) as exc:
                detail = self._extract_provider_error_detail(exc)
                if (
                    api_format == "openai"
                    and not responses_endpoint_fallback_applied
                    and self._is_endpoint_not_supported_detail(detail)
                ):
                    responses_endpoint_fallback_applied = True
                    api_format = "openai-responses"
                    logger.warning(
                        "OpenAI chat/completions 返回端点不兼容错误，自动切换到 Responses API 重试: "
                        "base_url=%s model=%s attempt=%d/%d detail=%s",
                        config.get("base_url"),
                        model_name,
                        attempt,
                        max_retries + 1,
                        detail,
                    )
                    continue
                if (
                    isinstance(exc, BadRequestError)
                    and api_format == "openai"
                    and response_format_target not in self._UNSUPPORTED_STREAM_OPTIONS_TARGETS
                    and self._is_stream_options_unsupported_error(exc)
                ):
                    self._UNSUPPORTED_STREAM_OPTIONS_TARGETS.add(response_format_target)
                    logger.warning(
                        "provider 不支持 stream_options.include_usage，禁用后自动重试(后续将回退 token 估算): "
                        "base_url=%s model=%s", config.get("base_url"), model_name,
                    )
                    continue
                if (
                    isinstance(exc, BadRequestError)
                    and api_format == "openai"
                    and not use_max_completion_tokens
                    and max_tokens is not None
                    and self._is_max_completion_tokens_error(exc)
                ):
                    use_max_completion_tokens = True
                    logger.warning(
                        "模型要求 max_completion_tokens(而非 max_tokens)，改参后自动重试: "
                        "base_url=%s model=%s", config.get("base_url"), model_name,
                    )
                    continue
                # reasoning_effort 必须排在 response_format 降级之前判定：后者把「空错误体的
                # 400」也当成自己的信号，会抢先吞掉这个错误，导致推理参数的闩永远记不上，
                # 每次调用都白费一次往返。
                if (
                    isinstance(exc, BadRequestError)
                    and api_format in ("openai", "openai-responses")
                    and reasoning_effort_supported
                    and reasoning_effort
                    and self._is_reasoning_effort_unsupported_error(exc)
                ):
                    self._UNSUPPORTED_REASONING_EFFORT_TARGETS.add(response_format_target)
                    reasoning_effort_supported = False
                    logger.warning(
                        "provider 不接受 reasoning_effort，去掉该参数后自动重试并记闩: "
                        "base_url=%s model=%s effort=%s", config.get("base_url"), model_name, reasoning_effort,
                    )
                    continue
                if (
                    isinstance(exc, BadRequestError)
                    and api_format in ("openai", "openai-responses")
                    and not temperature_fallback_applied
                    and (effective_temperature is not None or effective_top_p is not None)
                    and self._is_temperature_unsupported_error(exc)
                ):
                    temperature_fallback_applied = True
                    logger.warning(
                        "检测到模型不支持 temperature/top_p（多为推理模型），剔除后自动重试: "
                        "base_url=%s model=%s attempt=%d/%d detail=%s",
                        config.get("base_url"), model_name, attempt, max_retries + 1, detail,
                    )
                    effective_temperature = None
                    effective_top_p = None
                    continue
                if (
                    isinstance(exc, BadRequestError)
                    and api_format in ("openai", "openai-responses")
                    and effective_response_format is not None
                    and not response_format_fallback_applied
                    and self._is_response_format_unsupported_error(exc)
                ):
                    response_format_fallback_applied = True
                    logger.warning(
                        "检测到服务商不支持 response_format=%s，自动降级重试: base_url=%s model=%s attempt=%d/%d detail=%s",
                        effective_response_format,
                        config.get("base_url"),
                        model_name,
                        attempt,
                        max_retries + 1,
                        detail,
                    )
                    self._UNSUPPORTED_RESPONSE_FORMAT_TARGETS.add(response_format_target)
                    effective_response_format = None
                    continue
                logger.error(
                    "LLM请求错误: base_url=%s model=%s user_id=%s error_type=%s detail=%s",
                    config.get("base_url"), model_name, user_id,
                    type(exc).__name__, detail,
                    exc_info=exc,
                )
                raise HTTPException(
                    status_code=getattr(exc, "status_code", 400),
                    detail=detail,
                ) from exc

            except httpx.HTTPStatusError as exc:
                # httpx 客户端（Anthropic/Gemini/OpenAI-Responses）返回的 HTTP 错误
                resp_status = exc.response.status_code
                try:
                    resp_body = exc.response.text[:500]
                except Exception:
                    resp_body = str(exc)
                resp_body_lower = (resp_body or "").lower()

                if resp_status in (429, 500, 502, 503, 529):
                    # 可重试的服务端错误
                    last_exc = exc
                    logger.warning(
                        "LLM HTTP %d (attempt %d/%d): base_url=%s model=%s body=%s",
                        resp_status, attempt, max_retries + 1,
                        config.get("base_url"), model_name, resp_body,
                    )
                    if attempt <= max_retries:
                        wait = 2 ** attempt
                        logger.info("将在 %ds 后重试 (attempt %d/%d)...", wait, attempt + 1, max_retries + 1)
                        await asyncio.sleep(wait)
                        continue
                    raise HTTPException(
                        status_code=503,
                        detail=f"AI 服务持续出错 (HTTP {resp_status})，已重试 {max_retries} 次",
                    ) from exc

                if resp_status in (401, 403):
                    detail = f"AI 服务鉴权失败: {resp_body}"
                    logger.error("LLM auth error: base_url=%s model=%s detail=%s",
                                 config.get("base_url"), model_name, detail)
                    raise HTTPException(status_code=403, detail=detail) from exc

                # 推理参数降级：同样必须排在下方 response_format 降级之前——那条分支对任何
                # 400 都成立，会抢先把这个错误当成格式问题处理。
                if (
                    resp_status == 400
                    and api_format == "openai-responses"
                    and reasoning_effort_supported
                    and reasoning_effort
                    and self._detail_indicates_reasoning_unsupported(resp_body)
                ):
                    self._UNSUPPORTED_REASONING_EFFORT_TARGETS.add(response_format_target)
                    reasoning_effort_supported = False
                    logger.warning(
                        "Responses 端点不接受 reasoning.effort，去掉该参数后自动重试并记闩: "
                        "base_url=%s model=%s body=%s", config.get("base_url"), model_name, resp_body,
                    )
                    continue

                # response_format 降级：httpx 客户端（OpenAI-Responses/Anthropic）的 400 错误
                if (
                    resp_status == 400
                    and effective_response_format is not None
                    and not response_format_fallback_applied
                ):
                    response_format_fallback_applied = True
                    logger.warning(
                        "httpx 400 检测到可能的 response_format 不兼容，自动降级重试: "
                        "base_url=%s model=%s api_format=%s body=%s",
                        config.get("base_url"), model_name, api_format, resp_body,
                    )
                    self._UNSUPPORTED_RESPONSE_FORMAT_TARGETS.add(response_format_target)
                    effective_response_format = None
                    continue

                # OpenAI Responses 兼容降级：部分代理暴露了 /responses 路径，
                # 但上游模型并不真正支持，常见表现是 400 upstream_error / 空错误体。
                if (
                    api_format == "openai-responses"
                    and not responses_endpoint_fallback_applied
                    and resp_status in (400, 404, 405, 422, 500)
                    and (
                        "upstream_error" in resp_body_lower
                        or "unsupported" in resp_body_lower
                        or "not support" in resp_body_lower
                        or "not found" in resp_body_lower
                        or "unknown" in resp_body_lower
                        or "endpoint not supported" in resp_body_lower
                        or "convert_request_failed" in resp_body_lower
                        or not resp_body_lower.strip()
                    )
                ):
                    responses_endpoint_fallback_applied = True
                    api_format = "openai"
                    logger.warning(
                        "OpenAI-Responses 端点疑似不兼容，自动回退到 OpenAI chat/completions 重试: "
                        "base_url=%s model=%s attempt=%d/%d status=%d body=%s",
                        config.get("base_url"),
                        model_name,
                        attempt,
                        max_retries + 1,
                        resp_status,
                        resp_body,
                    )
                    continue

                if resp_status == 404:
                    detail = f"AI 服务不支持该模型或接口: {resp_body}"
                    logger.error("LLM not found: base_url=%s model=%s detail=%s",
                                 config.get("base_url"), model_name, detail)
                    raise HTTPException(status_code=404, detail=detail) from exc

                detail = f"AI 服务请求错误 (HTTP {resp_status}): {resp_body}"
                logger.error("LLM HTTP error: base_url=%s model=%s detail=%s",
                             config.get("base_url"), model_name, detail)
                raise HTTPException(status_code=502, detail=detail) from exc

            except httpx.UnsupportedProtocol as exc:
                detail = (
                    "LLM 服务地址配置无效：请为 llm.base_url 或个人 LLM 地址填写完整的 "
                    "http:// 或 https:// 前缀"
                )
                logger.error(
                    "LLM unsupported protocol: base_url=%s model=%s user_id=%s detail=%s",
                    config.get("base_url"),
                    model_name,
                    user_id,
                    exc,
                    exc_info=exc,
                )
                raise HTTPException(status_code=500, detail=detail) from exc

            except self._RETRYABLE_ERRORS as exc:
                last_exc = exc
                collected_chars = len(full_response)
                logger.warning(
                    "LLM stream interrupted (attempt %d/%d): base_url=%s model=%s user_id=%s "
                    "error_type=%s error=%s collected_chars=%d",
                    attempt, max_retries + 1,
                    config.get("base_url"), model_name, user_id,
                    type(exc).__name__, exc, collected_chars,
                )

                # 已收集到足够内容且看起来接近完成，直接返回已有内容
                if collected_chars >= 200 and finish_reason is not None:
                    logger.info(
                        "LLM stream interrupted but has usable content (%d chars, finish_reason=%s), returning partial.",
                        collected_chars, finish_reason,
                    )
                    break

                if attempt <= max_retries:
                    wait = 2 ** attempt  # 2s, 4s
                    logger.info("将在 %ds 后重试 (attempt %d/%d)...", wait, attempt + 1, max_retries + 1)
                    await asyncio.sleep(wait)
                    continue

                # 重试耗尽
                if isinstance(exc, httpx.RemoteProtocolError):
                    detail = f"AI 服务连接被意外中断（已重试 {max_retries} 次），请稍后重试"
                elif isinstance(exc, httpx.ConnectTimeout):
                    detail = f"AI 服务连接超时（已重试 {max_retries} 次），请检查网络或服务地址配置"
                elif isinstance(exc, httpx.ConnectError):
                    raw_msg = str(exc)
                    if "name resolution" in raw_msg.lower():
                        detail = (
                            f"AI 服务域名解析失败（已重试 {max_retries} 次）。"
                            f"请检查 llm.base_url 或个人 LLM 地址是否可解析：{config.get('base_url') or '未配置'}"
                        )
                    else:
                        detail = (
                            f"无法连接到 AI 服务（已重试 {max_retries} 次）。"
                            f"请检查服务地址与网络连通性：{config.get('base_url') or '未配置'}"
                        )
                elif isinstance(exc, (httpx.ReadTimeout, APITimeoutError)):
                    detail = f"AI 服务响应超时（已重试 {max_retries} 次），请稍后重试"
                else:
                    detail = f"无法连接到 AI 服务（已重试 {max_retries} 次），请稍后重试"
                logger.error(
                    "LLM stream failed after %d retries: base_url=%s model=%s user_id=%s detail=%s",
                    max_retries, config.get("base_url"), model_name, user_id, detail,
                    exc_info=exc,
                )
                raise HTTPException(status_code=503, detail=detail) from exc

        logger.debug(
            "LLM response collected: base_url=%s model=%s user_id=%s finish_reason=%s preview=%s",
            config.get("base_url"),
            config.get("model"),
            user_id,
            finish_reason,
            full_response[:500],
        )

        if not full_response:
            logger.error(
                "LLM returned empty response: model=%s user_id=%s finish_reason=%s",
                config.get("model"),
                user_id,
                finish_reason,
            )
            # P2: 使用缓存客户端，不再逐次关闭
            raise HTTPException(
                status_code=500,
                detail=f"AI 未返回有效内容（结束原因: {finish_reason or '未知'}），请稍后重试或联系管理员"
            )

        await self._increment_usage_metric("api_request_count")
        # 记录 API 用量（请求次数精确）。token 优先用服务端返回的真实 usage（含推理模型 reasoning token），
        # 拿不到时回退中英混合估算。失败不影响生成。
        if real_usage and (real_usage.get("prompt_tokens") or real_usage.get("completion_tokens")):
            rec_prompt = int(real_usage.get("prompt_tokens") or 0)
            rec_completion = int(real_usage.get("completion_tokens") or 0)
        else:
            prompt_text = "".join(m.get("content") or "" for m in messages)
            rec_prompt = estimate_tokens(prompt_text)
            rec_completion = estimate_tokens(full_response)
        if _call_meta is not None:
            _call_meta["prompt_tokens"] = rec_prompt
            _call_meta["completion_tokens"] = rec_completion
        await self._record_token_usage(
            model=model_name,
            api_type=api_type,
            prompt_tokens=rec_prompt,
            completion_tokens=rec_completion,
        )
        # 截断检测放在用量记录之后：被截断的调用恰是吃满 completion token 的最贵调用，必须计入统计
        if finish_reason == "length":
            logger.warning(
                "LLM response truncated (finish_reason=length)%s: "
                "model=%s user_id=%s response_length=%d",
                "" if fail_on_truncation else ", returning partial content",
                config.get("model"),
                user_id,
                len(full_response),
            )
            if fail_on_truncation:
                raise LLMResponseTruncated(full_response)
        logger.info(
            "LLM response success: base_url=%s model=%s user_id=%s chars=%d",
            config.get("base_url"),
            config.get("model"),
            user_id,
            len(full_response),
        )
        # P2: 使用缓存客户端，不再逐次关闭
        return full_response

    async def _increment_usage_metric(self, key: str) -> None:
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                await UsageService(session).increment(key)

    async def _record_token_usage(
        self,
        *,
        model: Optional[str],
        api_type: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """记录一次 API 调用的 token 用量（后台用量统计）。失败仅告警，不影响主流程。"""
        try:
            async with self._db_access_lock:
                async with AsyncSessionLocal() as session:
                    await record_usage(
                        session,
                        model=model,
                        api_type=api_type,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                    )
        except Exception as exc:  # pragma: no cover - 记录失败不应中断生成
            logger.warning("记录 API 用量失败(已忽略): %s", exc)

    def _classify_call_error(self, exc: Exception) -> tuple:
        """把 LLM 调用异常归类为 (status, http_status)。status ∈ {timeout, error}。"""
        # _stream_and_collect_impl 终态失败抛 503 HTTPException，detail 含「超时」可区分
        if isinstance(exc, HTTPException):
            detail = str(getattr(exc, "detail", "") or "")
            if "超时" in detail or "timeout" in detail.lower():
                return "timeout", exc.status_code
            return "error", exc.status_code
        if isinstance(exc, (APITimeoutError, httpx.TimeoutException, asyncio.TimeoutError)):
            return "timeout", None
        if isinstance(exc, httpx.HTTPStatusError):
            return "error", (exc.response.status_code if exc.response is not None else None)
        # openai 库的 APIStatusError 系列带 status_code 属性
        status_code = getattr(exc, "status_code", None)
        http_status = status_code if isinstance(status_code, int) else None
        if "timeout" in type(exc).__name__.lower():
            return "timeout", http_status
        return "error", http_status

    async def _record_call_log(
        self,
        *,
        api_type: str,
        model: Optional[str],
        host: Optional[str],
        status: str,
        latency_ms: int,
        http_status: Optional[int],
        error_type: Optional[str],
        error_message: Optional[str],
        prompt_tokens: int,
        completion_tokens: int,
        user_id: Optional[int],
    ) -> None:
        """记录一次 LLM 调用遥测（后台「通道诊断」）。失败仅 debug 日志，不影响生成。"""
        try:
            async with self._db_access_lock:
                async with AsyncSessionLocal() as session:
                    await record_call_log(
                        session,
                        api_type=api_type,
                        model=model,
                        host=host,
                        status=status,
                        latency_ms=latency_ms,
                        http_status=http_status,
                        error_type=error_type,
                        error_message=error_message,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        user_id=user_id,
                    )
        except Exception as exc:  # pragma: no cover - 遥测失败不应中断生成
            logger.debug("记录 LLM 调用遥测失败(已忽略): %s", exc)

    async def _get_config_value_for_session(self, session, key: str) -> Optional[str]:
        record = await SystemConfigRepository(session).get_by_key(key)
        if record:
            return record.value
        env_key = key.upper().replace(".", "_")
        return os.getenv(env_key)

    async def _resolve_aux_reasoning_effort(self) -> Optional[str]:
        """辅助（结构化 JSON）调用的推理档，SystemConfig `llm.aux_reasoning_effort`。

        带进程级 TTL 缓存：这个值每次 json 调用都要读，而它几乎不变；没有缓存就等于给
        每次结构化调用加一次 DB 往返。设成 `off` 或空即关闭降档（回到用通道自身的推理档）。
        """
        now = time.monotonic()
        if self._aux_effort_cache is not None and now < self._aux_effort_expires_at:
            return self._aux_effort_cache or None
        try:
            async with self._db_access_lock:
                async with AsyncSessionLocal() as session:
                    raw = await self._get_config_value_for_session(session, "llm.aux_reasoning_effort")
        except Exception as exc:  # 读配置失败不应影响生成，退回「不降档」
            logger.debug("读取 llm.aux_reasoning_effort 失败(已忽略): %s", exc)
            return None
        value = (raw or "").strip().lower()
        if value in {"off", "none", "disabled"}:
            value = ""
        elif value not in {"minimal", "low", "medium", "high"}:
            value = self._DEFAULT_AUX_REASONING_EFFORT
        self._aux_effort_cache = value
        self._aux_effort_expires_at = now + self._AUX_EFFORT_TTL_SEC
        return value or None

    async def _resolve_config_by_model_code(self, code: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
        """按「模型目录」code 解析整套通道配置（通道五键留空则回退 llm.*）。
        未指定/未入库/已下架 → 返回 None（调用方据此用默认通道）。供生成链路把用户所选模型
        转成 get_llm_response(config_override=...) 实际生效。"""
        if not code:
            return None
        from sqlalchemy import select
        from ..models.model_catalog import ModelCatalog
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                row = (
                    await session.execute(select(ModelCatalog).where(ModelCatalog.code == code))
                ).scalar_one_or_none()
                if row is None or not row.is_active:
                    return None
                api_key = await self._get_config_value_for_session(session, row.api_key_ref or "llm.api_key")
                base_url = self._normalize_base_url(
                    row.base_url or await self._get_config_value_for_session(session, "llm.base_url")
                )
                model = row.real_model or await self._get_config_value_for_session(session, "llm.model")
                api_format = row.api_format or await self._get_config_value_for_session(session, "llm.api_format")
                reasoning_effort = row.reasoning_effort or await self._get_config_value_for_session(session, "llm.reasoning_effort")
                return {
                    "api_key": api_key,
                    "base_url": base_url,
                    "model": model,
                    "api_format": api_format,
                    "reasoning_effort": reasoning_effort,
                }

    async def _resolve_llm_config(self, user_id: Optional[int]) -> Dict[str, Optional[str]]:
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                user_repo = UserRepository(session)
                admin_setting_service = AdminSettingService(session)

                if user_id:
                    limit_str = await admin_setting_service.get("daily_request_limit", "100")
                    limit = int(limit_str or 10)
                    used = await user_repo.get_daily_request(user_id)
                    if used >= limit:
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="今日请求次数已达上限，请明日再试。",
                        )
                    await user_repo.increment_daily_request(user_id)
                    await session.commit()

                api_key = await self._get_config_value_for_session(session, "llm.api_key")
                base_url = self._normalize_base_url(await self._get_config_value_for_session(session, "llm.base_url"))
                model = await self._get_config_value_for_session(session, "llm.model")
                api_format = await self._get_config_value_for_session(session, "llm.api_format")
                reasoning_effort = await self._get_config_value_for_session(session, "llm.reasoning_effort")

                if not api_key:
                    logger.error("未配置系统 LLM API Key，用户 %s 无法使用", user_id)
                    raise HTTPException(
                        status_code=500,
                        detail="系统 LLM API Key 未配置，请联系管理员在后台配置"
                    )

                return {"api_key": api_key, "base_url": base_url, "model": model, "api_format": api_format, "reasoning_effort": reasoning_effort}

    async def _resolve_optimize_llm_config(self) -> Dict[str, Optional[str]]:
        """解析润色优化专用 LLM 配置，未设置的字段回退到默认 llm.* 配置。"""
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                opt_api_key = await self._get_config_value_for_session(session, "llm_optimize.api_key")
                opt_base_url = self._normalize_base_url(await self._get_config_value_for_session(session, "llm_optimize.base_url"))
                opt_model = await self._get_config_value_for_session(session, "llm_optimize.model")
                opt_api_format = await self._get_config_value_for_session(session, "llm_optimize.api_format")
                opt_reasoning = await self._get_config_value_for_session(session, "llm_optimize.reasoning_effort")

                if not channel_explicitly_configured(opt_api_key, opt_base_url, opt_model, opt_api_format):
                    api_key = await self._get_config_value_for_session(session, "llm.api_key")
                    base_url = self._normalize_base_url(await self._get_config_value_for_session(session, "llm.base_url"))
                    model = await self._get_config_value_for_session(session, "llm.model")
                    reasoning_effort = await self._get_config_value_for_session(session, "llm.reasoning_effort")
                    if not api_key:
                        raise HTTPException(
                            status_code=500,
                            detail="未配置润色优化模型，且默认 LLM API Key 也未设置",
                        )
                    return {"api_key": api_key, "base_url": base_url, "model": model, "api_format": None, "reasoning_effort": reasoning_effort}

                api_key = opt_api_key or await self._get_config_value_for_session(session, "llm.api_key")
                base_url = opt_base_url or self._normalize_base_url(await self._get_config_value_for_session(session, "llm.base_url"))
                model = opt_model or await self._get_config_value_for_session(session, "llm.model")
                api_format = opt_api_format

                if not api_key:
                    raise HTTPException(
                        status_code=500,
                        detail="润色优化模型与默认 LLM 均未配置 API Key",
                    )

                return {"api_key": api_key, "base_url": base_url, "model": model, "api_format": api_format, "reasoning_effort": opt_reasoning}

    async def _resolve_fallback_llm_config(self) -> Optional[Dict[str, Optional[str]]]:
        """解析兜底 LLM 通道（llm_fallback.*）。

        未配置 api_key 时返回 None（视为未启用兜底）；base_url/model 缺省时
        回退默认 llm.*（典型场景：同模型换备用 key/服务商）。
        仅 get_llm_response 在默认通道彻底失败时使用，不参与 polish/search/grader。
        """
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                fb_api_key = await self._get_config_value_for_session(session, "llm_fallback.api_key")
                if not fb_api_key:
                    return None
                fb_base_url = self._normalize_base_url(
                    await self._get_config_value_for_session(session, "llm_fallback.base_url")
                    or await self._get_config_value_for_session(session, "llm.base_url")
                )
                fb_model = (
                    await self._get_config_value_for_session(session, "llm_fallback.model")
                    or await self._get_config_value_for_session(session, "llm.model")
                )
                fb_api_format = await self._get_config_value_for_session(session, "llm_fallback.api_format")
                fb_reasoning = await self._get_config_value_for_session(session, "llm_fallback.reasoning_effort")
                return {
                    "api_key": fb_api_key,
                    "base_url": fb_base_url,
                    "model": fb_model,
                    "api_format": fb_api_format,
                    "reasoning_effort": fb_reasoning,
                }

    async def _resolve_grader_llm_config(self) -> Optional[Dict[str, Optional[str]]]:
        """解析证据评分专用 LLM 配置（轻量级小模型）。未配置时返回 None（静默跳过）。"""
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                grader_api_key = await self._get_config_value_for_session(session, "llm_grader.api_key")
                grader_base_url = self._normalize_base_url(await self._get_config_value_for_session(session, "llm_grader.base_url"))
                grader_model = await self._get_config_value_for_session(session, "llm_grader.model")
                grader_api_format = await self._get_config_value_for_session(session, "llm_grader.api_format")

                if not channel_explicitly_configured(grader_api_key, grader_base_url, grader_model, grader_api_format):
                    return None

                api_key = grader_api_key or await self._get_config_value_for_session(session, "llm.api_key")
                base_url = grader_base_url or self._normalize_base_url(await self._get_config_value_for_session(session, "llm.base_url"))
                model = grader_model or await self._get_config_value_for_session(session, "llm.model")
                api_format = grader_api_format
                reasoning_effort = await self._get_config_value_for_session(session, "llm_grader.reasoning_effort")

                if not api_key:
                    return None

                return {"api_key": api_key, "base_url": base_url, "model": model, "api_format": api_format, "reasoning_effort": reasoning_effort}

    async def _resolve_search_llm_config(self) -> Dict[str, Optional[str]]:
        """解析参考小说搜索专用 LLM 配置；未启用 llm_search.* 时返回未配置错误。"""
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                search_api_key = await self._get_config_value_for_session(session, "llm_search.api_key")
                search_base_url = self._normalize_base_url(await self._get_config_value_for_session(session, "llm_search.base_url"))
                search_model = await self._get_config_value_for_session(session, "llm_search.model")
                search_api_format = await self._get_config_value_for_session(session, "llm_search.api_format")

                if not channel_explicitly_configured(search_api_key, search_base_url, search_model, search_api_format):
                    raise HTTPException(
                        status_code=503,
                        detail="未配置参考小说搜索模型（llm_search.*），已跳过网络搜索",
                    )

                api_key = search_api_key or await self._get_config_value_for_session(session, "llm.api_key")
                base_url = search_base_url or self._normalize_base_url(await self._get_config_value_for_session(session, "llm.base_url"))
                model = search_model or await self._get_config_value_for_session(session, "llm.model")
                api_format = search_api_format
                reasoning_effort = await self._get_config_value_for_session(session, "llm_search.reasoning_effort")

                if not api_key:
                    raise HTTPException(
                        status_code=500,
                        detail="搜索模型与默认 LLM 均未配置 API Key",
                    )

                return {"api_key": api_key, "base_url": base_url, "model": model, "api_format": api_format, "reasoning_effort": reasoning_effort}

    async def get_optimize_llm_response(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        temperature: float = 0.75,
        timeout: float = 600.0,
        max_tokens: Optional[int] = None,
        fail_on_truncation: bool = False,
    ) -> str:
        """使用润色优化专用模型生成响应，不走用户级配置，不扣用户配额。"""
        config = await self._resolve_optimize_llm_config()
        messages = [{"role": "system", "content": system_prompt}, *conversation_history]
        return await self._stream_and_collect(
            messages,
            temperature=temperature,
            user_id=None,
            timeout=timeout,
            config_override=config,
            response_format=None,
            max_tokens=max_tokens,
            api_type="polish",
            fail_on_truncation=fail_on_truncation,
        )

    async def get_search_llm_response(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        temperature: float = 0.4,
        timeout: float = 120.0,
        max_tokens: Optional[int] = None,
        config_override: Optional[Dict[str, Optional[str]]] = None,
    ) -> str:
        """使用搜索专用模型生成响应，不走用户级配置，不扣用户配额。"""
        config = config_override or await self._resolve_search_llm_config()
        messages = [{"role": "system", "content": system_prompt}, *conversation_history]
        return await self._stream_and_collect(
            messages,
            temperature=temperature,
            user_id=None,
            timeout=timeout,
            config_override=config,
            response_format=None,
            max_tokens=max_tokens,
            api_type="search",
        )

    async def get_grader_llm_response(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        temperature: float = 0.1,
        timeout: float = 30.0,
        max_tokens: Optional[int] = 2000,
        config_override: Optional[Dict[str, Optional[str]]] = None,
    ) -> str:
        """使用证据评分专用模型生成响应（极速小模型），不走用户级配置。"""
        config = config_override or await self._resolve_grader_llm_config()
        if config is None:
            raise ValueError("证据评分模型未配置")
        messages = [{"role": "system", "content": system_prompt}, *conversation_history]
        return await self._stream_and_collect(
            messages,
            temperature=temperature,
            user_id=None,
            timeout=timeout,
            config_override=config,
            response_format=None,
            max_tokens=max_tokens,
            api_type="grader",
        )

    async def test_channel(self, channel_type: str) -> Dict[str, Any]:
        """真实检测某个已配置的 LLM / embedding 通道是否可用（管理后台「测试」按钮）。

        channel_type: default | fallback | polish | search | grader | embedding | rerank
        返回: {ok: bool, configured: bool, model: str, latency_ms: int, detail: str}
        - configured=False 表示这条通道被判定为「未启用」，运行时根本不会走它（相关能力
          静默跳过或直接失败）；此时不发测试请求，也不会拿别的通道的配置冒名顶替。
        - configured=True 时才真正发起一次最小调用（LLM 回 "ok" / embedding 取一条向量），
          ok 反映的是「配了但通不通」。
        - 任何异常都被捕获为 ok=False + detail，绝不抛出。
        """
        import time as _time

        prefix_map = {
            "default": "llm",
            "fallback": "llm_fallback",
            "polish": "llm_optimize",
            "search": "llm_search",
            "grader": "llm_grader",
        }
        start = _time.monotonic()
        try:
            if channel_type == "rerank":
                # 重排不是 LLM 通道（请求体/响应体都不同），实现留在 rerank_utils，
                # 这里只做转发，保证后台仍是「一个测试入口」。configured 由 rerank_utils
                # 自己给（它才知道 rerank.enabled 与回退来源）；缺省视为已配置。
                from ..utils.rerank_utils import test_rerank_connection

                return {"configured": True, **await test_rerank_connection()}

            if channel_type == "embedding":
                model = (
                    await self._get_config_value("embedding.model")
                    or await self._get_config_value("ollama.embedding_model")
                    or ""
                )
                vec = await self.get_embedding("连接测试", user_id=None)
                latency = int((_time.monotonic() - start) * 1000)
                if vec:
                    return {"ok": True, "configured": True, "model": model, "latency_ms": latency, "detail": f"返回向量维度 {len(vec)}"}
                return {"ok": False, "configured": True, "model": model, "latency_ms": latency, "detail": "未返回向量，请检查 embedding 配置"}

            prefix = prefix_map.get(channel_type)
            if not prefix:
                return {"ok": False, "configured": False, "model": "", "latency_ms": 0, "detail": f"未知通道类型: {channel_type}"}

            api_key = await self._get_config_value(f"{prefix}.api_key")
            base_url = self._normalize_base_url(await self._get_config_value(f"{prefix}.base_url"))
            model = await self._get_config_value(f"{prefix}.model")
            api_format = await self._get_config_value(f"{prefix}.api_format")

            # 搜索/评分：启用判据是「四键任一非空」，未启用时运行时直接 503 / 静默跳过，
            # 不存在「回退默认通道」这回事。这里必须先按同一判据拦下，否则就会拿 llm.* 的
            # key 去测一条实际禁用的通道，把它报成「可用」——正是后台假信心的来源。
            if channel_type in ("search", "grader") and not channel_explicitly_configured(
                api_key, base_url, model, api_format
            ):
                return {
                    "ok": False, "configured": False, "model": "", "latency_ms": 0,
                    "detail": _UNCONFIGURED_CHANNEL_DETAIL[channel_type],
                }

            # 润色未单独配置时确实会复用默认 llm.*（与 _resolve_optimize_llm_config 一致），
            # 所以它算「已配置」，测的也正是运行时真会走的那套配置。
            if channel_type == "polish" and not api_key:
                api_key = await self._get_config_value("llm.api_key")
                base_url = self._normalize_base_url(await self._get_config_value("llm.base_url"))
                model = model or await self._get_config_value("llm.model")
                api_format = api_format or await self._get_config_value("llm.api_format")

            # 搜索/评分显式配置后，缺省字段同样回退 llm.*（与各自 resolver 一致）
            if channel_type in ("search", "grader") and not api_key:
                api_key = await self._get_config_value("llm.api_key")
                base_url = base_url or self._normalize_base_url(await self._get_config_value("llm.base_url"))
                model = model or await self._get_config_value("llm.model")

            # 兜底通道：api_key 必须独立配置（否则视为未启用），
            # base_url/model 缺省回退 llm.*（与 _resolve_fallback_llm_config 一致）
            if channel_type == "fallback" and api_key:
                base_url = base_url or self._normalize_base_url(await self._get_config_value("llm.base_url"))
                model = model or await self._get_config_value("llm.model")

            if not api_key:
                return {
                    "ok": False, "configured": False, "model": model or "", "latency_ms": 0,
                    "detail": _UNCONFIGURED_CHANNEL_DETAIL.get(channel_type, "未配置 API Key"),
                }

            override = {"api_key": api_key, "base_url": base_url, "model": model, "api_format": api_format}
            resp = await self._stream_and_collect(
                [{"role": "user", "content": "ping，请只回复：ok"}],
                temperature=0.0,
                user_id=None,
                timeout=30.0,
                config_override=override,
                response_format=None,
                max_tokens=16,
                max_retries=0,
                api_type=channel_type,
                _record_telemetry=False,
            )
            latency = int((_time.monotonic() - start) * 1000)
            if resp and resp.strip():
                return {"ok": True, "configured": True, "model": model or "", "latency_ms": latency, "detail": f"模型响应正常：{resp.strip()[:40]}"}
            return {"ok": False, "configured": True, "model": model or "", "latency_ms": latency, "detail": "模型返回空响应"}
        except Exception as exc:  # noqa: BLE001 - 测试不应抛出
            latency = int((_time.monotonic() - start) * 1000)
            return {"ok": False, "configured": True, "model": "", "latency_ms": latency, "detail": str(exc)[:200]}

    async def get_embedding(
        self,
        text: str,
        *,
        user_id: Optional[int] = None,
        model: Optional[str] = None,
    ) -> List[float]:
        """生成文本向量，用于章节 RAG 检索，支持 openai 与 ollama 双提供方。"""
        provider = await self._get_config_value("embedding.provider") or "openai"
        default_model = (
            await self._get_config_value("ollama.embedding_model") or "nomic-embed-text:latest"
            if provider == "ollama"
            else await self._get_config_value("embedding.model") or "text-embedding-3-large"
        )
        target_model = model or default_model

        if provider == "ollama":
            if OllamaAsyncClient is None:
                logger.error("未安装 ollama 依赖，无法调用本地嵌入模型。")
                raise HTTPException(status_code=500, detail="缺少 Ollama 依赖，请先安装 ollama 包。")

            base_url = self._normalize_base_url(
                await self._get_config_value("ollama.embedding_base_url")
                or await self._get_config_value("embedding.base_url")
            )
            client = OllamaAsyncClient(host=base_url)
            try:
                response = await client.embeddings(model=target_model, prompt=text)
            except Exception as exc:  # pragma: no cover - 本地服务调用失败
                logger.error(
                    "Ollama 嵌入请求失败: model=%s url=%s/api/embeddings error=%s",
                    target_model,
                    base_url,
                    exc,
                    exc_info=True,
                )
                return []
            embedding: Optional[List[float]]
            if isinstance(response, dict):
                embedding = response.get("embedding")
            else:
                embedding = getattr(response, "embedding", None)
            if not embedding:
                logger.warning("Ollama 返回空向量: model=%s", target_model)
                return []
            if not isinstance(embedding, list):
                embedding = list(embedding)
        else:
            config = await self._resolve_llm_config(user_id)
            embedding_api_key = await self._get_config_value("embedding.api_key")
            embedding_base_url = self._normalize_base_url(await self._get_config_value("embedding.base_url"))
            api_key = embedding_api_key or config["api_key"]
            base_url = embedding_base_url or config.get("base_url")

            # 如果没有独立的 embedding 配置，且 LLM base_url 看起来不支持 embedding
            # （非 OpenAI 官方地址），发出警告并跳过
            if not embedding_api_key and not embedding_base_url and base_url:
                base_lower = str(base_url).lower()
                if not any(host in base_lower for host in ("api.openai.com", "openai.azure.com")):
                    logger.warning(
                        "未配置独立的嵌入模型（embedding.api_key / embedding.base_url），"
                        "且当前 LLM 地址 %s 可能不支持 /embeddings 端点。"
                        "请在管理面板配置嵌入模型或设置 EMBEDDING_BASE_URL 环境变量。",
                        base_url,
                    )
                    return []
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            try:
                response = await client.embeddings.create(
                    input=text,
                    model=target_model,
                )
            except Exception as exc:  # pragma: no cover - 网络或鉴权失败
                logger.error(
                    "OpenAI 嵌入请求失败: model=%s url=%s/embeddings user_id=%s error=%s",
                    target_model,
                    str(base_url).rstrip("/"),
                    user_id,
                    exc,
                    exc_info=True,
                )
                return []
            if not response.data:
                logger.warning("OpenAI 嵌入请求返回空数据: model=%s user_id=%s", target_model, user_id)
                return []
            embedding = response.data[0].embedding

        if not isinstance(embedding, list):
            embedding = list(embedding)

        dimension = len(embedding)
        if not dimension:
            vector_size_str = await self._get_config_value("embedding.model_vector_size")
            if vector_size_str:
                dimension = int(vector_size_str)
        if dimension:
            self._embedding_dimensions[target_model] = dimension
        await self._record_token_usage(
            model=target_model,
            api_type="embedding",
            prompt_tokens=estimate_tokens(text),
            completion_tokens=0,
        )
        return embedding

    async def get_embeddings_batch(
        self,
        texts: List[str],
        *,
        user_id: Optional[int] = None,
        model: Optional[str] = None,
        batch_size: int = 2048,
    ) -> List[List[float]]:
        """批量生成文本向量，单次请求处理多个文本，提升效率。

        Args:
            texts: 待向量化的文本列表
            user_id: 用户ID（用于配置解析）
            model: 指定模型（可选）
            batch_size: 单次请求最大文本数（OpenAI 限制 2048）

        Returns:
            向量列表，顺序与输入文本对应；失败的文本返回空列表
        """
        if not texts:
            return []

        provider = await self._get_config_value("embedding.provider") or "openai"
        default_model = (
            await self._get_config_value("ollama.embedding_model") or "nomic-embed-text:latest"
            if provider == "ollama"
            else await self._get_config_value("embedding.model") or "text-embedding-3-large"
        )
        target_model = model or default_model

        # Ollama 不支持批量，回退到逐个调用
        if provider == "ollama":
            logger.warning("Ollama 不支持批量 embedding，回退到逐个调用: count=%d", len(texts))
            results = await asyncio.gather(
                *[self.get_embedding(text, user_id=user_id, model=model) for text in texts],
                return_exceptions=True,
            )
            return [r if isinstance(r, list) else [] for r in results]

        # OpenAI/Jina 批量处理
        config = await self._resolve_llm_config(user_id)
        embedding_api_key = await self._get_config_value("embedding.api_key")
        embedding_base_url = self._normalize_base_url(await self._get_config_value("embedding.base_url"))
        api_key = embedding_api_key or config["api_key"]
        base_url = embedding_base_url or config.get("base_url")

        if not embedding_api_key and not embedding_base_url and base_url:
            base_lower = str(base_url).lower()
            if not any(host in base_lower for host in ("api.openai.com", "openai.azure.com", "jina.ai")):
                logger.warning(
                    "未配置独立的嵌入模型，且当前地址 %s 可能不支持批量 embeddings",
                    base_url,
                )
                return [[] for _ in texts]

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        all_embeddings: List[List[float]] = []

        # 分批处理（OpenAI 限制单次 2048 个文本）
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = await client.embeddings.create(
                    input=batch,
                    model=target_model,
                )
                if not response.data:
                    logger.warning(
                        "批量 embedding 返回空数据: model=%s batch_size=%d",
                        target_model,
                        len(batch),
                    )
                    all_embeddings.extend([[] for _ in batch])
                    continue

                # 按 index 排序确保顺序正确
                sorted_data = sorted(response.data, key=lambda x: x.index)
                batch_embeddings = [item.embedding for item in sorted_data]
                all_embeddings.extend(batch_embeddings)

                # 缓存维度信息
                if batch_embeddings and batch_embeddings[0]:
                    dimension = len(batch_embeddings[0])
                    if dimension:
                        self._embedding_dimensions[target_model] = dimension

                # 记录用量：每个批次算一次请求，token 估算为批内文本之和
                await self._record_token_usage(
                    model=target_model,
                    api_type="embedding",
                    prompt_tokens=sum(estimate_tokens(t) for t in batch),
                    completion_tokens=0,
                )

            except Exception as exc:
                logger.error(
                    "批量 embedding 请求失败: model=%s batch_size=%d error=%s",
                    target_model,
                    len(batch),
                    exc,
                    exc_info=True,
                )
                all_embeddings.extend([[] for _ in batch])

        return all_embeddings

    async def get_embedding_dimension(self, model: Optional[str] = None) -> Optional[int]:
        """获取嵌入向量维度，优先返回缓存结果，其次读取配置。"""
        provider = await self._get_config_value("embedding.provider") or "openai"
        default_model = (
            await self._get_config_value("ollama.embedding_model") or "nomic-embed-text:latest"
            if provider == "ollama"
            else await self._get_config_value("embedding.model") or "text-embedding-3-large"
        )
        target_model = model or default_model
        if target_model in self._embedding_dimensions:
            return self._embedding_dimensions[target_model]
        vector_size_str = await self._get_config_value("embedding.model_vector_size")
        return int(vector_size_str) if vector_size_str else None

    async def _enforce_daily_limit(self, user_id: int) -> None:
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                admin_setting_service = AdminSettingService(session)
                user_repo = UserRepository(session)
                limit_str = await admin_setting_service.get("daily_request_limit", "100")
                limit = int(limit_str or 10)
                used = await user_repo.get_daily_request(user_id)
                if used >= limit:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="今日请求次数已达上限，请明日再试。",
                    )
                await user_repo.increment_daily_request(user_id)
                await session.commit()

    async def _get_config_value(self, key: str) -> Optional[str]:
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                return await self._get_config_value_for_session(session, key)
