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
from sqlalchemy import case, select, update

from ...agents.hybrid_executor import HybridExecutor
from ...core.config import settings
from ...core.feature_gating import (
    ensure_flow_overrides_allowed,
    ensure_generation_preset_allowed,
    ensure_model_allowed,
    get_user_tier,
)
from ...core.safe_task import safe_create_task
from ...db.session import AsyncSessionLocal
from ...models.novel import Chapter
from ...services.blueprint_generation_service import generate_blueprint_for_project
from ...services.batch_generation_service import BatchGenerationService
from ...services.cache_service import CacheService
from ...services.generation_billing_service import (
    charge_blueprint_deep,
    charge_generation,
    polish_undelivered,
    refund_generation,
    refund_polish_surcharge,
    should_charge_blueprint_deep,
)
from ...services.generation_write_task_service import GenerationWriteTaskService
from ...services.mission_pregen_service import pregen_next_chapter_mission
from ...services.novel_service import NovelService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/tasks", tags=["internal"])


async def _watch_task_cancellation(task_id: str, running_task: "asyncio.Task[Any]") -> None:
    """跨进程监听网关写入的取消标记，并取消真正执行生成的 Python 协程。

    仅关闭 Go→FastAPI 的 HTTP socket 不足以保证 ASGI handler 停止；共享 Redis 标记
    可让请求落到任意 app 副本时都在 1 秒内终止模型调用，并进入既有退款/状态收束路径。
    Redis 短暂不可用时按“未取消”处理，避免观测故障误杀正常任务。
    """
    cache = CacheService()
    cancel_key = f"arboris:task_cancel:{task_id}"
    try:
        while not running_task.done():
            await asyncio.sleep(0.5)
            if await cache.exists(cancel_key):
                running_task.cancel()
                return
    except asyncio.CancelledError:
        return
    except Exception as exc:  # pragma: no cover - 旁路监听失败不影响生成
        logger.warning("任务取消监听失败(已忽略): task_id=%s error=%s", task_id, exc)


# ============================================================
# 请求/响应模型
# ============================================================

class TaskConfig(BaseModel):
    preset: str = "fast"
    use_agent_system: bool = False
    rag_mode: str = "simple"
    writing_notes: str = ""
    depth: str = "deep"
    auto_select: bool = False
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

    async def report(self, progress: int, stage: str, message: str, checkpoint: Optional[Dict[str, Any]] = None):
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
                    **({"checkpoint": checkpoint} if checkpoint is not None else {}),
                },
            )
        except Exception as e:
            logger.debug(f"进度回调失败 (task={self.task_id}): {e}")

    async def close(self):
        if self._client:
            await self._client.aclose()


# 生成阶段 key → 进度百分比。key 是管线发出的稳定标识（starting / generate_versions /
# post_consistency…），前端 utils/generationStages.ts 用同一套词汇表映射显示文案。
# 此前这里只有下面那张中文关键词表，靠在 message 正文里找「审核」「写入」这类词猜进度：
# 谁改一句阶段文案，进度条就悄悄失准，而且和前端那张各写各的。
_STAGE_PROGRESS: dict[str, int] = {
    "starting": 22,
    "prepare_context": 28,
    "generate_chapter_mission": 34,
    "build_generation_prompt": 40,
    "generate_fast_version": 50,
    "generate_versions": 50,
    "generate_scene_by_scene": 50,
    "post_combined_revision": 58,
    "post_consistency": 62,
    "post_humanization": 64,
    "post_optimizer": 66,
    "post_polish": 68,
    "post_enrichment": 70,
    "post_density_compression": 72,
    "post_six_dimension": 74,
    "post_auto_refine": 76,
    "post_six_dimension_rescore": 77,
    "post_guardrail_rewrite": 78,
    "persist_versions": 79,
}

# 关键词兜底：agent:* 等没进上表的阶段仍按中文关键词估算，保持 Agent 模式的旧行为
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
        best = state["pct"]
        mapped = _STAGE_PROGRESS.get(stage)
        if mapped is not None:
            best = max(best, mapped)
        else:
            text = f"{stage}{message}"
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


