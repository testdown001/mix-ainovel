"""蓝图生成异步任务化（blueprint:generate worker 分支）测试。

覆盖：
- execute_task 对 blueprint:generate 的成功分支（复用 blueprint_generation_service，
  且不触碰章节任务的档位门控/积分计费）
- HTTPException（400/409/403 等确定性失败）→ permanent=True，Go dispatcher 不重试
- 普通异常 → permanent=False（可重试），且不逃逸为 HTTP 500
- 路由绑定回归：/api/internal/tasks/execute 仍绑定 execute_task 本身，
  新增的 _execute_blueprint_generate 未被错绑为路由
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.routers import task_worker


@pytest.fixture(autouse=True)
def _stub_internal_secret(monkeypatch):
    monkeypatch.setattr(task_worker.settings, "task_dispatcher_internal_callback_secret", "s3cret")


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return None


def _blueprint_req() -> task_worker.WorkerTaskRequest:
    # Go 网关 executeBlueprintGenerate 只带 project_id/user_id + 空 config
    return task_worker.WorkerTaskRequest(
        task_id="task-bp-1",
        task_type="blueprint:generate",
        project_id="project-1",
        user_id=12,
    )


def test_execute_task_blueprint_success_skips_chapter_gate(monkeypatch):
    fake_session = SimpleNamespace()
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(fake_session))

    fake_result = {"blueprint": {"title": "测试书名"}, "ai_message": "蓝图已生成"}
    fake_response = SimpleNamespace(model_dump=lambda: fake_result)
    gen = AsyncMock(return_value=fake_response)
    monkeypatch.setattr(task_worker, "generate_blueprint_for_project", gen)

    # 蓝图任务不得进入章节任务的档位门控/章节积分计费分支
    gate = AsyncMock(side_effect=AssertionError("蓝图任务不应调用档位门控"))
    charge = AsyncMock(side_effect=AssertionError("蓝图任务不应走章节扣费"))
    monkeypatch.setattr(task_worker, "ensure_generation_preset_allowed", gate)
    monkeypatch.setattr(task_worker, "charge_generation", charge)
    # 本用例不测深度扣费：默认判定为不扣（快速等价 / 审稿门关）
    monkeypatch.setattr(task_worker, "should_charge_blueprint_deep", AsyncMock(return_value=False))
    monkeypatch.setattr(
        task_worker, "charge_blueprint_deep",
        AsyncMock(side_effect=AssertionError("不应扣深度打磨积分")),
    )

    resp = asyncio.run(task_worker.execute_task(_blueprint_req(), x_internal_secret="s3cret"))

    assert resp.status == "completed"
    assert resp.result == fake_result
    assert resp.permanent is False
    gen.assert_awaited_once_with(fake_session, "project-1", 12, depth="deep", paid_deep=False)
    gate.assert_not_awaited()
    charge.assert_not_awaited()


def test_execute_task_blueprint_http_exception_is_permanent(monkeypatch):
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(SimpleNamespace()))
    monkeypatch.setattr(task_worker, "should_charge_blueprint_deep", AsyncMock(return_value=False))
    refund = AsyncMock(return_value=0)
    monkeypatch.setattr(task_worker, "refund_generation", refund)
    gen = AsyncMock(
        side_effect=HTTPException(status_code=409, detail="项目已有章节创作成果，已阻止操作。")
    )
    monkeypatch.setattr(task_worker, "generate_blueprint_for_project", gen)

    resp = asyncio.run(task_worker.execute_task(_blueprint_req(), x_internal_secret="s3cret"))

    assert resp.status == "failed"
    assert resp.permanent is True
    assert "章节创作成果" in (resp.error or "")
    refund.assert_awaited()


def test_execute_task_blueprint_generic_error_is_retryable(monkeypatch):
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(SimpleNamespace()))
    monkeypatch.setattr(task_worker, "should_charge_blueprint_deep", AsyncMock(return_value=False))
    gen = AsyncMock(side_effect=RuntimeError("LLM 通道超时"))
    monkeypatch.setattr(task_worker, "generate_blueprint_for_project", gen)
    # 通用失败路径会走幂等退款（蓝图未扣过积分应为 no-op）；桩掉避免真实调用
    refund = AsyncMock()
    monkeypatch.setattr(task_worker, "refund_generation", refund)

    resp = asyncio.run(task_worker.execute_task(_blueprint_req(), x_internal_secret="s3cret"))

    assert resp.status == "failed"
    assert resp.permanent is False
    assert "LLM 通道超时" in (resp.error or "")


def _blueprint_req_fast() -> task_worker.WorkerTaskRequest:
    return task_worker.WorkerTaskRequest(
        task_id="task-bp-fast",
        task_type="blueprint:generate",
        project_id="project-1",
        user_id=12,
        config=task_worker.TaskConfig(depth="fast"),
    )


def test_execute_task_blueprint_deep_charges_then_passes_paid_deep(monkeypatch):
    fake_session = SimpleNamespace()
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(fake_session))
    fake_result = {"blueprint": {"title": "深打磨"}, "ai_message": "ok"}
    gen = AsyncMock(return_value=SimpleNamespace(model_dump=lambda: fake_result))
    monkeypatch.setattr(task_worker, "generate_blueprint_for_project", gen)
    monkeypatch.setattr(task_worker, "should_charge_blueprint_deep", AsyncMock(return_value=True))
    charge = AsyncMock(return_value=20)
    monkeypatch.setattr(task_worker, "charge_blueprint_deep", charge)

    resp = asyncio.run(task_worker.execute_task(_blueprint_req(), x_internal_secret="s3cret"))

    assert resp.status == "completed"
    charge.assert_awaited_once()
    assert charge.await_args.kwargs.get("ref_key") == "task-bp-1"
    gen.assert_awaited_once_with(fake_session, "project-1", 12, depth="deep", paid_deep=True)


def test_execute_task_blueprint_deep_insufficient_is_permanent_no_generate(monkeypatch):
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(SimpleNamespace()))
    monkeypatch.setattr(task_worker, "should_charge_blueprint_deep", AsyncMock(return_value=True))
    monkeypatch.setattr(
        task_worker,
        "charge_blueprint_deep",
        AsyncMock(side_effect=HTTPException(status_code=402, detail="积分不足：本次需 20 积分，剩余 0。")),
    )
    gen = AsyncMock(side_effect=AssertionError("积分不足不应进入生成"))
    monkeypatch.setattr(task_worker, "generate_blueprint_for_project", gen)

    resp = asyncio.run(task_worker.execute_task(_blueprint_req(), x_internal_secret="s3cret"))

    assert resp.status == "failed"
    assert resp.permanent is True
    assert "积分不足" in (resp.error or "")
    gen.assert_not_awaited()


def test_execute_task_blueprint_failure_after_charge_refunds(monkeypatch):
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(SimpleNamespace()))
    monkeypatch.setattr(task_worker, "should_charge_blueprint_deep", AsyncMock(return_value=True))
    monkeypatch.setattr(task_worker, "charge_blueprint_deep", AsyncMock(return_value=20))
    gen = AsyncMock(side_effect=RuntimeError("LLM 通道超时"))
    monkeypatch.setattr(task_worker, "generate_blueprint_for_project", gen)
    refund = AsyncMock(return_value=20)
    monkeypatch.setattr(task_worker, "refund_generation", refund)

    resp = asyncio.run(task_worker.execute_task(_blueprint_req(), x_internal_secret="s3cret"))

    assert resp.status == "failed"
    refund.assert_awaited()
    assert refund.await_args.kwargs.get("ref_key") == "task-bp-1"


def test_execute_task_blueprint_fast_does_not_charge(monkeypatch):
    fake_session = SimpleNamespace()
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(fake_session))
    should = AsyncMock(return_value=False)
    monkeypatch.setattr(task_worker, "should_charge_blueprint_deep", should)
    charge = AsyncMock(side_effect=AssertionError("快速成书不应扣费"))
    monkeypatch.setattr(task_worker, "charge_blueprint_deep", charge)
    gen = AsyncMock(return_value=SimpleNamespace(model_dump=lambda: {"blueprint": {}}))
    monkeypatch.setattr(task_worker, "generate_blueprint_for_project", gen)

    resp = asyncio.run(task_worker.execute_task(_blueprint_req_fast(), x_internal_secret="s3cret"))

    assert resp.status == "completed"
    should.assert_awaited()
    assert should.await_args.args[2] == "fast"
    charge.assert_not_awaited()
    gen.assert_awaited_once_with(fake_session, "project-1", 12, depth="fast", paid_deep=False)


def test_execute_route_still_bound_to_execute_task():
    """回归：新增 _execute_blueprint_generate 后 /api/internal/tasks/execute 必须仍绑
    execute_task 本身（历史教训：新函数插在 @router.post 与函数之间会错绑路由）。"""
    routes = task_worker.router.routes
    execute_routes = [r for r in routes if getattr(r, "endpoint", None) is task_worker.execute_task]
    assert execute_routes, "execute_task 未注册为路由（@router.post 可能被错绑到其它函数）"
    assert execute_routes[0].path == "/api/internal/tasks/execute"
    # 新增的蓝图执行函数是内部 helper，绝不能出现在路由表里
    assert not any(
        getattr(r, "endpoint", None) is task_worker._execute_blueprint_generate for r in routes
    )
