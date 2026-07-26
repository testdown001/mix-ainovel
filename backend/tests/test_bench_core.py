"""bench 核心库测试：夹具 / 配置矩阵 / 评分器（mock LLM，绝不真调）。

覆盖：demo 夹具解析与 round-trip；sqlite 播种完整性与完成态口径；双配置播种
互不共享项目；先行章向量播种（逐章调用 + 失败降级）；cleanup 干净（含无外键的
chapter_reviews / writing_archives + best-effort 向量清理）+ cleanup_all_bench；
Unknown column 包装 BenchSeedSchemaError；freeze 往返等价；full 配置真实取自
resolve_config 白名单（防漂移动态断言）；消融变体（含 KNOWN_INTERACTIONS
no_op/语义注记）；机械评分各指标（含 distinct_ratio 定长口径）；judge mock
解析与 A/B 位置互换逻辑。
"""
import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

import app.models  # noqa: F401  触发全部 mapper 注册
from app.models.chapter_review import ChapterReview
from app.models.entity_registry import EntityRegistry
from app.models.novel import (
    BlueprintCharacter,
    Chapter,
    ChapterOutline,
    ChapterVersion,
    NovelBlueprint,
    NovelProject,
)
from app.models.user import User
from app.models.writing_archive import WritingArchive
from app.services.bench import fixtures as bench_fixtures
from app.services.bench import scoring as bench_scoring
from app.services.bench.configs import (
    BUILTIN_CONFIGS,
    DEFAULT_ABLATION_SWITCHES,
    FULL,
    KNOWN_INTERACTIONS,
    QUALITY_SWITCHES,
    BenchConfig,
    build_ablations,
)
from app.services.bench.fixtures import (
    BENCH_USERNAME,
    FIXTURES_DIR,
    BenchScenario,
    BenchSeedSchemaError,
    cleanup_all_bench,
    cleanup_run,
    freeze_project,
    load_scenario,
    seed_scenario,
    seed_scenario_vectors,
)
from app.services.llm_service import LLMService
from app.services.pipeline_config_service import PipelineConfigService

DEMO_PATH = FIXTURES_DIR / "demo_xuanhuan.json"


def _demo() -> BenchScenario:
    return load_scenario(DEMO_PATH)


@pytest.fixture(autouse=True)
def _stub_vector_store(monkeypatch):
    """测试环境 .env 可能真配了 QDRANT_HOST——默认把 fixtures 的向量清理出口
    桩成 no-op，保证单测不碰网络（专项测试再各自覆写）。"""

    class _NoopVectorStore:
        def __init__(self):
            pass

        async def delete_by_chapters(self, project_id, chapter_numbers):
            pass

    monkeypatch.setattr(bench_fixtures, "VectorStoreService", _NoopVectorStore)


# ---------------------------------------------------------------------------
# 夹具 schema / demo 夹具
# ---------------------------------------------------------------------------
def test_demo_fixture_parses():
    scenario = _demo()
    assert scenario.scenario_id == "demo_xuanhuan"
    assert scenario.target_chapter == 4
    assert len(scenario.outlines) == 6
    assert len(scenario.prior_chapters) == 3
    assert 2 <= len(scenario.must_include) <= 3
    assert len(scenario.blueprint["volumes"]) == 2
    # 每个先行章 600-900 字左右的中文正文 + 摘要
    for prior in scenario.prior_chapters:
        assert 500 <= len(prior.content) <= 1000, f"第{prior.chapter_number}章正文长度异常"
        assert len(prior.summary) >= 40
    # 必含词应真实出现在目标章大纲里（保证机械评分有据可依）
    target_outline = next(o for o in scenario.outlines if o.chapter_number == 4)
    for term in scenario.must_include:
        assert term in target_outline.summary


def test_scenario_dict_roundtrip():
    scenario = _demo()
    restored = BenchScenario.from_dict(scenario.to_dict())
    assert restored.to_dict() == scenario.to_dict()


