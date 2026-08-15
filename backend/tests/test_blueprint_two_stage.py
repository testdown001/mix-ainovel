"""蓝图多段式生成回归测试（审计 P0 #13 + P1 #8；2026-08-15 分批章纲后更新）。

覆盖：
1. 生成成功：设定段 1 次 + 章纲分批 2 次（50 章 ÷ 25 章/批，max_tokens 8192/12288、
   不同模板、批间携带前批尾部上下文），蓝图完整落库且含 volumes 分卷；
2. 章纲不足承诺章数 80% → 按缺失章号区间补问一次后补齐；
3. 补问后仍不足 → 502 且蓝图/大纲均不落库（不再静默落库残缺蓝图）;
4. 旧格式兼容：设定段无 volumes 仍成功，volumes 为空列表；
5. 伏笔 <3 条只记 warning 不阻断；
6. 设定段返回不可解析内容 → 500 且不进入章纲段。

通过最小 FastAPI 应用挂载真实 novels 路由（薄壳端点），LLM/Prompt 在
blueprint_generation_service 模块内打桩，底层走 conftest 真内存 SQLite，
真正命中多段式生成与 replace_blueprint 落库路径。
审稿门在本测试中因 Prompt 表为空（缺 blueprint_review 提示词）自然跳过——
这本身就是「审稿门软失败不阻断蓝图」契约的一部分。
"""
import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

import app.models.user_quota  # noqa: F401  触发 mapper 注册，防 KeyError
from app.api.routers import novels
from app.core.dependencies import get_current_user
from app.db.session import get_session
from app.models.novel import ChapterOutline, NovelBlueprint, NovelConversation, NovelProject
from app.schemas.user import UserInDB
from app.services import blueprint_generation_service as bgs

OWNER = UserInDB(id=1, username="owner", hashed_password="x")
PROJECT_ID = "proj-bp-two-stage"


def _build_client(db_session):
    test_app = FastAPI()
    test_app.include_router(novels.router)

    async def _override_session():
        yield db_session

    async def _override_user():
        return OWNER

    test_app.dependency_overrides[get_session] = _override_session
    test_app.dependency_overrides[get_current_user] = _override_user
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


class _FakePromptService:
    def __init__(self, session):
        pass

    async def get_prompt(self, name):
        return {
            "screenwriting": "SETTINGS_PROMPT",
            "screenwriting_outline": "OUTLINE_PROMPT",
        }.get(name)


def _patch_two_stage(monkeypatch, responses):
    """按调用顺序依次弹出 responses；记录每次调用 kwargs。"""
    calls = []
    queue = list(responses)

    class _FakeLLMService:
        def __init__(self, session):
            pass

        async def get_llm_response(self, **kwargs):
            calls.append(kwargs)
            return queue.pop(0)

    monkeypatch.setattr(bgs, "LLMService", _FakeLLMService)
    monkeypatch.setattr(bgs, "PromptService", _FakePromptService)
    return calls


async def _seed_project_with_history(db_session):
    db_session.add(NovelProject(id=PROJECT_ID, user_id=OWNER.id, title="旧标题"))
    db_session.add(
        NovelConversation(
            project_id=PROJECT_ID, seq=1, role="user",
            content=json.dumps({"value": "我想写一本赛博修仙小说"}, ensure_ascii=False),
        )
    )
    db_session.add(
        NovelConversation(
            project_id=PROJECT_ID, seq=2, role="assistant",
            content=json.dumps({"ai_message": "方向已明确，可以生成蓝图了"}, ensure_ascii=False),
        )
    )
    await db_session.commit()


