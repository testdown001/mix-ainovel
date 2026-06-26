"""
Go Task Dispatcher Worker 适配器

接收来自 Go Task Dispatcher 的 HTTP 任务请求，
执行章节生成逻辑，返回结果。

新增 API:
  POST /api/internal/tasks/execute  - 执行任务（由 Go Dispatcher 调用）
"""
import asyncio
import hmac
import logging
import time
import traceback
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import update

from ...agents.hybrid_executor import HybridExecutor
from ...core.config import settings
from ...core.feature_gating import (
    ensure_flow_overrides_allowed,
    ensure_generation_preset_allowed,
    get_user_tier,
)
from ...db.session import AsyncSessionLocal
from ...models.novel import Chapter
from ...services.novel_service import NovelService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/tasks", tags=["internal"])


# ============================================================
# 请求/响应模型
# ============================================================

class TaskConfig(BaseModel):
    preset: str = "fast"
    use_agent_system: bool = False
    rag_mode: str = "simple"
    writing_notes: str = ""
    extra: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _drop_nulls(cls, data):
        # Go 网关的 nil map/空值序列化为 JSON null（如 extra:null），而这些字段非 Optional、
        # 显式 null 会被 Pydantic 拒绝(422)。丢弃 null 项使其回落到各自默认值，容忍网关的序列化。
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v is not None}
        return data


class WorkerTaskRequest(BaseModel):
    task_id: str
    task_type: str
    project_id: str
    chapter_number: Optional[int] = None
    chapter_numbers: Optional[list[int]] = None
    user_id: int
    config: TaskConfig = Field(default_factory=TaskConfig)
    callback_url: Optional[str] = None


class WorkerTaskResponse(BaseModel):
    status: str  # completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    # 确定性失败（如档位门控 403）：Go dispatcher 看到该标记不再重试
    permanent: bool = False


# ============================================================
# 进度回调
# ============================================================

class ProgressReporter:
    """向 Go Task Dispatcher 报告进度"""

    def __init__(self, callback_url: Optional[str], task_id: str):
        self.callback_url = callback_url
        self.task_id = task_id
        self._client: Optional[httpx.AsyncClient] = None

    async def report(self, progress: int, stage: str, message: str):
        """报告进度"""
        if not self.callback_url:
            return

        try:
            if self._client is None:
                self._client = httpx.AsyncClient(timeout=5.0)

            headers = {}
            if settings.task_dispatcher_internal_callback_secret:
                headers["X-Internal-Secret"] = settings.task_dispatcher_internal_callback_secret

            await self._client.post(
                self.callback_url,
                headers=headers,
                json={
                    "progress": progress,
                    "stage": stage,
                    "message": message,
                },
            )
        except Exception as e:
            logger.debug(f"进度回调失败 (task={self.task_id}): {e}")

    async def close(self):
        if self._client:
            await self._client.aclose()


# 生成阶段关键词 → 进度百分比（取最大匹配，单调不回退，封顶 79，留给后处理/收尾 80~100）
_STAGE_PROGRESS_KEYWORDS = [
    ("写入", 85), ("持久", 85), ("保存", 85),
    ("审核", 70), ("评审", 70), ("质量", 70),
    ("版本", 58), ("多版本", 55), ("场景", 55), ("正文", 50), ("写作", 48),
    ("组装", 44), ("上下文", 40),
    ("检索", 32), ("证据", 32), ("RAG", 32),
    ("设定", 28), ("世界观", 28),
    ("规划", 26), ("计划", 26), ("策略", 26),
    ("解析", 24), ("需求", 24),
    ("开始", 22), ("准备", 22),
]


def _build_stage_progress_forwarder(reporter: "ProgressReporter"):
    """返回一个 stream_handler：把生成管线的 "stage" 事件实时转发为任务进度。

    异步路径(Go 网关调度)默认只在生成前后报 4 个粗进度点，长生成期间静默，前端因此卡在
    "正在生成章节..."像"转后台"。本转发器把管线逐阶段 telemetry(starting/上下文组装/
    多版本生成/写入版本等)实时上报，使前端 WS 看到细粒度阶段。text_delta/中间产物等
    非阶段事件忽略(异步路径不展示逐字草稿)。进度按关键词映射、单调不回退、封顶 79。
    """
    state = {"pct": 20}

    async def _handler(data: Dict[str, Any]) -> None:
        if not isinstance(data, dict) or data.get("event") != "stage":
            return
        stage = str(data.get("stage") or "")
        message = str(data.get("message") or stage) or "生成中..."
        text = f"{stage}{message}"
        best = state["pct"]
        for kw, pct in _STAGE_PROGRESS_KEYWORDS:
            if kw in text and pct > best:
                best = pct
        state["pct"] = min(79, best)
        await reporter.report(state["pct"], stage or "generating", message)

    return _handler


