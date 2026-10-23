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


# ------------------------------------------------------------------
# 7. 故事骨架存在：锚点注入 → 设定段对账 → 章纲批次带前置条件 → 核心未埋补问一次
# ------------------------------------------------------------------

def _seed_backbone_state():
    from app.services.story_backbone_service import precut_volumes

    ranges = precut_volumes(100)
    climaxes = []
    for index, (start, end) in enumerate(ranges, start=1):
        climaxes.append({
            "volume_index": index, "chapter": end, "event": f"第{index}卷高潮事件",
            "reversal": "", "cost": "", "protagonist_state_after": "",
            "setups": [{"name": "旧伤", "what_must_be_established": "见过师父避开左肩", "why_needed": "",
                        "plant_from": 2, "plant_to": 10, "tier": "支线"}] if index == 1 else [],
        })
    return {
        "dossier": {"core_selling_line": "当铺文", "notes": "写 100 章"},
        "backbone": {
            "total_chapters": 100,
            "endgame": {"final_confrontation": "剑冢决战", "core_answer": "规则改了", "setups": []},
            "first_promise": {"volume_index": 0, "chapter": 8, "event": "拍卖会打脸",
                              "setups": [{"name": "账本", "what_must_be_established": "读者见过死当账本第三页",
                                          "why_needed": "打脸变天降", "plant_from": 1, "plant_to": 4, "tier": "核心"}]},
            "midpoint": None,
            "climaxes": climaxes,
        },
        "backbone_meta": {"generated_at": "2026-10-23T00:00:00+00:00", "source_hash": "x",
                          "ranges": [[s, e] for s, e in ranges], "revised_by_author": False, "edited_blocks": []},
    }, ranges


@pytest.mark.asyncio
async def test_backbone_drives_settings_outline_and_setup_retry(db_session, monkeypatch):
    state, ranges = _seed_backbone_state()
    retry_payload = json.dumps({"chapter_outline": [
        {"chapter_number": 3, "title": "第3章·账本", "summary": "主角翻到死当账本第三页，读者见过账本",
         "foreshadowing_ops": [{"op": "plant", "name": "账本"}]},
        {"chapter_number": 30, "title": "窗口外", "summary": "不该被接受"},
    ]}, ensure_ascii=False)
    calls = _patch_two_stage(
        monkeypatch,
        [_settings_payload(), _outline_payload(range(1, 26)), _outline_payload(range(26, 51)), retry_payload],
    )
    await _seed_project_with_history(db_session)
    project = await db_session.get(NovelProject, PROJECT_ID)
    project.concept_dossier = state
    await db_session.commit()

    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")
    assert resp.status_code == 200, resp.text
    body = resp.json()["blueprint"]

    # 设定段：立项书锚点之后紧跟骨架锚点
    history = calls[0]["conversation_history"]
    assert "【故事立项书】" in history[0]["content"]
    assert "【故事骨架】" in history[1]["content"] and "前置条件「账本」" in history[1]["content"]

    # 章纲批 1：带本批前置条件与高潮；批 2 不带账本（窗口 1-4）
    batch1 = calls[1]["conversation_history"][0]["content"]
    assert "本批必须埋下的前置条件" in batch1 and "「账本」[核心]（第 1-4 章之间）" in batch1
    assert "本批内要兑现的高潮" in batch1 and "第 8 章 第一次兑现：拍卖会打脸" in batch1
    assert "第 20 章 第 1 卷高潮" in batch1
    batch2 = calls[2]["conversation_history"][0]["content"]
    assert "「账本」" not in batch2

    # 对账：卷区间照骨架（4 卷），高潮节点进 volumes.climax；模型 3 卷的卷名不再沿用
    assert [(v["start_chapter"], v["end_chapter"]) for v in body["volumes"]] == [list(r) for r in ranges] or \
        [(v["start_chapter"], v["end_chapter"]) for v in body["volumes"]] == ranges
    assert body["volumes"][0]["climax"]["event"] == "第1卷高潮事件"
    assert body["volumes"][0]["climax_hint"] == "第1卷高潮事件"
    fs_names = [f["name"] for f in body["foreshadowings"]]
    assert "账本" in fs_names and "旧伤" in fs_names and "伏笔1" in fs_names

    # 核心前置条件「账本」未埋 → 第 4 次调用是补埋重问；窗口外的第 30 章被丢弃
    assert len(calls) == 4
    retry_input = calls[3]["conversation_history"][0]["content"]
    assert "补埋任务" in retry_input and "「账本」必须在第 1-4 章之间埋下" in retry_input
    outline = {c["chapter_number"]: c for c in body["chapter_outline"]}
    assert "账本第三页" in outline[3]["summary"]
    assert outline[30]["title"] != "窗口外"

    # 落库：Volume 表 extra 带 climax；快速成书无审稿评分，但覆盖报告仍有落点（coverage_only）
    from app.models.novel import Volume
    vol = (await db_session.execute(select(Volume).where(Volume.project_id == PROJECT_ID, Volume.position == 1))).scalar_one()
    assert vol.extra["climax"]["chapter"] == ranges[0][1]
    report = body["review_report"]
    assert report["coverage_only"] is True and "total_score" not in report
    cov = report["setup_coverage"]
    assert cov["retried"] is True and cov["core_planted"] == 1 and cov["core_total"] == 1
    assert [e["name"] for e in cov["entries"] if not e["planted"]] == ["旧伤"]  # 支线未埋不补问


