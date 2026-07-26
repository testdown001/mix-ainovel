#!/usr/bin/env python3
"""评估基线 CLI：在固定基准场景上以不同管线配置生成章节、打分、对比。

子命令：
  list     列出可用场景夹具与内置配置
  freeze   把既有真实项目冻结为场景夹具 JSON
  run      跑 场景 × 配置 基准矩阵并生成报告
  cleanup  按 run_tag（或 --all-bench 全量）清理 bench 项目

用法示例（在 backend/ 下，激活 .venv）：
  python run_bench.py list
  python run_bench.py freeze --project-id <uuid> --upto 3 --target 4 \
      --out bench_fixtures/my_novel.json
  python run_bench.py run --scenarios demo_xuanhuan --configs standard,full --yes
  python run_bench.py run --scenarios demo_xuanhuan --configs full \
      --ablate optimizer,polish --baseline full --yes
  python run_bench.py run --scenarios demo_xuanhuan --configs standard --dry-run
  python run_bench.py cleanup --run-tag baseline-01
  python run_bench.py cleanup --all-bench --yes

详见 docs/bench-guide.md。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 测试注入口：设为可调用的 session 工厂后，所有子命令都不再触碰开发库
_SESSION_FACTORY = None


class CLIError(Exception):
    """带人话消息的 CLI 错误（打印后以退出码 2 结束）。"""


def _apply_time_budget_override(respect: bool) -> None:
    """默认在**导入 app 之前**把生成时间预算关掉（GENERATION_TIME_BUDGET_SEC=0）。

    bench 测的是各配置的质量上限；540s 预算降级是生产运维特性——它会按耗时
    随机砍掉后处理步，把「配置差异」污染成「预算运气差异」（名义配置≠实际执行）。
    --respect-time-budget 保留生产行为；环境里已显式导出该变量则不覆盖（setdefault）。
    必须先于任何 app 模块导入调用（settings 单例在导入时定型）。
    """
    if respect:
        return
    os.environ.setdefault("GENERATION_TIME_BUDGET_SEC", "0")


# ---------------------------------------------------------------------------
# 启动校验
# ---------------------------------------------------------------------------
def _ensure_app_importable() -> Optional[str]:
    """校验 backend/.env 可加载（SECRET_KEY 等必填项齐全），返回人话错误或 None。"""
    try:
        from app.core.config import settings  # noqa: F401
        return None
    except Exception as exc:  # noqa: BLE001
        return (
            "无法加载应用配置：\n"
            f"  {type(exc).__name__}: {exc}\n"
            "请确认 backend/.env 存在且至少包含 SECRET_KEY 与 ADMIN_DEFAULT_PASSWORD\n"
            "（参考 backend/env.example），并从 backend/ 目录运行本脚本。"
        )


def _get_session_factory():
    if _SESSION_FACTORY is not None:
        return _SESSION_FACTORY
    from app.db.session import AsyncSessionLocal

    return AsyncSessionLocal


async def _check_db(session_factory) -> None:
    from sqlalchemy import text

    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise CLIError(
            "无法连接数据库：\n"
            f"  {type(exc).__name__}: {exc}\n"
            "请确认 backend/.env 的 DB_PROVIDER / MYSQL_* / SQLITE_PATH 配置，"
            "以及数据库已启动（bench 跑在开发库上）。"
        ) from exc


async def _check_llm_configured(session_factory) -> None:
    from app.models.system_config import SystemConfig

    async with session_factory() as session:
        row = await session.get(SystemConfig, "llm.api_key")
    if row is not None and (row.value or "").strip():
        return
    # 与 LLMService._get_config_value 的真实解析一致：DB 缺失时回退同名 env
    if (os.getenv("LLM_API_KEY") or "").strip():
        return
    raise CLIError(
        "SystemConfig 里没有可用的 llm.api_key（env LLM_API_KEY 也未设置）"
        "—— bench 需要真实 LLM 通道。\n"
        "请先启动后端并在管理后台「接口管理」配置默认 LLM 通道；\n"
        "或先用 --dry-run 做零成本冒烟。"
    )


# ---------------------------------------------------------------------------
# dry-run 假 LLM 桩（零成本冒烟：真实管线 + 桩掉全部外部 LLM 出口）
# ---------------------------------------------------------------------------
_FAKE_PARAGRAPHS = (
    "夜色压在丹阁的飞檐上，沈青崖握紧腰间的玉瓶，一步步走向内堂深处。"
    "檀香混着药气扑面而来，他却嗅到了一丝极淡的血腥味，像是有人刻意用香雾掩盖。"
    "识海里那柄断剑微微震颤，剑身的裂纹里渗出一缕幽光，替他照亮了脚下的暗纹。\n"
    "「小心，地上的阵纹是活的。」焚寂的声音冷而低。沈青崖脚步一顿，"
    "灵力沿着足底铺开，暗纹如蛇般游走，避开了他的气息。他屏住呼吸，"
    "从袖中摸出半枚残符，指尖的血珠落在符面上，残符无声燃尽，四周的香雾豁然裂开一线。\n"
    "内堂的灯影里坐着一个人，背对着他，手中把玩着那枚本该封存在丹阁密库的丹方。"
    "「你来得比我想的快。」那人缓缓转身，嘴角噙着笑意，眼底却没有半分温度。"
    "沈青崖的瞳孔骤然收紧——那张脸，他在宗门大殿的画像上见过。\n"
)

_FAKE_CHAPTER = _FAKE_PARAGRAPHS * 3 + (
    "他退后半步，断剑出鞘三寸，寒光映着两人的影子。就在这时，"
    "识海深处的焚寂忽然一颤：「等等——他身后那扇门里，还有第三个人的呼吸。」"
)

_FAKE_WRITER_PROMPT = (
    "你是一位资深网文作者。请根据给定的章节大纲、人物设定与前文摘要，"
    "写出本章正文，保持紧凑节奏与人物一致性。直接输出正文。"
)

_SCHEMA_MARKER = "多余文字：\n"


def _resolve_ref(schema: Dict[str, Any], defs: Dict[str, Any]) -> Dict[str, Any]:
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        return defs.get(ref[len("#/$defs/"):], {})
    return schema


def _instance_from_schema(schema: Any, defs: Optional[Dict[str, Any]] = None) -> Any:
    """按 JSON Schema 合成一个最小合法实例（dry-run 桩喂给 generate_structured）。"""
    if not isinstance(schema, dict):
        return "占位"
    if defs is None:
        defs = schema.get("$defs") or {}
    schema = _resolve_ref(schema, defs)
    if "const" in schema:
        return schema["const"]
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        return schema["enum"][0]
    for combinator in ("anyOf", "oneOf", "allOf"):
        options = schema.get(combinator)
        if isinstance(options, list) and options:
            non_null = [o for o in options if isinstance(o, dict) and o.get("type") != "null"]
            return _instance_from_schema((non_null or options)[0], defs)
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = schema_type[0] if schema_type else None
    if schema_type == "object" or "properties" in schema:
        return {
            key: _instance_from_schema(value, defs)
            for key, value in (schema.get("properties") or {}).items()
        }
    if schema_type == "array":
        return []
    if schema_type == "boolean":
        return False
    if schema_type in ("number", "integer"):
        value = 5
        minimum = schema.get("minimum", schema.get("exclusiveMinimum"))
        maximum = schema.get("maximum", schema.get("exclusiveMaximum"))
        if isinstance(minimum, (int, float)) and value <= minimum:
            value = int(minimum) + 1
        if isinstance(maximum, (int, float)) and value >= maximum:
            value = int(maximum)
        return value
    if schema_type == "null":
        return None
    return "占位"


def _fake_json_reply(system_prompt: str) -> str:
    """json 响应：system prompt 里带 generate_structured 注入的 schema 就按 schema 合成，
    否则回一个覆盖常见键的宽松 JSON（parse_llm_json 消费方走默认分支）。"""
    marker_at = (system_prompt or "").rfind(_SCHEMA_MARKER)
    if marker_at >= 0:
        try:
            schema = json.loads(system_prompt[marker_at + len(_SCHEMA_MARKER):].strip())
            return json.dumps(_instance_from_schema(schema), ensure_ascii=False)
        except Exception:  # noqa: BLE001
            pass
    return json.dumps(
        {"summary": "dry-run 摘要占位", "goals": [], "scenes": [], "key_points": [],
         "issues": [], "suggestions": []},
        ensure_ascii=False,
    )


def _apply_dry_run_stubs():
    """桩掉全部外部 LLM 出口；返回 restore() 用于恢复（测试直调 main 时防污染）。"""
    from app.services.cache_service import CacheService
    from app.services.llm_service import LLMService
    from app.services.writer_prompt_service import WriterPromptService

    patches: List[tuple] = []

    def _patch(owner, name, value):
        patches.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    def _extract(args, kwargs):
        system_prompt = kwargs.get("system_prompt")
        if system_prompt is None and args:
            system_prompt = args[0] if isinstance(args[0], str) else None
        return system_prompt or "", kwargs.get("response_format")

    async def fake_llm_response(self, *args, **kwargs):
        system_prompt, response_format = _extract(args, kwargs)
        if response_format in ("json", "json_object"):
            return _fake_json_reply(system_prompt)
        return _FAKE_CHAPTER

    async def fake_unconfigured(self, *args, **kwargs):
        # 模拟通道未配置：所有调用方都有现成的降级路径（评审降级默认通道等）
        raise ValueError("dry-run: 该 LLM 通道未配置")

    async def fake_chat_with_tools(self, *args, **kwargs):
        return {"content": _FAKE_CHAPTER, "tool_calls": [], "finish_reason": "stop"}

    async def fake_embedding(self, *args, **kwargs):
        return []

    async def fake_prefetch_writer_prompt(self, *args, **kwargs):
        return _FAKE_WRITER_PROMPT

    async def fake_none(self, *args, **kwargs):
        return None

    _patch(LLMService, "get_llm_response", fake_llm_response)
    _patch(LLMService, "get_optimize_llm_response", fake_llm_response)
    _patch(LLMService, "get_grader_llm_response", fake_unconfigured)
    _patch(LLMService, "get_search_llm_response", fake_unconfigured)
    _patch(LLMService, "chat_with_tools", fake_chat_with_tools)
    _patch(LLMService, "get_embedding", fake_embedding)
    _patch(LLMService, "get_embeddings_batch", fake_embedding)
    _patch(WriterPromptService, "prefetch_writer_prompt", fake_prefetch_writer_prompt)
    _patch(CacheService, "get_project_schema", fake_none)
    _patch(CacheService, "set_project_schema", fake_none)
    _patch(CacheService, "invalidate_project_schema", fake_none)

    def restore():
        for owner, name, original in reversed(patches):
            setattr(owner, name, original)

    return restore


# ---------------------------------------------------------------------------
# 成本预估
# ---------------------------------------------------------------------------
_PRESET_CALL_ESTIMATE = {"fast": 3, "standard": 10, "premium": 14}


def _estimate_cell_calls(config) -> int:
    """一个 cell 的 LLM 调用量级粗估：preset 基数 + 显式开开关数。"""
    base = _PRESET_CALL_ESTIMATE.get(config.preset, 8)
    extra = sum(1 for value in config.flow_config.values() if value is True)
    return base + extra


def _print_cost_estimate(scenarios, configs, *, judge: bool, baseline: Optional[str],
                         chapters_per_cell: int, dry_run: bool) -> None:
    runnable = [config for config in configs if not config.no_op]
    no_op_configs = [config for config in configs if config.no_op]
    cells = len(scenarios) * len(runnable)
    samples = cells * chapters_per_cell
    gen_calls = sum(
        _estimate_cell_calls(config) for config in runnable
    ) * len(scenarios) * chapters_per_cell
    judge_calls = 0
    if judge:
        non_baseline = [c for c in runnable if c.name != baseline]
        judge_calls = samples  # 绝对评分：每样本 1 次
        judge_calls += len(non_baseline) * len(scenarios) * chapters_per_cell * 2  # 成对 ×2
    print("成本预估（量级，非精确）：")
    print(f"  cell 数：{len(scenarios)} 场景 × {len(runnable)} 配置 = {cells}"
          f"（每 cell {chapters_per_cell} 个样本，共 {samples} 次生成）")
    for config in runnable:
        print(f"  - {config.name}（preset={config.preset}）：约 {_estimate_cell_calls(config)} 次 LLM 调用/样本")
    for config in no_op_configs:
        print(f"  - {config.name}：跳过不跑（与基准管线等价的 no-op 消融，"
              f"{config.note or '见 KNOWN_INTERACTIONS'}）")
    print(f"  生成调用合计：约 {gen_calls} 次；评审调用：约 {judge_calls} 次"
          f"（绝对评分 ×1 + 非基线成对对比 ×2）")
    if dry_run:
        print("  --dry-run：全部 LLM 出口已桩掉，零成本。")


def _confirm_or_abort(args) -> bool:
    if args.dry_run or args.yes:
        return True
    if not sys.stdin.isatty():
        print("非交互环境需要显式 --yes 确认（真实 LLM 跑批会产生费用）。", file=sys.stderr)
        return False
    reply = input("以上将真实调用 LLM 产生费用，继续？[y/N] ").strip().lower()
    return reply in ("y", "yes")


# ---------------------------------------------------------------------------
# 参数解析辅助
# ---------------------------------------------------------------------------
def _resolve_scenarios(spec: str):
    from app.services.bench.fixtures import FIXTURES_DIR, load_scenario

    scenarios = []
    for name in [part.strip() for part in spec.split(",") if part.strip()]:
        path = Path(name) if name.endswith(".json") else FIXTURES_DIR / f"{name}.json"
        if not path.exists():
            available = sorted(p.stem for p in FIXTURES_DIR.glob("*.json"))
            raise CLIError(
                f"场景夹具不存在: {path}\n可用夹具: {', '.join(available) or '（无）'}"
            )
        try:
            scenarios.append(load_scenario(path))
        except Exception as exc:  # noqa: BLE001
            raise CLIError(f"场景夹具解析失败 {path}: {type(exc).__name__}: {exc}") from exc
    if not scenarios:
        raise CLIError("--scenarios 不能为空")
    return scenarios


def _resolve_configs(spec: str, ablate_spec: str):
    from app.services.bench.configs import (
        BUILTIN_CONFIGS, FULL, QUALITY_SWITCHES, build_ablations,
    )

    names = [part.strip() for part in spec.split(",") if part.strip()]
    if not names:
        raise CLIError("--configs 不能为空")
    configs = []
    for name in names:
        if name not in BUILTIN_CONFIGS:
            raise CLIError(
                f"未知配置: {name}（内置配置: {', '.join(BUILTIN_CONFIGS)}）"
            )
        configs.append(BUILTIN_CONFIGS[name])

    switches = []
    for raw in [part.strip() for part in ablate_spec.split(",") if part.strip()]:
        switch = raw if raw.startswith("enable_") else f"enable_{raw}"
        if switch not in QUALITY_SWITCHES:
            shorts = ", ".join(s[len("enable_"):] for s in QUALITY_SWITCHES)
            raise CLIError(
                f"不可消融的开关: {raw}\n"
                f"可消融开关（flow_config 覆写白名单内的质量开关）: {shorts}"
            )
        switches.append(switch)
    if switches:
        if FULL.name not in [config.name for config in configs]:
            print(f"提示：--ablate 需要 {FULL.name} 作为消融基准，已自动加入。")
            configs.append(FULL)
        existing = {config.name for config in configs}
        for variant in build_ablations(FULL, switches):
            if variant.name not in existing:
                configs.append(variant)
    return configs


def _print_progress(event: Dict[str, Any]) -> None:
    kind = event.get("event")
    if kind == "cell_start":
        print(f"[{event['cell_index']}/{event['total_cells']}] "
              f"{event['scenario']} × {event['config']} ...", flush=True)
    elif kind == "sample_done":
        status = "失败: " + str(event["error"])[:120] if event.get("error") else "完成"
        judge_note = f"（评审失败: {str(event['judge_error'])[:80]}）" if event.get("judge_error") else ""
        print(f"    样本 {event['sample']} {status}，{event['duration_ms']}ms{judge_note}",
              flush=True)


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------
async def cmd_list(args) -> int:
    from app.services.bench.configs import BUILTIN_CONFIGS, QUALITY_SWITCHES
    from app.services.bench.fixtures import FIXTURES_DIR, load_scenario

    print(f"场景夹具（{FIXTURES_DIR}）：")
    paths = sorted(FIXTURES_DIR.glob("*.json"))
    if not paths:
        print("  （无。用 freeze 从真实项目冻结，或参考 docs/bench-guide.md 手写）")
    for path in paths:
        try:
            scenario = load_scenario(path)
            print(f"  - {scenario.scenario_id}: 目标第 {scenario.target_chapter} 章，"
                  f"先行章 {len(scenario.prior_chapters)}，大纲 {len(scenario.outlines)} 条"
                  f" — {scenario.description[:60]}")
        except Exception as exc:  # noqa: BLE001
            print(f"  - {path.name}: 解析失败（{type(exc).__name__}: {exc}）")

    print("\n内置配置：")
    for config in BUILTIN_CONFIGS.values():
        switches = sum(1 for value in config.flow_config.values() if value is True)
        print(f"  - {config.name}: preset={config.preset}"
              + (f"，显式开 {switches} 个质量开关" if switches else ""))

    shorts = ", ".join(s[len("enable_"):] for s in QUALITY_SWITCHES)
    print(f"\n可消融开关（--ablate，从 full 减一）：{shorts}")
    print("说明：preset 驱动键（enable_memory / enable_six_dimension 等）不在 flow_config"
          " 覆写白名单内，无法单独消融，只能靠 standard vs premium 对比近似。")
    return 0


async def cmd_freeze(args) -> int:
    from app.services.bench.fixtures import freeze_project, save_scenario

    session_factory = _get_session_factory()
    await _check_db(session_factory)
    must_include = [part.strip() for part in (args.must_include or "").split(",") if part.strip()]
    async with session_factory() as session:
        try:
            scenario = await freeze_project(
                session,
                args.project_id,
                upto_chapter=args.upto,
                target_chapter=args.target,
                scenario_id=args.scenario_id,
                description=args.description,
                must_include=must_include,
            )
        except ValueError as exc:
            raise CLIError(str(exc)) from exc
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_scenario(scenario, out)
    print(f"已冻结场景 {scenario.scenario_id} → {out}")
    print(f"  先行章 {len(scenario.prior_chapters)}，大纲 {len(scenario.outlines)} 条，"
          f"目标第 {scenario.target_chapter} 章")
    if not must_include:
        print("  ⚠️ must_include 为空：机械评分的必含词维度无据可依，"
              "建议对照目标章大纲人工补 2-3 个剧情关键词。")
    return 0


async def cmd_run(args) -> int:
    from app.services.bench.fixtures import BenchSeedSchemaError, cleanup_run
    from app.services.bench.report import write_report
    from app.services.bench.runner import drain_background_tasks, run_bench

    scenarios = _resolve_scenarios(args.scenarios)
    configs = _resolve_configs(args.configs, args.ablate)
    judge = not args.no_judge
    baseline = args.baseline if judge else None
    if baseline is not None and baseline not in [config.name for config in configs]:
        print(f"提示：基线 {baseline} 不在本次配置里，成对对比已禁用。")
        baseline = None

    _print_cost_estimate(
        scenarios, configs, judge=judge, baseline=baseline,
        chapters_per_cell=args.chapters_per_cell, dry_run=args.dry_run,
    )
    if not _confirm_or_abort(args):
        return 2

    session_factory = _get_session_factory()
    await _check_db(session_factory)
    if not args.dry_run:
        await _check_llm_configured(session_factory)

    run_tag = args.run_tag or time.strftime("bench-%Y%m%d-%H%M%S")
    restore = _apply_dry_run_stubs() if args.dry_run else None
    try:
        result = await run_bench(
            scenarios,
            configs,
            judge=judge,
            pairwise_baseline=baseline,
            chapters_per_cell=args.chapters_per_cell,
            run_tag=run_tag,
            progress_cb=_print_progress,
            session_factory=session_factory,
        )
    except BenchSeedSchemaError as exc:
        raise CLIError(
            f"{exc}\n"
            "开发库 schema 落后于 ORM：先启动一次后端（uvicorn app.main:app 或 "
            "start-dev.sh）让 init_db() 启动修复补列，再跑 bench。"
        ) from exc
    finally:
        # 先 drain 掉生成收尾的 fire-and-forget 后台任务，再恢复 dry-run 桩——
        # 否则 restore 之后仍在跑的后台任务会真调用 LLM 计费
        await drain_background_tasks()
        if restore is not None:
            restore()

    run_dir = write_report(
        result, base_dir=Path(args.report_dir) if args.report_dir else None
    )
    total = sum(len(cell.samples) for cell in result.cells)
    failed = sum(1 for cell in result.cells for sample in cell.samples if not sample.ok)
    print(f"\n完成：{total - failed}/{total} 个样本成功。报告：{run_dir}/report.md")
    if failed:
        print(f"⚠️ 有 {failed} 个样本失败，详见报告「失败 cell 清单」。")

    if args.cleanup:
        async with session_factory() as session:
            removed = await cleanup_run(session, run_tag)
        print(f"已清理 {removed} 个 bench 项目（run_tag={run_tag}）。")
    else:
        print(f"bench 项目保留在库中（run_tag={run_tag}），复核后可用 "
              f"`python run_bench.py cleanup --run-tag {run_tag}` 清理。")
    return 1 if (total > 0 and failed == total) else 0


async def cmd_cleanup(args) -> int:
    from app.services.bench.fixtures import cleanup_all_bench, cleanup_run

    if bool(args.all_bench) == bool(args.run_tag):
        raise CLIError("cleanup 需要 --run-tag <标签> 或 --all-bench 二选一。")
    if args.all_bench and not args.yes:
        raise CLIError(
            "--all-bench 会删除 bench 用户（bench@local）名下**全部**项目及其向量，"
            "须显式加 --yes 确认。"
        )
    session_factory = _get_session_factory()
    await _check_db(session_factory)
    async with session_factory() as session:
        if args.all_bench:
            removed = await cleanup_all_bench(session)
            print(f"已清理 bench 用户全部项目：{removed} 个。")
        else:
            removed = await cleanup_run(session, args.run_tag)
            print(f"已清理 {removed} 个 bench 项目（run_tag={args.run_tag}）。")
    return 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_bench.py",
        description="评估基线：固定场景 × 管线配置矩阵的生成-打分-对比跑批",
    )
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="列出场景夹具与内置配置")
    p_list.set_defaults(func=cmd_list)

    p_freeze = sub.add_parser("freeze", help="把真实项目冻结为场景夹具 JSON")
    p_freeze.add_argument("--project-id", required=True, help="来源项目 UUID")
    p_freeze.add_argument("--upto", type=int, required=True, help="纳入前 N 个已完成章为先行章")
    p_freeze.add_argument("--target", type=int, required=True, help="基准生成的目标章号")
    p_freeze.add_argument("--out", required=True, help="夹具 JSON 输出路径")
    p_freeze.add_argument("--scenario-id", default=None, help="场景 id（默认自动生成）")
    p_freeze.add_argument("--description", default=None, help="场景描述")
    p_freeze.add_argument("--must-include", default="", help="逗号分隔的剧情必含词（机械评分用）")
    p_freeze.set_defaults(func=cmd_freeze)

    p_run = sub.add_parser("run", help="跑基准矩阵并生成报告")
    p_run.add_argument("--scenarios", required=True,
                       help="逗号分隔的夹具名（bench_fixtures/<名>.json）或 JSON 路径")
    p_run.add_argument("--configs", default="standard,premium,full",
                       help="逗号分隔的内置配置名（默认 standard,premium,full）")
    p_run.add_argument("--ablate", default="",
                       help="逗号分隔的消融开关（如 optimizer,polish；从 full 减一，"
                            "自动补 full 作基准）")
    p_run.add_argument("--baseline", default="standard",
                       help="成对对比的基线配置名（默认 standard；跑消融建议设为 full）")
    p_run.add_argument("--chapters-per-cell", type=int, default=1,
                       help="每 cell 独立生成样本数（>1 平滑单次方差，成本线性上涨）")
    p_run.add_argument("--no-judge", action="store_true", help="关闭 LLM 评审，仅机械评分")
    p_run.add_argument("--run-tag", default=None, help="批次标签（默认 bench-时间戳）")
    p_run.add_argument("--report-dir", default=None,
                       help="报告根目录（默认 backend/storage/bench/reports）")
    p_run.add_argument("--cleanup", action="store_true", help="跑完后按 run_tag 清理 bench 项目")
    p_run.add_argument("--yes", action="store_true", help="跳过成本确认")
    p_run.add_argument("--dry-run", action="store_true",
                       help="桩掉全部 LLM 出口做零成本全链路冒烟")
    p_run.add_argument("--respect-time-budget", action="store_true",
                       help="保留生产的生成时间预算(GENERATION_TIME_BUDGET_SEC)；"
                            "默认 bench 会将其置 0——预算随机砍后处理步会污染测量")
    p_run.set_defaults(func=cmd_run)

    p_cleanup = sub.add_parser("cleanup", help="清理 bench 项目（按 run_tag 或全量）")
    p_cleanup.add_argument("--run-tag", default=None, help="要清理的批次标签")
    p_cleanup.add_argument("--all-bench", action="store_true",
                           help="删除 bench 用户名下全部项目（需 --yes 确认）")
    p_cleanup.add_argument("--yes", action="store_true", help="确认 --all-bench 全量删除")
    p_cleanup.set_defaults(func=cmd_cleanup)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2

    # 相对路径锚定 backend/（sqlite/storage/报告目录不随调用方 CWD 漂移）
    os.chdir(BACKEND_DIR)
    # 必须在任何 app 模块导入之前生效（settings 单例导入时定型）
    _apply_time_budget_override(getattr(args, "respect_time_budget", False))

    env_error = _ensure_app_importable()
    if env_error:
        print(env_error, file=sys.stderr)
        return 2

    async def _run_with_teardown() -> int:
        try:
            return await args.func(args)
        finally:
            # 事件循环关闭前收尾 redis 连接，否则进程退出时 __del__ 在已关循环上
            # 析构连接，刷出 "RuntimeError: Event loop is closed" 噪音 traceback
            try:
                from app.services.cache_service import close_all_cache_clients

                await close_all_cache_clients()
            except Exception:
                pass

    try:
        return asyncio.run(_run_with_teardown())
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n已中断。已生成的 bench 项目可用 "
              "`python run_bench.py cleanup --run-tag <批次标签>` 清理"
              "（或 cleanup --all-bench --yes 全量清）。",
              file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
