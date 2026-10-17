"""Benchmark receipts and per-adopted-text accounting reuse existing usage only."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import hashlib

import pytest
from sqlalchemy import select

from app.models.novel import Chapter, ChapterVersion, NovelProject
from app.services.bench.runner import (SampleResult, adopt_bench_winner,
    capture_sample_telemetry, price_sample_usage, validate_model_prices)
from app.services.bench.fixtures import FIXTURES_DIR, load_scenario, seed_scenario, seed_scenario_vectors
from app.services.chapter_ingest_service import IngestionReceipt
from app.services.retrieval_scope import RetrievalScope


@pytest.fixture(autouse=True)
def no_external_cache(monkeypatch):
    from app.services.cache_service import CacheService
    for method in ("get_project_schema", "set_project_schema", "invalidate_project_schema"):
        monkeypatch.setattr(CacheService, method, AsyncMock(return_value=None))


def test_costs_require_real_usage_and_explicit_price_snapshot():
    sample = SampleResult(index=0, chapter_text="文" * 2000, duration_ms=6000,
                          output_basis="adopted_manuscript")
    capture_sample_telemetry(sample, {"preset":"standard", "variants":[{"metadata":{
        "execution_receipt":{"status":"recorded", "steps":[{"step":"review","status":"report_completed"}]}}}],
        "debug_metadata":{"stages":{"review":True}, "llm_metrics":{
            "summary":{"prompt_tokens":1000,"completion_tokens":2000,"call_count":1},
            "calls":[{"model":"writer","prompt_tokens":1000,"completion_tokens":2000}]}}})
    prices = validate_model_prices({"writer":{"currency":"USD","input_per_million":1,"output_per_million":2}})
    price_sample_usage(sample, prices)
    assert sample.generation_cost['amount'] == .005
    assert sample.adopted_metrics() == {"status":"measured", "tokens":1500., "cost":.0025,
                                       "currency":"USD", "latency_ms":3000.}
    assert sample.execution_receipt['steps'][0]['status'] == "report_completed"
    assert sample.resolved_config['completeness'] == "partial"
    price_sample_usage(sample, {})
    assert sample.generation_cost['amount'] is None
    assert sample.generation_cost['unpriced_models'] == ['writer']
    assert sample.adopted_metrics()['cost'] is None
    sample.output_basis = "recommended_candidate"
    assert sample.adopted_metrics()['status'] == 'not_adopted'


@pytest.mark.parametrize('price', [float('nan'), float('inf'), -1])
def test_price_snapshot_rejects_unsafe_rates(price):
    with pytest.raises(ValueError):
        validate_model_prices({'writer':{'currency':'USD','input_per_million':price,'output_per_million':1}})


def test_unknown_execution_and_usage_do_not_become_free_completed_work():
    sample = SampleResult(index=0)
    capture_sample_telemetry(sample, {'preset':'premium','debug_metadata':{'stages':{'polish':True}}})
    price_sample_usage(sample, {})
    assert sample.execution_receipt['status'] == 'unknown'
    assert sample.llm_usage['total_tokens'] is None
    assert sample.generation_cost['amount'] is None
    assert sample.to_dict()['per_1000_adopted_chars']['tokens'] is None


@pytest.mark.asyncio
async def test_benchmark_adoption_does_not_touch_a_user_project(db_session):
    project = NovelProject(id='protected',user_id=1,title='author project',creation_source='user')
    db_session.add(project)
    await db_session.commit()
    result = await adopt_bench_winner(db_session, {'variants':[{'version_id':1,'content':'candidate'}]},
            project_id=project.id,chapter_number=4,user_id=1)
    assert result['status'] == 'not_adopted'
    assert result['reason'] == 'not_isolated_benchmark'


@pytest.mark.asyncio
async def test_benchmark_winner_is_adopted_by_real_revision_boundary(db_session):
    project = NovelProject(id='bench',user_id=1,title='benchmark',creation_source='ai_test')
    chapter = Chapter(project_id='bench',chapter_number=4)
    db_session.add_all([project,chapter])
    await db_session.flush()
    version = ChapterVersion(chapter_id=chapter.id, content='有效正文。' * 500, source='generation')
    db_session.add(version)
    await db_session.commit()
    result = await adopt_bench_winner(db_session, {'variants':[{'version_id':version.id,'content':version.content}]},
            project_id='bench',chapter_number=4,user_id=1)
    assert result['status'] == 'adopted'
    assert result['source_version_id'] == version.id
    assert result['source_content_hash'] == hashlib.sha256(version.content.encode()).hexdigest()


@pytest.mark.asyncio
async def test_fixture_vector_seeding_activates_source_bound_indices(db_session, monkeypatch):
    from app.services.bench import fixtures
    from app.services.chapter_ingest_service import ChapterIngestionService
    from app.core.config import settings
    monkeypatch.setattr(type(settings), 'vector_store_enabled', property(lambda self: True))
    scenario = load_scenario(FIXTURES_DIR / 'demo_xuanhuan.json')
    project_id = await seed_scenario(db_session,scenario,'safe-vector-fixture')
    counter = []
    async def fake_ingest(self, **kwargs):
        counter.append(kwargs)
        return IngestionReceipt(f'new-index-{kwargs["chapter_number"]}',1,1,'not_requested')
    monkeypatch.setattr(ChapterIngestionService,'ingest_chapter',fake_ingest)
    assert await seed_scenario_vectors(db_session,scenario,project_id)
    bound = await RetrievalScope.build(db_session,project_id=project_id,before_chapter=scenario.target_chapter)
    for call in counter:
        number = call['chapter_number']
        assert bound.accepts(number,{**call['source_ref'],'index_revision_id':f'new-index-{number}'})
    assert len(counter) == len(scenario.prior_chapters)
