"""蓝图生成深度档（fast/deep）+ 会员降级 + 后台开关回归。

锁定的契约：
- normalize/resolve：缺省与未知值 = deep；档位不足静默降为 fast；
- depth=fast 不调用审稿/修订；
- review_enabled=false 时即使 deep 也不审；
- review_auto_revise=false 只审不修；
- 免费档请求 deep 静默降为 fast；
- GET /concept/dossier 的 deep_available：free=false，creator+=true。
"""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routers import novels, task_worker
from app.core.dependencies import get_current_user
from app.db.session import get_session
from app.models.novel import NovelConversation, NovelProject
from app.models.system_config import SystemConfig
from app.models.user import User
from app.models.user_quota import UserQuota
from app.schemas.concept_dossier import BlueprintReviewReport, DossierResponse, ReviewIssue
from app.schemas.user import UserInDB
from app.services import blueprint_generation_service as bgs
from app.services.blueprint_generation_service import (
    normalize_blueprint_depth,
    resolve_blueprint_depth,
)
from app.services.blueprint_review_service import (
    REVIEW_AUTO_REVISE_KEY,
    REVIEW_ENABLED_KEY,
    BlueprintReviewService,
)
from app.services.llm_service import LLMService


OWNER = UserInDB(id=1, username="owner", hashed_password="x")
PROJECT_ID = "proj-bp-depth"


# ---------------------------------------------------------------------------
# 纯函数
# ---------------------------------------------------------------------------

def test_normalize_blueprint_depth():
    assert normalize_blueprint_depth(None) == "deep"
    assert normalize_blueprint_depth("") == "deep"
    assert normalize_blueprint_depth("DEEP") == "deep"
    assert normalize_blueprint_depth("unknown") == "deep"
    assert normalize_blueprint_depth("fast") == "fast"
    assert normalize_blueprint_depth(" FAST ") == "fast"


def test_resolve_blueprint_depth_degrades_when_locked():
    assert resolve_blueprint_depth("deep", deep_allowed=True) == "deep"
    assert resolve_blueprint_depth("deep", deep_allowed=False) == "fast"
    assert resolve_blueprint_depth("fast", deep_allowed=True) == "fast"
    assert resolve_blueprint_depth("fast", deep_allowed=False) == "fast"
    assert resolve_blueprint_depth(None, deep_allowed=False) == "fast"


def test_dossier_response_includes_deep_available():
    free = DossierResponse(status="ready", deep_available=False, stress_available=False)
    assert free.deep_available is False
    creator = DossierResponse(status="ready", deep_available=True, stress_available=True)
    assert creator.deep_available is True


# ---------------------------------------------------------------------------
# 生成路径：审稿/修订是否触发
# ---------------------------------------------------------------------------

class _FakePromptService:
    def __init__(self, session):
        pass

    async def get_prompt(self, name):
        return {
            "screenwriting": "SETTINGS_PROMPT",
            "screenwriting_outline": "OUTLINE_PROMPT",
        }.get(name)


def _settings_payload():
    return json.dumps({
        "title": "深度测试",
        "target_audience": "男频",
        "genre": "都市",
        "style": "爽文",
        "tone": "快",
        "one_sentence_summary": "卖点",
        "full_synopsis": "梗概",
        "world_setting": {"core_rules": "规则"},
        "golden_finger": {"name": "系统", "description": "d", "limitations": "l"},
        "characters": [
            {"name": "甲", "identity": "主角", "personality": "轴",
             "goals": "活", "abilities": "无", "relationship_to_protagonist": "本人"},
        ],
        "relationships": [],
        "foreshadowings": [
            {"name": f"伏{i}", "description": "d", "planted_chapter": i,
             "target_chapter": i + 10, "tier": "支线", "type": "hint",
             "reveal_method": "揭", "reveal_impact": "反转",
             "related_characters": ["甲"], "related_plots": []}
            for i in range(1, 4)
        ],
        "volumes": [
            {"name": "卷一", "start_chapter": 1, "end_chapter": 50,
             "arc_goal": "立足", "climax_hint": "翻案"},
        ],
    }, ensure_ascii=False)


