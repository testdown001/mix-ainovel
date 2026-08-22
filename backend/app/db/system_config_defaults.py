# AIMETA P=系统配置默认值_初始配置数据|R=默认配置字典|NR=不含配置逻辑|E=SYSTEM_CONFIG_DEFAULTS|X=internal|A=配置字典|D=none|S=none|RD=./README.ai
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..core.config import Settings


def _to_optional_str(value: Optional[object]) -> Optional[str]:
    return str(value) if value is not None else None


def _bool_to_text(value: bool) -> str:
    return "true" if value else "false"


@dataclass(frozen=True)
class SystemConfigDefault:
    key: str
    value_getter: Callable[[Settings], Optional[str]]
    description: Optional[str] = None


SYSTEM_CONFIG_DEFAULTS: list[SystemConfigDefault] = [
    SystemConfigDefault(
        key="llm.api_key",
        value_getter=lambda config: config.openai_api_key,
        description="默认 LLM API Key，用于后台调用大模型。",
    ),
    SystemConfigDefault(
        key="llm.base_url",
        value_getter=lambda config: _to_optional_str(config.openai_base_url),
        description="默认大模型 API Base URL。",
    ),
    SystemConfigDefault(
        key="llm.model",
        value_getter=lambda config: config.openai_model_name,
        description="默认 LLM 模型名称。",
    ),
    SystemConfigDefault(
        key="llm.api_format",
        value_getter=lambda _: "auto",
        description="LLM 请求格式：auto（自动识别）、openai（/v1/chat/completions）、anthropic（原生 /v1/messages，x-api-key 认证）、anyrouter（Claude Code 兼容代理，Bearer 认证）、gemini（Google Gemini 原生 API）、openai-responses（OpenAI Responses API /v1/responses）。",
    ),
    SystemConfigDefault(
        key="llm.aux_reasoning_effort",
        value_getter=lambda _: "low",
        description=(
            "辅助调用（结构化 JSON 输出：使命规划、一致性检查、摘要抽取等）的推理档："
            "minimal/low/medium/high，填 off 关闭降档。正文创作不受此项影响，仍用通道或"
            "模型目录配置的推理档。实测标准档一章约有四分之一时间花在这类调用的推理上，"
            "降档是最直接的提速手段；若上游不接受该参数会自动去掉并记闩，不影响可用性。"
        ),
    ),
    SystemConfigDefault(
        key="blueprint.review_enabled",
        value_getter=lambda _: "true",
        description=(
            "蓝图审稿门总开关。false 时即使深度打磨也不跑审稿/修订（平台级成本熔断）。"
            "与会员档位无关；用户侧深度选项仍按 blueprint_deep 能力展示。"
        ),
    ),
    SystemConfigDefault(
        key="blueprint.review_auto_revise",
        value_getter=lambda _: "true",
        description=(
            "审稿总分低于 blueprint.review_min_score 时是否触发定向修订轮（只重写被点名的"
            "设定块/章号区间）后复审。false = 只审不修（报告仍生成并透传）。"
            "正式替代「把达标分调成 0 来关修订」的隐晦用法。"
        ),
    ),
    SystemConfigDefault(
        key="blueprint.review_min_score",
        value_getter=lambda _: "70",
        description=(
            "蓝图审稿门达标分（0-100，纯及格线）：商业量表总分低于该值且"
            "blueprint.review_auto_revise=true 时触发一轮定向修订后复审；"
            "仍不达标照常落库并把审稿报告透传给用户决策。"
        ),
    ),
    SystemConfigDefault(
        key="blueprint.stress_enabled",
        value_getter=lambda _: "true",
        description=(
            "开书压力推演平台级熔断。false 时即使创作者+也不跑推演（与档位无关）。"
            "推演本身仍按 premise_stress 能力门控；本键只做成本熔断。"
        ),
    ),
    SystemConfigDefault(
        key="pregen.mission_enabled",
        value_getter=lambda _: "true",
        description=(
            "选定章节版本后，后台预生成下一章的章节使命（导演脚本），下次生成直接命中，"
            "写作前等待从 ~2 分钟降到秒级。属内部预付成本（同异步后续任务），不向用户"
            "计费；带写作指令的生成不消费预生成结果。填 false 关闭（60 秒内生效）。"
        ),
    ),
    SystemConfigDefault(
        key="logging.llm_prompt_preview",
        value_getter=lambda _: "digest",
        description=(
            "llm.log 正文预览模式：digest（默认，只记长度+sha1前8位+前80字符，足够对上 "
            "trace 又不落创作全文）、full（明文前 2000 字符，排障期临时用）、off（完全不记正文）。"
            "改动约 60 秒内生效（进程内缓存）。保留期即 llm.log 自身的 20MB×10 轮转。"
        ),
    ),
    SystemConfigDefault(
        key="smtp.server",
        value_getter=lambda config: config.smtp_server,
        description="用于发送邮件验证码的 SMTP 服务器地址。",
    ),
    SystemConfigDefault(
        key="smtp.port",
        value_getter=lambda config: _to_optional_str(config.smtp_port),
        description="SMTP 服务端口。",
    ),
    SystemConfigDefault(
        key="smtp.username",
        value_getter=lambda config: config.smtp_username,
        description="SMTP 登录用户名。",
    ),
    SystemConfigDefault(
        key="smtp.password",
        value_getter=lambda config: config.smtp_password,
        description="SMTP 登录密码。",
    ),
    SystemConfigDefault(
        key="smtp.from",
        value_getter=lambda config: config.email_from,
        description="邮件显示的发件人名称或邮箱。",
    ),
    SystemConfigDefault(
        key="email.provider",
        value_getter=lambda config: config.email_provider,
        description="邮件发送通道：smtp（自建 SMTP）或 resend（Resend API）。",
    ),
    SystemConfigDefault(
        key="resend.api_key",
        value_getter=lambda config: config.resend_api_key,
        description="Resend API Key（email.provider=resend 时生效）。",
    ),
    SystemConfigDefault(
        key="resend.from",
        value_getter=lambda config: config.resend_from,
        description="Resend 发件人地址，须为已验证域名下的邮箱，如 验证码 <noreply@example.com>。",
    ),
    SystemConfigDefault(
        key="auth.allow_registration",
        value_getter=lambda config: _bool_to_text(config.allow_registration),
        description="是否允许用户自助注册。",
    ),
    SystemConfigDefault(
        key="referral.enabled",
        value_getter=lambda _: "true",
        description="是否启用邀请返积分：新用户填邀请码注册，双方各得积分（入永久池，不随月度重置清零）。",
    ),
    SystemConfigDefault(
        key="referral.inviter_credits",
        value_getter=lambda _: "30",
        description="每成功邀请一位新用户，邀请人获得的积分（受 referral.max_invites 上限约束）。",
    ),
    SystemConfigDefault(
        key="referral.invitee_credits",
        value_getter=lambda _: "20",
        description="通过邀请码注册的新用户获得的积分（在注册试用积分之外额外发放）。",
    ),
    SystemConfigDefault(
        key="referral.max_invites",
        value_getter=lambda _: "50",
        description="单个邀请人最多可获奖励的邀请次数（防刷）；超限后受邀人照常得积分，邀请人不再得。",
    ),
    SystemConfigDefault(
        key="auth.linuxdo_enabled",
        value_getter=lambda config: _bool_to_text(config.enable_linuxdo_login),
        description="是否启用 Linux.do OAuth 登录。",
    ),
    SystemConfigDefault(
        key="rate_limit.requests_per_minute",
        value_getter=lambda config: _to_optional_str(config.api_rate_limit_requests_per_minute),
        description="普通 API 请求每分钟限流阈值，修改后下一次请求立即生效。",
    ),
    SystemConfigDefault(
        key="rate_limit.user_rps",
        value_getter=lambda config: _to_optional_str(config.api_rate_limit_user_rps),
        description="已认证用户每秒请求数上限，修改后下一次请求立即生效。",
    ),
    SystemConfigDefault(
        key="rate_limit.ip_rps",
        value_getter=lambda config: _to_optional_str(config.api_rate_limit_ip_rps),
        description="未认证 IP 每秒请求数上限（放宽以容纳 SPA 首屏并发），修改后下一次请求立即生效。",
    ),
    SystemConfigDefault(
        key="rate_limit.auth_rpm",
        value_getter=lambda config: _to_optional_str(config.api_rate_limit_auth_rpm),
        description="登录/注册/验证码等敏感端点每 IP 每分钟上限（暴力破解防护），修改后下一次请求立即生效。",
    ),
    SystemConfigDefault(
        key="linuxdo.client_id",
        value_getter=lambda config: config.linuxdo_client_id,
        description="Linux.do OAuth Client ID。",
    ),
    SystemConfigDefault(
        key="linuxdo.client_secret",
        value_getter=lambda config: config.linuxdo_client_secret,
        description="Linux.do OAuth Client Secret。",
    ),
    SystemConfigDefault(
        key="linuxdo.redirect_uri",
        value_getter=lambda config: _to_optional_str(config.linuxdo_redirect_uri),
        description="Linux.do OAuth 回调地址。",
    ),
    SystemConfigDefault(
        key="linuxdo.auth_url",
        value_getter=lambda config: _to_optional_str(config.linuxdo_auth_url),
        description="Linux.do OAuth 授权地址。",
    ),
    SystemConfigDefault(
        key="linuxdo.token_url",
        value_getter=lambda config: _to_optional_str(config.linuxdo_token_url),
        description="Linux.do OAuth Token 获取地址。",
    ),
    SystemConfigDefault(
        key="linuxdo.user_info_url",
        value_getter=lambda config: _to_optional_str(config.linuxdo_user_info_url),
        description="Linux.do 用户信息接口地址。",
    ),
    SystemConfigDefault(
        key="writer.chapter_versions",
        value_getter=lambda config: _to_optional_str(config.writer_chapter_versions),
        description="每次生成章节的候选版本数量。",
    ),
    SystemConfigDefault(
        key="embedding.provider",
        value_getter=lambda config: config.embedding_provider,
        description="嵌入模型提供方，支持 openai 或 ollama。",
    ),
    SystemConfigDefault(
        key="embedding.api_key",
        value_getter=lambda config: config.embedding_api_key,
        description="嵌入模型专用 API Key，留空则使用默认 LLM API Key。",
    ),
    SystemConfigDefault(
        key="embedding.base_url",
        value_getter=lambda config: _to_optional_str(config.embedding_base_url),
        description="嵌入模型使用的 Base URL，留空则使用默认 LLM Base URL。",
    ),
    SystemConfigDefault(
        key="embedding.model",
        value_getter=lambda config: config.embedding_model,
        description="OpenAI 嵌入模型名称。",
    ),
    SystemConfigDefault(
        key="embedding.model_vector_size",
        value_getter=lambda config: _to_optional_str(config.embedding_model_vector_size),
        description="嵌入向量维度，留空则自动检测。",
    ),
    SystemConfigDefault(
        # 默认改 true（2026-08-15 质量机制重设计）：异步不阻塞正文、成本低、收益直接；
        # 仍是旗舰档 preset=premium 才生效（gating 不变），后台「质量回路」可随时关
        key="quality_loop.outline_revision",
        value_getter=lambda _: "true",
        description="滚动细纲修订（旗舰档）：章节定稿后评审后续大纲是否被本章实际内容写过时，产出修订提示。异步、不阻塞正文。",
    ),
    SystemConfigDefault(
        key="quality_loop.volume_retrospective",
        value_getter=lambda _: "true",
        description="卷级复盘重规划（旗舰档）：一卷末章定稿后对比「原规划 vs 实际写成」，复盘并修订下一卷方向。异步、不阻塞正文。",
    ),
    SystemConfigDefault(
        key="quality_loop.character_significance",
        value_getter=lambda config: _bool_to_text(config.character_significance_enabled),
        description="人物意义层（旗舰档）：抽取信念变化/代价/关系质变/未言明，作为后续生成的底色注入。异步、不阻塞正文，成本较低。",
    ),
    SystemConfigDefault(
        key="quality_loop.two_pass_draft",
        value_getter=lambda config: _bool_to_text(config.two_pass_draft_enabled),
        description="两遍制草稿-改写（旗舰档）：先以轻约束写草稿，再据全部规则改写一遍。⚠️ 每章多一次整章级 LLM 调用，单章成本近乎翻倍。",
    ),
    SystemConfigDefault(
        key="rerank.enabled",
        value_getter=lambda config: _bool_to_text(config.rag_reranker_enabled),
        description="是否启用检索结果重排序（Reranker）。关闭后检索保持原始召回顺序。",
    ),
    SystemConfigDefault(
        key="rerank.api_url",
        value_getter=lambda config: _to_optional_str(config.rag_reranker_api_url),
        description="Reranker API 地址。可填基础地址（自动补 /rerank）或完整 /rerank 端点；留空则回退 embedding.base_url。",
    ),
    SystemConfigDefault(
        key="rerank.api_key",
        value_getter=lambda config: config.rag_reranker_api_key,
        description="Reranker API Key，留空则回退 embedding.api_key。",
    ),
    SystemConfigDefault(
        key="rerank.model",
        value_getter=lambda config: config.rag_reranker_model,
        description="Reranker 模型名称，例如 jina-reranker-v2-base-multilingual。",
    ),
    SystemConfigDefault(
        key="ollama.embedding_base_url",
        value_getter=lambda config: _to_optional_str(config.ollama_embedding_base_url),
        description="Ollama 嵌入模型服务地址。",
    ),
    SystemConfigDefault(
        key="ollama.embedding_model",
        value_getter=lambda config: config.ollama_embedding_model,
        description="Ollama 嵌入模型名称。",
    ),
    SystemConfigDefault(
        key="llm_optimize.api_key",
        value_getter=lambda _: None,
        description="润色优化专用 API Key，留空则使用默认 llm.api_key。",
    ),
    SystemConfigDefault(
        key="llm_optimize.base_url",
        value_getter=lambda _: None,
        description="润色优化专用 Base URL，留空则使用默认 llm.base_url。",
    ),
    SystemConfigDefault(
        key="llm_optimize.model",
        value_getter=lambda _: None,
        description="润色优化专用模型名称，留空则使用默认 llm.model。",
    ),
    SystemConfigDefault(
        key="llm_optimize.api_format",
        value_getter=lambda _: None,
        description="润色优化专用 API 格式，留空则使用默认 llm.api_format。",
    ),
    SystemConfigDefault(
        key="llm_search.api_key",
        value_getter=lambda _: None,
        description="参考小说搜索专用 API Key，留空表示关闭网络搜索。",
    ),
    SystemConfigDefault(
        key="llm_search.base_url",
        value_getter=lambda _: None,
        description="参考小说搜索专用 Base URL，留空表示关闭网络搜索。",
    ),
    SystemConfigDefault(
        key="llm_search.model",
        value_getter=lambda _: None,
        description="参考小说搜索专用模型名称（如 grok-3），留空表示关闭网络搜索。",
    ),
    SystemConfigDefault(
        key="llm_search.api_format",
        value_getter=lambda _: None,
        description="参考小说搜索专用 API 格式，留空表示关闭网络搜索。",
    ),
    # ---- 积分制（数值后台可改；模型单价存于 ModelCatalog 行，不在此处） ----
    SystemConfigDefault(
        key="credits.price.polish",
        value_getter=lambda _: "5",
        description="润色(humanize/polish)附加积分单价，默认不勾选；勾选时每章额外扣此积分。",
    ),
    SystemConfigDefault(
        key="credits.price.transform_expand",
        value_getter=lambda _: "3",
        description="选区扩写积分单价。只改圈中的一段，失败退回。",
    ),
    SystemConfigDefault(
        key="credits.price.transform_rewrite",
        value_getter=lambda _: "3",
        description="选区改写积分单价。只改圈中的一段，失败退回。",
    ),
    SystemConfigDefault(
        key="credits.price.transform_de_ai",
        value_getter=lambda _: "2",
        description="选区去 AI 味积分单价。规则修复免费，不够再走 LLM。",
    ),
    SystemConfigDefault(
        key="credits.price.blueprint_deep",
        value_getter=lambda _: "20",
        description=(
            "蓝图深度打磨积分单价。仅在用户选择深度、档位允许 blueprint_deep、"
            "且 blueprint.review_enabled=true（实际会跑审稿/修订）时扣费；快速成书免费。"
        ),
    ),
    SystemConfigDefault(
        key="credits.price.cover_generation",
        value_getter=lambda _: "10",
        description="AI 小说封面每次生成的积分单价；仅创作者档及以上可用，生成失败自动退回。",
    ),
    SystemConfigDefault(
        key="credits.monthly.free",
        value_getter=lambda _: "60",
        description="free 档每月发放积分(无套餐用户兜底)，≈10 篇章鱼1.0。",
    ),
    SystemConfigDefault(
        key="credits.monthly.creator",
        value_getter=lambda _: "3000",
        description="创作者档每月发放积分，=300 篇章鱼2.0(10/天×30)；Plan.monthly_credits>0 时以套餐为准。",
    ),
    SystemConfigDefault(
        key="credits.monthly.flagship",
        value_getter=lambda _: "18000",
        description="旗舰档每月发放积分，=1800 篇章鱼2.0(60/天×30)；Plan.monthly_credits>0 时以套餐为准。",
    ),
    # ---- 投稿预检词表（只提示，不拦截） ----
    SystemConfigDefault(
        key="compliance.lexicon.qidian",
        value_getter=lambda _: '["详细血腥描写", "现实政治影射", "未成年恋爱"]',
        description="起点投稿预检词表（JSON 数组）。命中只提示，从不拦截生成或导出。",
    ),
    SystemConfigDefault(
        key="compliance.lexicon.fanqie",
        value_getter=lambda _: '["详细血腥描写", "现实政治影射", "未成年恋爱"]',
        description="番茄投稿预检词表（JSON 数组）。命中只提示，从不拦截生成或导出。",
    ),
    SystemConfigDefault(
        key="compliance.lexicon.jjwxc",
        value_getter=lambda _: '["详细血腥描写", "现实政治影射"]',
        description="晋江投稿预检词表（JSON 数组）。命中只提示，从不拦截生成或导出。",
    ),
]