# ---------------------------------------------------------------------------
# 播种
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_seed_scenario_complete(db_session):
    scenario = _demo()
    project_id = await seed_scenario(db_session, scenario, "bench-seed")

    project = await db_session.get(NovelProject, project_id)
    assert project is not None
    assert project.title.startswith("[bench-seed] ")

    user = (
        await db_session.execute(select(User).where(User.username == BENCH_USERNAME))
    ).scalar_one()
    assert project.user_id == user.id
    assert user.is_active is True

    blueprint = await db_session.get(NovelBlueprint, project_id)
    assert blueprint.genre == "玄幻"
    assert len(blueprint.volumes) == 2

    character_count = (
        await db_session.execute(
            select(func.count()).select_from(BlueprintCharacter).where(
                BlueprintCharacter.project_id == project_id
            )
        )
    ).scalar_one()
    assert character_count == 5

    outline_count = (
        await db_session.execute(
            select(func.count()).select_from(ChapterOutline).where(
                ChapterOutline.project_id == project_id
            )
        )
    ).scalar_one()
    assert outline_count == 6

    # 先行章完成态口径：selected_version_id 非空 + status=successful + real_summary
    for prior in scenario.prior_chapters:
        chapter = (
            await db_session.execute(
                select(Chapter).where(
                    Chapter.project_id == project_id,
                    Chapter.chapter_number == prior.chapter_number,
                )
            )
        ).scalar_one()
        assert chapter.selected_version_id is not None
        assert chapter.status == "successful"
        assert chapter.real_summary == prior.summary
        assert chapter.word_count == len(prior.content)
        version = await db_session.get(ChapterVersion, chapter.selected_version_id)
        assert version.content == prior.content


@pytest.mark.asyncio
async def test_seed_twice_isolated_projects_shared_user(db_session):
    scenario = _demo()
    pid_a = await seed_scenario(db_session, scenario, "bench-iso")
    pid_b = await seed_scenario(db_session, scenario, "bench-iso")
    assert pid_a != pid_b

    # bench 用户 get-or-create：只建一次
    user_count = (
        await db_session.execute(
            select(func.count()).select_from(User).where(User.username == BENCH_USERNAME)
        )
    ).scalar_one()
    assert user_count == 1

    # 项目域数据互不共享（各自独立的章节副本）
    for pid in (pid_a, pid_b):
        completed = (
            await db_session.execute(
                select(func.count()).select_from(Chapter).where(
                    Chapter.project_id == pid,
                    Chapter.selected_version_id.is_not(None),
                )
            )
        ).scalar_one()
        assert completed == 3


# ---------------------------------------------------------------------------
# 先行章向量播种（P1-2：逐章调用 + 失败降级）
# ---------------------------------------------------------------------------
class _FakeLLMForVectors:
    def __init__(self, session):
        pass

    async def get_embedding(self, text, **kwargs):
        return [0.1] * 8


def _enable_vector_store(monkeypatch):
    # vector_store_enabled 是 Settings 的 @property（bool(qdrant_host)），
    # 类级覆写为 True（monkeypatch 自动还原）
    monkeypatch.setattr(
        type(bench_fixtures.settings), "vector_store_enabled", True
    )


