import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.reference_novel import MemoryCard
from app.services.prompt_budget_manager import PromptBudgetManager
from app.services.prompt_service import PromptService
from app.services.reference_novel_library_service import ReferenceNovelLibraryService
from app.services.reference_reading_contract import (
    FusionDNA, fallback_dna, format_contract, fusion_materials, is_current, project_contract, stamp,
)


def books():
    return [SimpleNamespace(
        id=i, title=f"参考{i}", status="ready", outline_content="剧情摘要" * 500,
        style_samples_content="AI仿写不能当作证据", style_guide={"narrative_pov": f"单书视角{i}"},
        memory_card={"core_selling_point": f"回报{i}", "reader_expectation": f"等待改变{i}",
                     "payoff_rhythm": f"兑现与余波{i}", "relationship_pull": f"关系牵挂{i}"},
        beat_library={"beats": [{"setup": f"铺垫{i}", "turn": f"触发{i}", "payoff": f"兑现{i}"}],
                      "structure": {"conflict_escalation": f"升级{i}"}},
    ) for i in range(1, 4)]


def generated_dna(novels):
    data = fallback_dna(novels)
    data.update(style_fingerprint="统一限知视角，动作紧时短促，关系变化处允许停顿",
                dialogue_style="由人物身份决定腔调", scene_rhythm="余波里处理关系变化")
    return FusionDNA.model_validate(data)


def test_fusion_materials_keep_each_books_payoff_relationship_and_beats():
    materials = fusion_materials(books())
    assert "AI仿写不能当作证据" not in materials
    for i, block in enumerate(materials.split("\n\n"), 1):
        data = json.loads(block)  # 每本仍是完整 JSON，没有头部截断破坏后续字段
        assert data["reading_mechanisms"]["relationship_pull"] == f"关系牵挂{i}"
        assert data["reading_mechanisms"]["payoff_rhythm"] == f"兑现与余波{i}"
        assert data["beats"][0]["payoff"] == f"兑现{i}"
        assert data["voice"]["narrative_pov"] == f"单书视角{i}"


@pytest.mark.parametrize("count", [1, 2, 3])
def test_structured_fusion_covers_every_source_even_for_single_book(count):
    novels = books()[:count]
    service = ReferenceNovelLibraryService(SimpleNamespace())
    service.prompt_service = SimpleNamespace(get_prompt=AsyncMock(return_value="{reference_materials}"),
                                            render_prompt=PromptService.render_prompt)
    service.llm_service = SimpleNamespace(generate_structured=AsyncMock(return_value=generated_dna(novels)))
    result = asyncio.run(service.generate_fusion_dna(novels, 7))
    assert result["generation_status"] == "ready"
    assert is_current(result, novels, [n.id for n in novels])
    assert [item["from"] for item in result["structure_references"]] == [n.title for n in novels]
    kwargs = service.llm_service.generate_structured.call_args.kwargs
    assert kwargs["schema"] is FusionDNA
    assert "关系牵挂1" in kwargs["prompt"]


@pytest.mark.parametrize("failure", ["missing_book", "extra_book", "invalid", "missing_prompt"])
def test_failed_or_incomplete_fusion_is_labeled_as_provisional(failure):
    novels = books()
    service = ReferenceNovelLibraryService(SimpleNamespace())
    service.prompt_service = SimpleNamespace(get_prompt=AsyncMock(return_value=None if failure == "missing_prompt" else "x"),
                                            render_prompt=PromptService.render_prompt)
    generated = generated_dna(novels[:2] if failure == "missing_book" else novels)
    if failure == "extra_book":
        generated.structure_references[2].source = "未选择的书"
    service.llm_service = SimpleNamespace(generate_structured=AsyncMock(
        side_effect=ValueError("invalid json") if failure == "invalid" else None, return_value=generated))
    result = asyncio.run(service.generate_fusion_dna(novels, 7))
    assert result["generation_status"] == "fallback"
    assert len(result["structure_references"]) == 3
    assert "临时参考方案" in format_contract(result)


def test_unified_voice_all_contributions_and_loop_survive_budget():
    novels = books()
    dna = stamp(generated_dna(novels).model_dump(by_alias=True), novels, generated=True)
    contract = project_contract(novels, dna, [1, 2, 3])
    assert "统一限知视角" in contract
    assert "单书视角" not in contract
    assert all(f"《参考{i}》分工" in contract for i in (1, 2, 3))
    assert "兑现与余波1" in contract and "情绪余波与后续牵挂" in contract
    sections = PromptBudgetManager(total_budget=2000).apply_budget([
        ("[上一章摘要]", "前情" * 10000), ("[参考阅读动力与融合指引]", contract)])
    assert dict(sections)["[参考阅读动力与融合指引]"] == contract
    assert len(contract) <= 2700
    assert "不把整套循环硬塞进每章" in contract


def test_reorder_reanalysis_or_missing_book_invalidates_old_fusion():
    novels = books()
    dna = stamp(generated_dna(novels).model_dump(by_alias=True), novels, generated=True)
    assert not is_current(dna, novels[::-1], [3, 2, 1])
    assert not is_current(dna, novels[:2], [1, 2, 3])
    assert "参考资料未齐" in project_contract(novels[:2], dna, [1, 2, 3])
    novels[2].memory_card = {"core_selling_point": "改变过的分析"}
    assert not is_current(dna, novels, [1, 2, 3])


def test_reading_mechanisms_survive_memory_card_validation_and_prompt_formatting():
    novels = books()[:1]
    card = MemoryCard.model_validate(novels[0].memory_card).model_dump(exclude_defaults=True)
    assert card["reader_expectation"] == "等待改变1"
    svc = ReferenceNovelLibraryService(SimpleNamespace())
    text = svc.format_memory_card_for_prompt(novels)
    assert all(value in text for value in ("等待改变1", "兑现与余波1", "关系牵挂1"))


def test_long_three_book_fusion_keeps_conflict_resolution_and_evidence_boundary():
    dna = generated_dna(books()).model_dump(by_alias=True)
    for key, value in dna.items():
        if isinstance(value, str):
            dna[key] = "长分析" * 300
    for ref in dna["structure_references"]:
        for key in ref:
            ref[key] = "长分析" * 300
    dna["reader_loop"] = {key: "长分析" * 300 for key in dna["reader_loop"]}
    dna["conflict_resolution"] = ["长分析" * 300]
    dna["avoidance_list"] = ["长分析" * 300]
    text = format_contract(dna)
    assert text.count("分工】") == 3
    for label in ("统一叙事声音", "情绪余波与后续牵挂", "本章执行", "冲突取舍", "避免复刻", "依据边界"):
        assert f"【{label}】" in text
    assert text.endswith(("长分析" * 300)[:110])  # 尾部边界也有独立预算，不被整段截掉
