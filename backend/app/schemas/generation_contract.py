from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GenerationVariantPayload(BaseModel):
    """Stable internal contract for one generated chapter candidate."""

    model_config = ConfigDict(extra="allow")

    index: int
    version_id: int
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata", mode="before")
    @classmethod
    def _metadata_dict(cls, value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}


class GenerationResultPayload(BaseModel):
    """Stable response contract shared by legacy pipeline and Agent generation."""

    model_config = ConfigDict(extra="allow")

    project_id: str
    chapter_number: int
    preset: str
    best_version_index: int = 0
    variants: List[GenerationVariantPayload]
    review_summaries: Dict[str, Any] = Field(default_factory=dict)
    debug_metadata: Optional[Dict[str, Any]] = None

    @field_validator("variants")
    @classmethod
    def _variants_required(cls, variants: List[GenerationVariantPayload]) -> List[GenerationVariantPayload]:
        if not variants:
            raise ValueError("generation result must include at least one variant")
        return variants

    @field_validator("review_summaries", mode="before")
    @classmethod
    def _review_summaries_dict(cls, value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @model_validator(mode="after")
    def _best_index_in_range(self) -> "GenerationResultPayload":
        if self.best_version_index < 0 or self.best_version_index >= len(self.variants):
            raise ValueError("best_version_index must point to an existing variant")
        return self


def normalize_generation_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize generated output before routers serialize it."""

    return GenerationResultPayload.model_validate(payload).model_dump(exclude_none=True)