# ============================================================
# API 端点
# ============================================================

def _verify_internal_secret(provided):
    expected = settings.task_dispatcher_internal_callback_secret
    if not expected:
        raise HTTPException(status_code=503, detail="内部任务端点未启用：缺少 task_dispatcher_internal_callback_secret 配置")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="未授权的内部任务调用")


@router.post("/execute", response_model=WorkerTaskResponse)
async def _reset_generating_chapters_to_failed(req: "WorkerTaskRequest") -> None:
    """任务失败时，把本任务相关、仍停在 generating 的章节回写 failed（独立 session、
    best-effort）。异步路径下 worker 抛错只会向网关返回 failed，**不写章节表**——若不回写，
    章节会永久卡在 generating，前端一直显示"等待生成"。只更新仍 generating 的行，
    不覆盖已成功/待选状态，也不创建新行。"""
    if req.task_type not in ("chapter:generate", "chapter:batch_generate"):
        return
    numbers = set()
    if req.chapter_number is not None:
        numbers.add(req.chapter_number)
    for n in (req.chapter_numbers or []):
        numbers.add(n)
    if not numbers:
        return
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Chapter)
                .where(
                    Chapter.project_id == req.project_id,
                    Chapter.chapter_number.in_(numbers),
                    Chapter.status == "generating",
                )
                .values(status="failed")
            )
            await session.commit()
        logger.info("任务 %s 失败，已将仍在 generating 的章节 %s 回写 failed", req.task_id, sorted(numbers))
    except Exception as exc:  # pragma: no cover - 回写失败不影响主流程
        logger.warning("回写章节 failed 状态失败(已忽略): %s", exc)


async def execute_task(req: WorkerTaskRequest, x_internal_secret: Optional[str] = Header(default=None, alias="X-Internal-Secret")):
    """
    执行来自 Go Task Dispatcher 的任务

    此接口由 Go Task Dispatcher 调用，不对外暴露。
    """
    _verify_internal_secret(x_internal_secret)

    start_time = time.time()
    reporter = ProgressReporter(req.callback_url, req.task_id)

    try:
        logger.info(
            f"收到任务: task_id={req.task_id}, type={req.task_type}, "
            f"project={req.project_id}, chapter={req.chapter_number}"
        )

        # 会员档位门控：异步入口与 /advanced/generate 同一套判定，
        # 否则经 Go 网关提交任务即可绕过预设档位限制
        if req.task_type in ("chapter:generate", "chapter:batch_generate"):
            async with AsyncSessionLocal() as gate_session:
                tier = await get_user_tier(gate_session, req.user_id)
                try:
                    await ensure_generation_preset_allowed(gate_session, req.config.preset, tier)
                    # config.extra 会原样并入 flow_config，受控开关同样要过档位
                    await ensure_flow_overrides_allowed(gate_session, req.config.extra, tier)
                except HTTPException as exc:
                    return WorkerTaskResponse(status="failed", error=str(exc.detail), permanent=True)

        if req.task_type == "chapter:generate":
            result = await _execute_chapter_generate(req, reporter)
        elif req.task_type == "chapter:batch_generate":
            result = await _execute_batch_generate(req, reporter)
        else:
            return WorkerTaskResponse(
                status="failed",
                error=f"未知任务类型: {req.task_type}",
            )

        duration_ms = int((time.time() - start_time) * 1000)

        return WorkerTaskResponse(
            status="completed",
            result=result,
            duration_ms=duration_ms,
        )

    # 同时捕获 CancelledError（生成超时/时间预算触发取消，属 BaseException，
    # 不在 except Exception 内）——否则它会逃逸成 HTTP 500，导致网关 3× 重试且章节卡死。
    # 排除 KeyboardInterrupt/SystemExit（进程级信号应正常传播）。
    except (Exception, asyncio.CancelledError) as e:
        duration_ms = int((time.time() - start_time) * 1000)
        err_label = f"{type(e).__name__}: {e}".strip() or type(e).__name__
        logger.error(f"任务执行失败: {err_label}\n{traceback.format_exc()}")

        # 把仍卡在 generating 的章节回写 failed。用 shield 确保即便本任务正被取消
        # (CancelledError)，复位也能跑完；并吞掉取消导致的二次抛出——否则在已取消的
        # 任务里再 await 会立刻重抛 CancelledError，逃逸成 HTTP 500。
        try:
            await asyncio.shield(_reset_generating_chapters_to_failed(req))
        except BaseException:  # noqa: BLE001 - 复位失败/取消都不应阻断优雅返回
            pass

        # 向网关优雅返回 failed（HTTP 200）而非裸奔 500：网关据此判失败、不再无谓重试
        return WorkerTaskResponse(
            status="failed",
            error=err_label[:500],
            duration_ms=duration_ms,
        )

    finally:
        # finally 内 await 抛出会覆盖返回值 → 500，故吞掉关闭异常
        try:
            await reporter.close()
        except BaseException:  # noqa: BLE001
            pass


