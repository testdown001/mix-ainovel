"""bench 跑批器 / 报告 / CLI 测试（mock HybridExecutor 与 judge，绝不真调 LLM）。

覆盖：2 场景 × 3 配置矩阵（cell 独立播种、基线成对对比、进度回调）；
失败 cell 不中断且报告显式标注；消融 delta 表（含 ▲ 标注与胜负）与落盘产物；
后台任务 drain（完成/超时 cancel）；no_op 消融变体跳过生成；时间预算砍步透传；
环境快照；向量播种失败标记；CLI --dry-run 全链路冒烟（假 LLM 桩 + 内存库 +
报告 + --cleanup）与 cleanup 子命令/预算覆写/LLM_API_KEY 回退/schema 报错提示。
"""
import asyncio
import json
import os
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  触发全部 mapper 注册
from app.db.base import Base
from app.models.novel import NovelProject
from app.services.bench import fixtures as bench_fixtures
from app.services.bench import report as bench_report
from app.services.bench import runner as bench_runner
from app.services.bench.configs import FULL, PREMIUM, STANDARD, build_ablations
from app.services.bench.fixtures import FIXTURES_DIR, load_scenario
from app.services.bench.runner import run_bench

DEMO_PATH = FIXTURES_DIR / "demo_xuanhuan.json"

_DIMS = ("immersion", "pacing", "hook", "character", "prose", "outline_fit")

