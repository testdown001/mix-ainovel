"""下一章使命预生成（mission_pregen_service）回归。

锁定的契约：
- 指纹 = sha256(title\\nsummary\\nstr(前章selected_version_id)) 前 16 位，输入变则指纹变；
- 生产者幂等（已有指纹匹配的 pregen 不重算）、前章重选版本后指纹变化会重算；
- metadata_ 是共享 JSON 列（scenes/planning 等），写入/清除绝不能覆盖其它 key；
- 消费端：命中即取走并清除（一次性）、带 writing_notes 不消费、指纹失配丢弃回退正常生成；
- SystemConfig 开关 pregen.mission_enabled=false 时触发点 no-op。
"""
import time
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.novel import Chapter, ChapterOutline, ChapterVersion, NovelProject
from app.models.system_config import SystemConfig
from app.services import mission_pregen_service
from app.services.mission_pregen_service import (
    PREGEN_KEY,
    _load_enabled,
    _pregen_next_chapter_mission,
    load_selected_version_id,
    mission_fingerprint,
    take_valid_pregen_mission,
)

PROJECT_ID = "pregen-proj-1"
USER_ID = 7


def _outline(title="第四章", summary="风起于青萍之末", metadata=None):
    return SimpleNamespace(title=title, summary=summary, metadata_=metadata)


# ---------------------------------------------------------------------------
# 指纹
# ---------------------------------------------------------------------------

def test_fingerprint_stable_and_sensitive():
    a = mission_fingerprint(_outline(), 11)
    assert a == mission_fingerprint(_outline(), 11)  # 同输入稳定
    assert len(a) == 16
    assert a != mission_fingerprint(_outline(title="改了标题"), 11)
    assert a != mission_fingerprint(_outline(summary="改了摘要"), 11)
    assert a != mission_fingerprint(_outline(), 12)  # 前章重选版本
    assert a != mission_fingerprint(_outline(), None)


def test_fingerprint_tolerates_none_fields():
    assert mission_fingerprint(_outline(title=None, summary=None), None) == mission_fingerprint(
        _outline(title=None, summary=None), None
    )


# ---------------------------------------------------------------------------
# 消费端纯函数：查找 + 校验 + 清除
# ---------------------------------------------------------------------------

def _entry(mission, fingerprint):
    return {"mission": mission, "fingerprint": fingerprint, "created_at": "2026-08-14T00:00:00+00:00"}


def test_take_hit_returns_mission_and_clears_only_pregen_key():
    mission = {"beat": "挑衅1", "allowed_new_characters": []}
    outline = _outline(metadata={"planning": {"phase": "铺垫"}, PREGEN_KEY: _entry(mission, "fp-1")})
    got, state = take_valid_pregen_mission(outline, "fp-1", has_writing_notes=False)
    assert state == "hit"
    assert got == mission
    assert PREGEN_KEY not in outline.metadata_  # 一次性使用，用后即清
    assert outline.metadata_["planning"] == {"phase": "铺垫"}  # 其它 key 不被覆盖


def test_take_with_writing_notes_not_consumed_and_untouched():
    outline = _outline(metadata={PREGEN_KEY: _entry({"beat": "x"}, "fp-1")})
    got, state = take_valid_pregen_mission(outline, "fp-1", has_writing_notes=True)
    assert (got, state) == (None, "writing_notes")
    # 不消费也不清除：对之后「无指令」的请求仍有效
    assert outline.metadata_[PREGEN_KEY]["fingerprint"] == "fp-1"


def test_take_fingerprint_mismatch_discards_but_preserves_others():
    outline = _outline(metadata={"scenes": [1, 2], PREGEN_KEY: _entry({"beat": "x"}, "老指纹")})
    got, state = take_valid_pregen_mission(outline, "新指纹", has_writing_notes=False)
    assert (got, state) == (None, "stale_discarded")
    assert PREGEN_KEY not in outline.metadata_
    assert outline.metadata_["scenes"] == [1, 2]


