import json

import pytest
from pydantic import ValidationError

from app.services.bench.serial_reading import (
    DIMENSIONS, SerialCase, SerialJudgement, blind_packet, judge_serial, write_reading_packet,
)


def case():
    return SerialCase(context="两人曾因借粮决裂，刚刚重逢。共同前情只有这一份。", versions=[
        {"source": source, "chapters": [
            {"number": number, "content": f"第{number}次，她端着缺口的碗进屋。{source[-1]}号人物问：还吃吗？"}
            for number in (4, 5, 6)]}
        for source in ("before-secret-x", "after-secret-y")])


def verdict(packet, *, winner="A", swapped=False):
    versions = packet["versions"] if not swapped else {"A": packet["versions"]["B"], "B": packet["versions"]["A"]}
    evidence = [{"side": side, "chapter": c["number"], "quote": c["content"]}
                for side, chapters in versions.items() for c in chapters[:2]]
    return SerialJudgement(dimensions=[{"dimension": name, "winner": winner, "reason": "用前后行为说明关系变化。",
                                        "evidence": evidence} for name in DIMENSIONS])


@pytest.mark.parametrize("mutation", ["gap", "different_range", "duplicate_source", "single_chapter"])
def test_sequences_must_be_aligned_and_contiguous(mutation):
    data = case().model_dump()
    if mutation == "gap":
        data["versions"][0]["chapters"][1]["number"] = 9
    elif mutation == "different_range":
        data["versions"][1]["chapters"][-1]["number"] = 7
    elif mutation == "duplicate_source":
        data["versions"][1]["source"] = data["versions"][0]["source"]
    else:
        data["versions"][0]["chapters"] = data["versions"][0]["chapters"][:1]
    with pytest.raises(ValidationError):
        SerialCase.model_validate(data)


def test_packet_has_full_chapters_but_no_source_identity_and_escapes_html(tmp_path):
    c = case()
    c.versions[0].chapters[-1].content += '<script>alert("x")</script>'
    out = tmp_path / "packet"
    packet = write_reading_packet(c, out)
    public = (out / "reading.html").read_text(encoding="utf-8") + (out / "packet.json").read_text(encoding="utf-8")
    assert "before-secret-x" not in public and "after-secret-y" not in public
    key = json.loads((out / "private" / "answer-key.json").read_text(encoding="utf-8"))
    for side, chapters in packet["versions"].items():
        original = next(v for v in c.versions if v.source == key[side])
        assert chapters == [chapter.model_dump() for chapter in original.chapters]
    html = (out / "reading.html").read_text(encoding="utf-8")
    assert "&lt;script&gt;" in html and "<script>" not in html
    with pytest.raises(FileExistsError):
        write_reading_packet(c, out)


@pytest.mark.asyncio
@pytest.mark.parametrize("second,expected", [("B", "A"), ("A", None)])
async def test_swapped_judges_must_agree_and_evidence_sides_are_normalized(second, expected):
    packet, _ = blind_packet(case())
    calls = []
    class LLM:
        async def generate_structured(self, **kwargs):
            calls.append(kwargs)
            assert "secret" not in kwargs["prompt"]
            return verdict(packet, winner="A" if len(calls) == 1 else second, swapped=len(calls) == 2)
    result = await judge_serial(LLM(), packet)
    assert result["winner"] == expected
    assert result["status"] == ("completed" if expected else "inconclusive")
    for dim in result["passes"][1]["dimensions"]:
        for evidence in dim["evidence"]:
            chapter = next(c for c in packet["versions"][evidence["side"]] if c["number"] == evidence["chapter"])
            assert evidence["quote"] in chapter["content"]
    assert len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "fake_quote", "single_chapter_evidence"])
async def test_failed_or_unsupported_judgement_is_never_a_tie(failure):
    packet, _ = blind_packet(case())
    class LLM:
        async def generate_structured(self, **kwargs):
            if failure == "timeout":
                raise TimeoutError()
            result = verdict(packet)
            if failure == "fake_quote":
                result.dimensions[0].evidence[0].quote = "不存在的旧事"
            else:
                for d in result.dimensions:
                    d.evidence = [e for e in d.evidence if e.chapter == 4]
            return result
    result = await judge_serial(LLM(), packet)
    assert result["status"] == "unavailable" and result["winner"] is None
