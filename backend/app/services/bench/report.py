# AIMETA P=基准报告渲染|R=JSON与Markdown报告_消融差异表_正文存档落盘|NR=不跑批不评分|E=render_write_report|X=internal|A=报告器|D=runner结果结构|S=none
"""基准报告：render(result) -> (json_str, markdown) + write_report 落盘。

Markdown 四段：
① 配置 × 场景总表（六维均分/机械分/时长/胜负）
② 消融差异表（base vs base-minus-X 的逐指标 delta + pairwise 胜负，
   delta 约定：Δ = base − 变体，正值 = 该开关有正贡献，显著方向 ▲/▼）
③ 每 cell 详情（评审理由摘录）
④ 失败 cell 清单

write_report 写入 backend/storage/bench/reports/<run_tag>/：
report.md / report.json / chapters/<cell>.txt 正文存档。
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .runner import BenchRunResult, CellResult, SampleResult

logger = logging.getLogger(__name__)

# backend/ 根（与 fixtures.FIXTURES_DIR 同一取法）
_BACKEND_DIR = Path(__file__).resolve().parents[3]
DEFAULT_REPORTS_DIR = _BACKEND_DIR / "storage" / "bench" / "reports"

_DIMS = ("immersion", "pacing", "hook", "character", "prose", "outline_fit")
_DIM_LABELS = {
    "immersion": "沉浸",
    "pacing": "节奏",
    "hook": "钩子",
    "character": "人物",
    "prose": "文笔",
    "outline_fit": "契合",
}

# delta 显著阈值（超过才标 ▲/▼）
_DELTA_THRESHOLD_JUDGE = 0.5   # 六维 1-10 分制
_DELTA_THRESHOLD_MECH = 3.0    # 机械分 0-100 分制


def _slug(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z_\-一-鿿]+", "_", name).strip("_") or "cell"


def _mean(values: List[float]) -> Optional[float]:
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _fmt(value: Optional[float], nd: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{nd}f}"


def _fmt_delta(value: Optional[float], threshold: float, nd: int = 2) -> str:
    if value is None:
        return "—"
    marker = ""
    if value >= threshold:
        marker = "▲"
    elif value <= -threshold:
        marker = "▼"
    return f"{value:+.{nd}f}{marker}"


def _truncate(text: str, limit: int = 60) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# cell 聚合
# ---------------------------------------------------------------------------
def _cell_stats(cell: CellResult) -> Dict[str, Any]:
    """一个 cell 的样本均值聚合（失败样本不计入均值）。"""
    ok = cell.ok_samples
    judged = [s for s in ok if s.judge]
    mech = [s for s in ok if s.mechanical]
    stats: Dict[str, Any] = {
        "ok": len(ok),
        "total": len(cell.samples),
        "judge_overall": _mean([s.judge.get("overall") for s in judged]),
        "dims": {
            dim: _mean([(s.judge.get(dim) or {}).get("score") for s in judged])
            for dim in _DIMS
        },
        "mech_score": _mean([s.mechanical["bench_lite"].get("score") for s in mech]),
        "human_score": _mean([s.mechanical["humanization"].get("score") for s in mech]),
        "distinct_ratio": _mean(
            [s.mechanical["repetition"].get("distinct_ratio") for s in mech]
        ),
        "chars": _mean([float(len(s.chapter_text)) for s in ok]),
        "duration_s": _mean([s.duration_ms / 1000.0 for s in cell.samples]),
        "pairwise": _pairwise_record(ok),
        "skipped_no_op": cell.skipped_no_op,
        "note": cell.note,
        # 被时间预算砍掉的后处理步（任一样本命中即列出——该 cell 数字不可信）
        "budget_skipped": sorted(
            {step for s in cell.samples for step in s.budget_skipped_steps}
        ),
        "followups_timeout": any(s.followups_timeout for s in cell.samples),
    }
    return stats


def _pairwise_record(samples: List[SampleResult]) -> Optional[Dict[str, int]]:
    """胜/平/负计数（winner 相对本 cell：a=本配置胜）。"""
    compared = [s for s in samples if s.pairwise]
    if not compared:
        return None
    record = {"win": 0, "tie": 0, "loss": 0}
    for sample in compared:
        winner = sample.pairwise.get("winner")
        if winner == "a":
            record["win"] += 1
        elif winner == "b":
            record["loss"] += 1
        else:
            record["tie"] += 1
    return record


def _fmt_record(record: Optional[Dict[str, int]], is_baseline: bool) -> str:
    if is_baseline:
        return "基线"
    if record is None:
        return "—"
    return f"{record['win']}胜/{record['tie']}平/{record['loss']}负"


# ---------------------------------------------------------------------------
# 消融配对
# ---------------------------------------------------------------------------
def _ablation_pairs(config_names: List[str]) -> List[Tuple[str, str, str]]:
    """识别 (base, variant, switch) 消融配对：variant 名形如 <base>-minus-<switch>。"""
    pairs: List[Tuple[str, str, str]] = []
    for name in config_names:
        if "-minus-" not in name:
            continue
        candidates = [
            base for base in config_names
            if base != name and name.startswith(base + "-minus-")
        ]
        if not candidates:
            continue
        base = max(candidates, key=len)
        pairs.append((base, name, name[len(base) + len("-minus-"):]))
    return pairs


def _ablation_rows(
    result: BenchRunResult,
    stats_by_key: Dict[Tuple[str, str], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """逐（消融开关 × 场景）行的 delta 数据；多场景时附均值行。"""
    rows: List[Dict[str, Any]] = []
    for base, variant, switch in _ablation_pairs(result.config_names):
        variant_spec = result.config_specs.get(variant) or {}
        per_scenario: List[Dict[str, Any]] = []
        for scenario_id in result.scenario_ids:
            base_stats = stats_by_key.get((scenario_id, base))
            variant_stats = stats_by_key.get((scenario_id, variant))
            if base_stats is None or variant_stats is None:
                continue
            per_scenario.append(
                _delta_row(
                    scenario_id, base, variant, switch,
                    base_stats, variant_stats, variant_spec,
                )
            )
        rows.extend(per_scenario)
        if len(per_scenario) > 1 and not variant_spec.get("no_op"):
            rows.append(_mean_delta_row(per_scenario))
    return rows


def _sub(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b


def _ablation_note(
    variant_spec: Dict[str, Any],
    base_stats: Dict[str, Any],
    variant_stats: Dict[str, Any],
) -> str:
    """消融行备注：no_op / 语义变化注记 + 时间预算砍步警告。"""
    parts: List[str] = []
    if variant_spec.get("no_op"):
        parts.append("与基准管线等价，未跑")
    if variant_spec.get("note"):
        parts.append(str(variant_spec["note"]))
    for label, stats in (("base", base_stats), ("变体", variant_stats)):
        skipped = stats.get("budget_skipped") or []
        if skipped:
            parts.append(f"⚠️ {label} 被时间预算砍步（{'/'.join(skipped)}），数字不可信")
    return "；".join(parts)


def _delta_row(
    scenario_id: str,
    base: str,
    variant: str,
    switch: str,
    base_stats: Dict[str, Any],
    variant_stats: Dict[str, Any],
    variant_spec: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    spec = variant_spec or {}
    no_op = bool(spec.get("no_op"))
    return {
        "scenario_id": scenario_id,
        "base": base,
        "variant": variant,
        "switch": switch,
        "no_op": no_op,
        "note": _ablation_note(spec, base_stats, variant_stats),
        "delta_overall": _sub(base_stats["judge_overall"], variant_stats["judge_overall"]),
        "delta_dims": {
            dim: _sub(base_stats["dims"][dim], variant_stats["dims"][dim]) for dim in _DIMS
        },
        "delta_mech": _sub(base_stats["mech_score"], variant_stats["mech_score"]),
        "delta_duration_s": _sub(base_stats["duration_s"], variant_stats["duration_s"]),
        "variant_pairwise": variant_stats["pairwise"],
    }


def _mean_delta_row(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged_record: Optional[Dict[str, int]] = None
    records = [row["variant_pairwise"] for row in rows if row["variant_pairwise"]]
    if records:
        merged_record = {
            key: sum(record[key] for record in records) for key in ("win", "tie", "loss")
        }
    return {
        "scenario_id": "（均值）",
        "base": rows[0]["base"],
        "variant": rows[0]["variant"],
        "switch": rows[0]["switch"],
        "no_op": False,
        "note": rows[0]["note"],
        "delta_overall": _mean([row["delta_overall"] for row in rows]),
        "delta_dims": {
            dim: _mean([row["delta_dims"][dim] for row in rows]) for dim in _DIMS
        },
        "delta_mech": _mean([row["delta_mech"] for row in rows]),
        "delta_duration_s": _mean([row["delta_duration_s"] for row in rows]),
        "variant_pairwise": merged_record,
    }


# ---------------------------------------------------------------------------
# 失败清单
# ---------------------------------------------------------------------------
def _failures(result: BenchRunResult) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    for cell in result.cells:
        for sample in cell.samples:
            if sample.error:
                failures.append({
                    "scenario_id": cell.scenario_id,
                    "config_name": cell.config_name,
                    "sample": sample.index,
                    "stage": "生成",
                    "error": sample.error,
                })
            elif sample.judge_error:
                failures.append({
                    "scenario_id": cell.scenario_id,
                    "config_name": cell.config_name,
                    "sample": sample.index,
                    "stage": "评审",
                    "error": sample.judge_error,
                })
    return failures


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------
def chapter_filename(scenario_id: str, config_name: str, sample_index: int) -> str:
    return f"{_slug(scenario_id)}__{_slug(config_name)}__s{sample_index}.txt"


def render(result: BenchRunResult) -> Tuple[str, str]:
    """渲染 (json_str, markdown)。JSON 含逐 cell 聚合 stats 与消融 delta 数据。"""
    stats_by_key = {
        (cell.scenario_id, cell.config_name): _cell_stats(cell) for cell in result.cells
    }
    ablation_rows = _ablation_rows(result, stats_by_key)
    failures = _failures(result)

    payload = result.to_dict(include_text=False)
    for cell_dict in payload["cells"]:
        cell_dict["stats"] = stats_by_key[(cell_dict["scenario_id"], cell_dict["config_name"])]
    payload["ablation"] = ablation_rows
    payload["failures"] = failures
    json_str = json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    markdown = _render_markdown(result, stats_by_key, ablation_rows, failures)
    return json_str, markdown


def _render_markdown(
    result: BenchRunResult,
    stats_by_key: Dict[Tuple[str, str], Dict[str, Any]],
    ablation_rows: List[Dict[str, Any]],
    failures: List[Dict[str, Any]],
) -> str:
    lines: List[str] = []
    add = lines.append

    total_samples = sum(len(cell.samples) for cell in result.cells)
    failed_samples = sum(1 for cell in result.cells for s in cell.samples if not s.ok)
    add(f"# 评估基线报告：{result.run_tag}")
    add("")
    if not result.vectors_seeded:
        add("> ⚠️ **本 run 向量层不可用（先行章向量播种失败：Qdrant 未运行或 "
            "embedding 未配置），RAG 相关配置差异无效。**")
        add("")
    add(f"- 时间：{result.started_at} → {result.finished_at}")
    add(f"- 场景：{', '.join(result.scenario_ids)}")
    add(f"- 配置：{', '.join(result.config_names)}")
    add(f"- 对比基线：{result.pairwise_baseline or '（未启用）'}")
    add(f"- 每 cell 样本数：{result.chapters_per_cell}")
    add(f"- LLM 评审：{'开' if result.judge_enabled else '关（仅机械评分）'}")
    add(f"- 样本：{total_samples - failed_samples}/{total_samples} 成功")
    add("")

    # 环境快照（跨 run 可比性的前提）
    if result.environment:
        add("## 环境快照")
        add("")
        env_labels = (
            ("llm_model", "默认 LLM 模型"),
            ("llm_base_url_host", "默认 LLM host"),
            ("llm_grader_configured", "grader 通道已配置"),
            ("writer_chapter_versions", "writer_chapter_versions"),
            ("writer_fast_mode", "writer_fast_mode"),
            ("writer_ultra_fast_mode", "writer_ultra_fast_mode"),
            ("generation_time_budget_sec", "生成时间预算(生效值,秒)"),
            ("rag_retrieval_mode", "rag_retrieval_mode"),
            ("rag_reranker_enabled", "rag_reranker_enabled"),
            ("db_provider", "db_provider"),
        )
        for key, label in env_labels:
            if key in result.environment:
                add(f"- {label}：{result.environment[key]}")
        for key in sorted(set(result.environment) - {key for key, _ in env_labels}):
            add(f"- {key}：{result.environment[key]}")
        add("")

    # ① 总表
    add("## ① 配置 × 场景总表")
    add("")
    dim_headers = " | ".join(_DIM_LABELS[dim] for dim in _DIMS)
    add(
        "| 配置 | 场景 | 成功 | 六维均分 | " + dim_headers
        + " | 机械分 | 人味† | 重复度‡ | 字数 | 时长(s) | vs基线 |"
    )
    add("|" + "---|" * (10 + len(_DIMS)))
    for config_name in result.config_names:
        for scenario_id in result.scenario_ids:
            stats = stats_by_key[(scenario_id, config_name)]
            if stats["skipped_no_op"]:
                dashes = " | ".join("—" for _ in _DIMS)
                add(
                    f"| {config_name} | {scenario_id} | 未跑 | — | {dashes} "
                    f"| — | — | — | — | — | 与基准管线等价，未跑 |"
                )
                continue
            dim_cells = " | ".join(_fmt(stats["dims"][dim]) for dim in _DIMS)
            add(
                f"| {config_name} | {scenario_id} | {stats['ok']}/{stats['total']} "
                f"| {_fmt(stats['judge_overall'], 2)} | {dim_cells} "
                f"| {_fmt(stats['mech_score'])} | {_fmt(stats['human_score'])} "
                f"| {_fmt(stats['distinct_ratio'], 3)} | {_fmt(stats['chars'], 0)} "
                f"| {_fmt(stats['duration_s'])} "
                f"| {_fmt_record(stats['pairwise'], config_name == result.pairwise_baseline)} |"
            )
    add("")
    add("† 人味分与管线内 humanize 步同尺（HumanizationService.scan），非独立指标——"
        "不能用它佐证 humanization 相关开关的贡献。")
    add("‡ 4-gram distinct ratio，按正文前 3000 字定长口径计算（不足 3000 字取全量），"
        "消除长度伪影。")
    add("")

    # ② 消融差异表
    add("## ② 消融差异表")
    add("")
    if not ablation_rows:
        add("（本次运行未包含消融变体。）")
    else:
        add(
            "Δ = base − 变体（正值 = 该开关有正贡献）；"
            f"|Δ| ≥ {_DELTA_THRESHOLD_JUDGE}（六维）/ {_DELTA_THRESHOLD_MECH:.0f}（机械）"
            "时标注 ▲（正贡献显著）/ ▼（负贡献显著）。"
            "Δ时长为正表示该开关额外耗时。变体胜负为变体 vs 本次对比基线"
            f"（{result.pairwise_baseline or '未启用'}）。"
        )
        add("")
        delta_dim_headers = " | ".join("Δ" + _DIM_LABELS[dim] for dim in _DIMS)
        add(
            "| 消融开关 | 场景 | Δ六维均分 | " + delta_dim_headers
            + " | Δ机械分 | Δ时长(s) | 变体胜负 | 备注 |"
        )
        add("|" + "---|" * (7 + len(_DIMS)))
        for row in ablation_rows:
            if row.get("no_op"):
                dashes = " | ".join("—" for _ in _DIMS)
                add(
                    f"| {row['switch']} | {row['scenario_id']} | — | {dashes} "
                    f"| — | — | — | {row.get('note') or '与基准管线等价，未跑'} |"
                )
                continue
            delta_dim_cells = " | ".join(
                _fmt_delta(row["delta_dims"][dim], _DELTA_THRESHOLD_JUDGE)
                for dim in _DIMS
            )
            add(
                f"| {row['switch']} | {row['scenario_id']} "
                f"| {_fmt_delta(row['delta_overall'], _DELTA_THRESHOLD_JUDGE)} "
                f"| {delta_dim_cells} "
                f"| {_fmt_delta(row['delta_mech'], _DELTA_THRESHOLD_MECH, 1)} "
                f"| {_fmt_delta(row['delta_duration_s'], float('inf'), 1)} "
                f"| {_fmt_record(row['variant_pairwise'], False)} "
                f"| {row.get('note') or ''} |"
            )
    add("")

    # ③ 每 cell 详情
    add("## ③ 每 cell 详情")
    add("")
    for cell in result.cells:
        add(f"### {cell.scenario_id} × {cell.config_name}")
        add("")
        if cell.skipped_no_op:
            add(f"- 与基准管线等价，未跑生成。{_truncate(cell.note or '', 200)}")
            add("")
            continue
        for sample in cell.samples:
            if sample.error:
                add(f"- 样本 {sample.index}：**生成失败** — {_truncate(sample.error, 200)}")
                continue
            mech = sample.mechanical or {}
            bench_lite = mech.get("bench_lite") or {}
            human = mech.get("humanization") or {}
            overall = (sample.judge or {}).get("overall")
            add(
                f"- 样本 {sample.index}：六维 {_fmt(overall, 2)}"
                f" | 机械 {_fmt(bench_lite.get('score'))}"
                f" | 人味 {_fmt(human.get('score'))}"
                f" | {len(sample.chapter_text)} 字"
                f" | {sample.duration_ms / 1000:.1f}s"
                f"（正文：chapters/{chapter_filename(cell.scenario_id, cell.config_name, sample.index)}）"
            )
            if sample.judge:
                reasons = "；".join(
                    f"{_DIM_LABELS[dim]} {_fmt((sample.judge.get(dim) or {}).get('score'), 0)}"
                    f"（{_truncate((sample.judge.get(dim) or {}).get('reason', ''), 40)}）"
                    for dim in _DIMS
                )
                add(f"  - 评审：{reasons}")
            if sample.pairwise:
                verdict = {"a": "胜", "b": "负", "tie": "平"}.get(
                    sample.pairwise.get("winner"), "平"
                )
                consistency = "一致" if sample.pairwise.get("consistent") else "两轮不一致→记平"
                pass_reasons = " / ".join(
                    _truncate(p.get("reason", ""), 50)
                    for p in sample.pairwise.get("passes", [])
                )
                add(
                    f"  - 对比基线（{result.pairwise_baseline}）：{verdict}（{consistency}）"
                    f"—— {pass_reasons}"
                )
            if sample.budget_skipped_steps:
                add(
                    f"  - ⚠️ 被时间预算砍步：{'/'.join(sample.budget_skipped_steps)}"
                    "——该样本数字不可信"
                )
            if sample.followups_timeout:
                add("  - ⚠️ 收尾后台任务 drain 超时（已 cancel），伏笔/记忆等后续写入可能不完整")
            if sample.judge_error:
                add(f"  - ⚠️ 评审失败：{_truncate(sample.judge_error, 200)}")
        add("")

    # ④ 失败清单
    add("## ④ 失败 cell 清单")
    add("")
    if not failures:
        add("（无失败。）")
    else:
        add("| 场景 | 配置 | 样本 | 阶段 | 错误 |")
        add("|---|---|---|---|---|")
        for item in failures:
            add(
                f"| {item['scenario_id']} | {item['config_name']} | {item['sample']} "
                f"| {item['stage']} | {_truncate(item['error'], 160)} |"
            )
    add("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 落盘
# ---------------------------------------------------------------------------
def write_report(result: BenchRunResult, base_dir: Optional[Path] = None) -> Path:
    """写入 <base_dir>/<run_tag>/{report.md, report.json, chapters/*.txt}，返回目录。"""
    reports_root = Path(base_dir) if base_dir is not None else DEFAULT_REPORTS_DIR
    run_dir = reports_root / _slug(result.run_tag)
    chapters_dir = run_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    json_str, markdown = render(result)
    (run_dir / "report.json").write_text(json_str + "\n", encoding="utf-8")
    (run_dir / "report.md").write_text(markdown, encoding="utf-8")

    for cell in result.cells:
        for sample in cell.samples:
            if not sample.chapter_text:
                continue
            path = chapters_dir / chapter_filename(
                cell.scenario_id, cell.config_name, sample.index
            )
            path.write_text(sample.chapter_text, encoding="utf-8")

    logger.info("bench 报告已写入 %s", run_dir)
    return run_dir