@pytest.mark.asyncio
async def test_backbone_absent_keeps_old_path(db_session, monkeypatch):
    """无骨架：锚点、批次任务、调用次数与旧路径完全一致。"""
    calls = _patch_two_stage(
        monkeypatch, [_settings_payload(), _outline_payload(range(1, 26)), _outline_payload(range(26, 51))],
    )
    await _seed_project_with_history(db_session)
    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")
    assert resp.status_code == 200
    assert len(calls) == 3
    assert "【故事骨架】" not in json.dumps(calls[0]["conversation_history"], ensure_ascii=False)
    assert "前置条件" not in calls[1]["conversation_history"][0]["content"]
    assert resp.json()["blueprint"]["volumes"][0].get("climax") is None


# ------------------------------------------------------------------
# 8. 参考小说材料进蓝图：设定段带剧情结构，章纲批次带本批桥段
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reference_bundle_reaches_settings_and_outline_batches(db_session, monkeypatch):
    from types import SimpleNamespace as NS

    novel = NS(
        id=1, title="参考书", status="ready", plot_structure=None, memory_card=None, style_guide=None, outline_content="",
        beat_library={"beats": [
            {"name": "大赛翻案", "situation": "公开大赛上翻案打脸", "tags": ["翻案", "打脸"], "setup": "s", "turn": "t", "payoff": "p"},
            {"name": "无关桥段", "situation": "恋爱误会", "tags": ["误会"], "setup": "", "turn": "", "payoff": ""},
            {"name": "无关2", "situation": "日常吃饭", "tags": ["日常"], "setup": "", "turn": "", "payoff": ""},
            {"name": "无关3", "situation": "赶路遇雨", "tags": ["赶路"], "setup": "", "turn": "", "payoff": ""},
            {"name": "无关4", "situation": "买菜砍价", "tags": ["砍价"], "setup": "", "turn": "", "payoff": ""},
        ]},
    )

    async def fake_bundle(session, project):
        return "《参考书》的剧情结构：\n  升级轴：灵网层级", [novel]

    monkeypatch.setattr(bgs, "_load_reference_bundle", fake_bundle)
    calls = _patch_two_stage(
        monkeypatch, [_settings_payload(), _outline_payload(range(1, 26)), _outline_payload(range(26, 51))],
    )
    await _seed_project_with_history(db_session)
    async with _build_client(db_session) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")
    assert resp.status_code == 200, resp.text

    assert "[参考小说的剧情结构与阅读动力]" in calls[0]["system_prompt"] and "升级轴：灵网层级" in calls[0]["system_prompt"]
    # 批 1 在卷一（climax_hint「灵网大赛翻案」）→ 关键词回退选中「大赛翻案」桥段，不带无关桥段
    batch1 = calls[1]["conversation_history"][0]["content"]
    assert "参考桥段" in batch1 and "大赛翻案" in batch1 and "情节必须原创" in batch1
    assert batch1.index("大赛翻案") < batch1.index("无关")  # 相关桥段排最前；无关桥段只是补位
    assert "买菜砍价" not in batch1  # top-3 之外的不带
