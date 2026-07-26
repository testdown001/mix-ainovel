"""服务器冒烟暴露的两个生产潜伏 bug 的回归锁定。

1. QDRANT_API_KEY 空串 → qdrant-client 强制 https 对纯 HTTP 容器说 TLS，
   生产全部向量操作以 SSL WRONG_VERSION_NUMBER 静默失败（compose 默认注入空串）。
2. 反幻觉后台检查以类名调用实例方法 format_report_for_review，report 绑到
   self 致必然 TypeError，反幻觉报告从未写进评审数据。
"""
import app.models.user_quota  # noqa: F401  防 mapper KeyError

from app.core.config import Settings
from app.services.anti_hallucination_service import (
    AntiHallucinationReport,
    AntiHallucinationService,
    HallucinationIssue,
)


def test_empty_qdrant_api_key_normalized_to_none():
    settings = Settings(qdrant_api_key="")
    assert settings.qdrant_api_key is None
    settings = Settings(qdrant_api_key="   ")
    assert settings.qdrant_api_key is None
    # 真实 key 原样保留
    settings = Settings(qdrant_api_key="real-key")
    assert settings.qdrant_api_key == "real-key"


def test_format_report_callable_as_classlevel():
    """锁定 generation_analysis_task_service:118 的类名直调形态不再 TypeError。"""
    ok = AntiHallucinationService.format_report_for_review(
        AntiHallucinationReport(passed=True)
    )
    assert "通过" in ok

    bad = AntiHallucinationService.format_report_for_review(
        AntiHallucinationReport(
            passed=False,
            issues=[
                HallucinationIssue(
                    severity="critical",
                    category="entity",
                    description="出现未注册角色「王五」",
                    suggested_fix="替换为已注册角色",
                )
            ],
            registered_count=2,
        )
    )
    assert "未通过" in bad and "王五" in bad and "自动注册 2" in bad
