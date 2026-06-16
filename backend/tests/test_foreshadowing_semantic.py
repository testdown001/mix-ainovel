"""伏笔语义化(B4)：build_foreshadowing_urgency_brief 的语义相关性排序 + 降级。

mock llm_service.get_embeddings_batch，不触网。验证：
- 语义相关的伏笔获得加成、排序提升到紧迫度更高但无关的伏笔之前；
- llm 缺失 / embedding 返回空 时降级为纯启发式排序，不报错。
"""
import asyncio
from unittest.mock import MagicMock

import app.models  # noqa: F401  mapper 注册
from app.db.base import Base
from app.models.foreshadowing import Foreshadowing
from app.services.platinum_writing_context import build_foreshadowing_urgency_brief, _cosine

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


def _make_sessionmaker():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _seed(session):
    # A: 紧迫度低(3)但语义相关(ALPHA)；B: 紧迫度高(5)但语义无关(BETA)。
    # 纯启发式应 B 在前；语义加成应把 A 提到 B 前。
    session.add(Foreshadowing(
        project_id="p1", chapter_id=1, chapter_number=1, content="ALPHA 主角的玉佩浮现线索",
        type="clue", status="planted", urgency=3, name="玉佩线索",
    ))
    session.add(Foreshadowing(
        project_id="p1", chapter_id=1, chapter_number=1, content="BETA 反派的财务支线",
        type="hint", status="planted", urgency=5, name="财务支线",
    ))
    await session.commit()


def _llm_with_keyword_embeddings():
    """get_embeddings_batch 按文本关键词返回正交向量：ALPHA→x 轴，BETA→y 轴，其它→z 轴。"""
    llm = MagicMock()

    async def _embed(texts):
        out = []
        for t in texts:
            if "ALPHA" in t:
                out.append([1.0, 0.0, 0.0])
            elif "BETA" in t:
                out.append([0.0, 1.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out

    llm.get_embeddings_batch = _embed
    return llm


def test_cosine_basic():
    assert _cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert _cosine([], [1.0]) == 0.0  # 维度不匹配降级 0


def test_semantic_promotes_relevant_foreshadowing():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session)
            brief = await build_foreshadowing_urgency_brief(
                session=session, project_id="p1", chapter_number=2,
                query_text="ALPHA 玉佩的秘密力量", llm_service=_llm_with_keyword_embeddings(),
            )
            # 语义相关的 A(玉佩线索)应排在紧迫度更高但无关的 B(财务支线)之前
            assert brief.index("玉佩线索") < brief.index("财务支线")
        await engine.dispose()
    asyncio.run(_run())


def test_degrade_without_llm_uses_heuristic():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session)
            brief = await build_foreshadowing_urgency_brief(
                session=session, project_id="p1", chapter_number=2,
                query_text="ALPHA 玉佩", llm_service=None,  # 无 llm → 纯启发式
            )
            # 纯启发式：B 紧迫度(5)高于 A(3)，B 在前
            assert brief.index("财务支线") < brief.index("玉佩线索")
        await engine.dispose()
    asyncio.run(_run())


def test_degrade_on_empty_embeddings():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed(session)
            llm = MagicMock()

            async def _empty(texts):
                return []  # embedding 不可用

            llm.get_embeddings_batch = _empty
            brief = await build_foreshadowing_urgency_brief(
                session=session, project_id="p1", chapter_number=2,
                query_text="ALPHA 玉佩", llm_service=llm,
            )
            # 降级为启发式，不报错，B 仍在前
            assert brief.index("财务支线") < brief.index("玉佩线索")
        await engine.dispose()
    asyncio.run(_run())