async def _reset_generating_chapters_to_failed(req: "WorkerTaskRequest") -> None:
    """任务失败时，逐章收束本任务留下的 ``generating`` 状态。

    已经有选中正文的章节仍然是可交付成果，后续重试失败不能把它降级成“生成失败”；
    这类行恢复为 ``successful``。只有从未产出选中正文的章节才落 ``failed``。
    SQL 的条件与 CASE 在同一条 UPDATE 中执行，避免先读后写覆盖并发选版结果。
    """
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
                .values(
                    status=case(
                        (Chapter.selected_version_id.is_not(None), "successful"),
                        else_="failed",
                    )
                )
            )
            await session.commit()
        await CacheService.invalidate_project_schema_safely(req.project_id)
        logger.info("任务 %s 失败，已逐章收束 generating 状态: %s", req.task_id, sorted(numbers))
    except Exception as exc:  # pragma: no cover - 回写失败不影响主流程
        logger.warning("回写章节 failed 状态失败(已忽略): %s", exc)


@router.post("/execute", response_model=WorkerTaskResponse)
async def execute_task(req: WorkerTaskRequest, x_internal_secret: Optional[str] = Header(default=None, alias="X-Internal-Secret")):
    """
    执行来自 Go Task Dispatcher 的任务

    此接口由 Go Task Dispatcher 调用，不对外暴露。
    """
    _verify_internal_secret(x_internal_secret)

    start_time = time.time()
    reporter = ProgressReporter(req.callback_url, req.task_id)
    running_task = asyncio.current_task()
    cancel_watcher = (
        asyncio.create_task(
            _watch_task_cancellation(req.task_id, running_task),
            name=f"task-cancel-watch-{req.task_id}",
        )
        if running_task is not None
        else None
    )

    try:
        logger.info(
            f"收到任务: task_id={req.task_id}, type={req.task_type}, "
            f"project={req.project_id}, chapter={req.chapter_number}"
        )

        # 会员档位门控：异步入口与 /advanced/generate 同一套判定，
        # 否则经 Go 网关提交任务即可绕过预设档位限制
        if req.task_type in ("chapter:generate", "chapter:batch_generate"):
            extra = req.config.extra or {}
            model_code = extra.get("model_code")
            # literary 分支（enable_scene_by_scene）的后处理链不含 polish 步，
            # 勾选也不会执行——不收附加费（收了必须交付，交付不了就不收）
            enable_polish = bool(extra.get("enable_polish")) and not bool(
                extra.get("enable_scene_by_scene")
            )
            chapters = len(req.chapter_numbers) if req.chapter_numbers else 1
            async with AsyncSessionLocal() as gate_session:
                tier = await get_user_tier(gate_session, req.user_id)
                try:
                    await ensure_generation_preset_allowed(gate_session, req.config.preset, tier)
                    # config.extra 会原样并入 flow_config，受控开关同样要过档位
                    await ensure_flow_overrides_allowed(gate_session, req.config.extra, tier)
                    # 模型按档门控 + 先扣后跑积分（model_code 缺省时均 no-op，向后兼容）
                    await ensure_model_allowed(gate_session, model_code, tier)
                    await charge_generation(
                        gate_session, req.user_id, model_code, enable_polish,
                        ref_key=req.task_id, chapters=chapters,
                    )
                except HTTPException as exc:
                    # 403 档位/模型不够、402 积分不足：均不应重试
                    return WorkerTaskResponse(status="failed", error=str(exc.detail), permanent=True)

        if req.task_type == "chapter:generate":
            result = await _execute_chapter_generate(req, reporter)
            if req.config.auto_select and req.chapter_number is not None:
                selected_version_id = await _select_batch_generated_chapter(
                    req,
                    req.chapter_number,
                    int(result.get("best_version_index", 0) or 0),
                )
                result["selected_version_id"] = selected_version_id
        elif req.task_type == "chapter:batch_generate":
            result = await _execute_batch_generate(req, reporter)
        elif req.task_type == "blueprint:generate":
            # 深度打磨先扣后跑（与章节路径同口径）；快速成书/降级/审稿门关闭不扣。
            # 402 积分不足 → permanent，避免网关重试空烧。
            depth = (req.config.depth or "deep") if req.config else "deep"
            blueprint_paid = False
            try:
                async with AsyncSessionLocal() as gate_session:
                    if await should_charge_blueprint_deep(gate_session, req.user_id, depth):
                        charged = await charge_blueprint_deep(
                            gate_session, req.user_id, ref_key=req.task_id
                        )
                        blueprint_paid = charged > 0
            except HTTPException as exc:
                return WorkerTaskResponse(status="failed", error=str(exc.detail), permanent=True)
            try:
                result = await _execute_blueprint_generate(
                    req, reporter, paid_deep=blueprint_paid
                )
            except HTTPException as exc:
                # 按状态码区分：4xx（403 非所有者/400 缺对话历史/409 已有章节成果）是
                # 确定性失败，重试无意义 → permanent；500/502（LLM 坏 JSON/章纲不完整）
                # 是概率性失败 → 走普通 failed 让 Go dispatcher 重试
                # 本分支直接 return，进不了外层 except 的退款，这里补一次（未扣过 no-op）
                try:
                    async with AsyncSessionLocal() as _refund_session:
                        await asyncio.shield(
                            refund_generation(_refund_session, req.user_id, ref_key=req.task_id)
                        )
                except BaseException:  # noqa: BLE001
                    pass
                permanent = exc.status_code < 500
                return WorkerTaskResponse(status="failed", error=str(exc.detail), permanent=permanent)
        else:
            return WorkerTaskResponse(
                status="failed",
                error=f"未知任务类型: {req.task_type}",
            )

        duration_ms = int((time.time() - start_time) * 1000)

        # literary 场景级降级：部分场景缺失的残章仍按 completed 交付（内容保留），
        # 但已扣积分全额退还——收了钱必须交付完整章（batch 路径整批一笔扣费、
        # 无法按章拆退，暂不处理，literary 批量场景极少）
        if (
            req.task_type == "chapter:generate"
            and isinstance(result, dict)
            and result.get("missing_scenes")
        ):
            try:
                async with AsyncSessionLocal() as _refund_session:
                    refunded = await asyncio.shield(
                        refund_generation(_refund_session, req.user_id, ref_key=req.task_id)
                    )
                result["degraded"] = True
                if refunded:
                    logger.warning(
                        "任务 %s 残章降级（缺失场景 %s），已全额退还积分 %d",
                        req.task_id, result["missing_scenes"], refunded,
                    )
            except Exception:
                logger.warning("残章退款检查失败（不影响任务交付）", exc_info=True)

        # 润色未兑现：章节交付了，但勾选并已计费的润色实际没生效（通道故障/空响应/
        # 产出非正文/合并进 optimizer 而 optimizer 失败）→ 只退这笔附加费。
        # 与上面的残章全额退款互斥（refund_polish_surcharge 内部已判定）。
        elif req.task_type in ("chapter:generate", "chapter:batch_generate"):
            try:
                unpolished = _count_unpolished(req.task_type, result)
                if unpolished:
                    async with AsyncSessionLocal() as _refund_session:
                        await asyncio.shield(
                            refund_polish_surcharge(
                                _refund_session, req.user_id,
                                ref_key=req.task_id, chapters=unpolished,
                            )
                        )
            except Exception:
                logger.warning("润色退款检查失败（不影响任务交付）", exc_info=True)

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
            # 批量循环会在每一章自己的异常边界内收束状态。这里不能再拿整个章节列表
            # 做批次级覆盖，否则一个基础设施异常会把其它章节的结果一起判失败。
            if req.task_type != "chapter:batch_generate":
                await asyncio.shield(_reset_generating_chapters_to_failed(req))
        except BaseException:  # noqa: BLE001 - 复位失败/取消都不应阻断优雅返回
            pass

        # 失败/取消退还已扣积分（按 task_id 幂等；未扣过则 no-op）
        try:
            async with AsyncSessionLocal() as _refund_session:
                await asyncio.shield(refund_generation(_refund_session, req.user_id, ref_key=req.task_id))
        except BaseException:  # noqa: BLE001
            pass

        # 向网关优雅返回 failed（HTTP 200）而非裸奔 500：网关据此判失败、不再无谓重试
        return WorkerTaskResponse(
            status="failed",
            error=err_label[:500],
            duration_ms=duration_ms,
        )

    finally:
        if cancel_watcher is not None:
            cancel_watcher.cancel()
            try:
                await cancel_watcher
            except BaseException:  # noqa: BLE001 - 收尾不能覆盖任务返回值
                pass
        # finally 内 await 抛出会覆盖返回值 → 500，故吞掉关闭异常
        try:
            await reporter.close()
        except BaseException:  # noqa: BLE001
            pass