def _settings_payload(with_volumes=True, foreshadowing_count=5):
    data = {
        "title": "赛博修仙指南",
        "target_audience": "男频",
        "genre": "科幻修仙",
        "style": "热血升级流",
        "tone": "节奏快、压迫感强",
        "one_sentence_summary": "程序员觉醒灵气编译器，硬刚修真大厂。",
        "full_synopsis": "【开局】觉醒【中期】扩张【后期】决战。",
        "world_setting": {
            "core_rules": "灵气可被编译",
            "key_locations": [{"name": "废都", "description": "第一卷主场"}],
            "factions": [{"name": "修真大厂", "description": "垄断灵网"}],
        },
        "golden_finger": {
            "name": "灵气编译器",
            "type": "系统",
            "description": "把功法当代码调试",
            "limitations": "每日编译次数有限",
            "growth_potential": "可解锁新语言特性",
        },
        "characters": [
            {"name": "张三", "identity": "底层程序员", "personality": "轴",
             "goals": "活下去并变强", "abilities": "调试灵气",
             "relationship_to_protagonist": "本人"},
        ],
        "relationships": [
            {"character_from": "张三", "character_to": "李四", "description": "宿敌"},
        ],
        "foreshadowings": [
            {
                "name": f"伏笔{i}",
                "description": "身世线索",
                "planted_chapter": i,
                "target_chapter": i + 10,
                "tier": "支线",
                "type": "hint",
                "reveal_method": "对峙揭破",
                "reveal_impact": "身份反转",
                "related_characters": ["张三"],
                "related_plots": [],
            }
            for i in range(1, foreshadowing_count + 1)
        ],
    }
    if with_volumes:
        data["volumes"] = [
            {"name": "第一卷·废都编译", "start_chapter": 1, "end_chapter": 120,
             "arc_goal": "立足与破局", "climax_hint": "灵网大赛翻案"},
            {"name": "第二卷·灵网扩张", "start_chapter": 121, "end_chapter": 260,
             "arc_goal": "地图与势力升级", "climax_hint": "大厂内战"},
            {"name": "第三卷·根服务器", "start_chapter": 261, "end_chapter": 400,
             "arc_goal": "终局对决", "climax_hint": "重写世界规则"},
        ]
    return json.dumps(data, ensure_ascii=False)


def _outline_payload(numbers):
    return json.dumps(
        {
            "chapter_outline": [
                {"chapter_number": n, "title": f"第{n}章·破局", "summary": f"主角在第{n}章遇阻、破局并留下钩子"}
                for n in numbers
            ]
        },
        ensure_ascii=False,
    )


async def _outline_count(db_session):
    return (
        await db_session.execute(
            select(func.count()).select_from(ChapterOutline).where(ChapterOutline.project_id == PROJECT_ID)
        )
    ).scalar_one()


# ------------------------------------------------------------------
# 1. 生成成功（设定 1 次 + 章纲分批 2 次）+ volumes 落库
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_stage_success_persists_volumes(db_session, monkeypatch):
    calls = _patch_two_stage(
        monkeypatch,
        [
            _settings_payload(),
            _outline_payload(range(1, 26)),   # 批 1：第 1-25 章
            _outline_payload(range(26, 51)),  # 批 2：第 26-50 章
        ],
    )
    await _seed_project_with_history(db_session)

    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["blueprint"]["title"] == "赛博修仙指南"
    assert len(body["blueprint"]["chapter_outline"]) == 50
    assert [v["name"] for v in body["blueprint"]["volumes"]] == [
        "第一卷·废都编译", "第二卷·灵网扩张", "第三卷·根服务器",
    ]

    # 设定段 1 次 + 章纲 2 批：模板与 max_tokens 不同
    assert len(calls) == 3
    assert calls[0]["system_prompt"] == "SETTINGS_PROMPT"
    assert calls[0]["max_tokens"] == 8192
    for call in calls[1:]:
        assert call["system_prompt"] == "OUTLINE_PROMPT"
        assert call["max_tokens"] == 12288
    # 批 1 输入带设定段产出摘要与本批章号范围
    batch1_input = calls[1]["conversation_history"][0]["content"]
    assert "赛博修仙指南" in batch1_input and "第一卷·废都编译" in batch1_input
    assert "第 1-25 章" in batch1_input
    # 批 2 带前批尾部衔接上下文
    batch2_input = calls[2]["conversation_history"][0]["content"]
    assert "第 26-50 章" in batch2_input
    assert "前批已生成章纲的尾部" in batch2_input and "第25章" in batch2_input

    # 落库：蓝图主体含 volumes，章纲 50 条，项目标题已更新
    record = await db_session.get(NovelBlueprint, PROJECT_ID)
    assert record is not None
    assert [v["name"] for v in record.volumes] == [
        "第一卷·废都编译", "第二卷·灵网扩张", "第三卷·根服务器",
    ]
    assert await _outline_count(db_session) == 50
    project = await db_session.get(NovelProject, PROJECT_ID)
    assert project.title == "赛博修仙指南"


