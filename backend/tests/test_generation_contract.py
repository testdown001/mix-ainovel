import pytest

from app.schemas.generation_contract import normalize_generation_result
from app.services.generation_result_service import GenerationResultService


def test_generation_contract_normalizes_optional_maps_and_preserves_extra_fields():
    payload = normalize_generation_result(
        {
            "project_id": "novel-1",
            "chapter_number": 3,
            "preset": "agent",
            "best_version_index": 0,
            "variants": [
                {
                    "index": 0,
                    "version_id": 7,
                    "content": "chapter text",
                    "metadata": None,
                }
            ],
            "review_summaries": None,
            "archive_id": 42,
        }
    )

    assert payload["variants"][0]["metadata"] == {}
    assert payload["review_summaries"] == {}
    assert payload["archive_id"] == 42


def test_generation_contract_rejects_best_index_outside_variants():
    with pytest.raises(ValueError, match="best_version_index"):
        normalize_generation_result(
            {
                "project_id": "novel-1",
                "chapter_number": 3,
                "preset": "basic",
                "best_version_index": 1,
                "variants": [
                    {
                        "index": 0,
                        "version_id": 1,
                        "content": "chapter text",
                    }
                ],
            }
        )


def test_generation_result_service_emits_contract_compliant_payload():
    payload = GenerationResultService().build_response_payload(
        project_id="novel-1",
        chapter_number=1,
        preset="basic",
        best_version_index=0,
        variants=[{"index": 0, "version_id": 1, "content": "text"}],
        review_summaries={},
        debug_metadata={"mode": "legacy_pipeline"},
    )

    assert payload == {
        "project_id": "novel-1",
        "chapter_number": 1,
        "preset": "basic",
        "best_version_index": 0,
        "variants": [{"index": 0, "version_id": 1, "content": "text", "metadata": {}}],
        "review_summaries": {},
        "debug_metadata": {"mode": "legacy_pipeline"},
    }
