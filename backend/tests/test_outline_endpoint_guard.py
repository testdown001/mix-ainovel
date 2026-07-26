"""/chapters/outline 端点落库校验回归。

锁定两件事（此前遗漏，regenerate-outlines 路径早有同款校验）：
1. LLM 返回缺字段的项被跳过，不再 KeyError → 500；
2. LLM 返回已完成章节号时跳过，不静默覆盖其大纲。
"""
import asyncio
import json
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException

import app.models.user_quota  # noqa: F401  防 mapper KeyError
from app.api.routers import writer


class _DummySession:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True


def _make_project(chapters=None, outlines=None):
    return NS(
        chapters=chapters or [],
        outlines=outlines or [],
    )


class _FakeNovelService:
    instances = []

    def __init__(self, session, project=None):
        self.session = session
        self.saved = []  # (chapter_number, title, summary)
        self.project = project if project is not None else _make_project()
        _FakeNovelService.instances.append(self)

    async def ensure_project_owner(self, project_id, user_id):
        return self.project

    async def _serialize_project(self, project):
        return NS(blueprint=NS(model_dump=lambda: {"title": "测试蓝图"}))

    async def update_or_create_outline(self, project_id, chapter_number, title, summary):
        self.saved.append((chapter_number, title, summary))


class _FakePromptService:
    def __init__(self, session):
        pass

    async def get_prompt(self, name):
        return "大纲生成系统提示词"


class _FakeCacheService:
    async def invalidate_project_schema(self, project_id):
        pass


def _run_endpoint(monkeypatch, project, llm_payload):
    """monkeypatch 端点内部依赖后直接调用端点函数，返回 (novel_service, session)。"""
    _FakeNovelService.instances = []

    class _BoundNovelService(_FakeNovelService):
        def __init__(self, session):
            super().__init__(session, project=project)

    class _FakeLLMService:
        def __init__(self, session):
            pass

        async def get_llm_response(self, **kwargs):
            return llm_payload

    async def _fake_load_schema(service, project_id, user_id):
        return NS(id=project_id)

    monkeypatch.setattr(writer, "NovelService", _BoundNovelService)
    monkeypatch.setattr(writer, "PromptService", _FakePromptService)
    monkeypatch.setattr(writer, "LLMService", _FakeLLMService)
    monkeypatch.setattr(writer, "CacheService", _FakeCacheService)
    monkeypatch.setattr(writer, "_load_project_schema", _fake_load_schema)

    request = NS(
        start_chapter=2,
        num_chapters=4,
        estimated_total_chapters=None,
        user_prompt=None,
    )
    session = _DummySession()
    result = asyncio.run(
        writer.generate_chapters_outline(
            "p1", request, session=session, current_user=NS(id=1)
        )
    )
    assert result.id == "p1"
    return _FakeNovelService.instances[0], session


def test_missing_fields_skipped_not_500(monkeypatch):
    """缺 chapter_number/title/summary 的项被跳过（修复前 KeyError → 500）。"""
    payload = json.dumps(
        {
            "chapters": [
                {"title": "缺章号", "summary": "x"},
                {"chapter_number": 4, "summary": "缺标题"},
                {"chapter_number": 5, "title": "缺摘要"},
                {"chapter_number": "第六章", "title": "章号非数字", "summary": "x"},
                {"chapter_number": 3, "title": "正常章", "summary": "正常摘要"},
            ]
        },
        ensure_ascii=False,
    )
    service, session = _run_endpoint(monkeypatch, _make_project(), payload)
    assert service.saved == [(3, "正常章", "正常摘要")]
    assert session.committed


def test_completed_chapter_not_overwritten(monkeypatch):
    """LLM 返回已完成章节号时跳过，不覆盖其大纲；未完成章照常落库。"""
    project = _make_project(
        chapters=[
            NS(chapter_number=1, status="successful"),
            NS(chapter_number=2, status="failed"),
        ],
        outlines=[
            NS(chapter_number=1, title="旧一章", summary="旧摘要1"),
            NS(chapter_number=2, title="旧二章", summary="旧摘要2"),
        ],
    )
    payload = json.dumps(
        {
            "chapters": [
                {"chapter_number": 1, "title": "妄图覆盖", "summary": "bad"},
                {"chapter_number": 2, "title": "重写未完成章", "summary": "ok2"},
                {"chapter_number": 3, "title": "新章", "summary": "ok3"},
            ]
        },
        ensure_ascii=False,
    )
    service, session = _run_endpoint(monkeypatch, project, payload)
    assert service.saved == [(2, "重写未完成章", "ok2"), (3, "新章", "ok3")]
    assert session.committed


def test_normal_items_all_saved(monkeypatch):
    """无缺字段、无已完成章冲突时，全部照常落库。"""
    payload = json.dumps(
        {
            "chapters": [
                {"chapter_number": 2, "title": "二章", "summary": "s2"},
                {"chapter_number": 3, "title": "三章", "summary": "s3"},
            ]
        },
        ensure_ascii=False,
    )
    service, session = _run_endpoint(monkeypatch, _make_project(), payload)
    assert service.saved == [(2, "二章", "s2"), (3, "三章", "s3")]
    assert session.committed


def test_out_of_range_chapter_skipped(monkeypatch):
    """章号超出本次请求范围 [start, start+num-1] 的项被跳过（repair_json 修复残缺回包时易产生 0/负数/越界章号）。"""
    payload = json.dumps(
        {
            "chapters": [
                {"chapter_number": 0, "title": "零章", "summary": "x"},
                {"chapter_number": -3, "title": "负章", "summary": "x"},
                {"chapter_number": 99999, "title": "越界章", "summary": "x"},
                {"chapter_number": 5, "title": "边界内", "summary": "ok"},
            ]
        },
        ensure_ascii=False,
    )
    service, session = _run_endpoint(monkeypatch, _make_project(), payload)
    assert service.saved == [(5, "边界内", "ok")]
    assert session.committed


def test_string_chapter_number_coerced(monkeypatch):
    """数字字符串章号（LLM 常见输出 "4"）被强转后正常落库，而非静默跳过。"""
    payload = json.dumps(
        {"chapters": [{"chapter_number": "4", "title": "字符串章号", "summary": "s"}]},
        ensure_ascii=False,
    )
    service, session = _run_endpoint(monkeypatch, _make_project(), payload)
    assert service.saved == [(4, "字符串章号", "s")]
    assert session.committed


def test_unparseable_response_still_500(monkeypatch):
    """完全不可解析的响应仍走原有 500 分支（仅新增校验，不改其他行为）。"""
    with pytest.raises(HTTPException) as exc_info:
        _run_endpoint(monkeypatch, _make_project(), "这不是 JSON 也修不好 [[[")
    assert exc_info.value.status_code == 500