@pytest.mark.asyncio
async def test_seed_scenario_vectors_ingests_each_prior_chapter(db_session, monkeypatch):
    _enable_vector_store(monkeypatch)
    calls = []

    class FakeIngestion:
        def __init__(self, *, llm_service):
            pass

        async def ingest_chapter(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(bench_fixtures, "LLMService", _FakeLLMForVectors)
    monkeypatch.setattr(bench_fixtures, "ChapterIngestionService", FakeIngestion)

    scenario = _demo()
    ok = await seed_scenario_vectors(db_session, scenario, "pid-vec")
    assert ok is True
    assert [call["chapter_number"] for call in calls] == [1, 2, 3]
    for call, prior in zip(calls, scenario.prior_chapters):
        assert call["project_id"] == "pid-vec"
        assert call["content"] == prior.content
        assert call["summary"] == prior.summary


@pytest.mark.asyncio
async def test_seed_scenario_vectors_degrades_on_failure(db_session, monkeypatch):
    scenario = _demo()

    # ① 向量库未配置：直接 False，零调用
    monkeypatch.setattr(type(bench_fixtures.settings), "vector_store_enabled", False)
    assert await seed_scenario_vectors(db_session, scenario, "pid") is False

    # ② embedding 探针失败（返回 []）：False，且不逐章调用
    _enable_vector_store(monkeypatch)
    calls = []

    class ProbeFailLLM:
        def __init__(self, session):
            pass

        async def get_embedding(self, text, **kwargs):
            return []

    class NeverIngestion:
        def __init__(self, *, llm_service):
            pass

        async def ingest_chapter(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(bench_fixtures, "LLMService", ProbeFailLLM)
    monkeypatch.setattr(bench_fixtures, "ChapterIngestionService", NeverIngestion)
    assert await seed_scenario_vectors(db_session, scenario, "pid") is False
    assert calls == []

    # ③ 入库中途抛异常（如 Qdrant 挂了）：捕获降级 False，不上抛
    class BoomIngestion:
        def __init__(self, *, llm_service):
            pass

        async def ingest_chapter(self, **kwargs):
            raise RuntimeError("qdrant down")

    monkeypatch.setattr(bench_fixtures, "LLMService", _FakeLLMForVectors)
    monkeypatch.setattr(bench_fixtures, "ChapterIngestionService", BoomIngestion)
    assert await seed_scenario_vectors(db_session, scenario, "pid") is False


# ---------------------------------------------------------------------------
# 播种撞 schema 落后（P2f）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_seed_unknown_column_wrapped_as_schema_error(db_session, monkeypatch):
    class SchemaLagNovelService:
        def __init__(self, session):
            pass

        async def replace_blueprint(self, project_id, blueprint):
            raise OperationalError(
                "INSERT INTO ...", {},
                Exception("(1054, \"Unknown column 'foo' in 'field list'\")"),
            )

    monkeypatch.setattr(bench_fixtures, "NovelService", SchemaLagNovelService)
    with pytest.raises(BenchSeedSchemaError) as exc_info:
        await seed_scenario(db_session, _demo(), "bench-schema")
    assert "Unknown column" in str(exc_info.value)

    # 非 Unknown column 的 OperationalError 原样上抛，不误包装
    class OtherFailNovelService:
        def __init__(self, session):
            pass

        async def replace_blueprint(self, project_id, blueprint):
            raise OperationalError("SELECT 1", {}, Exception("Lock wait timeout exceeded"))

    monkeypatch.setattr(bench_fixtures, "NovelService", OtherFailNovelService)
    with pytest.raises(OperationalError):
        await seed_scenario(db_session, _demo(), "bench-schema2")


# ---------------------------------------------------------------------------
# 清理
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cleanup_run_removes_everything(db_session):
    scenario = _demo()
    pid_1 = await seed_scenario(db_session, scenario, "runA")
    pid_2 = await seed_scenario(db_session, scenario, "runA")
    pid_keep = await seed_scenario(db_session, scenario, "runB")

    # 补种无外键约束的两张表（数据库级联管不到，验证逐表清理覆盖它们）
    db_session.add(
        ChapterReview(project_id=pid_1, chapter_number=1, approved=False, overall_score=55.0)
    )
    db_session.add(
        WritingArchive(imperial_edict_id="ed_bench_test_001", project_id=pid_1, chapter_number=1)
    )
    await db_session.commit()

    deleted = await cleanup_run(db_session, "runA")
    assert deleted == 2

    for pid in (pid_1, pid_2):
        assert await db_session.get(NovelProject, pid) is None
        for model in (Chapter, ChapterOutline, ChapterReview, WritingArchive, EntityRegistry):
            count = (
                await db_session.execute(
                    select(func.count()).select_from(model).where(model.project_id == pid)
                )
            ).scalar_one()
            assert count == 0, f"{model.__tablename__} 残留 project_id={pid}"
        assert await db_session.get(NovelBlueprint, pid) is None

    # 版本行（无 project_id 的孙表）也应清空——runA 双项目共 6 个先行章版本被删
    # 仅剩 runB 的 3 个
    version_total = (
        await db_session.execute(select(func.count()).select_from(ChapterVersion))
    ).scalar_one()
    assert version_total == 3

    # 不同 run_tag 的项目不受影响
    keep = await db_session.get(NovelProject, pid_keep)
    assert keep is not None
    keep_completed = (
        await db_session.execute(
            select(func.count()).select_from(Chapter).where(
                Chapter.project_id == pid_keep,
                Chapter.selected_version_id.is_not(None),
            )
        )
    ).scalar_one()
    assert keep_completed == 3

    # 空 run_tag 幂等
    assert await cleanup_run(db_session, "runA") == 0
    assert await cleanup_run(db_session, "no-such-tag") == 0


@pytest.mark.asyncio
async def test_cleanup_all_bench_removes_every_run(db_session):
    scenario = _demo()
    await seed_scenario(db_session, scenario, "runX")
    await seed_scenario(db_session, scenario, "runY")

    removed = await cleanup_all_bench(db_session)
    assert removed == 2

    remaining = (
        await db_session.execute(select(func.count()).select_from(NovelProject))
    ).scalar_one()
    assert remaining == 0
    # 幂等
    assert await cleanup_all_bench(db_session) == 0


@pytest.mark.asyncio
async def test_cleanup_deletes_vectors_best_effort(db_session, monkeypatch):
    """P1-2：cleanup 按项目现存章号 best-effort 删 Qdrant 向量；失败仅降级 warning。"""
    monkeypatch.setattr(type(bench_fixtures.settings), "vector_store_enabled", True)
    recorded = []

    class RecordingVectorStore:
        def __init__(self):
            pass

        async def delete_by_chapters(self, project_id, chapter_numbers):
            recorded.append((project_id, sorted(chapter_numbers)))

    monkeypatch.setattr(bench_fixtures, "VectorStoreService", RecordingVectorStore)
    scenario = _demo()
    pid = await seed_scenario(db_session, scenario, "vec-run")
    assert await cleanup_run(db_session, "vec-run") == 1
    assert len(recorded) == 1
    assert recorded[0][0] == pid
    assert {1, 2, 3} <= set(recorded[0][1])  # 至少覆盖 3 个先行章

    # 向量层抛异常：清理照常完成（best-effort）
    class BoomVectorStore:
        def __init__(self):
            pass

        async def delete_by_chapters(self, project_id, chapter_numbers):
            raise RuntimeError("qdrant down")

    monkeypatch.setattr(bench_fixtures, "VectorStoreService", BoomVectorStore)
    pid2 = await seed_scenario(db_session, scenario, "vec-run2")
    assert await cleanup_run(db_session, "vec-run2") == 1
    assert await db_session.get(NovelProject, pid2) is None


# ---------------------------------------------------------------------------
# 冻结（seed → freeze → re-seed 往返）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_freeze_roundtrip(db_session):
    scenario = _demo()
    project_id = await seed_scenario(db_session, scenario, "bench-frz")

    frozen = await freeze_project(
        db_session,
        project_id,
        upto_chapter=3,
        target_chapter=4,
        scenario_id=scenario.scenario_id,
        description=scenario.description,
        must_include=scenario.must_include,
    )
    assert frozen.to_dict() == scenario.to_dict()

    # 冻结产物可再播种，且完成态口径一致
    pid_2 = await seed_scenario(db_session, frozen, "bench-frz2")
    completed = (
        await db_session.execute(
            select(func.count()).select_from(Chapter).where(
                Chapter.project_id == pid_2,
                Chapter.selected_version_id.is_not(None),
            )
        )
    ).scalar_one()
    assert completed == 3


# ---------------------------------------------------------------------------
# 配置矩阵
# ---------------------------------------------------------------------------
def test_builtin_configs_shape():
    assert set(BUILTIN_CONFIGS) == {"standard", "premium", "full"}
    assert BUILTIN_CONFIGS["standard"].preset == "standard"
    assert BUILTIN_CONFIGS["standard"].flow_config == {}
    assert BUILTIN_CONFIGS["premium"].preset == "premium"
    assert FULL.preset == "premium"
    assert FULL.flow_config == {switch: True for switch in QUALITY_SWITCHES}
    assert FULL.to_flow_config()["preset"] == "premium"


@pytest.mark.asyncio
async def test_full_switches_really_overridable(db_session):
    """防漂移动态断言：QUALITY_SWITCHES 每个键都必须真实位于
    resolve_config 的 flow_config 覆写白名单内（True/False 双向覆写都生效）。
    白名单收缩或键改名时此测试立即翻红。"""
    service = PipelineConfigService(db_session)
    for switch in QUALITY_SWITCHES:
        config_on = await service.resolve_config({"preset": "premium", switch: True})
        assert getattr(config_on, switch) is True, f"{switch} 开覆写未生效（不在白名单？）"
        config_off = await service.resolve_config({"preset": "premium", switch: False})
        assert getattr(config_off, switch) is False, f"{switch} 关覆写未生效（不在白名单？）"

    # full 配置整体解析后所有质量开关均为开
    resolved = await service.resolve_config(FULL.to_flow_config())
    for switch in QUALITY_SWITCHES:
        assert getattr(resolved, switch) is True


def test_build_ablations():
    variants = build_ablations(FULL)
    assert len(variants) == len(DEFAULT_ABLATION_SWITCHES)
    names = {variant.name for variant in variants}
    assert "full-minus-optimizer" in names
    assert "full-minus-consistency" in names
    for variant, switch in zip(variants, DEFAULT_ABLATION_SWITCHES):
        assert variant.preset == FULL.preset
        assert variant.flow_config[switch] is False
        # 其余开关保持全开
        others = [k for k in QUALITY_SWITCHES if k != switch]
        assert all(variant.flow_config[k] is True for k in others)
    # base 不被就地修改
    assert all(value is True for value in FULL.flow_config.values())


def test_build_ablations_custom_switches():
    base = BenchConfig(name="premium", preset="premium")
    variants = build_ablations(base, ["enable_rag"])
    assert len(variants) == 1
    assert variants[0].name == "premium-minus-rag"
    assert variants[0].flow_config == {"enable_rag": False}


def test_build_ablations_marks_known_interactions():
    """P1-3：KNOWN_INTERACTIONS 标注——enrichment 被 optimizer 压制 → no_op；
    optimizer 反向激活 polish/enrichment → 语义注记；无交互开关无标注。"""
    variants = {
        v.name: v
        for v in build_ablations(
            FULL, ["enable_enrichment", "enable_optimizer", "enable_rag"]
        )
    }

    enrichment = variants["full-minus-enrichment"]
    assert enrichment.no_op is True
    assert enrichment.note and "压制" in enrichment.note

    optimizer = variants["full-minus-optimizer"]
    assert optimizer.no_op is False
    assert optimizer.note and "组合步 vs 独立步" in optimizer.note

    rag = variants["full-minus-rag"]
    assert rag.no_op is False and rag.note is None

    # 条件开关未显式开（premium 底座空 flow_config）→ 不标注
    base = BenchConfig(name="premium", preset="premium")
    plain = build_ablations(base, ["enable_enrichment"])[0]
    assert plain.no_op is False and plain.note is None

    # 注册表形状防漂移：effect 只允许两种取值
    for meta in KNOWN_INTERACTIONS.values():
        assert meta["effect"] in ("suppressed", "semantics_change")
        assert meta["note"]
        assert meta["condition_switch"]


# ---------------------------------------------------------------------------
# 机械评分
# ---------------------------------------------------------------------------
def _sample_chapter_text(scenario: BenchScenario) -> str:
    body = (
        "沈青崖踏入丹阁大门，檀香与药气扑面而来。执事捧出玉瓶，称这便是试炼头名的血魄丹。\n"
        "「丹瓶被人换过了。」识海里焚寂冷冷开口，「瓶底的封泥是新的，丹方也是伪造的。」\n"
        "赵擎的人影从廊柱后转出，冷笑着喝出「偷丹」二字，四周执事围拢过来。\n"
        "沈青崖不退反进，将玉瓶举过头顶，一字一句道明封泥与丹方的破绽。\n"
        "争执惊动了内堂。段云舟拂袖而出，燎原丹火在他掌心一燃，真伪立判，执事面如死灰。\n"
    ) * 3
    ending = "他刚要退出丹阁，识海深处的焚寂忽然一颤：「等等——它就在下面。」"
    return body + ending


def test_mechanical_score_metrics():
    scenario = _demo()
    text = _sample_chapter_text(scenario)
    result = bench_scoring.mechanical_score(
        text, scenario, target_min_chars=300, target_max_chars=5000
    )

    assert result["length"] == len(text)
    # must_include 三词都在正文里 → 无缺词，长度过关
    assert result["bench_lite"]["missing_terms"] == []
    assert result["bench_lite"]["length_status"] == "passed"
    assert result["bench_lite"]["score"] >= 70
    # 人味分为 0-100 整数
    assert 0 <= result["humanization"]["score"] <= 100
    # 结尾钩子：末段短 + 对话/悬念信号
    assert result["ending_hook"]["has_hook"] is True
    assert "short_paragraph" in result["ending_hook"]["signals"]
    # 重复度：正文由重复块构成，distinct ratio 应显著低于 1
    assert 0.0 < result["repetition"]["distinct_ratio"] < 0.75
    # 段落统计
    assert result["paragraphs"]["count"] == 16
    assert result["paragraphs"]["dialogue_ratio"] > 0


def test_mechanical_score_detects_missing_terms_and_length():
    scenario = _demo()
    text = "少年推门而入，殿内空无一人。\n他等了一夜。"
    result = bench_scoring.mechanical_score(
        text, scenario, target_min_chars=300, target_max_chars=5000
    )
    assert set(result["bench_lite"]["missing_terms"]) == set(scenario.must_include)
    assert result["bench_lite"]["length_status"] == "failed"
    assert result["bench_lite"]["status"] == "failed"


def test_repetition_metric_bounds():
    highly_repetitive = "同样的一句话。" * 60
    diverse = _sample_chapter_text(_demo())
    rep_high = bench_scoring._repetition_metrics(highly_repetitive)
    rep_low = bench_scoring._repetition_metrics(diverse)
    assert rep_high["distinct_ratio"] < rep_low["distinct_ratio"]
    assert rep_high["distinct_ratio"] < 0.05


def test_repetition_metric_fixed_window():
    """P2e：distinct_ratio 按前 3000 字定长口径——追加超窗内容不改变结果，
    消除「更长正文天然更低 ratio」的长度伪影。"""
    diverse = "".join(chr(0x4E00 + (i * 37) % 20000) for i in range(3000))
    padded = diverse + "同样的一句话。" * 400  # 窗外的高重复尾巴

    base = bench_scoring._repetition_metrics(diverse)
    result = bench_scoring._repetition_metrics(padded)
    assert result["window_chars"] == 3000
    assert result["total_ngrams"] == base["total_ngrams"] == 3000 - 4 + 1
    assert result["distinct_ratio"] == base["distinct_ratio"]

    # 不足窗口取全量
    short = bench_scoring._repetition_metrics("短文本测试内容")
    assert short["total_ngrams"] == len("短文本测试内容") - 4 + 1


# ---------------------------------------------------------------------------
# LLM 评审（mock 通道出口，绝不真调 LLM）
# ---------------------------------------------------------------------------
_JUDGE_JSON = json.dumps(
    {
        "immersion": {"score": 7, "reason": "画面感尚可"},
        "pacing": {"score": 6, "reason": "中段略拖"},
        "hook": {"score": 8, "reason": "结尾悬念有效"},
        "character": {"score": 7, "reason": "人设稳定"},
        "prose": {"score": 5, "reason": "偶有AI腔"},
        "outline_fit": {"score": 9, "reason": "完成大纲推进"},
    },
    ensure_ascii=False,
)


@pytest.mark.asyncio
async def test_judge_absolute_prefers_grader_channel(db_session):
    scenario = _demo()
    llm = LLMService(db_session)
    calls = {"grader": 0, "default": 0}

    async def fake_grader(system_prompt, conversation_history, **kwargs):
        calls["grader"] += 1
        prompt = conversation_history[0]["content"]
        # 模板占位符已被真实填充
        assert "{{chapter_text}}" not in prompt
        assert "丹阁风波" in prompt
        return _JUDGE_JSON

    async def fake_generate(*args, **kwargs):
        calls["default"] += 1
        return _JUDGE_JSON

    llm.get_grader_llm_response = fake_grader
    llm.generate = fake_generate

    result = await bench_scoring.judge_absolute(llm, "正文内容", scenario)
    assert calls == {"grader": 1, "default": 0}
    assert result["judge_channel"] == "grader"
    assert result["hook"]["score"] == 8
    assert result["overall"] == pytest.approx((7 + 6 + 8 + 7 + 5 + 9) / 6, abs=0.01)


@pytest.mark.asyncio
async def test_judge_absolute_falls_back_to_default_channel(db_session):
    scenario = _demo()
    llm = LLMService(db_session)
    calls = {"default": 0}

    async def fake_grader(*args, **kwargs):
        raise ValueError("证据评分模型未配置")

    async def fake_generate(*args, **kwargs):
        calls["default"] += 1
        return _JUDGE_JSON

    llm.get_grader_llm_response = fake_grader
    llm.generate = fake_generate

    result = await bench_scoring.judge_absolute(llm, "正文内容", scenario)
    assert calls["default"] == 1
    assert result["judge_channel"] == "default"


def _make_content_aware_pair_judge(marker: str):
    """按内容判胜负的假评审：版本 A 段落含 marker 则 A 胜，否则 B 胜。"""

    async def fake_grader(system_prompt, conversation_history, **kwargs):
        prompt = conversation_history[0]["content"]
        section_a = prompt.split("## 版本 A")[1].split("## 版本 B")[0]
        winner = "A" if marker in section_a else "B"
        return json.dumps({"winner": winner, "reason": "内容更佳"}, ensure_ascii=False)

    return fake_grader


@pytest.mark.asyncio
async def test_judge_pairwise_consistent_winner(db_session):
    scenario = _demo()
    llm = LLMService(db_session)
    llm.get_grader_llm_response = _make_content_aware_pair_judge("神来之笔")

    result = await bench_scoring.judge_pairwise(
        llm, "这段有神来之笔。", "平平无奇的一段。", scenario
    )
    # 两次互换位置都判同一文本胜 → 一致，text_a 胜
    assert result["consistent"] is True
    assert result["winner"] == "a"
    assert [p["verdict"] for p in result["passes"]] == ["a", "a"]
    assert [p["raw_winner"] for p in result["passes"]] == ["A", "B"]

    # 反向：好文本作为 text_b 传入 → b 胜
    result_b = await bench_scoring.judge_pairwise(
        llm, "平平无奇的一段。", "这段有神来之笔。", scenario
    )
    assert result_b["winner"] == "b"
    assert result_b["consistent"] is True


@pytest.mark.asyncio
async def test_judge_pairwise_position_bias_becomes_tie(db_session):
    scenario = _demo()
    llm = LLMService(db_session)

    async def always_first(system_prompt, conversation_history, **kwargs):
        # 位置偏差模型：永远选 A
        return json.dumps({"winner": "A", "reason": "先看到的顺眼"}, ensure_ascii=False)

    llm.get_grader_llm_response = always_first

    result = await bench_scoring.judge_pairwise(llm, "文本一", "文本二", scenario)
    assert result["consistent"] is False
    assert result["winner"] == "tie"
    assert [p["verdict"] for p in result["passes"]] == ["a", "b"]


@pytest.mark.asyncio
async def test_judge_pairwise_double_tie_is_consistent(db_session):
    scenario = _demo()
    llm = LLMService(db_session)

    async def always_tie(system_prompt, conversation_history, **kwargs):
        return json.dumps({"winner": "tie", "reason": "难分高下"}, ensure_ascii=False)

    llm.get_grader_llm_response = always_tie

    result = await bench_scoring.judge_pairwise(llm, "文本一", "文本二", scenario)
    assert result["winner"] == "tie"
    assert result["consistent"] is True
