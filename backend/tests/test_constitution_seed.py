"""宪法自动播种（constitution_seed_service）回归。

锁定的契约：
- build_forbidden_content = 用户禁区 + 推演高危毒点（中低危不进）+ 题材禁忌 + 通用禁忌，
  去重限长；
- seed_constitution_from_blueprint：从蓝图/立项书组装宪法字段；幂等（已有宪法不覆盖）；
- 播种产物能被 to_prompt_context 渲染（注入链路吃得到）。
"""
import pytest
from sqlalchemy import select

from app.models.constitution import NovelConstitution
from app.models.novel import NovelProject
from app.models.user import User
from app.services.constitution_seed_service import (
    build_forbidden_content,
    seed_constitution_from_blueprint,
)

PROJECT_ID = "seed-proj-1"


def test_build_forbidden_content_composition():
    items = build_forbidden_content(
        exclusions="不要后宫；不要系统流\n不要无脑打脸",
        stress_report={
            "toxic_points": [
                {"issue": "爽点太迟", "severity": "高危", "fix_suggestion": "第5章前给第一次兑现"},
                {"issue": "桥段过老", "severity": "中危", "fix_suggestion": "换新写法"},
            ]
        },
        genre="都市爽文",
    )
    text = "\n".join(items)
    assert "用户禁区：不要后宫" in text
    assert "用户禁区：不要系统流" in text
    assert "高危毒点：爽点太迟" in text
    assert "桥段过老" not in text  # 中危不进宪法（宪法只放红线）
    assert "主角连续多章被动挨打" in text  # 题材禁忌（爽文/都市）
    assert "配角集体智商下线" in text  # 通用禁忌
    assert len(items) == len(set(items))  # 去重


def test_build_forbidden_content_empty_inputs():
    items = build_forbidden_content(exclusions="", stress_report=None, genre="")
    # 只剩通用禁忌
    assert items and all("用户禁区" not in i and "高危毒点" not in i for i in items)


async def _seed(db_session):
    db_session.add_all([
        User(id=7, username="u7", hashed_password="x"),
        NovelProject(id=PROJECT_ID, user_id=7, title="p"),
    ])
    await db_session.commit()


_BLUEPRINT_DATA = {
    "title": "都市当铺",
    "genre": "都市异能",
    "tone": "压迫感强、爽点后置",
    "style": "热血升级流",
    "one_sentence_summary": "废柴接手欠债当铺",
    "world_setting": {"core_rules": "死当兑现要折寿"},
    "golden_finger": {"name": "万物当铺", "description": "可典当无形物", "limitations": "折寿"},
    "characters": [{"name": "陈默"}],
}

_DOSSIER = {
    "core_selling_line": "废柴接手欠债当铺，死当藏大能遗产",
    "core_conflict": "与旧主仇家的连环冲突",
    "protagonist": {"name": "陈默"},
    "anticipation": {"long_term": "当铺真正主人的身份之谜"},
}


@pytest.mark.asyncio
async def test_seed_constitution_from_blueprint(db_session):
    await _seed(db_session)
    created = await seed_constitution_from_blueprint(
        db_session,
        project_id=PROJECT_ID,
        blueprint_data=_BLUEPRINT_DATA,
        dossier=_DOSSIER,
        stress_report={"toxic_points": [{"issue": "开局信息过载", "severity": "高危"}]},
        exclusions="不要后宫",
    )
    await db_session.commit()
    assert created is True

    constitution = (await db_session.execute(
        select(NovelConstitution).where(NovelConstitution.project_id == PROJECT_ID)
    )).scalar_one()
    assert constitution.core_theme == "废柴接手欠债当铺，死当藏大能遗产"
    assert constitution.genre == "都市异能"
    assert constitution.core_conflict == "与旧主仇家的连环冲突"
    assert constitution.story_direction == "当铺真正主人的身份之谜"
    assert constitution.pov_character == "陈默"
    assert constitution.overall_tone == "压迫感强、爽点后置"
    assert constitution.world_rules == {"core_rules": "死当兑现要折寿"}
    assert "万物当铺" in (constitution.power_system or "")
    forbidden = "\n".join(constitution.forbidden_content or [])
    assert "用户禁区：不要后宫" in forbidden
    assert "高危毒点：开局信息过载" in forbidden
    assert constitution.extra["seeded_by"] == "blueprint"

    # 注入链路可渲染（非空、含禁忌节）
    context = constitution.to_prompt_context()
    assert "小说宪法" in context and "禁忌内容" in context


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session):
    await _seed(db_session)
    db_session.add(NovelConstitution(project_id=PROJECT_ID, core_theme="手工配置的宪法"))
    await db_session.commit()

    created = await seed_constitution_from_blueprint(
        db_session,
        project_id=PROJECT_ID,
        blueprint_data=_BLUEPRINT_DATA,
        dossier=_DOSSIER,
        stress_report=None,
        exclusions="",
    )
    assert created is False
    constitution = (await db_session.execute(
        select(NovelConstitution).where(NovelConstitution.project_id == PROJECT_ID)
    )).scalar_one()
    assert constitution.core_theme == "手工配置的宪法"  # 不覆盖既有宪法
