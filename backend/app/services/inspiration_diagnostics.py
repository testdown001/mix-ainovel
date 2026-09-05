# AIMETA P=灵感响应异常诊断|R=分类与独立事务记录|E=record_inspiration_error|X=internal|A=服务函数|D=LLMCallLog|S=db
"""仅保存定位元数据，不保存构思正文、提示词、密钥或上游响应原文。"""
import hashlib
import logging
from uuid import uuid4

from ..db.session import AsyncSessionLocal
from .api_usage_recorder import record_call_log

logger = logging.getLogger(__name__)


async def record_inspiration_error(*, project_id: str, user_id: int,
                                   raw: str, kind: str) -> str:
    reference = uuid4().hex[:12]
    category = "empty_response" if not raw.strip() else kind
    labels = {"empty_response": "空白回复", "invalid_json": "JSON 格式错误",
              "invalid_object": "回复不是 JSON 对象", "invalid_schema": "回复缺少必要字段"}
    message = (f"编号={reference} 项目={project_id} 阶段=灵感对话 "
               f"原因={labels.get(category, category)} 字符数={len(raw)} "
               f"非空白字符数={len(''.join(raw.split()))} "
               f"摘要={hashlib.sha256(raw.encode()).hexdigest()[:16]}")
    try:
        async with AsyncSessionLocal() as session:
            await record_call_log(session, api_type="inspiration", status="error",
                                  user_id=user_id, error_type=category,
                                  error_message=message)
    except Exception:
        logger.warning("灵感异常诊断写入失败: reference=%s", reference, exc_info=True)
    return reference
