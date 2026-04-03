# 用户友好错误处理模块

本模块提供分层的错误处理和用户友好的错误提示，
让作者在遇到问题时能快速理解并解决。
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """错误分类"""
    LLM_API = "llm_api"           # LLM API 相关
    PARSING = "parsing"           # 解析失败
    CONFIG = "config"             # 配置问题
    CONTEXT = "context"           # 上下文问题
    DATABASE = "database"         # 数据库问题
    VALIDATION = "validation"     # 验证失败
    NETWORK = "network"           # 网络问题
    UNKNOWN = "unknown"            # 未知错误


class UserFriendlyError(Exception):
    """
    用户友好错误类
    
    特点：
    - 分类明确
    - 用户可理解的中文提示
    - 提供解决建议
    - 包含技术细节（用于调试）
    """
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        user_message: str,
        suggestion: str,
        technical_detail: Optional[str] = None,
        recoverable: bool = True,
    ):
        self.message = message
        self.category = category
        self.user_message = user_message
        self.suggestion = suggestion
        self.technical_detail = technical_detail
        self.recoverable = recoverable
        
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为 API 响应格式"""
        return {
            "error": self.category.value,
            "message": self.user_message,
            "suggestion": self.suggestion,
            "recoverable": self.recoverable,
            # 技术细节仅在调试模式时返回
            "technical_detail": self.technical_detail,
        }


class ErrorHandler:
    """
    错误处理器
    
    将技术错误转换为用户友好的提示
    """
    
    # 错误映射表
    ERROR_MAPPINGS = {
        # LLM API 相关
        "rate_limit_exceeded": (
            ErrorCategory.LLM_API,
            "AI 服务请求过于频繁，请稍后再试",
            "建议：等待几秒后重试，或配置自己的 API Key 以获得更高配额",
        ),
        "insufficient_quota": (
            ErrorCategory.LLM_API,
            "API 配额不足",
            "建议：在个人设置中检查 API Key 余额，或联系管理员",
        ),
        "invalid_api_key": (
            ErrorCategory.CONFIG,
            "API Key 无效",
            "建议：检查 .env 文件中的 OPENAI_API_KEY 是否正确",
        ),
        "api_key_missing": (
            ErrorCategory.CONFIG,
            "未配置 API Key",
            "建议：在 .env 文件中配置 OPENAI_API_KEY",
        ),
        
        # 解析相关
        "json_decode_error": (
            ErrorCategory.PARSING,
            "AI 返回格式有误，已自动尝试修复",
            "建议：如果频繁出现，可尝试更换模型或在设置中调整生成参数",
        ),
        "invalid_response_format": (
            ErrorCategory.PARSING,
            "AI 返回内容格式不符合预期",
            "建议：这是偶发现象，点击重试通常可以解决",
        ),
        
        # 上下文相关
        "context_length_exceeded": (
            ErrorCategory.CONTEXT,
            "本章内容过长，已自动分段处理",
            "建议：分段生成或调整章节纲要，缩短单章长度",
        ),
        "blueprint_not_found": (
            ErrorCategory.CONTEXT,
            "未找到本章大纲",
            "建议：请先在蓝图中创建本章的章节纲要",
        ),
        
        # 网络相关
        "connection_timeout": (
            ErrorCategory.NETWORK,
            "连接 AI 服务超时",
            "建议：检查网络连接，或稍后重试",
        ),
        "connection_refused": (
            ErrorCategory.NETWORK,
            "无法连接到 AI 服务",
            "建议：检查 OPENAI_API_BASE_URL 配置是否正确",
        ),
        
        # 配置相关
        "model_not_found": (
            ErrorCategory.CONFIG,
            "指定的模型不可用",
            "建议：检查 OPENAI_MODEL_NAME 配置是否正确",
        ),
        
        # 数据库相关
        "database_error": (
            ErrorCategory.DATABASE,
            "数据库操作失败",
            "建议：刷新页面后重试，如持续出现请联系管理员",
        ),
    }
    
    @classmethod
    def handle_error(
        cls,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> UserFriendlyError:
        """
        处理错误并返回用户友好的错误
        
        Args:
            error: 原始异常
            context: 错误上下文信息
            
        Returns:
            UserFriendlyError: 用户友好的错误对象
        """
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # 尝试匹配已知错误
        for key, (category, user_msg, suggestion) in cls.ERROR_MAPPINGS.items():
            if key in error_str:
                logger.warning(f"Known error detected: {key}, original: {error}")
                return UserFriendlyError(
                    message=str(error),
                    category=category,
                    user_message=user_msg,
                    suggestion=suggestion,
                    technical_detail=f"{error_type}: {error}" if context and context.get("debug") else None,
                )
        
        # 尝试从错误类型推断
        if "timeout" in error_str or "timed out" in error_str:
            return cls._create_error(
                ErrorCategory.NETWORK,
                "连接 AI 服务超时",
                "网络不稳定，请稍后重试",
                error,
            )
        
        if "json" in error_str or "parse" in error_str:
            return cls._create_error(
                ErrorCategory.PARSING,
                "AI 返回内容解析失败",
                "这是偶发现象，点击重试通常可以解决",
                error,
            )
        
        if "auth" in error_str or "unauthorized" in error_str:
            return cls._create_error(
                ErrorCategory.CONFIG,
                "认证失败",
                "检查 API Key 是否正确",
                error,
            )
        
        if "quota" in error_str or "limit" in error_str:
            return cls._create_error(
                ErrorCategory.LLM_API,
                "API 配额已用完",
                "请联系管理员增加配额",
                error,
            )
        
        # 默认未知错误
        return cls._create_error(
            ErrorCategory.UNKNOWN,
            "生成过程中遇到问题",
            "请稍后重试，如果持续出现请联系管理员",
            error,
        )
    
    @classmethod
    def _create_error(
        cls,
        category: ErrorCategory,
        user_message: str,
        suggestion: str,
        original_error: Exception,
    ) -> UserFriendlyError:
        """创建错误对象"""
        return UserFriendlyError(
            message=str(original_error),
            category=category,
            user_message=user_message,
            suggestion=suggestion,
            technical_detail=type(original_error).__name__,
        )


class ErrorResponseBuilder:
    """
    错误响应构建器
    
    根据不同的使用场景构建合适的错误响应
    """
    
    @staticmethod
    def for_api(error: Exception, debug: bool = False) -> Dict[str, Any]:
        """
        为 API 响应构建错误
        
        Args:
            error: 原始异常
            debug: 是否显示技术细节
            
        Returns:
            适合 API 返回的错误字典
        """
        friendly_error = ErrorHandler.handle_error(error, {"debug": debug})
        return friendly_error.to_dict()
    
    @staticmethod
    def for_stream(error: Exception) -> str:
        """
        为流式响应构建错误消息
        
        返回 SSE 格式的错误消息
        """
        friendly_error = ErrorHandler.handle_error(error)
        return f"data: {}\n\n"
    
    @staticmethod
    def for_frontend(error: Exception) -> Dict[str, Any]:
        """
        为前端构建错误信息
        
        包含用户友好的提示和可采取的行动
        """
        friendly_error = ErrorHandler.handle_error(error)
        
        return {
            "title": "生成失败",
            "message": friendly_error.user_message,
            "suggestion": friendly_error.suggestion,
            "category": friendly_error.category.value,
            "recoverable": friendly_error.recoverable,
            "actions": ErrorResponseBuilder._get_suggested_actions(friendly_error),
        }
    
    @staticmethod
    def _get_suggested_actions(error: UserFriendlyError) -> list:
        """根据错误类型返回建议的操作"""
        actions = []
        
        if error.category == ErrorCategory.LLM_API:
            actions.append({"type": "retry", "label": "重试"})
            actions.append({"type": "open_settings", "label": "检查 API 配置"})
        
        elif error.category == ErrorCategory.PARSING:
            actions.append({"type": "retry", "label": "重试生成"})
            actions.append({"type": "change_model", "label": "尝试其他模型"})
        
        elif error.category == ErrorCategory.CONFIG:
            actions.append({"type": "open_settings", "label": "检查配置"})
        
        elif error.category == ErrorCategory.CONTEXT:
            actions.append({"type": "open_blueprint", "label": "编辑大纲"})
        
        else:
            actions.append({"type": "retry", "label": "重试"})
            actions.append({"type": "contact_support", "label": "联系技术支持"})
        
        return actions


# 便捷函数
def handle_generation_error(error: Exception) -> Dict[str, Any]:
    """处理生成错误的便捷函数"""
    return ErrorResponseBuilder.for_frontend(error)


def format_error_for_user(error: Exception, show_technical: bool = False) -> str:
    """
    将错误格式化为用户可读的字符串
    
    用于日志、通知等场景
    """
    friendly = ErrorHandler.handle_error(error)
    
    if show_technical:
        return f"[{friendly.category.value}] {friendly.user_message} | 建议: {friendly.suggestion} | 技术: {friendly.technical_detail}"
    
    return f"{friendly.user_message} | 建议: {friendly.suggestion}"