# ============================================================
# 任务执行逻辑
# ============================================================

def _skipped_for_budget(result: Any) -> list:
    """管线因时间预算跳过的后处理步骤名（没有就空列表）。

    review_summaries 不进异步 payload，结论得在这里取出来带走——与 missing_scenes /
    polish_undelivered 同一套做法。
    """
    if not isinstance(result, dict):
        return []
    for variant in result.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        summaries = (variant.get("metadata") or {}).get("review_summaries") or {}
        budget = summaries.get("time_budget") if isinstance(summaries, dict) else None
        if isinstance(budget, dict) and budget.get("skipped"):
            return list(budget["skipped"])
    return []


def _count_unpolished(task_type: str, result: Any) -> int:
    """本次任务里「已计费但润色没兑现」的章数（单章 0/1，批量按章计）。"""
    if not isinstance(result, dict):
        return 0
    if task_type == "chapter:generate":
        return 1 if result.get("polish_undelivered") else 0
    return sum(
        1
        for item in (result.get("results") or [])
        if isinstance(item, dict)
        and item.get("status") == "success"
        and isinstance(item.get("result"), dict)
        and item["result"].get("polish_undelivered")
    )


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
        # 项目详情缓存里存着章节状态，直接改 ORM 不会让它失效（30 分钟 TTL 内前端
        # 刷新看到的仍是旧状态，既不提示后台在跑也不拦重复点击）
        await CacheService.invalidate_project_schema_safely(req.project_id)

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

        # literary 场景级降级信号：任一版本 metadata 带 missing_scenes 即上报，
        # 供 execute_task 成功路径做"残章退款"判定
        missing_scenes: list = []
        for variant in result.get("variants") or []:
            if isinstance(variant, dict):
                scenes = (variant.get("metadata") or {}).get("missing_scenes")
                if scenes:
                    missing_scenes = list(scenes)
                    break

        payload = {
            "chapter_id": chapter.id,
            "chapter_number": req.chapter_number,
            "status": "completed",
            "versions_count": len(result.get("variants", [])),
            "best_version_index": result.get("best_version_index", 0),
            "preset": result.get("preset", config.preset),
        }
        debug_metadata = result.get("debug_metadata") or {}
        performance = {
            "stage_timings_ms": debug_metadata.get("stage_timings_ms") or {},
            "llm_metrics": debug_metadata.get("llm_metrics") or {"summary": {}, "calls": []},
        }
        if performance["stage_timings_ms"] or performance["llm_metrics"]["calls"]:
            # 单章任务与批量原子结果都会进入 Redis task.result，便于任务完成后直接排障；
            # 同一数据也已写入 WritingArchive，Redis 7 天过期后仍可追溯。
            payload["performance"] = performance
        if missing_scenes:
            payload["missing_scenes"] = missing_scenes
        # 精修步骤被时间预算跳过：正文照常交付，但用户拿到的是没过质检的稿子。
        # 上游慢的时候这会静默发生（实测上游变慢后标准档整条链全跳），必须带出去让前端说明。
        skipped = _skipped_for_budget(result)
        if skipped:
            payload["skipped_for_budget"] = skipped
        # 润色未兑现信号：与 missing_scenes 同理，管线的 review_summaries 不进 payload，
        # 得在这里把结论带出去，供成功路径退还润色附加费
        if flow_config.get("enable_polish") and polish_undelivered(result):
            payload["polish_undelivered"] = True
        return payload


