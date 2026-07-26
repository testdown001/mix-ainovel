# AIMETA P=基准跑批编排|R=场景x配置矩阵串行执行_独立播种_评分_对比|NR=不渲染报告不做CLI|E=run_bench|X=internal|A=跑批器|D=hybrid_executor_fixtures_scoring|S=none
"""基准跑批编排器。

每个 cell（场景 × 配置）串行执行：独立播种项目 → HybridExecutor 生成目标章
→ 取最佳版正文 → 机械评分 + LLM 绝对评审 → 与 baseline cell 正文成对对比。

- 串行不并发：真 LLM 跑批并发会互相抢限流与 token 预算，结果失真。
- 每个样本独立 session（session_factory，默认 AsyncSessionLocal）、独立播种
  项目 —— 生成会写记忆/伏笔/实体等状态，配置之间绝不共享项目。
- 单 cell 失败（生成炸了）记 error 继续跑其余 cell，报告里显式标注，
  绝不静默丢 cell。
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence
from urllib.parse import urlparse

from ...agents.hybrid_executor import HybridExecutor
from ..llm_service import LLMService
from .configs import BenchConfig
from .fixtures import (
    BenchScenario,
    BenchSeedSchemaError,
    get_or_create_bench_user,
    seed_scenario,
    seed_scenario_vectors,
)
from .scoring import judge_absolute, judge_pairwise, mechanical_score

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[Dict[str, Any]], None]


# ---------------------------------------------------------------------------
# 结果结构
# ---------------------------------------------------------------------------
@dataclass
class SampleResult:
    """一次独立生成样本（chapters_per_cell>1 时一个 cell 含多个样本）。"""

    index: int
    project_id: Optional[str] = None
    duration_ms: int = 0
    chapter_text: str = ""
    review_summaries: Dict[str, Any] = field(default_factory=dict)
    mechanical: Optional[Dict[str, Any]] = None
    judge: Optional[Dict[str, Any]] = None
    pairwise: Optional[Dict[str, Any]] = None
    error: Optional[str] = None       # 生成阶段致命错误（cell 失败）
    judge_error: Optional[str] = None  # 评审阶段错误（正文与机械分仍有效）
    vectors_seeded: bool = True        # 先行章向量播种是否成功（False=RAG 检索空转）
    followups_timeout: bool = False    # 收尾后台任务 drain 超时（已 cancel）
    budget_skipped_steps: List[str] = field(default_factory=list)  # 被时间预算砍掉的后处理步

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self, include_text: bool = False) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "index": self.index,
            "project_id": self.project_id,
            "duration_ms": self.duration_ms,
            "chapter_chars": len(self.chapter_text),
            "review_summaries": self.review_summaries,
            "mechanical": self.mechanical,
            "judge": self.judge,
            "pairwise": self.pairwise,
            "error": self.error,
            "judge_error": self.judge_error,
            "vectors_seeded": self.vectors_seeded,
            "followups_timeout": self.followups_timeout,
            "budget_skipped_steps": list(self.budget_skipped_steps),
        }
        if include_text:
            data["chapter_text"] = self.chapter_text
        return data


@dataclass
class CellResult:
    """场景 × 配置 一个 cell 的全部样本。

    skipped_no_op=True：该配置是与基准管线等价的 no-op 消融变体
    （KNOWN_INTERACTIONS 判定），未跑生成，samples 为空。
    """

    scenario_id: str
    config_name: str
    samples: List[SampleResult] = field(default_factory=list)
    skipped_no_op: bool = False
    note: Optional[str] = None

    @property
    def ok_samples(self) -> List[SampleResult]:
        return [s for s in self.samples if s.ok]

    def to_dict(self, include_text: bool = False) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "config_name": self.config_name,
            "samples": [s.to_dict(include_text) for s in self.samples],
            "skipped_no_op": self.skipped_no_op,
            "note": self.note,
        }


@dataclass
class BenchRunResult:
    """一次跑批的完整结果（report.render 的唯一输入）。"""

    run_tag: str
    scenario_ids: List[str]
    config_names: List[str]
    config_specs: Dict[str, Dict[str, Any]]
    pairwise_baseline: Optional[str]
    chapters_per_cell: int
    judge_enabled: bool
    started_at: str
    finished_at: str = ""
    cells: List[CellResult] = field(default_factory=list)
    environment: Dict[str, Any] = field(default_factory=dict)  # 环境快照（跨 run 可比性）
    vectors_seeded: bool = True  # False=至少一个样本向量播种失败，RAG 相关差异无效

    def cell(self, scenario_id: str, config_name: str) -> Optional[CellResult]:
        for cell in self.cells:
            if cell.scenario_id == scenario_id and cell.config_name == config_name:
                return cell
        return None

    def to_dict(self, include_text: bool = False) -> Dict[str, Any]:
        return {
            "run_tag": self.run_tag,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "scenario_ids": list(self.scenario_ids),
            "config_names": list(self.config_names),
            "config_specs": self.config_specs,
            "pairwise_baseline": self.pairwise_baseline,
            "chapters_per_cell": self.chapters_per_cell,
            "judge_enabled": self.judge_enabled,
            "environment": dict(self.environment),
            "vectors_seeded": self.vectors_seeded,
            "cells": [cell.to_dict(include_text) for cell in self.cells],
        }


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------
def _emit(progress_cb: Optional[ProgressCallback], **event: Any) -> None:
    if progress_cb is None:
        return
    try:
        progress_cb(event)
    except Exception:  # pragma: no cover - 进度回调绝不影响跑批
        logger.warning("bench progress_cb 抛出异常，已忽略", exc_info=True)


def _default_session_factory():
    # 惰性导入：测试注入内存工厂时绝不触碰开发库引擎
    from ...db.session import AsyncSessionLocal

    return AsyncSessionLocal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def drain_background_tasks(timeout: float = 180.0) -> bool:
    """等待事件循环里除当前任务外的全部任务结束，返回是否全部按时完成。

    生成收尾 schedule_followups 是 fire-and-forget（asyncio.create_task）——
    不等它们会导致：dry-run restore 后真调用计费 / cleanup 竞态孤儿数据 /
    后台任务跨 cell 污染下一样本时长。超时未完的任务会被 cancel。

    ⚠️ 仅适用于 bench 专用事件循环（CLI asyncio.run / 测试）——循环里只有
    bench 自己派生的任务；生产 Web 进程绝不可用（会等到别人的任务）。
    """
    current = asyncio.current_task()
    pending = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
    if not pending:
        return True
    _, still_pending = await asyncio.wait(pending, timeout=timeout)
    if not still_pending:
        return True
    logger.warning("bench 后台任务 drain 超时（%ss），cancel %d 个任务", timeout, len(still_pending))
    for task in still_pending:
        task.cancel()
    await asyncio.wait(still_pending, timeout=5)
    return False


async def snapshot_environment(session_factory) -> Dict[str, Any]:
    """跑批开始时的环境快照——写进结果与 report.md 头部，保证跨 run 可比。"""
    from ...core.config import settings

    snapshot: Dict[str, Any] = {
        "writer_chapter_versions": settings.writer_chapter_versions,
        "writer_fast_mode": settings.writer_fast_mode,
        "writer_ultra_fast_mode": settings.writer_ultra_fast_mode,
        "generation_time_budget_sec": settings.generation_time_budget_sec,
        "rag_retrieval_mode": settings.rag_retrieval_mode,
        "rag_reranker_enabled": settings.rag_reranker_enabled,
        "db_provider": settings.db_provider,
    }
    try:
        from ...models.system_config import SystemConfig

        async with session_factory() as session:

            async def _value(key: str) -> str:
                row = await session.get(SystemConfig, key)
                return (row.value or "").strip() if row is not None else ""

            snapshot["llm_model"] = await _value("llm.model") or "（未配置）"
            base_url = await _value("llm.base_url")
            # 脱敏：只留 host（base_url 可能带路径/凭据痕迹）
            snapshot["llm_base_url_host"] = (
                (urlparse(base_url).netloc or base_url) if base_url else "（未配置）"
            )
            snapshot["llm_grader_configured"] = bool(await _value("llm_grader.api_key"))
    except Exception as exc:  # noqa: BLE001 - 快照失败不阻断跑批，但显式留痕
        logger.warning("bench 环境快照读取 SystemConfig 失败: %s", exc)
        snapshot.setdefault("llm_model", f"（读取失败: {type(exc).__name__}）")
        snapshot.setdefault("llm_base_url_host", "（读取失败）")
        snapshot.setdefault("llm_grader_configured", False)
    return snapshot


async def _generate_sample(
    session_factory,
    scenario: BenchScenario,
    config: BenchConfig,
    run_tag: str,
    index: int,
    drain_timeout: float = 180.0,
) -> SampleResult:
    """独立播种 + 生成一个样本；生成失败记 error 返回（绝不上抛）。

    BenchSeedSchemaError（开发库 schema 落后）例外——环境问题会让每个 cell
    都失败，原样上抛中止跑批。每个样本收尾都 drain 后台任务（见
    drain_background_tasks），dry-run 下这些任务是桩、秒完。
    """
    sample = SampleResult(index=index)
    gen_started: Optional[float] = None
    try:
        try:
            async with session_factory() as session:
                sample.project_id = await seed_scenario(session, scenario, run_tag)
                sample.vectors_seeded = await seed_scenario_vectors(
                    session, scenario, sample.project_id
                )
                user = await get_or_create_bench_user(session)
                executor = HybridExecutor(session, user_id=user.id)
                gen_started = time.monotonic()
                result = await executor.generate_chapter(
                    project_id=sample.project_id,
                    chapter_number=scenario.target_chapter,
                    flow_config=config.to_flow_config(),
                )
                sample.duration_ms = int((time.monotonic() - gen_started) * 1000)
                await session.commit()
        except BenchSeedSchemaError:
            raise
        except Exception as exc:  # noqa: BLE001 - 单 cell 失败不中断跑批
            if gen_started is not None and sample.duration_ms == 0:
                sample.duration_ms = int((time.monotonic() - gen_started) * 1000)
            sample.error = f"{type(exc).__name__}: {exc}"
            logger.exception(
                "bench cell 生成失败: scenario=%s config=%s sample=%d",
                scenario.scenario_id, config.name, index,
            )
            return sample
    finally:
        if not await drain_background_tasks(drain_timeout):
            sample.followups_timeout = True

    variants = result.get("variants") or []
    best_index = result.get("best_version_index", 0)
    if not variants or not (0 <= best_index < len(variants)):
        sample.error = f"生成结果异常: variants={len(variants)} best_version_index={best_index}"
        return sample
    best = variants[best_index]
    sample.chapter_text = (best.get("content") if isinstance(best, dict) else "") or ""
    summaries = result.get("review_summaries")
    sample.review_summaries = summaries if isinstance(summaries, dict) else {}
    # belt+braces：即便预算覆写失效（如 --respect-time-budget），被砍步也显式留痕，
    # 报告据此标注「该 cell 数字不可信」
    time_budget = sample.review_summaries.get("time_budget")
    if isinstance(time_budget, dict) and isinstance(time_budget.get("skipped"), list):
        sample.budget_skipped_steps = [str(step) for step in time_budget["skipped"]]
    if not sample.chapter_text.strip():
        sample.error = "生成结果无正文（最佳版 content 为空）"
        return sample

    try:
        sample.mechanical = mechanical_score(
            sample.chapter_text, scenario, sample.review_summaries
        )
    except Exception as exc:  # noqa: BLE001 - 机械评分失败不丢正文
        sample.judge_error = f"mechanical_score 失败: {type(exc).__name__}: {exc}"
        logger.exception("bench 机械评分失败: %s/%s", scenario.scenario_id, config.name)
    return sample


async def _judge_sample(
    session_factory,
    sample: SampleResult,
    scenario: BenchScenario,
    config_name: str,
    baseline_name: Optional[str],
    baseline_texts: List[str],
) -> None:
    """LLM 评审一个样本：绝对评分 + （非基线 cell）与基线正文成对对比。"""
    try:
        async with session_factory() as session:
            llm = LLMService(session)
            sample.judge = await judge_absolute(llm, sample.chapter_text, scenario)
            if baseline_name is not None and config_name != baseline_name and baseline_texts:
                # 样本 i 对基线样本 i（基线样本不足时退到基线第一个成功样本）
                opponent = baseline_texts[min(sample.index, len(baseline_texts) - 1)]
                sample.pairwise = await judge_pairwise(
                    llm, sample.chapter_text, opponent, scenario
                )
    except Exception as exc:  # noqa: BLE001 - 评审失败不丢正文与机械分
        sample.judge_error = f"{type(exc).__name__}: {exc}"
        logger.exception(
            "bench 评审失败: scenario=%s config=%s sample=%d",
            scenario.scenario_id, config_name, sample.index,
        )


# ---------------------------------------------------------------------------
# 跑批入口
# ---------------------------------------------------------------------------
async def run_bench(
    scenarios: Sequence[BenchScenario],
    configs: Sequence[BenchConfig],
    *,
    judge: bool = True,
    pairwise_baseline: Optional[str] = "standard",
    chapters_per_cell: int = 1,
    run_tag: str,
    progress_cb: Optional[ProgressCallback] = None,
    session_factory=None,
    drain_timeout: float = 180.0,
) -> BenchRunResult:
    """在场景 × 配置矩阵上串行跑基准。

    - judge=False 时只做机械评分（零 LLM 评审成本）。
    - pairwise_baseline：作为对比基线的配置名；不在 configs 里则自动禁用对比。
    - chapters_per_cell：每 cell 独立生成的样本数（>1 用于平滑单次生成方差，
      每个样本都独立播种项目）。
    - session_factory：默认 AsyncSessionLocal（开发库）；测试注入内存工厂。
    - drain_timeout：每样本收尾等待 fire-and-forget 后台任务的秒数（超时 cancel）。
    - no_op 消融变体（config.no_op=True，与基准管线等价）直接跳过生成，
      cell 记 skipped_no_op，报告消融表标「与基准管线等价，未跑」。
    """
    if not scenarios:
        raise ValueError("scenarios 不能为空")
    if not configs:
        raise ValueError("configs 不能为空")
    if chapters_per_cell < 1:
        raise ValueError("chapters_per_cell 必须 >= 1")
    config_names = [config.name for config in configs]
    if len(set(config_names)) != len(config_names):
        raise ValueError(f"配置名重复: {config_names}")
    scenario_ids = [scenario.scenario_id for scenario in scenarios]
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError(f"场景 id 重复: {scenario_ids}")

    if session_factory is None:
        session_factory = _default_session_factory()

    baseline_name: Optional[str] = pairwise_baseline
    if baseline_name is not None and baseline_name not in config_names:
        logger.warning(
            "pairwise_baseline=%s 不在本次配置里 %s，成对对比已禁用",
            baseline_name, config_names,
        )
        baseline_name = None

    result = BenchRunResult(
        run_tag=run_tag,
        scenario_ids=scenario_ids,
        config_names=config_names,
        config_specs={
            config.name: {
                "preset": config.preset,
                "flow_config": dict(config.flow_config),
                "no_op": config.no_op,
                "note": config.note,
            }
            for config in configs
        },
        pairwise_baseline=baseline_name if judge else None,
        chapters_per_cell=chapters_per_cell,
        judge_enabled=judge,
        started_at=_now_iso(),
        environment=await snapshot_environment(session_factory),
    )

    total_cells = len(scenarios) * len(configs)
    cell_index = 0
    cells_by_key: Dict[tuple, CellResult] = {}

    for scenario in scenarios:
        # 基线 cell 先跑，其正文供同场景其余 cell 做成对对比
        ordered = sorted(configs, key=lambda c: 0 if c.name == baseline_name else 1)
        baseline_texts: List[str] = []
        for config in ordered:
            cell_index += 1
            cell = CellResult(scenario_id=scenario.scenario_id, config_name=config.name)
            cells_by_key[(scenario.scenario_id, config.name)] = cell
            if config.no_op:
                # 与基准管线等价的假消融行：跳过生成省真金白银，报告显式标注
                cell.skipped_no_op = True
                cell.note = config.note
                _emit(
                    progress_cb,
                    event="cell_skipped",
                    scenario=scenario.scenario_id,
                    config=config.name,
                    cell_index=cell_index,
                    total_cells=total_cells,
                    note=config.note,
                )
                continue
            _emit(
                progress_cb,
                event="cell_start",
                scenario=scenario.scenario_id,
                config=config.name,
                cell_index=cell_index,
                total_cells=total_cells,
            )
            for sample_index in range(chapters_per_cell):
                sample = await _generate_sample(
                    session_factory, scenario, config, run_tag, sample_index,
                    drain_timeout=drain_timeout,
                )
                if judge and sample.ok:
                    await _judge_sample(
                        session_factory, sample, scenario,
                        config.name, baseline_name, baseline_texts,
                    )
                cell.samples.append(sample)
                _emit(
                    progress_cb,
                    event="sample_done",
                    scenario=scenario.scenario_id,
                    config=config.name,
                    sample=sample_index,
                    duration_ms=sample.duration_ms,
                    error=sample.error,
                    judge_error=sample.judge_error,
                )
            if config.name == baseline_name:
                baseline_texts = [s.chapter_text for s in cell.ok_samples if s.chapter_text]
            _emit(
                progress_cb,
                event="cell_done",
                scenario=scenario.scenario_id,
                config=config.name,
                ok=len(cell.ok_samples),
                total=len(cell.samples),
            )

    # cells 按入参 场景 × 配置 顺序落位（执行顺序里基线被提前）
    for scenario_id in scenario_ids:
        for config_name in config_names:
            result.cells.append(cells_by_key[(scenario_id, config_name)])

    # 返回前最后 drain 一次：保证调用方（cleanup/restore）看不到任何 pending 任务
    if not await drain_background_tasks(drain_timeout):
        logger.warning("bench run %s 收尾 drain 超时，残留后台任务已 cancel", run_tag)

    result.vectors_seeded = all(
        sample.vectors_seeded for cell in result.cells for sample in cell.samples
    )
    result.finished_at = _now_iso()
    failed = sum(1 for cell in result.cells for s in cell.samples if not s.ok)
    _emit(
        progress_cb,
        event="run_done",
        cells=len(result.cells),
        failed_samples=failed,
    )
    logger.info(
        "bench run %s 完成: %d cells × %d samples, 失败样本 %d",
        run_tag, len(result.cells), chapters_per_cell, failed,
    )
    return result