# ------------------------------------------------------------------
# 2. 章纲 30/50 → 触发补问后补齐
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outline_shortfall_triggers_retry_and_completes(db_session, monkeypatch):
    calls = _patch_two_stage(
        monkeypatch,
        [
            _settings_payload(),
            _outline_payload(range(1, 26)),      # 批 1 齐
            _outline_payload(range(26, 31)),     # 批 2 只给 26-30 → 覆盖 30/50 < 80%
            _outline_payload(range(31, 51)),     # 补问补齐 31-50
        ],
    )
    await _seed_project_with_history(db_session)

    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")

    assert resp.status_code == 200, resp.text
    assert len(resp.json()["blueprint"]["chapter_outline"]) == 50
    assert len(calls) == 4
    # 补问只要缺失章号区间
    retry_message = calls[3]["conversation_history"][-1]["content"]
    assert "31-50" in retry_message
    assert await _outline_count(db_session) == 50


# ------------------------------------------------------------------
# 3. 补问后仍不足 → 502 且不落库
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outline_still_short_after_retry_502_and_nothing_saved(db_session, monkeypatch):
    calls = _patch_two_stage(
        monkeypatch,
        [
            _settings_payload(),
            _outline_payload(range(1, 26)),   # 批 1 齐
            _outline_payload(range(26, 31)),  # 批 2 只到 30
            _outline_payload(range(31, 34)),  # 补问只补到 33 章，仍 < 40
        ],
    )
    await _seed_project_with_history(db_session)

    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")

    assert resp.status_code == 502
    assert "章纲生成不完整" in resp.json()["detail"]
    assert len(calls) == 4
    # 绝不静默落库残缺蓝图
    assert await db_session.get(NovelBlueprint, PROJECT_ID) is None
    assert await _outline_count(db_session) == 0
    project = await db_session.get(NovelProject, PROJECT_ID)
    assert project.title == "旧标题"


# ------------------------------------------------------------------
# 4. 旧格式兼容：设定段无 volumes
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_settings_without_volumes_still_works(db_session, monkeypatch):
    _patch_two_stage(
        monkeypatch,
        [
            _settings_payload(with_volumes=False),
            _outline_payload(range(1, 26)),
            _outline_payload(range(26, 51)),
        ],
    )
    await _seed_project_with_history(db_session)

    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")

    assert resp.status_code == 200, resp.text
    assert resp.json()["blueprint"]["volumes"] == []
    record = await db_session.get(NovelBlueprint, PROJECT_ID)
    assert record.volumes == []
    assert await _outline_count(db_session) == 50


# ------------------------------------------------------------------
# 5. 伏笔 <3 条：warning 不阻断
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_few_foreshadowings_warn_but_not_block(db_session, monkeypatch, caplog):
    _patch_two_stage(
        monkeypatch,
        [
            _settings_payload(foreshadowing_count=1),
            _outline_payload(range(1, 26)),
            _outline_payload(range(26, 51)),
        ],
    )
    await _seed_project_with_history(db_session)

    with caplog.at_level("WARNING", logger="app.services.blueprint_generation_service"):
        async with _build_client(db_session) as client:
            resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")

    assert resp.status_code == 200, resp.text
    assert "伏笔偏少" in caplog.text
    assert await _outline_count(db_session) == 50


# ------------------------------------------------------------------
# 6. 设定段失败 → 500，且不进入章纲段、不落库
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_settings_stage_failure_returns_500_without_outline_call(db_session, monkeypatch):
    calls = _patch_two_stage(monkeypatch, ["抱歉，我无法完成这个任务。"])
    await _seed_project_with_history(db_session)

    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")

    assert resp.status_code == 500
    assert "设定段" in resp.json()["detail"]
    assert len(calls) == 1  # 未进入章纲段
    assert await db_session.get(NovelBlueprint, PROJECT_ID) is None
    assert await _outline_count(db_session) == 0
