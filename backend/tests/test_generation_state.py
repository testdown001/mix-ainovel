"""PreCollectedContext 类型化共享状态——序列化往返与字段保全。"""
from app.services.generation_state import PreCollectedContext


def test_from_empty_and_to_dict_is_compact():
    pcc = PreCollectedContext.from_dict(None)
    assert pcc.to_dict() == {}  # 全 None → 紧凑空 dict
    assert PreCollectedContext.from_dict({}).to_dict() == {}


def test_known_keys_roundtrip():
    src = {
        "history_context": {"previous_summary": "前情"},
        "blueprint": {"title": "书"},
        "rag_context": {"chunks": [1, 2]},
        "rag_stats": {"mode": "simple"},
        "chapter_state_context": "状态",
        "power_system": "体系",
        "relationship_context": "关系",
        "foreshadowing_data": {"x": 1},
    }
    pcc = PreCollectedContext.from_dict(src)
    assert pcc.history_context == {"previous_summary": "前情"}
    assert pcc.power_system == "体系"
    # 往返一致
    assert pcc.to_dict() == src


def test_unknown_keys_preserved_via_extra():
    src = {"blueprint": {"t": 1}, "未来新键": "保留", "another": [1]}
    pcc = PreCollectedContext.from_dict(src)
    assert pcc.extra == {"未来新键": "保留", "another": [1]}
    # round-trip 不丢未知键
    assert pcc.to_dict() == src


def test_mutate_then_serialize():
    pcc = PreCollectedContext.from_dict({"history_context": {"a": 1}})
    pcc.context_plan = {"retrieval_tasks": [], "agentic": True}  # 模拟 ContextPlan.to_dict()
    out = pcc.to_dict()
    assert out["history_context"] == {"a": 1}
    assert out["context_plan"] == {"retrieval_tasks": [], "agentic": True}


def test_none_fields_omitted():
    pcc = PreCollectedContext(history_context={"a": 1})
    out = pcc.to_dict()
    assert out == {"history_context": {"a": 1}}  # 其余 None 不输出