async def _execute_batch_generate(
    req: WorkerTaskRequest,
    reporter: ProgressReporter,
) -> Dict[str, Any]:
    """执行依赖感知的原子批量生成。

    连续章节因依赖上一章正文而保持串行；已经有中间完成章隔开的章节链可以限量
    并行。每章完成立即写检查点，选版后的摘要/向量等非关键后处理统一延迟到正文
    批次结束后串行执行，避免与下一章正文争抢上游模型和数据库连接。
    """
    chapter_numbers = sorted(set(req.chapter_numbers or []))
    total = len(chapter_numbers)
    if not chapter_numbers:
        return {
            "project_id": req.project_id,
            "total": 0,
            "completed": 0,
            "failed": 0,
            "reused": 0,
            "results": [],
            "status": "completed",
        }

    completed_chapters = await _load_completed_batch_chapters(req)
    existing_generated = await BatchGenerationService.load_existing_generated_chapters(
        req.project_id,
        chapter_numbers[-1],
    )
    existing_generated.update(completed_chapters)
    parallel_workers = BatchGenerationService.resolve_parallel_workers(req.config.extra)
    deferred_post_process: list[dict[str, Any]] = []
    atomic_results: dict[int, dict[str, Any]] = {}
    batch_started = time.monotonic()
    positions = {number: idx + 1 for idx, number in enumerate(chapter_numbers)}

    async def _generate_one(chapter_number: int) -> Dict[str, Any]:
        single_extra = dict(req.config.extra or {})
        # 批量下一章不能抢在前章后台摘要完成前又同步调用摘要模型；历史服务已有
        # 大纲/正文节选兜底，先用兜底保证连续生成，完整摘要由后处理补齐。
        single_extra["skip_history_summary_backfill"] = True
        single_req = WorkerTaskRequest(
            task_id=req.task_id,
            task_type="chapter:generate",
            project_id=req.project_id,
            chapter_number=chapter_number,
            user_id=req.user_id,
            config=req.config.model_copy(update={"extra": single_extra}),
            callback_url=None,
        )
        try:
            # 网关重试的是同一个批次。前一次尝试已经选版成功的章节必须直接复用，
            # 不能重置为 generating 后再跑一遍，更不能因后续章节失败而降级。
            existing = completed_chapters.get(chapter_number)
            if existing is not None:
                return {
                    "chapter_number": chapter_number,
                    "status": "success",
                    "reused": True,
                    "result": existing,
                }

            single_reporter = ProgressReporter(None, req.task_id)
            result = await _execute_chapter_generate(single_req, single_reporter)
            selected_version_id = await _select_batch_generated_chapter(
                req,
                chapter_number,
                int(result.get("best_version_index", 0) or 0),
                schedule_next_mission=False,
                schedule_post_process=False,
                deferred_post_process=deferred_post_process,
            )
            result["selected_version_id"] = selected_version_id
            return {
                "chapter_number": chapter_number,
                "status": "success",
                "result": result,
            }

        except asyncio.CancelledError:
            # 取消只收束当前原子章节；已完成和尚未开始的章节都不动。
            try:
                await asyncio.shield(_reset_generating_chapters_to_failed(single_req))
            except BaseException:  # noqa: BLE001
                pass
            raise
        except Exception as e:
            logger.error(f"章节 {chapter_number} 生成失败: {e}")
            # 每章独立提交失败状态，批量结果只做汇总，不反向覆盖其它章节。
            await _reset_generating_chapters_to_failed(single_req)
            return {
                "chapter_number": chapter_number,
                "status": "failed",
                "error": str(e),
            }

    async def _on_started(chapter_number: int, active_count: int, completed_count: int) -> None:
        progress = int((completed_count / max(1, total)) * 100)
        parallel_hint = f"，当前并行 {active_count} 章" if active_count > 1 else ""
        await reporter.report(
            progress,
            "batch_generating",
            f"正在生成第 {chapter_number} 章 ({positions[chapter_number]}/{total}{parallel_hint})",
        )

    async def _on_completed(
        chapter_number: int,
        item: Dict[str, Any],
        processed_count: int,
        expected_total: int,
    ) -> None:
        atomic_results[chapter_number] = item
        # 检查点按章节落盘到网关 Redis。页面刷新、网络断开或网关重启后，
        # 用户仍能看到哪些章节已交付；重试任务也只会提交失败章节。
        completed_so_far = [
            number
            for number, result in sorted(atomic_results.items())
            if result.get("status") == "success"
        ]
        failed_so_far = [
            number
            for number, result in sorted(atomic_results.items())
            if result.get("status") == "failed"
        ]
        elapsed = max(0.001, time.monotonic() - batch_started)
        remaining = max(0, expected_total - processed_count)
        estimated_remaining_seconds = round(elapsed / max(1, processed_count) * remaining)
        checkpoint = {
            "kind": "chapter_batch",
            "last_chapter": chapter_number,
            "completed_chapters": completed_so_far,
            "failed_chapters": failed_so_far,
            "processed": processed_count,
            "total": expected_total,
            "parallel_workers": parallel_workers,
            "estimated_remaining_seconds": estimated_remaining_seconds,
        }
        checkpoint_message = (
            f"第 {chapter_number} 章已处理，成功 {len(completed_so_far)} 章，失败 {len(failed_so_far)} 章"
        )
        try:
            await reporter.report(
                int((processed_count / max(1, expected_total)) * 100),
                "batch_checkpoint",
                checkpoint_message,
                checkpoint=checkpoint,
            )
        except TypeError as exc:
            # 保持内部测试/第三方 reporter 的旧三参数接口兼容；生产 reporter
            # 支持 checkpoint 时会走上面的持久化路径。
            if "checkpoint" not in str(exc):
                raise
            await reporter.report(
                int((processed_count / max(1, expected_total)) * 100),
                "batch_checkpoint",
                checkpoint_message,
            )

    results = await BatchGenerationService.run_dependency_aware(
        chapter_numbers=chapter_numbers,
        existing_generated=existing_generated,
        parallel_workers=parallel_workers,
        generate_one=_generate_one,
        on_started=_on_started,
        on_completed=_on_completed,
    )

    # 后处理不影响本批正文交付。集中为一个串行后台任务，避免旧实现每选完一章就
    # 同时启动摘要、向量、卷/书摘要，和下一章正文一起挤占模型通道。
    if deferred_post_process:
        safe_create_task(
            GenerationWriteTaskService().run_chapter_batch_post_processors(
                project_id=req.project_id,
                chapters=deferred_post_process,
                user_id=req.user_id,
            ),
            name=f"batch-post-process-{req.project_id}-{req.task_id}",
        )

    completed = sum(1 for item in results if item["status"] == "success")
    failed = total - completed
    reused = sum(1 for item in results if item.get("reused") is True)
    return {
        "project_id": req.project_id,
        "total": total,
        "completed": completed,
        "failed": failed,
        "reused": reused,
        "results": results,
        "status": "completed" if failed == 0 else "partial",
    }


