# AIMETA P=LLM服务_大模型调用封装|R=API调用_流式生成|NR=不含业务逻辑|E=LLMService|X=internal|A=服务类|D=openai,httpx|S=net|RD=./README.ai
import asyncio
import hashlib
import inspect
import logging
import os
from typing import Any, Awaitable, Callable, Dict, List, Optional

import httpx
from cachetools import LRUCache
from fastapi import HTTPException, status
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, InternalServerError, PermissionDeniedError, AuthenticationError, NotFoundError, BadRequestError

from ..core.config import settings
from ..db.session import AsyncSessionLocal
from ..repositories.llm_config_repository import LLMConfigRepository
from ..repositories.system_config_repository import SystemConfigRepository
from ..repositories.user_repository import UserRepository
from ..services.admin_setting_service import AdminSettingService
from ..services.prompt_service import PromptService
from ..services.usage_service import UsageService
from ..utils.llm_tool import ChatMessage, LLMClient, AnthropicLLMClient, AnyRouterLLMClient, GeminiLLMClient, OpenAIResponsesLLMClient

logger = logging.getLogger(__name__)

try:  # pragma: no cover - 运行环境未安装时兼容
    from ollama import AsyncClient as OllamaAsyncClient
except ImportError:  # pragma: no cover - Ollama 为可选依赖
    OllamaAsyncClient = None


