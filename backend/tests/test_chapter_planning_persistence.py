"""章级规划落盘（chapter_planning_service + 写入方接线）回归。

锁定的契约：
- extract_planning_from_item：字段清洗归一（含 "plant:名" 简写、字符串 must_not_include）；
- map_planning_to_blueprint_fields：中文功能→枚举、密度/颠覆等级推导、develop→reinforce、
  must_not_include 进 mission_constraints；
- replace_blueprint 全量落盘：章号乱序时按 number_map 重排对齐 chapter_outlines；
  无规划字段的蓝图清空 chapter_blueprints（读取方对空表 no-op）；
- 落盘即激活 validate_coolpoint_rhythm（不再因表空恒空转）；
- upsert 单章：只改规划列，保留 is_finalized 等状态列；
- writer_shared.extract_outline_planning_metadata 把五字段并进 planning 子键。
"""
import pytest
from sqlalchemy import select

from app.models.chapter_blueprint import ChapterBlueprint
from app.models.novel import ChapterOutline, NovelProject
from app.models.user import User
from app.schemas.novel import Blueprint
from app.services.chapter_planning_service import (
    extract_planning_from_item,
    map_planning_to_blueprint_fields,
    normalize_chapter_function,
    upsert_chapter_blueprint,
)
from app.services.generation_support_service import GenerationSupportService
from app.services.novel_service import NovelService
from app.services.writer_shared import extract_outline_planning_metadata

PROJECT_ID = "planning-proj-1"


# ---------------------------------------------------------------------------
# 提取与映射
# ---------------------------------------------------------------------------

def test_extract_planning_from_item_variants():
    full = extract_planning_from_item({
        "chapter_function": "爽点",
        "hook_type": "新危机压脸",
        "coolpoint": "信息差打脸",
        "foreshadowing_ops": [
            {"op": "plant", "name": "死当账本"},
            "payoff:身世玉佩",           # 简写形态
            {"op": "unknown", "name": "非法op"},
        ],
        "must_not_include": "提前揭示会长身份",  # 字符串归一为列表
    })
    assert full["chapter_function"] == "爽点"
    assert full["foreshadowing_ops"] == [
        {"op": "plant", "name": "死当账本"},
        {"op": "payoff", "name": "身世玉佩"},
    ]
    assert full["must_not_include"] == ["提前揭示会长身份"]

    assert extract_planning_from_item({"title": "无规划"}) is None
    assert extract_planning_from_item("not-a-dict") is None  # type: ignore[arg-type]


def test_normalize_chapter_function():
    assert normalize_chapter_function("爽点") == "climax"
    assert normalize_chapter_function("转折") == "turning"
    assert normalize_chapter_function("过渡") == "interlude"
    assert normalize_chapter_function("climax") == "climax"  # 英文枚举直通
    assert normalize_chapter_function("不认识") is None
    assert normalize_chapter_function("") is None


def test_map_planning_to_blueprint_fields():
    fields = map_planning_to_blueprint_fields({
        "chapter_function": "转折",
        "hook_type": "身份暴露前兆",
        "coolpoint": "越级反杀",
        "foreshadowing_ops": [
            {"op": "plant", "name": "账本"},
            {"op": "develop", "name": "玉佩"},
        ],
        "must_not_include": ["提前揭示身份"],
    })
    assert fields["chapter_function"] == "turning"
    assert fields["suspense_density"] == "explosive"
    assert fields["cognitive_twist_level"] == 4
    assert fields["suspense_type"] == "身份暴露前兆"
    assert fields["brief_summary"] == "越级反杀"
    assert fields["foreshadowing_ops"] == "plant,reinforce"  # develop 存储为 reinforce
    assert fields["involved_foreshadowings"] == ["账本", "玉佩"]
    assert fields["mission_constraints"] == {"must_not_include": ["提前揭示身份"]}
    assert fields["extra"]["planning"]["coolpoint"] == "越级反杀"

    assert map_planning_to_blueprint_fields({}) == {}


def test_writer_shared_metadata_includes_planning_fields():
    metadata = extract_outline_planning_metadata({
        "narrative_phase": "回击1",
        "emotion_hook": "压迫与反击",
        "chapter_function": "高潮",
        "coolpoint": "当众打脸",
        "foreshadowing_ops": [{"op": "payoff", "name": "死当账本"}],
    })
    assert metadata["narrative_phase"] == "回击1"  # 既有三字段不受影响
    assert metadata["chapter_function"] == "高潮"
    assert metadata["foreshadowing_ops"] == [{"op": "payoff", "name": "死当账本"}]


# ---------------------------------------------------------------------------
# 落库：全量替换 + 重排对齐 + 节奏校验激活
# ---------------------------------------------------------------------------