async def _load_completed_batch_chapters(
    req: WorkerTaskRequest,
) -> Dict[int, Dict[str, Any]]:
    """读取并修复批量任务中已经有选中正文的章节，用于幂等续跑。"""
    numbers = sorted(set(req.chapter_numbers or []))
    if not numbers:
        return {}

    repaired = False
    async with AsyncSessionLocal() as session:
        novel_service = NovelService(session)
        await novel_service.ensure_project_owner(req.project_id, req.user_id)
        rows = await session.execute(
            select(Chapter).where(
                Chapter.project_id == req.project_id,
                Chapter.chapter_number.in_(numbers),
                Chapter.selected_version_id.is_not(None),
            )
        )
        chapters = rows.scalars().all()
        completed: Dict[int, Dict[str, Any]] = {}
        for chapter in chapters:
            # selected_version_id 只能由非空版本的选版流程写入，因此它是“正文已交付”的
            # 数据库事实。修复旧超时任务留下的 generating/failed 状态。
            if chapter.status in {"generating", "failed"}:
                chapter.status = "successful"
                repaired = True
            completed[chapter.chapter_number] = {
                "chapter_id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "status": "already_completed",
                "selected_version_id": chapter.selected_version_id,
                "word_count": chapter.word_count or 0,
            }
        if repaired:
            await session.commit()

    if repaired:
        await CacheService.invalidate_project_schema_safely(req.project_id)
    return completed