class LLMService:
    """封装与大模型交互的所有逻辑，包括配额控制与配置选择。"""

    # 进程级 LLM 客户端缓存（LRU 限制大小，避免无限增长）
    _CLIENT_CACHE: LRUCache = LRUCache(maxsize=32)

    def __init__(self, session):
        self.session = session
        self.llm_repo = LLMConfigRepository(session)
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
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}, *conversation_history]
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
            on_chunk=on_chunk,
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
        )

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

    @staticmethod
    def _build_stream_extra_kwargs(
        api_format: str,
        *,
        thinking_budget: Optional[int],
        disable_thinking: bool,
    ) -> Dict[str, Any]:
        """按 provider 能力构建可透传的附加参数。"""
        extra_kwargs: Dict[str, Any] = {}

        # 仅 Anthropic/AnyRouter/Gemini 支持 thinking_budget。
        if thinking_budget and api_format in {"anthropic", "anyrouter", "gemini"}:
            extra_kwargs["thinking_budget"] = thinking_budget

        # disable_thinking 当前仅 AnyRouter 客户端实现了显式关闭逻辑。
        if disable_thinking and api_format == "anyrouter":
            extra_kwargs["disable_thinking"] = True

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
        _is_claude_thinking_model = any(
            kw in model_name.lower()
            for kw in ("claude-opus", "opus-4", "claude-3-7", "claude-4", "sonnet-4")
        )
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
        if _is_claude_thinking_model and api_format != "anyrouter":
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

        last_exc = None
        response_format_fallback_applied = False
        responses_endpoint_fallback_applied = False
        _active_format: Optional[str] = None
        client = None
        for attempt in range(1, max_retries + 2):  # max_retries + 1 次总尝试
            # P2 优化: 使用客户端缓存，仅当 api_format 变更时切换客户端
            if api_format != _active_format:
                client = self._get_or_create_client(api_format, config["api_key"], config.get("base_url"))
                _active_format = api_format
            full_response = ""
            finish_reason = None

            try:
                extra_kwargs = self._build_stream_extra_kwargs(
                    api_format,
                    thinking_budget=thinking_budget,
                    disable_thinking=disable_thinking,
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

        if finish_reason == "length":
            logger.warning(
                "LLM response truncated (finish_reason=length), returning partial content: "
                "model=%s user_id=%s response_length=%d",
                config.get("model"),
                user_id,
                len(full_response),
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

    async def _get_config_value_for_session(self, session, key: str) -> Optional[str]:
        record = await SystemConfigRepository(session).get_by_key(key)
        if record:
            return record.value
        env_key = key.upper().replace(".", "_")
        return os.getenv(env_key)

    async def _resolve_llm_config(self, user_id: Optional[int]) -> Dict[str, Optional[str]]:
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                llm_repo = LLMConfigRepository(session)
                user_repo = UserRepository(session)
                admin_setting_service = AdminSettingService(session)

                if user_id:
                    config = await llm_repo.get_by_user(user_id)
                    if config and config.llm_provider_api_key:
                        return {
                            "api_key": config.llm_provider_api_key,
                            "base_url": self._normalize_base_url(config.llm_provider_url),
                            "model": config.llm_provider_model,
                            "api_format": config.llm_provider_api_format,
                        }

                if user_id:
                    limit_str = await admin_setting_service.get("daily_request_limit", "100")
                    limit = int(limit_str or 10)
                    used = await user_repo.get_daily_request(user_id)
                    if used >= limit:
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="今日请求次数已达上限，请明日再试或设置自定义 API Key。",
                        )
                    await user_repo.increment_daily_request(user_id)
                    await session.commit()

                api_key = await self._get_config_value_for_session(session, "llm.api_key")
                base_url = self._normalize_base_url(await self._get_config_value_for_session(session, "llm.base_url"))
                model = await self._get_config_value_for_session(session, "llm.model")
                api_format = await self._get_config_value_for_session(session, "llm.api_format")

                if not api_key:
                    logger.error("未配置默认 LLM API Key，且用户 %s 未设置自定义 API Key", user_id)
                    raise HTTPException(
                        status_code=500,
                        detail="未配置默认 LLM API Key，请联系管理员配置系统默认 API Key 或在个人设置中配置自定义 API Key"
                    )

                return {"api_key": api_key, "base_url": base_url, "model": model, "api_format": api_format}

    async def _resolve_optimize_llm_config(self) -> Dict[str, Optional[str]]:
        """解析润色优化专用 LLM 配置，未设置的字段回退到默认 llm.* 配置。"""
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                opt_api_key = await self._get_config_value_for_session(session, "llm_optimize.api_key")
                opt_base_url = self._normalize_base_url(await self._get_config_value_for_session(session, "llm_optimize.base_url"))
                opt_model = await self._get_config_value_for_session(session, "llm_optimize.model")
                opt_api_format = await self._get_config_value_for_session(session, "llm_optimize.api_format")

                has_any = any(v for v in (opt_api_key, opt_base_url, opt_model, opt_api_format))
                if not has_any:
                    api_key = await self._get_config_value_for_session(session, "llm.api_key")
                    base_url = self._normalize_base_url(await self._get_config_value_for_session(session, "llm.base_url"))
                    model = await self._get_config_value_for_session(session, "llm.model")
                    if not api_key:
                        raise HTTPException(
                            status_code=500,
                            detail="未配置润色优化模型，且默认 LLM API Key 也未设置",
                        )
                    return {"api_key": api_key, "base_url": base_url, "model": model, "api_format": None}

                api_key = opt_api_key or await self._get_config_value_for_session(session, "llm.api_key")
                base_url = opt_base_url or self._normalize_base_url(await self._get_config_value_for_session(session, "llm.base_url"))
                model = opt_model or await self._get_config_value_for_session(session, "llm.model")
                api_format = opt_api_format

                if not api_key:
                    raise HTTPException(
                        status_code=500,
                        detail="润色优化模型与默认 LLM 均未配置 API Key",
                    )

                return {"api_key": api_key, "base_url": base_url, "model": model, "api_format": api_format}

    async def _resolve_grader_llm_config(self) -> Optional[Dict[str, Optional[str]]]:
        """解析证据评分专用 LLM 配置（轻量级小模型）。未配置时返回 None（静默跳过）。"""
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                grader_api_key = await self._get_config_value_for_session(session, "llm_grader.api_key")
                grader_base_url = self._normalize_base_url(await self._get_config_value_for_session(session, "llm_grader.base_url"))
                grader_model = await self._get_config_value_for_session(session, "llm_grader.model")
                grader_api_format = await self._get_config_value_for_session(session, "llm_grader.api_format")

                has_any = any(v for v in (grader_api_key, grader_base_url, grader_model, grader_api_format))
                if not has_any:
                    return None

                api_key = grader_api_key or await self._get_config_value_for_session(session, "llm.api_key")
                base_url = grader_base_url or self._normalize_base_url(await self._get_config_value_for_session(session, "llm.base_url"))
                model = grader_model or await self._get_config_value_for_session(session, "llm.model")
                api_format = grader_api_format

                if not api_key:
                    return None

                return {"api_key": api_key, "base_url": base_url, "model": model, "api_format": api_format}

    async def _resolve_search_llm_config(self) -> Dict[str, Optional[str]]:
        """解析参考小说搜索专用 LLM 配置；未启用 llm_search.* 时返回未配置错误。"""
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                search_api_key = await self._get_config_value_for_session(session, "llm_search.api_key")
                search_base_url = self._normalize_base_url(await self._get_config_value_for_session(session, "llm_search.base_url"))
                search_model = await self._get_config_value_for_session(session, "llm_search.model")
                search_api_format = await self._get_config_value_for_session(session, "llm_search.api_format")

                has_any = any(v for v in (search_api_key, search_base_url, search_model, search_api_format))
                if not has_any:
                    raise HTTPException(
                        status_code=503,
                        detail="未配置参考小说搜索模型（llm_search.*），已跳过网络搜索",
                    )

                api_key = search_api_key or await self._get_config_value_for_session(session, "llm.api_key")
                base_url = search_base_url or self._normalize_base_url(await self._get_config_value_for_session(session, "llm.base_url"))
                model = search_model or await self._get_config_value_for_session(session, "llm.model")
                api_format = search_api_format

                if not api_key:
                    raise HTTPException(
                        status_code=500,
                        detail="搜索模型与默认 LLM 均未配置 API Key",
                    )

                return {"api_key": api_key, "base_url": base_url, "model": model, "api_format": api_format}

    async def get_optimize_llm_response(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        temperature: float = 0.75,
        timeout: float = 600.0,
        max_tokens: Optional[int] = None,
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
        )

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
                        detail="今日请求次数已达上限，请明日再试或设置自定义 API Key。",
                    )
                await user_repo.increment_daily_request(user_id)
                await session.commit()

    async def _get_config_value(self, key: str) -> Optional[str]:
        async with self._db_access_lock:
            async with AsyncSessionLocal() as session:
                return await self._get_config_value_for_session(session, key)