def test_take_no_pregen():
    assert take_valid_pregen_mission(_outline(metadata=None), "fp", False) == (None, "no_pregen")
    assert take_valid_pregen_mission(_outline(metadata={}), "fp", False) == (None, "no_pregen")
    # mission 不是 dict 的畸形条目按不存在处理，不炸消费端
    outline = _outline(metadata={PREGEN_KEY: {"mission": "不是dict", "fingerprint": "fp"}})
    assert take_valid_pregen_mission(outline, "fp", False) == (None, "no_pregen")


# ---------------------------------------------------------------------------
# 生产者（真内存 SQLite）
# ---------------------------------------------------------------------------

async def _seed(session, *, with_next_outline=True, next_meta=None):
    session.add(NovelProject(id=PROJECT_ID, user_id=USER_ID, title="测试书"))
    session.add(
        ChapterOutline(project_id=PROJECT_ID, chapter_number=3, title="第三章", summary="旧事")
    )
    if with_next_outline:
        session.add(
            ChapterOutline(
                project_id=PROJECT_ID,
                chapter_number=4,
                title="第四章",
                summary="风起",
                metadata_=next_meta,
            )
        )
    # real_summary 预置好，跳过等待/回填分支（那是 ChapterPostProcessor 的职责）
    chapter = Chapter(
        project_id=PROJECT_ID, chapter_number=3, status="successful", real_summary="前章真实摘要"
    )
    session.add(chapter)
    await session.flush()
    version = ChapterVersion(chapter_id=chapter.id, content="正文" * 200, version_label="v1")
    session.add(version)
    await session.flush()
    chapter.selected_version_id = version.id
    await session.commit()
    return chapter


def _patch_builder(monkeypatch, mission=None):
    calls = []

    async def _fake_build(**kwargs):
        calls.append(kwargs)
        return {"beat": "挑衅1", "allowed_new_characters": []} if mission is None else mission

    monkeypatch.setattr(mission_pregen_service, "_build_mission_for_outline", _fake_build)
    return calls


async def _load_next_outline(session):
    result = await session.execute(
        select(ChapterOutline).where(
            ChapterOutline.project_id == PROJECT_ID, ChapterOutline.chapter_number == 4
        )
    )
    return result.scalars().first()


@pytest.mark.asyncio
async def test_pregen_writes_entry_and_preserves_other_metadata(db_session, monkeypatch):
    await _seed(db_session, next_meta={"planning": {"phase": "铺垫"}})
    calls = _patch_builder(monkeypatch)

    outcome = await _pregen_next_chapter_mission(db_session, PROJECT_ID, 3, USER_ID)

    assert outcome == "ok"
    assert len(calls) == 1
    outline = await _load_next_outline(db_session)
    entry = outline.metadata_[PREGEN_KEY]
    assert entry["mission"] == {"beat": "挑衅1", "allowed_new_characters": []}
    assert entry["created_at"]
    prev_vid = await load_selected_version_id(db_session, PROJECT_ID, 3)
    assert entry["fingerprint"] == mission_fingerprint(outline, prev_vid)
    assert outline.metadata_["planning"] == {"phase": "铺垫"}  # 共享列其它 key 保留


@pytest.mark.asyncio
async def test_pregen_idempotent_when_fingerprint_matches(db_session, monkeypatch):
    await _seed(db_session)
    calls = _patch_builder(monkeypatch)

    assert await _pregen_next_chapter_mission(db_session, PROJECT_ID, 3, USER_ID) == "ok"
    assert await _pregen_next_chapter_mission(db_session, PROJECT_ID, 3, USER_ID) == "already"
    assert len(calls) == 1  # 已有指纹匹配的 pregen，不重算


@pytest.mark.asyncio
async def test_pregen_recomputes_after_reselecting_prev_version(db_session, monkeypatch):
    await _seed(db_session)
    calls = _patch_builder(monkeypatch)
    assert await _pregen_next_chapter_mission(db_session, PROJECT_ID, 3, USER_ID) == "ok"

    # 前章重选另一个版本 → 指纹变化 → 幂等检查不放行，重新预生成。
    # 预生成流程内部会 rollback（过期 ORM 对象），这里重新加载前章再改
    result = await db_session.execute(
        select(Chapter).where(
            Chapter.project_id == PROJECT_ID, Chapter.chapter_number == 3
        )
    )
    chapter = result.scalars().first()
    new_version = ChapterVersion(chapter_id=chapter.id, content="另一版" * 200, version_label="v2")
    db_session.add(new_version)
    await db_session.flush()
    new_version_id = new_version.id
    chapter.selected_version_id = new_version_id
    await db_session.commit()

    assert await _pregen_next_chapter_mission(db_session, PROJECT_ID, 3, USER_ID) == "ok"
    assert len(calls) == 2
    outline = await _load_next_outline(db_session)
    assert outline.metadata_[PREGEN_KEY]["fingerprint"] == mission_fingerprint(
        outline, new_version_id
    )