async def _seed_user_project(db_session):
    db_session.add_all([
        User(id=7, username="u7", hashed_password="x"),
        NovelProject(id=PROJECT_ID, user_id=7, title="测试项目"),
    ])
    await db_session.commit()


def _blueprint_with_planning():
    # 章号故意乱序且不从 1 开始：3/7/9 → 重排为 1/2/3
    return Blueprint(
        title="测试书",
        chapter_outline=[
            {"chapter_number": 7, "title": "旧7", "summary": "s",
             "metadata": {"planning": {"chapter_function": "铺垫"}}},
            {"chapter_number": 3, "title": "旧3", "summary": "s",
             "metadata": {"planning": {"chapter_function": "爽点", "coolpoint": "打脸"}}},
            {"chapter_number": 9, "title": "旧9", "summary": "s"},  # 无规划
        ],
    )


@pytest.mark.asyncio
async def test_replace_blueprint_writes_renumbered_chapter_blueprints(db_session):
    await _seed_user_project(db_session)
    await NovelService(db_session).replace_blueprint(PROJECT_ID, _blueprint_with_planning())

    outlines = (await db_session.execute(
        select(ChapterOutline).where(ChapterOutline.project_id == PROJECT_ID)
        .order_by(ChapterOutline.chapter_number)
    )).scalars().all()
    assert [o.chapter_number for o in outlines] == [1, 2, 3]

    rows = (await db_session.execute(
        select(ChapterBlueprint).where(ChapterBlueprint.project_id == PROJECT_ID)
        .order_by(ChapterBlueprint.chapter_number)
    )).scalars().all()
    # 只有带规划的两章落盘；章号与重排后的 outline 对齐（原3→1 爽点，原7→2 铺垫）
    assert [(r.chapter_number, r.chapter_function) for r in rows] == [
        (1, "climax"), (2, "buildup"),
    ]
    assert rows[0].brief_summary == "打脸"


@pytest.mark.asyncio
async def test_replace_blueprint_without_planning_clears_rows(db_session):
    await _seed_user_project(db_session)
    novel_service = NovelService(db_session)
    await novel_service.replace_blueprint(PROJECT_ID, _blueprint_with_planning())
    # 再落一个无规划蓝图（旧蓝图/免费档形态）→ 规划行清空，读取方对空表 no-op
    await novel_service.replace_blueprint(
        PROJECT_ID,
        Blueprint(title="无规划蓝图", chapter_outline=[
            {"chapter_number": 1, "title": "t", "summary": "s"},
        ]),
    )
    rows = (await db_session.execute(
        select(ChapterBlueprint).where(ChapterBlueprint.project_id == PROJECT_ID)
    )).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_coolpoint_rhythm_validation_activated(db_session):
    """落盘后 validate_coolpoint_rhythm 不再空转：连续铺垫章触发节奏提示。"""
    await _seed_user_project(db_session)
    # 第 1-4 章全是铺垫（无爽点/转折）
    blueprint = Blueprint(
        title="节奏测试",
        chapter_outline=[
            {"chapter_number": n, "title": f"t{n}", "summary": "s",
             "metadata": {"planning": {"chapter_function": "铺垫"}}}
            for n in range(1, 5)
        ],
    )
    await NovelService(db_session).replace_blueprint(PROJECT_ID, blueprint)

    hint = await GenerationSupportService(db_session).validate_coolpoint_rhythm(
        PROJECT_ID, chapter_number=5, chapter_mission=None
    )
    assert hint is not None and "没有明显爽点" in hint


@pytest.mark.asyncio
async def test_upsert_preserves_status_columns(db_session):
    await _seed_user_project(db_session)
    db_session.add(ChapterBlueprint(
        project_id=PROJECT_ID, chapter_number=12,
        chapter_function="buildup", is_finalized=True, quality_score=88.0,
    ))
    await db_session.commit()

    await upsert_chapter_blueprint(
        db_session, PROJECT_ID, 12, {"chapter_function": "高潮", "coolpoint": "反杀"}
    )
    await db_session.commit()

    row = (await db_session.execute(
        select(ChapterBlueprint).where(
            ChapterBlueprint.project_id == PROJECT_ID,
            ChapterBlueprint.chapter_number == 12,
        )
    )).scalar_one()
    assert row.chapter_function == "climax"
    assert row.brief_summary == "反杀"
    assert row.is_finalized is True       # 状态列保留
    assert row.quality_score == 88.0

    # planning 为空时 no-op
    await upsert_chapter_blueprint(db_session, PROJECT_ID, 12, None)
    await upsert_chapter_blueprint(db_session, PROJECT_ID, 12, {})
