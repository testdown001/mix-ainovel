"""参考桥段按情境选取：语义路径、关键词回退、老数据容错。

契约：嵌入不可用时（get_embeddings_batch 失败返回空）必须回退关键词打分——
降级可以变糙，不能变没有；缺 beat_library 的老数据自然为空，不炸。
"""
import asyncio
from types import SimpleNamespace
from datetime import datetime

from app.services import reference_beat_service as module
from app.services.reference_beat_service import ReferenceBeatService


def _novel(novel_id, title, beats, structure=None, updated=None):
    return SimpleNamespace(
        id=novel_id,
        title=title,
        updated_at=updated or datetime(2026, 1, 1),
        beat_library={"beats": beats, "structure": structure or {}},
    )


def _beat(name, situation, tags=None):
    return {
        "name": name,
        "situation": situation,
        "tags": tags or [],
        "setup": "铺垫",
        "turn": "转折",
        "payoff": "兑现",
        "pitfalls": "翻车点",
    }


class _EmbeddingLLM:
    """按文本产出可控向量：含「对峙」的文本 → [1,0]，其余 → [0,1]。"""

    def __init__(self, fail=False):
        self.fail = fail
        self.batch_calls = 0

    async def get_embeddings_batch(self, texts, **_kw):
        self.batch_calls += 1
        if self.fail:
            return [[] for _ in texts]
        return [[1.0, 0.0] if "对峙" in t else [0.0, 1.0] for t in texts]


def setup_function(_fn):
    module._SITUATION_EMBEDDING_CACHE.clear()


def test_semantic_selection_picks_matching_situation():
    novels = [
        _novel(1, "书A", [
            _beat("当众对峙·反转", "主角与宿敌当众对峙"),
            _beat("温情日常", "主角与家人共处日常"),
        ]),
        _novel(2, "书B", [
            _beat("追逃战", "主角被围追堵截"),
            _beat("谈判桌交锋", "双方在谈判桌上对峙拉扯"),
        ]),
    ]
    service = ReferenceBeatService(_EmbeddingLLM())
    selected = asyncio.run(
        service.select_beats_for_chapter(novels, query_text="本章是一场公开对峙", top_k=2)
    )
    names = [b["name"] for b in selected]
    assert names == ["当众对峙·反转", "谈判桌交锋"]
    # 出处保留，供提示词标注「出自《X》」
    assert {b["source_novel"] for b in selected} == {"书A", "书B"}


def test_embedding_failure_falls_back_to_keywords():
    novels = [
        _novel(1, "书A", [
            _beat("打脸戏", "主角被公开羞辱后反击", tags=["打脸", "公开场合"]),
            _beat("寻宝", "主角进入秘境探索", tags=["秘境"]),
            _beat("日常", "宗门日常修炼", tags=["日常"]),
            _beat("大战", "宗门大战爆发", tags=["大战"]),
        ]),
    ]
    service = ReferenceBeatService(_EmbeddingLLM(fail=True))
    selected = asyncio.run(
        service.select_beats_for_chapter(novels, query_text="主角在公开场合被打脸羞辱", top_k=1)
    )
    assert selected[0]["name"] == "打脸戏"


def test_old_data_without_beat_library_is_noop():
    novels = [SimpleNamespace(id=9, title="老书", updated_at=None, beat_library=None)]
    service = ReferenceBeatService(_EmbeddingLLM())
    assert asyncio.run(service.select_beats_for_chapter(novels, query_text="任何情境")) == []
    assert ReferenceBeatService.format_beat_index_for_concept(novels) == ""
    assert ReferenceBeatService.format_structure_for_blueprint(novels) == ""


def test_situation_embeddings_cached_by_novel_version():
    llm = _EmbeddingLLM()
    novels = [_novel(1, "书A", [
        _beat("a", "主角与宿敌当众对峙"),
        _beat("b", "主角遁走"),
        _beat("c", "主角闭关"),
        _beat("d", "主角赶路"),
    ])]
    service = ReferenceBeatService(llm)
    asyncio.run(service.select_beats_for_chapter(novels, query_text="对峙", top_k=1))
    asyncio.run(service.select_beats_for_chapter(novels, query_text="又一次对峙", top_k=1))
    # 情境向量按 (novel_id, updated_at) 缓存：两次选取只嵌入一次情境 + 两次查询
    assert llm.batch_calls == 3


def test_format_beats_for_prompt_contains_technique_fields():
    beats = [{**_beat("当众打脸·信息差反转", "主角被公开羞辱"), "source_novel": "书A"}]
    text = ReferenceBeatService.format_beats_for_prompt(beats)
    assert "当众打脸·信息差反转" in text
    assert "出自《书A》" in text
    for label in ("适用局面", "铺垫", "转折", "兑现", "勿踩"):
        assert label in text
    assert "禁止照搬" in text


def test_format_structure_for_blueprint():
    novels = [
        _novel(1, "书A", [], structure={
            "volume_rhythm": "每卷一大高潮",
            "conflict_escalation": "对手量级逐卷抬升",
            "hook_pattern": "危机中断式",
        }),
        _novel(2, "书B", [], structure={}),
    ]
    text = ReferenceBeatService.format_structure_for_blueprint(novels)
    assert "《书A》的结构手法" in text
    assert "每卷一大高潮" in text
    assert "书B" not in text  # 空结构不占位