async def _select_batch_generated_chapter(
    req: WorkerTaskRequest,
    chapter_number: int,
    version_index: int,
    *,
    schedule_next_mission: bool = True,
    schedule_post_process: bool = True,
    deferred_post_process: Optional[list[dict[str, Any]]] = None,
) -> int:
    """批量正文采用无人值守语义：生成后自动确认管线推荐的最佳版本。

    单章生成保留多版本待用户选择；连续生成若不自动选版，会把 worker 的“成功”与
    Chapter.waiting_for_confirm 留库状态割裂，下一章也读不到已落定正文。
    """
    async with AsyncSessionLocal() as session:
        novel_service = NovelService(session)
        await novel_service.ensure_project_owner(req.project_id, req.user_id)
        chapter = await novel_service.get_or_create_chapter(req.project_id, chapter_number)
        selected = await novel_service.select_chapter_version(chapter, version_index)
        content_snapshot = selected.content or ""
        selected_version_id = selected.id

    await CacheService.invalidate_project_schema_safely(req.project_id)

    # 与同步连续生成的选版接口保持同样的后处理副作用；均为降级型后台任务，
    # 不阻塞下一章正文生成。
    if schedule_post_process:
        safe_create_task(
            GenerationWriteTaskService().run_chapter_post_processor(
                project_id=req.project_id,
                chapter_number=chapter_number,
                content=content_snapshot,
                user_id=req.user_id,
            ),
            name=f"post-process-{req.project_id}-ch{chapter_number}",
        )
    elif deferred_post_process is not None:
        deferred_post_process.append({
            "chapter_number": chapter_number,
            "content": content_snapshot,
        })
    # 连续批量会立刻进入下一章，预生成通常尚未完成，反而与正式 Mission 重复调用并
    # 争抢上游。单章自动选版仍保留预生成，批量则明确关闭。
    if schedule_next_mission:
        safe_create_task(
            pregen_next_chapter_mission(req.project_id, chapter_number, req.user_id),
            name=f"pregen-mission-{req.project_id}-ch{chapter_number + 1}",
        )
    return selected_version_id


async def _execute_blueprint_generate(
    req: WorkerTaskRequest,
    reporter: ProgressReporter,
    *,
    paid_deep: bool = False,
) -> Dict[str, Any]:
    """执行蓝图生成（异步任务路径）。

    两段式 LLM 生成可长达 10 分钟以上，同步端点在生产链路会被网关/nginx 超时掐断
    （后端实际已成功落库但前端看到失败）。生成核心完全复用
    blueprint_generation_service.generate_blueprint_for_project（含所有权校验、
    重生成保护、落库与内部 commit），此处只做进度上报与结果包装。
    paid_deep 由入口扣费结果传入：已扣费则审稿/修订付费必交付。
    """
    async with AsyncSessionLocal() as session:
        depth = (req.config.depth or "deep") if req.config else "deep"
        await reporter.report(10, "blueprint_generating", "正在生成蓝图（设定与章纲两段式）...")
        response = await generate_blueprint_for_project(
            session, req.project_id, req.user_id, depth=depth, paid_deep=paid_deep
        )
        await reporter.report(100, "completed", "蓝图生成完成")
        return response.model_dump()
