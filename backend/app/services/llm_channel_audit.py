# AIMETA P=LLM通道配置体检_查实调用查不出的静默失效与假冗余|R=audit_llm_config|E=audit_llm_config|X=internal|A=服务函数|D=sqlalchemy|S=db
"""LLM 通道配置体检。

「通道实时健康」是逐个通道发一次真实调用，它能告诉你「这条通道现在通不通」，
但有两类问题它天然查不出来：

1. **假冗余**：兜底通道与主通道指向同一个上游。两条都测「可用」，可一旦供应商
   整站故障，failover 会跟着一起挂——配了等于没配。2026-08-13 线上就是这样：
   llm 与 llm_fallback 同 base_url 同模型，双双 503，生成全线停摆。
2. **静默失效**：没配独立嵌入通道且主通道地址不是 OpenAI 官方地址时，
   get_embedding 直接返回空向量并跳过；RAG 检索与章节入库全程静默失灵，
   界面上一切正常。搜索/评分通道未配置时同样是静默跳过。

本模块只读配置、不发请求，把这些「看起来没事」的状态显式摆出来。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.system_config_repository import SystemConfigRepository

LEVEL_ERROR = "error"
LEVEL_WARN = "warn"
LEVEL_INFO = "info"

_LEVEL_ORDER = {LEVEL_ERROR: 0, LEVEL_WARN: 1, LEVEL_INFO: 2}

# 只有这些地址被认为自带 /embeddings 端点；其余地址在没有独立嵌入配置时
# 会被 LLMService.get_embedding 判定为不可用并静默返回空向量。
_EMBEDDING_CAPABLE_HOSTS = ("api.openai.com", "openai.azure.com")

_AUDIT_KEYS = (
    "llm.api_key", "llm.base_url", "llm.model",
    "llm_fallback.api_key", "llm_fallback.base_url", "llm_fallback.model",
    "llm_optimize.api_key",
    "llm_search.api_key",
    "llm_grader.api_key",
    "embedding.provider", "embedding.api_key", "embedding.base_url",
    "ollama.embedding_base_url",
    "rerank.enabled", "rerank.api_url",
)


def _same_endpoint(a: Optional[str], b: Optional[str]) -> bool:
    """两个 base_url 是否指向同一处（仅用于比较，不参与真实调用）。"""
    if not a or not b:
        return False
    return a.strip().rstrip("/").lower() == b.strip().rstrip("/").lower()


def _finding(level: str, code: str, title: str, detail: str, channels: List[str]) -> Dict[str, Any]:
    return {"level": level, "code": code, "title": title, "detail": detail, "channels": channels}


async def _load_values(session: AsyncSession) -> Dict[str, Optional[str]]:
    """按 LLMService._get_config_value_for_session 同一口径取值：
    SystemConfig 优先，缺失时回落同名大写环境变量。口径不一致会误报「未配置」。"""
    stored = await SystemConfigRepository(session).get_many(_AUDIT_KEYS)
    values: Dict[str, Optional[str]] = {}
    for key in _AUDIT_KEYS:
        value = stored.get(key)
        if value is None:
            value = os.getenv(key.upper().replace(".", "_"))
        values[key] = (value or "").strip() or None
    return values


def _audit_fallback(v: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    if not v["llm_fallback.api_key"]:
        return [_finding(
            LEVEL_INFO, "fallback_disabled", "未配置兜底通道",
            "主通道终局失败（429 日限之外的任何错误）时无处可退，本次生成直接失败。"
            "填 llm_fallback.api_key 即启用。",
            ["fallback"],
        )]

    # 兜底的 base_url/model 留空时回退 llm.*，比较要按回退后的实际值来
    fb_base = v["llm_fallback.base_url"] or v["llm.base_url"]
    fb_model = v["llm_fallback.model"] or v["llm.model"]
    if not _same_endpoint(fb_base, v["llm.base_url"]):
        return []

    if fb_model and v["llm.model"] and fb_model.strip().lower() == v["llm.model"].strip().lower():
        return [_finding(
            LEVEL_ERROR, "fallback_same_target", "兜底通道与主通道完全相同",
            f"两者都指向 {fb_base} 的 {fb_model}：主通道故障时兜底必然同样失败，"
            "failover 形同虚设。请把兜底指向另一家服务商。",
            ["default", "fallback"],
        )]
    return [_finding(
        LEVEL_WARN, "fallback_same_upstream", "兜底通道与主通道同一上游",
        f"两者共用地址 {fb_base}，只换了模型。供应商级故障（整站 503）会同时打挂两条通道，"
        "冗余只在「单个模型不可用」时有效。建议兜底换一家服务商。",
        ["default", "fallback"],
    )]


def _audit_embedding(v: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    provider = (v["embedding.provider"] or "openai").lower()
    if provider == "ollama":
        if not v["ollama.embedding_base_url"] and not v["embedding.base_url"]:
            return [_finding(
                LEVEL_WARN, "ollama_embedding_url_missing", "Ollama 嵌入地址未配置",
                "embedding.provider=ollama 但没有 ollama.embedding_base_url，向量化会失败。",
                ["embedding"],
            )]
        return []

    if v["embedding.api_key"] or v["embedding.base_url"]:
        return []

    base = v["llm.base_url"]
    if base and not any(host in base.lower() for host in _EMBEDDING_CAPABLE_HOSTS):
        return [_finding(
            LEVEL_ERROR, "embedding_silently_disabled", "向量检索实际处于关闭状态",
            f"没有独立嵌入通道，而主通道地址 {base} 不是 OpenAI 官方地址："
            "get_embedding 会直接返回空向量并跳过，RAG 检索与章节入库全程静默失效，"
            "界面上完全看不出来。请配置 embedding.api_key / embedding.base_url。",
            ["embedding"],
        )]
    return []


async def audit_llm_config(session: AsyncSession) -> List[Dict[str, Any]]:
    """只读配置体检，返回按严重程度排序的问题列表（无问题则为空）。"""
    v = await _load_values(session)
    findings: List[Dict[str, Any]] = []

    if not v["llm.api_key"]:
        findings.append(_finding(
            LEVEL_ERROR, "default_unconfigured", "默认通道未配置",
            "llm.api_key 为空，任何生成请求都会直接失败。",
            ["default"],
        ))

    findings.extend(_audit_fallback(v))
    findings.extend(_audit_embedding(v))

    if not v["llm_search.api_key"]:
        findings.append(_finding(
            LEVEL_WARN, "search_unconfigured", "未配置联网搜索通道",
            "灵感模式的「跨域找料」会静默跳过（失败即返回空，用户无感知），"
            "显式调用搜索的接口返回 503。创作者档以上用户会觉得这个能力不存在。",
            ["search"],
        ))

    if not v["llm_grader.api_key"]:
        findings.append(_finding(
            LEVEL_INFO, "grader_unconfigured", "未配置证据打分通道",
            "证据打分按设计静默跳过，检索到的证据不做质量分级（不影响生成成败）。",
            ["grader"],
        ))

    if not v["llm_optimize.api_key"]:
        findings.append(_finding(
            LEVEL_INFO, "polish_uses_default", "润色通道未单独配置",
            "润色会复用默认通道。注意润色是按积分收费的付费项：主通道故障时润色同样失败"
            "（附加费会自动退回，但用户拿不到润色）。",
            ["polish"],
        ))

    if (v["rerank.enabled"] or "").lower() == "true" and not v["rerank.api_url"]:
        findings.append(_finding(
            LEVEL_WARN, "rerank_url_missing", "重排已启用但未填地址",
            "会退回借用 embedding.base_url 并追加 /rerank；多数厂商的路径不是这个"
            "（如 /v1/rerank），大概率每次检索都白跑一次请求再失败。",
            ["rerank"],
        ))

    findings.sort(key=lambda f: _LEVEL_ORDER.get(f["level"], 9))
    return findings