def _outline_payload(numbers):
    return json.dumps({
        "chapter_outline": [
            {"chapter_number": n, "title": f"第{n}章", "summary": f"摘要{n}"}
            for n in numbers
        ]
    }, ensure_ascii=False)


def _patch_llm(monkeypatch):
    queue = [_settings_payload(), _outline_payload(range(1, 26)), _outline_payload(range(26, 51))]

    class _FakeLLM:
        def __init__(self, session):
            pass

        async def get_llm_response(self, **kwargs):
            return queue.pop(0)

    monkeypatch.setattr(bgs, "LLMService", _FakeLLM)
    monkeypatch.setattr(bgs, "PromptService", _FakePromptService)


async def _seed_project(db_session):
    db_session.add(NovelProject(id=PROJECT_ID, user_id=OWNER.id, title="旧标题"))
    db_session.add(NovelConversation(
        project_id=PROJECT_ID, seq=1, role="user",
        content=json.dumps({"value": "想写都市文"}, ensure_ascii=False),
    ))
    db_session.add(NovelConversation(
        project_id=PROJECT_ID, seq=2, role="assistant",
        content=json.dumps({"ai_message": "可以生成蓝图了"}, ensure_ascii=False),
    ))
    await db_session.commit()


class _SpyReviewer:
    def __init__(self, session, *, enabled=True, auto_revise=True, score=40):
        self.session = session
        self.enabled = enabled
        self.auto_revise = auto_revise
        self.review_calls = 0
        self.revise_settings_calls = 0
        self.revise_chapters_calls = 0
        self.score = score

    async def is_review_enabled(self):
        return self.enabled

    async def is_auto_revise_enabled(self):
        return self.auto_revise

    async def get_min_score(self):
        return 70

    async def review(self, **kwargs):
        self.review_calls += 1
        return BlueprintReviewReport(
            total_score=self.score,
            issues=[ReviewIssue(target="settings:title", problem="平", fix_hint="改")],
        )

    async def revise_settings_blocks(self, **kwargs):
        self.revise_settings_calls += 1
        return kwargs["settings_data"]

    async def revise_chapter_ranges(self, **kwargs):
        self.revise_chapters_calls += 1
        return kwargs["outline_items"]


def _install_spy(monkeypatch, spy):
    monkeypatch.setattr(
        "app.services.blueprint_review_service.BlueprintReviewService",
        lambda session: spy,
    )


async def _force_tier(monkeypatch, tier: str):
    async def fake_tier(session, user_id):
        return tier

    async def fake_min(session):
        from app.core.feature_gating import FEATURE_MIN_TIER
        return dict(FEATURE_MIN_TIER)

    monkeypatch.setattr(bgs, "get_user_tier", fake_tier)
    monkeypatch.setattr(bgs, "load_min_tiers", fake_min)


@pytest.mark.asyncio
async def test_fast_skips_review_and_revision(db_session, monkeypatch):
    _patch_llm(monkeypatch)
    await _seed_project(db_session)
    await _force_tier(monkeypatch, "creator")
    spy = _SpyReviewer(db_session)
    _install_spy(monkeypatch, spy)

    result = await bgs.generate_blueprint_for_project(
        db_session, PROJECT_ID, OWNER.id, depth="fast"
    )
    assert result.blueprint.title == "深度测试"
    assert spy.review_calls == 0
    assert spy.revise_settings_calls == 0
    assert spy.revise_chapters_calls == 0
    assert result.blueprint.review_report is None