_ENV_SNAPSHOT_KEYS = (
    "llm_model", "llm_base_url_host", "llm_grader_configured",
    "writer_chapter_versions", "writer_fast_mode", "writer_ultra_fast_mode",
    "generation_time_budget_sec", "rag_retrieval_mode", "rerank_enabled", "rerank_configured",
    "db_provider",
)


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(bind=engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest.fixture(autouse=True)
def _stub_vector_store(monkeypatch):
    """测试环境 .env 可能真配了 QDRANT_HOST——把 fixtures 的向量清理出口
    桩成 no-op，保证单测不碰网络。"""

    class _NoopVectorStore:
        def __init__(self):
            pass

        async def delete_by_chapters(self, project_id, chapter_numbers):
            pass

    monkeypatch.setattr(bench_fixtures, "VectorStoreService", _NoopVectorStore)


# ---------------------------------------------------------------------------
# mock：HybridExecutor 与 judge
# ---------------------------------------------------------------------------
def _make_fake_executor(fail_predicate=None, calls=None):
    """假执行器：正文带 preset/开关标记，供内容感知的假 judge 拉开分差。"""

    class FakeExecutor:
        def __init__(self, session, user_id=None):
            self.session = session
            self.user_id = user_id

        async def generate_chapter(
            self,
            *,
            project_id,
            chapter_number,
            writing_notes=None,
            flow_config=None,
            stream_handler=None,
            use_agent=False,
        ):
            flow_config = flow_config or {}
            if calls is not None:
                calls.append(dict(flow_config))
            if fail_predicate is not None and fail_predicate(flow_config):
                raise RuntimeError("boom: 生成炸了")
            marker = "OPT_ON" if flow_config.get("enable_optimizer") else "OPT_OFF"
            text = (
                f"[{flow_config.get('preset')}|{marker}] "
                + "沈青崖走进丹阁，香雾缭绕，识海里的断剑轻轻震颤。\n" * 40
            )
            return {
                "project_id": project_id,
                "chapter_number": chapter_number,
                "preset": flow_config.get("preset", "fast"),
                "best_version_index": 0,
                "variants": [
                    {"index": 0, "version_id": 1, "content": text, "metadata": {}}
                ],
                "review_summaries": {"note": "fake"},
            }

    return FakeExecutor


def _score_for(text: str) -> float:
    if "OPT_ON" in text:
        return 8.0
    if "premium" in text:
        return 7.0
    return 6.0


async def _fake_judge_absolute(llm, chapter_text, scenario, **kwargs):
    score = _score_for(chapter_text)
    data = {dim: {"score": score, "reason": f"{dim} 理由"} for dim in _DIMS}
    data["overall"] = score
    data["judge_channel"] = "mock"
    return data


async def _fake_judge_pairwise(llm, text_a, text_b, scenario, **kwargs):
    score_a, score_b = _score_for(text_a), _score_for(text_b)
    winner = "a" if score_a > score_b else ("b" if score_b > score_a else "tie")
    return {
        "winner": winner,
        "consistent": True,
        "judge_channel": "mock",
        "passes": [
            {"order": "ab", "verdict": winner, "raw_winner": "A", "reason": "内容更佳"},
            {"order": "ba", "verdict": winner, "raw_winner": "B", "reason": "内容更佳"},
        ],
    }


async def _fake_seed_vectors(session, scenario, project_id):
    return True


def _patch_mocks(monkeypatch, fail_predicate=None, calls=None, seed_vectors=None):
    monkeypatch.setattr(
        bench_runner, "HybridExecutor", _make_fake_executor(fail_predicate, calls)
    )
    monkeypatch.setattr(bench_runner, "judge_absolute", _fake_judge_absolute)
    monkeypatch.setattr(bench_runner, "judge_pairwise", _fake_judge_pairwise)
    monkeypatch.setattr(
        bench_runner, "seed_scenario_vectors", seed_vectors or _fake_seed_vectors
    )


def _two_scenarios():
    first = load_scenario(DEMO_PATH)
    second = load_scenario(DEMO_PATH)
    second.scenario_id = "demo_copy"
    return first, second


# ---------------------------------------------------------------------------
# 矩阵跑批
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_run_bench_matrix_cells_isolated(session_factory, monkeypatch):
    _patch_mocks(monkeypatch)
    scenarios = _two_scenarios()
    events = []

    result = await run_bench(
        scenarios,
        [STANDARD, PREMIUM, FULL],
        judge=True,
        pairwise_baseline="standard",
        run_tag="bench-test-matrix",
        progress_cb=events.append,
        session_factory=session_factory,
    )

    assert result.scenario_ids == ["demo_xuanhuan", "demo_copy"]
    assert result.config_names == ["standard", "premium", "full"]
    assert result.config_specs["full"]["preset"] == "premium"
    assert len(result.cells) == 6

    # 每个 cell 独立播种项目：6 个互不相同的 project_id，且都真实落库
    project_ids = {cell.samples[0].project_id for cell in result.cells}
    assert len(project_ids) == 6
    async with session_factory() as session:
        count = (
            await session.execute(
                select(func.count()).select_from(NovelProject).where(
                    NovelProject.title.like("[bench-test-matrix] %")
                )
            )
        ).scalar_one()
    assert count == 6

    for cell in result.cells:
        sample = cell.samples[0]
        assert sample.error is None
        assert sample.mechanical is not None
        assert sample.judge["judge_channel"] == "mock"
        assert sample.review_summaries == {"note": "fake"}
        if cell.config_name == "standard":
            assert sample.pairwise is None  # 基线 cell 不与自己对比
        else:
            assert sample.pairwise["winner"] in ("a", "b", "tie")

    # 假 judge 按内容打分：premium/full 均应胜过 standard 基线
    assert result.cell("demo_xuanhuan", "premium").samples[0].pairwise["winner"] == "a"
    assert result.cell("demo_xuanhuan", "full").samples[0].pairwise["winner"] == "a"

    kinds = {event["event"] for event in events}
    assert {"cell_start", "sample_done", "cell_done", "run_done"} <= kinds


@pytest.mark.asyncio
async def test_failed_cell_recorded_and_run_continues(session_factory, monkeypatch):
    # premium 配置（未显式开 optimizer）生成必炸；standard/full 应照常完成
    _patch_mocks(
        monkeypatch,
        fail_predicate=lambda fc: fc.get("preset") == "premium"
        and not fc.get("enable_optimizer"),
    )
    scenario = load_scenario(DEMO_PATH)

    result = await run_bench(
        [scenario],
        [STANDARD, PREMIUM, FULL],
        judge=True,
        pairwise_baseline="standard",
        run_tag="bench-test-fail",
        session_factory=session_factory,
    )

    failed = result.cell("demo_xuanhuan", "premium").samples[0]
    assert failed.error is not None and "RuntimeError: boom" in failed.error
    assert failed.judge is None and failed.pairwise is None  # 失败样本不评审
    for name in ("standard", "full"):
        assert result.cell("demo_xuanhuan", name).samples[0].error is None

    # 报告两种格式都显式标注失败，绝不静默丢 cell
    json_str, markdown = bench_report.render(result)
    data = json.loads(json_str)
    assert len(data["cells"]) == 3
    assert data["failures"] == [
        {
            "scenario_id": "demo_xuanhuan",
            "config_name": "premium",
            "sample": 0,
            "stage": "生成",
            "error": failed.error,
        }
    ]
    assert "## ④ 失败 cell 清单" in markdown
    assert "RuntimeError: boom" in markdown
    assert "**生成失败**" in markdown


# ---------------------------------------------------------------------------
# 后台任务 drain（P1-1）
# ---------------------------------------------------------------------------
def _make_bg_task_executor(spawned, sleep_s):
    """假执行器：模拟 schedule_followups 的 fire-and-forget 后台任务。"""

    class BgExecutor:
        def __init__(self, session, user_id=None):
            pass

        async def generate_chapter(self, *, project_id, chapter_number, **kwargs):
            spawned.append(asyncio.create_task(asyncio.sleep(sleep_s)))
            text = "沈青崖走进丹阁，香雾缭绕。\n" * 40
            return {
                "project_id": project_id,
                "chapter_number": chapter_number,
                "best_version_index": 0,
                "variants": [{"index": 0, "content": text, "metadata": {}}],
                "review_summaries": {},
            }

    return BgExecutor


@pytest.mark.asyncio
async def test_runner_drains_background_tasks(session_factory, monkeypatch):
    """样本收尾必须等 fire-and-forget 后台任务：runner 返回时任务已完成，
    事件循环里无 pending（cleanup/restore 之前绝无竞态孤儿）。"""
    spawned = []
    _patch_mocks(monkeypatch)
    monkeypatch.setattr(
        bench_runner, "HybridExecutor", _make_bg_task_executor(spawned, sleep_s=0.05)
    )
    scenario = load_scenario(DEMO_PATH)

    result = await run_bench(
        [scenario], [STANDARD], judge=False, pairwise_baseline=None,
        run_tag="bench-test-drain", session_factory=session_factory,
    )

    assert spawned, "假执行器应派生后台任务"
    assert all(task.done() for task in spawned), "runner 返回时后台任务应已完成"
    sample = result.cells[0].samples[0]
    assert sample.error is None
    assert sample.followups_timeout is False
    current = asyncio.current_task()
    leftover = [
        t for t in asyncio.all_tasks() if t is not current and not t.done()
    ]
    assert leftover == [], f"runner 返回后不应残留 pending 任务: {leftover}"


@pytest.mark.asyncio
async def test_runner_drain_timeout_cancels_and_flags(session_factory, monkeypatch):
    """drain 超时：任务被 cancel，样本记 followups_timeout=True。"""
    spawned = []
    _patch_mocks(monkeypatch)
    monkeypatch.setattr(
        bench_runner, "HybridExecutor", _make_bg_task_executor(spawned, sleep_s=30)
    )
    scenario = load_scenario(DEMO_PATH)

    result = await run_bench(
        [scenario], [STANDARD], judge=False, pairwise_baseline=None,
        run_tag="bench-test-drain-to", session_factory=session_factory,
        drain_timeout=0.05,
    )

    sample = result.cells[0].samples[0]
    assert sample.followups_timeout is True
    assert all(task.done() for task in spawned), "超时任务应已被 cancel"
    assert any(task.cancelled() for task in spawned)
    # 报告 cell 详情显式标注
    _, markdown = bench_report.render(result)
    assert "drain 超时" in markdown


# ---------------------------------------------------------------------------
# no_op 消融变体跳过生成（P1-3）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_op_variant_skipped_without_generation(session_factory, monkeypatch):
    """full-minus-enrichment（optimizer 开启压制 enrichment）与 full 管线等价：
    runner 零生成调用、零播种，报告消融表标「与基准管线等价，未跑」。"""
    calls = []
    _patch_mocks(monkeypatch, calls=calls)
    scenario = load_scenario(DEMO_PATH)
    configs = [FULL] + build_ablations(FULL, ["enable_enrichment"])
    variant = configs[1]
    assert variant.no_op is True and variant.note
    events = []

    result = await run_bench(
        [scenario], configs, judge=True, pairwise_baseline="full",
        run_tag="bench-test-noop", progress_cb=events.append,
        session_factory=session_factory,
    )

    # 只有 full cell 真跑（1 次生成调用、1 个播种项目）
    assert len(calls) == 1
    async with session_factory() as session:
        count = (
            await session.execute(
                select(func.count()).select_from(NovelProject).where(
                    NovelProject.title.like("[bench-test-noop] %")
                )
            )
        ).scalar_one()
    assert count == 1

    cell = result.cell("demo_xuanhuan", "full-minus-enrichment")
    assert cell.skipped_no_op is True
    assert cell.samples == []
    assert result.config_specs["full-minus-enrichment"]["no_op"] is True
    assert "cell_skipped" in {event["event"] for event in events}

    json_str, markdown = bench_report.render(result)
    data = json.loads(json_str)
    row = data["ablation"][0]
    assert row["no_op"] is True
    assert row["delta_overall"] is None
    assert "与基准管线等价，未跑" in markdown


# ---------------------------------------------------------------------------
# 时间预算砍步透传（P1-4 belt+braces）
# ---------------------------------------------------------------------------
def _make_budget_skipping_executor(skipped_steps):
    class BudgetExecutor:
        def __init__(self, session, user_id=None):
            pass

        async def generate_chapter(self, *, project_id, chapter_number, **kwargs):
            text = "沈青崖走进丹阁，香雾缭绕。\n" * 40
            return {
                "project_id": project_id,
                "chapter_number": chapter_number,
                "best_version_index": 0,
                "variants": [{"index": 0, "content": text, "metadata": {}}],
                "review_summaries": {
                    "time_budget": {"exceeded": True, "skipped": list(skipped_steps)}
                },
            }

    return BudgetExecutor


@pytest.mark.asyncio
async def test_budget_skipped_steps_surface_in_report(session_factory, monkeypatch):
    _patch_mocks(monkeypatch)
    monkeypatch.setattr(
        bench_runner, "HybridExecutor",
        _make_budget_skipping_executor(["optimizer", "enrichment"]),
    )
    scenario = load_scenario(DEMO_PATH)
    configs = [FULL] + build_ablations(FULL, ["enable_rag"])

    result = await run_bench(
        [scenario], configs, judge=True, pairwise_baseline="full",
        run_tag="bench-test-budget", session_factory=session_factory,
    )

    sample = result.cells[0].samples[0]
    assert sample.budget_skipped_steps == ["optimizer", "enrichment"]

    json_str, markdown = bench_report.render(result)
    data = json.loads(json_str)
    assert data["cells"][0]["stats"]["budget_skipped"] == ["enrichment", "optimizer"]
    # cell 详情 + 消融表备注两处都警示「数字不可信」
    assert "被时间预算砍步" in markdown
    assert "数字不可信" in markdown
    row = data["ablation"][0]
    assert "被时间预算砍步" in row["note"]


# ---------------------------------------------------------------------------
# 环境快照（P1-5）与向量播种标记（P1-2）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_environment_snapshot_keys_and_markdown(session_factory, monkeypatch):
    _patch_mocks(monkeypatch)
    scenario = load_scenario(DEMO_PATH)

    result = await run_bench(
        [scenario], [STANDARD], judge=False, pairwise_baseline=None,
        run_tag="bench-test-env", session_factory=session_factory,
    )

    for key in _ENV_SNAPSHOT_KEYS:
        assert key in result.environment, f"环境快照缺 {key}"
    # 内存库无 SystemConfig → 显式「未配置」而非缺键
    assert result.environment["llm_model"] == "（未配置）"

    json_str, markdown = bench_report.render(result)
    assert "## 环境快照" in markdown
    assert "rag_retrieval_mode" in markdown
    assert "生成时间预算" in markdown
    data = json.loads(json_str)
    assert data["environment"] == result.environment


@pytest.mark.asyncio
async def test_vectors_seed_failure_flagged_in_report(session_factory, monkeypatch):
    async def failing_seed(session, scenario, project_id):
        return False

    _patch_mocks(monkeypatch, seed_vectors=failing_seed)
    scenario = load_scenario(DEMO_PATH)

    result = await run_bench(
        [scenario], [STANDARD], judge=False, pairwise_baseline=None,
        run_tag="bench-test-novec", session_factory=session_factory,
    )

    assert result.vectors_seeded is False
    assert result.cells[0].samples[0].vectors_seeded is False
    _, markdown = bench_report.render(result)
    assert "本 run 向量层不可用" in markdown
    assert "RAG 相关配置差异无效" in markdown


# ---------------------------------------------------------------------------
# 消融报告 + 落盘
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_report_ablation_delta_and_artifacts(session_factory, monkeypatch, tmp_path):
    _patch_mocks(monkeypatch)
    scenario = load_scenario(DEMO_PATH)
    configs = [FULL] + build_ablations(FULL, ["enable_optimizer"])

    result = await run_bench(
        [scenario],
        configs,
        judge=True,
        pairwise_baseline="full",
        run_tag="bench-test-abl",
        session_factory=session_factory,
    )

    json_str, markdown = bench_report.render(result)
    data = json.loads(json_str)

    # 消融 delta：full(8.0) − full-minus-optimizer(7.0) = +1.0，显著 → ▲
    assert len(data["ablation"]) == 1
    row = data["ablation"][0]
    assert row["switch"] == "optimizer"
    assert row["base"] == "full" and row["variant"] == "full-minus-optimizer"
    assert row["delta_overall"] == pytest.approx(1.0)
    assert row["variant_pairwise"] == {"win": 0, "tie": 0, "loss": 1}
    # 已实证交互：关 optimizer 反向激活独立 polish/enrichment → 语义注记（仍然跑）
    assert row["no_op"] is False
    assert "组合步 vs 独立步" in row["note"]

    assert "## ② 消融差异表" in markdown
    assert "| optimizer |" in markdown
    assert "+1.00▲" in markdown
    assert "0胜/0平/1负" in markdown  # 变体 vs full 基线：负
    assert "组合步 vs 独立步" in markdown  # 备注列呈现语义注记

    # 落盘产物：report.md / report.json / chapters 正文存档
    run_dir = bench_report.write_report(result, base_dir=tmp_path)
    assert run_dir == tmp_path / "bench-test-abl"
    assert (run_dir / "report.md").read_text(encoding="utf-8") == markdown
    assert json.loads((run_dir / "report.json").read_text(encoding="utf-8")) == data
    chapters = sorted((run_dir / "chapters").glob("*.txt"))
    assert len(chapters) == 2
    for path in chapters:
        assert path.stat().st_size > 0
    assert (run_dir / "chapters" / "demo_xuanhuan__full__s0.txt").exists()


# ---------------------------------------------------------------------------
# CLI --dry-run 全链路冒烟（真实管线 + 假 LLM 桩 + 内存库）
# ---------------------------------------------------------------------------
class _LazyMemoryFactory:
    """在首次调用时（即 CLI 自己的事件循环内）才建内存库并预载提示词，
    避免跨事件循环复用 aiosqlite 连接。"""

    def __init__(self):
        self._engine = None
        self._maker = None

    async def _ensure(self):
        if self._maker is None:
            self._engine = create_async_engine(
                "sqlite+aiosqlite:///:memory:",
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            self._maker = async_sessionmaker(bind=self._engine, expire_on_commit=False)
            from app.services.prompt_service import PromptService

            async with self._maker() as session:
                await PromptService(session).preload()
                await session.commit()

    @asynccontextmanager
    async def _ctx(self):
        await self._ensure()
        async with self._maker() as session:
            yield session

    def __call__(self):
        return self._ctx()


def test_cli_dry_run_smoke(tmp_path, monkeypatch, capsys):
    import run_bench as bench_cli

    # main() 会 setdefault 该 env；先经 monkeypatch 设定以便测试结束后还原现场
    monkeypatch.setenv("GENERATION_TIME_BUDGET_SEC", "0")
    monkeypatch.setattr(bench_cli, "_SESSION_FACTORY", _LazyMemoryFactory())

    rc = bench_cli.main([
        "run",
        "--scenarios", "demo_xuanhuan",
        "--configs", "standard",
        "--dry-run",
        "--run-tag", "bench-dryrun-test",
        "--report-dir", str(tmp_path),
        "--cleanup",
    ])
    out = capsys.readouterr().out
    assert rc == 0, f"CLI 退出码非 0，输出:\n{out}"
    assert "成本预估" in out
    assert "已清理 1 个 bench 项目" in out

    run_dir = tmp_path / "bench-dryrun-test"
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "demo_xuanhuan" in markdown and "standard" in markdown
    assert "生成失败" not in markdown

    data = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert data["run_tag"] == "bench-dryrun-test"
    sample = data["cells"][0]["samples"][0]
    assert sample["error"] is None
    assert sample["chapter_chars"] > 500
    assert sample["mechanical"]["bench_lite"]["score"] is not None

    chapters = list((run_dir / "chapters").glob("*.txt"))
    assert chapters and chapters[0].stat().st_size > 500

    # dry-run 桩已恢复：LLM 出口不应残留假函数（防污染同进程其它测试）
    from app.services.llm_service import LLMService

    assert "fake" not in LLMService.get_llm_response.__name__


def test_cli_unknown_config_and_switch_errors(monkeypatch, capsys, tmp_path):
    import run_bench as bench_cli

    monkeypatch.setenv("GENERATION_TIME_BUDGET_SEC", "0")
    rc = bench_cli.main([
        "run", "--scenarios", "demo_xuanhuan", "--configs", "nope", "--yes",
        "--report-dir", str(tmp_path),
    ])
    assert rc == 2
    assert "未知配置" in capsys.readouterr().err

    rc = bench_cli.main([
        "run", "--scenarios", "demo_xuanhuan", "--configs", "full",
        "--ablate", "six_dimension", "--yes", "--report-dir", str(tmp_path),
    ])
    assert rc == 2
    assert "不可消融" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# CLI：时间预算覆写 / LLM_API_KEY 回退 / cleanup 子命令 / schema 报错提示
# ---------------------------------------------------------------------------
def test_time_budget_override_env(monkeypatch):
    """P1-4：默认把 GENERATION_TIME_BUDGET_SEC 置 0（setdefault，不覆盖显式设定）；
    --respect-time-budget 不动 env。"""
    import run_bench as bench_cli

    # 经 monkeypatch 先占位再删除：记录原始状态，测试后自动还原
    monkeypatch.setenv("GENERATION_TIME_BUDGET_SEC", "sentinel")
    monkeypatch.delenv("GENERATION_TIME_BUDGET_SEC")

    bench_cli._apply_time_budget_override(respect=True)
    assert "GENERATION_TIME_BUDGET_SEC" not in os.environ

    bench_cli._apply_time_budget_override(respect=False)
    assert os.environ["GENERATION_TIME_BUDGET_SEC"] == "0"

    os.environ["GENERATION_TIME_BUDGET_SEC"] = "300"
    bench_cli._apply_time_budget_override(respect=False)
    assert os.environ["GENERATION_TIME_BUDGET_SEC"] == "300"  # 显式设定不被覆盖


@pytest.mark.asyncio
async def test_check_llm_configured_env_fallback(session_factory, monkeypatch):
    """P2b：SystemConfig 无 llm.api_key 时回退 env LLM_API_KEY（与 LLMService 解析一致）。"""
    import run_bench as bench_cli

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(bench_cli.CLIError):
        await bench_cli._check_llm_configured(session_factory)

    monkeypatch.setenv("LLM_API_KEY", "sk-test-env")
    await bench_cli._check_llm_configured(session_factory)  # 不应抛


def test_cli_cleanup_argument_validation(monkeypatch, capsys):
    import run_bench as bench_cli

    monkeypatch.setenv("GENERATION_TIME_BUDGET_SEC", "0")
    rc = bench_cli.main(["cleanup"])
    assert rc == 2
    assert "二选一" in capsys.readouterr().err

    rc = bench_cli.main(["cleanup", "--all-bench"])
    assert rc == 2
    assert "--yes" in capsys.readouterr().err

    rc = bench_cli.main(["cleanup", "--run-tag", "x", "--all-bench", "--yes"])
    assert rc == 2
    assert "二选一" in capsys.readouterr().err


def test_cli_cleanup_subcommand_removes_projects(monkeypatch, capsys, tmp_path):
    """先 dry-run 落 1 个项目（不 --cleanup），再用独立 cleanup 子命令清掉。"""
    import run_bench as bench_cli

    monkeypatch.setenv("GENERATION_TIME_BUDGET_SEC", "0")
    factory = _LazyMemoryFactory()
    monkeypatch.setattr(bench_cli, "_SESSION_FACTORY", factory)

    rc = bench_cli.main([
        "run", "--scenarios", "demo_xuanhuan", "--configs", "standard",
        "--dry-run", "--run-tag", "bench-cleanup-cli", "--report-dir", str(tmp_path),
    ])
    out = capsys.readouterr().out
    assert rc == 0, f"CLI 退出码非 0，输出:\n{out}"
    assert "cleanup --run-tag bench-cleanup-cli" in out  # 保留提示指向 cleanup 子命令

    rc = bench_cli.main(["cleanup", "--run-tag", "bench-cleanup-cli"])
    assert rc == 0
    assert "已清理 1 个 bench 项目" in capsys.readouterr().out

    # 幂等：再清一次 0 个
    rc = bench_cli.main(["cleanup", "--run-tag", "bench-cleanup-cli"])
    assert rc == 0
    assert "已清理 0 个 bench 项目" in capsys.readouterr().out


def test_cli_seed_schema_error_hint(monkeypatch, capsys, tmp_path):
    """P2f：播种撞 Unknown column（schema 落后）→ CLIError 附 init_db 补列提示。"""
    import app.services.bench.runner as runner_mod
    import run_bench as bench_cli
    from app.services.bench.fixtures import BenchSeedSchemaError

    async def boom_run_bench(*args, **kwargs):
        raise BenchSeedSchemaError("(asyncmy) Unknown column 'chapters.foo' in 'field list'")

    monkeypatch.setenv("GENERATION_TIME_BUDGET_SEC", "0")
    monkeypatch.setattr(runner_mod, "run_bench", boom_run_bench)
    monkeypatch.setattr(bench_cli, "_SESSION_FACTORY", _LazyMemoryFactory())

    rc = bench_cli.main([
        "run", "--scenarios", "demo_xuanhuan", "--configs", "standard",
        "--dry-run", "--report-dir", str(tmp_path),
    ])
    err = capsys.readouterr().err
    assert rc == 2
    assert "Unknown column" in err
    assert "init_db" in err and "启动一次后端" in err
