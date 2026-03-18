import asyncio
from types import SimpleNamespace

from app.services.generation_support_service import GenerationSupportService


class _DummyScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return list(self._values)

    def first(self):
        return self._values[0] if self._values else None


class _DummyExecuteResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _DummyScalarResult(self._values)


class _DummySession:
    def __init__(self, values):
        self._values = values

    async def execute(self, stmt):
        return _DummyExecuteResult(self._values)


class _DummyReferenceService:
    async def get_by_ids(self, ids):
        return [
            SimpleNamespace(id=1, status="ready"),
            SimpleNamespace(id=2, status="draft"),
        ]


def test_generation_support_service_build_fast_rag_queries():
    service = GenerationSupportService(_DummySession([]))
    blueprint = SimpleNamespace(
        chapter_focus="黑玉碎片与宗门追查",
        brief_summary="主角追查黑玉碎片",
        chapter_function="revelation",
        suspense_type="mystery",
        emotional_arc="压抑后反击",
        mission_constraints={"must_include": ["黑玉碎片", "宗门长老"]},
    )

    queries = service.build_fast_rag_queries(
        outline_title="黑玉真相",
        outline_summary="主角逐步逼近真相",
        writing_notes="强化悬念",
        chapter_blueprint=blueprint,
    )

    assert queries[0] == "黑玉真相"
    assert "强化悬念" in queries
    assert len(queries) <= 4


def test_generation_support_service_load_project_reference_novels():
    service = GenerationSupportService(_DummySession([]))
    project = SimpleNamespace(reference_novel_ids=[1, 2])

    novels = asyncio.run(
        service.load_project_reference_novels(project, _DummyReferenceService())
    )

    assert len(novels) == 1
    assert novels[0].status == "ready"


def test_generation_support_service_validate_coolpoint_rhythm_mutates_mission():
    blueprints = [
        SimpleNamespace(cognitive_twist_level=0, chapter_function="progression"),
        SimpleNamespace(cognitive_twist_level=0, chapter_function="progression"),
        SimpleNamespace(cognitive_twist_level=0, chapter_function="progression"),
        SimpleNamespace(cognitive_twist_level=0, chapter_function="progression"),
        SimpleNamespace(cognitive_twist_level=0, chapter_function="progression"),
        SimpleNamespace(cognitive_twist_level=0, chapter_function="progression"),
    ]
    service = GenerationSupportService(_DummySession(blueprints))
    mission = {"satisfaction_design": {"type": "推进成长"}}

    directive = asyncio.run(
        service.validate_coolpoint_rhythm("proj-1", 8, mission)
    )

    assert directive is not None
    assert "节奏强制纠偏" in directive
    assert mission["satisfaction_design"]["type"] == "逆袭爽"