@pytest.mark.asyncio
async def test_review_disabled_skips_even_on_deep(db_session, monkeypatch):
    _patch_llm(monkeypatch)
    await _seed_project(db_session)
    await _force_tier(monkeypatch, "creator")
    spy = _SpyReviewer(db_session, enabled=False)
    _install_spy(monkeypatch, spy)

    result = await bgs.generate_blueprint_for_project(
        db_session, PROJECT_ID, OWNER.id, depth="deep"
    )
    assert result.blueprint.title == "深度测试"
    assert spy.review_calls == 0
    assert spy.revise_settings_calls == 0
    assert result.blueprint.review_report is None


@pytest.mark.asyncio
async def test_auto_revise_off_reviews_but_does_not_revise(db_session, monkeypatch):
    _patch_llm(monkeypatch)
    await _seed_project(db_session)
    await _force_tier(monkeypatch, "creator")
    spy = _SpyReviewer(db_session, auto_revise=False, score=40)
    _install_spy(monkeypatch, spy)

    result = await bgs.generate_blueprint_for_project(
        db_session, PROJECT_ID, OWNER.id, depth="deep"
    )
    assert spy.review_calls == 1
    assert spy.revise_settings_calls == 0
    assert spy.revise_chapters_calls == 0
    assert result.blueprint.review_report is not None
    assert result.blueprint.review_report["total_score"] == 40
    assert result.blueprint.review_report["revised"] is False


@pytest.mark.asyncio
async def test_free_tier_silently_degrades_deep_to_fast(db_session, monkeypatch):
    _patch_llm(monkeypatch)
    await _seed_project(db_session)
    await _force_tier(monkeypatch, "free")
    spy = _SpyReviewer(db_session)
    _install_spy(monkeypatch, spy)

    result = await bgs.generate_blueprint_for_project(
        db_session, PROJECT_ID, OWNER.id, depth="deep"
    )
    assert result.blueprint.title == "深度测试"
    assert spy.review_calls == 0
    assert result.blueprint.review_report is None


@pytest.mark.asyncio
async def test_creator_deep_runs_review_and_revise(db_session, monkeypatch):
    _patch_llm(monkeypatch)
    await _seed_project(db_session)
    await _force_tier(monkeypatch, "creator")
    spy = _SpyReviewer(db_session, score=40)
    _install_spy(monkeypatch, spy)

    result = await bgs.generate_blueprint_for_project(
        db_session, PROJECT_ID, OWNER.id, depth="deep"
    )
    assert spy.review_calls == 2  # 初审 + 复审
    assert spy.revise_settings_calls == 1
    assert spy.revise_chapters_calls == 1
    assert result.blueprint.review_report["revised"] is True


# ---------------------------------------------------------------------------
# 开关读取
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_switches_default_and_config(db_session):
    service = BlueprintReviewService(db_session)
    assert await service.is_review_enabled() is True
    assert await service.is_auto_revise_enabled() is True

    db_session.add(SystemConfig(key=REVIEW_ENABLED_KEY, value="false"))
    db_session.add(SystemConfig(key=REVIEW_AUTO_REVISE_KEY, value="0"))
    await db_session.commit()
    assert await service.is_review_enabled() is False
    assert await service.is_auto_revise_enabled() is False


@pytest.mark.asyncio
async def test_review_honors_enabled_flag(db_session, monkeypatch):
    db_session.add(SystemConfig(key=REVIEW_ENABLED_KEY, value="false"))
    await db_session.commit()

    async def should_not_call(self, **kwargs):  # pragma: no cover
        raise AssertionError("review_enabled=false 不应调用 LLM")

    monkeypatch.setattr(LLMService, "generate_structured", should_not_call)
    report = await BlueprintReviewService(db_session).review(
        settings_data={"title": "t"},
        outline_items=[{"chapter_number": 1, "title": "t", "summary": "s"}],
        stress_report=None,
        dossier=None,
        user_id=7,
    )
    assert report is None


# ---------------------------------------------------------------------------
# task_worker 透传
# ---------------------------------------------------------------------------