@pytest.mark.asyncio
async def test_pregen_noop_without_next_outline(db_session, monkeypatch):
    await _seed(db_session, with_next_outline=False)
    calls = _patch_builder(monkeypatch)
    assert await _pregen_next_chapter_mission(db_session, PROJECT_ID, 3, USER_ID) == "no_outline"
    assert calls == []


@pytest.mark.asyncio
async def test_pregen_discards_result_if_outline_changed_during_llm(db_session, monkeypatch):
    """LLM 跑的 ~2 分钟里大纲被改：落库前指纹复核失败，本次结果丢弃。"""
    await _seed(db_session)

    async def _build_and_mutate(**kwargs):
        outline = await _load_next_outline(db_session)
        outline.summary = "预生成期间被用户改掉的摘要"
        await db_session.commit()
        return {"beat": "已过时的使命"}

    monkeypatch.setattr(mission_pregen_service, "_build_mission_for_outline", _build_and_mutate)

    assert await _pregen_next_chapter_mission(db_session, PROJECT_ID, 3, USER_ID) == "stale_abort"
    outline = await _load_next_outline(db_session)
    assert not (outline.metadata_ or {}).get(PREGEN_KEY)


@pytest.mark.asyncio
async def test_pregen_empty_mission_not_written(db_session, monkeypatch):
    await _seed(db_session)
    _patch_builder(monkeypatch, mission={})
    assert await _pregen_next_chapter_mission(db_session, PROJECT_ID, 3, USER_ID) == "empty_mission"
    outline = await _load_next_outline(db_session)
    assert not (outline.metadata_ or {}).get(PREGEN_KEY)


# ---------------------------------------------------------------------------
# 开关
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_enabled_variants(db_session):
    assert await _load_enabled(db_session) is True  # 键缺失（老库未播种）按开启

    db_session.add(SystemConfig(key="pregen.mission_enabled", value="false"))
    await db_session.commit()
    assert await _load_enabled(db_session) is False

    record = await db_session.get(SystemConfig, "pregen.mission_enabled")
    record.value = "true"
    await db_session.commit()
    assert await _load_enabled(db_session) is True


@pytest.mark.asyncio
async def test_public_entry_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(mission_pregen_service, "_enabled_cache", False)
    monkeypatch.setattr(mission_pregen_service, "_enabled_expires_at", time.monotonic() + 999)

    async def _must_not_run(*args, **kwargs):
        raise AssertionError("开关关闭时不应进入预生成流程")

    monkeypatch.setattr(mission_pregen_service, "_pregen_next_chapter_mission", _must_not_run)
    await mission_pregen_service.pregen_next_chapter_mission(PROJECT_ID, 3, USER_ID)


@pytest.mark.asyncio
async def test_public_entry_skips_inflight_duplicate(monkeypatch):
    """finalize 自动选版与手动选版可能背靠背触发同一目标章，在途去重防双跑 LLM。"""
    monkeypatch.setattr(mission_pregen_service, "_enabled_cache", True)
    monkeypatch.setattr(mission_pregen_service, "_enabled_expires_at", time.monotonic() + 999)
    monkeypatch.setattr(mission_pregen_service, "_inflight", {(PROJECT_ID, 4)})

    async def _must_not_run(*args, **kwargs):
        raise AssertionError("在途任务存在时不应再次进入")

    monkeypatch.setattr(mission_pregen_service, "_pregen_next_chapter_mission", _must_not_run)
    await mission_pregen_service.pregen_next_chapter_mission(PROJECT_ID, 3, USER_ID)