# ============================================================
# 任务执行逻辑
# ============================================================

async def _execute_chapter_generate(
    req: WorkerTaskRequest,
    reporter: ProgressReporter,
) -> Dict[str, Any]:
    """执行章节生成"""
    if req.chapter_number is None:
        raise ValueError("章节生成任务缺少 chapter_number")

    async with AsyncSessionLocal() as session:
        novel_service = NovelService(session)
        await novel_service.ensure_project_owner(req.project_id, req.user_id)
        chapter = await novel_service.get_or_create_chapter(req.project_id, req.chapter_number)
        chapter.status = "generating"
        await session.commit()

        await reporter.report(10, "context_assembly", "正在收集上下文...")
        await reporter.report(20, "llm_generation", "正在生成章节...")

        config = req.config
        flow_config: Dict[str, Any] = dict(config.extra or {})
        flow_config.update({
            "preset": config.preset,
            "rag_mode": config.rag_mode,
            "use_agent": config.use_agent_system,
        })

        # 把生成管线的分阶段 telemetry 实时转发为任务进度，避免前端卡在"正在生成章节..."
        # 静默数分钟(异步路径无逐字草稿，但阶段进度必须实时)。
        _stage_stream_handler = _build_stage_progress_forwarder(reporter)

        executor = HybridExecutor(session, user_id=req.user_id)
        if config.use_agent_system:
            executor.enable_agent_system()

        result = await executor.generate_chapter(
            use_agent=config.use_agent_system,
            project_id=req.project_id,
            chapter_number=req.chapter_number,
            writing_notes=config.writing_notes or None,
            flow_config=flow_config,
            stream_handler=_stage_stream_handler,
        )

        await reporter.report(80, "post_processing", "正在后处理...")

        await session.commit()

        await reporter.report(100, "completed", "章节生成完成")

        return {
            "chapter_id": chapter.id,
            "chapter_number": req.chapter_number,
            "status": "completed",
            "versions_count": len(result.get("variants", [])),
            "best_version_index": result.get("best_version_index", 0),
            "preset": result.get("preset", config.preset),
        }


async def _execute_batch_generate(
    req: WorkerTaskRequest,
    reporter: ProgressReporter,
) -> Dict[str, Any]:
    """执行批量生成"""
    results = []
    total = len(req.chapter_numbers or [])

    for idx, chapter_number in enumerate(req.chapter_numbers or []):
        try:
            progress = int((idx / total) * 100)
            await reporter.report(
                progress,
                "batch_generating",
                f"正在生成第 {chapter_number} 章 ({idx + 1}/{total})",
            )

            # 创建单章请求
            single_req = WorkerTaskRequest(
                task_id=req.task_id,
                task_type="chapter:generate",
                project_id=req.project_id,
                chapter_number=chapter_number,
                user_id=req.user_id,
                config=req.config,
                callback_url=None,  # 批量任务由外层统一报告
            )

            single_reporter = ProgressReporter(None, req.task_id)
            result = await _execute_chapter_generate(single_req, single_reporter)
            results.append({
                "chapter_number": chapter_number,
                "status": "success",
                "result": result,
            })

        except Exception as e:
            logger.error(f"章节 {chapter_number} 生成失败: {e}")
            results.append({
                "chapter_number": chapter_number,
                "status": "failed",
                "error": str(e),
            })

    return {
        "project_id": req.project_id,
        "total": total,
        "results": results,
        "status": "completed",
    }