class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.fixture(autouse=False)
def _stub_secret(monkeypatch):
    monkeypatch.setattr(task_worker.settings, "task_dispatcher_internal_callback_secret", "s3cret")


def test_task_worker_passes_config_depth(monkeypatch):
    monkeypatch.setattr(task_worker.settings, "task_dispatcher_internal_callback_secret", "s3cret")
    fake_session = SimpleNamespace()
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(fake_session))
    gen = AsyncMock(return_value=SimpleNamespace(model_dump=lambda: {"ok": True}))
    monkeypatch.setattr(task_worker, "generate_blueprint_for_project", gen)

    req = task_worker.WorkerTaskRequest(
        task_id="t-fast",
        task_type="blueprint:generate",
        project_id="p1",
        user_id=3,
        config=task_worker.TaskConfig(depth="fast"),
    )
    import asyncio
    resp = asyncio.run(task_worker.execute_task(req, x_internal_secret="s3cret"))
    assert resp.status == "completed"
    gen.assert_awaited_once_with(fake_session, "p1", 3, depth="fast")


def test_task_worker_missing_depth_defaults_deep(monkeypatch):
    monkeypatch.setattr(task_worker.settings, "task_dispatcher_internal_callback_secret", "s3cret")
    fake_session = SimpleNamespace()
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(fake_session))
    gen = AsyncMock(return_value=SimpleNamespace(model_dump=lambda: {"ok": True}))
    monkeypatch.setattr(task_worker, "generate_blueprint_for_project", gen)

    req = task_worker.WorkerTaskRequest(
        task_id="t-old",
        task_type="blueprint:generate",
        project_id="p1",
        user_id=3,
        config=task_worker.TaskConfig(),
    )
    import asyncio
    resp = asyncio.run(task_worker.execute_task(req, x_internal_secret="s3cret"))
    assert resp.status == "completed"
    gen.assert_awaited_once_with(fake_session, "p1", 3, depth="deep")


# ---------------------------------------------------------------------------
# dossier deep_available
# ---------------------------------------------------------------------------

def _dossier_client(db_session, user: UserInDB):
    test_app = FastAPI()
    test_app.include_router(novels.router)

    async def _override_session():
        yield db_session

    async def _override_user():
        return user

    test_app.dependency_overrides[get_session] = _override_session
    test_app.dependency_overrides[get_current_user] = _override_user
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


async def _seed_user_project(db_session, *, premium: bool, tier: str, user_id: int = 21):
    user = User(id=user_id, username=f"u{user_id}", hashed_password="x")
    project = NovelProject(
        id=f"dossier-{user_id}",
        user_id=user_id,
        title="立项",
        concept_dossier={"dossier": {"core_selling_line": "卖点"}, "generated_at": "t"},
    )
    quota = UserQuota(
        user_id=user_id,
        is_premium=premium,
        plan_tier=tier,
        premium_expires_at=(datetime.utcnow() + timedelta(days=10)) if premium else None,
    )
    db_session.add_all([user, project, quota])
    await db_session.commit()
    return UserInDB(id=user_id, username=user.username, hashed_password="x"), project.id


@pytest.mark.asyncio
async def test_dossier_deep_available_false_for_free(db_session):
    user, project_id = await _seed_user_project(db_session, premium=False, tier="free", user_id=21)
    async with _dossier_client(db_session, user) as client:
        resp = await client.get(f"/api/novels/{project_id}/concept/dossier")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["deep_available"] is False
    assert body["stress_available"] is False


@pytest.mark.asyncio
async def test_dossier_deep_available_true_for_creator(db_session):
    user, project_id = await _seed_user_project(db_session, premium=True, tier="creator", user_id=22)
    async with _dossier_client(db_session, user) as client:
        resp = await client.get(f"/api/novels/{project_id}/concept/dossier")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["deep_available"] is True
    assert body["stress_available"] is True
