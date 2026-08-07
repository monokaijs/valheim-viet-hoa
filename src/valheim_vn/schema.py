from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Tier(StrEnum):
    BASIC = "basic"
    INSPECT = "need_more_inspection"
    HIGH = "high_inspection"
    ULTRA = "ultra_inspection"
    SKIP = "skip"


TIER_ORDER = {
    Tier.SKIP: -1,
    Tier.BASIC: 0,
    Tier.INSPECT: 1,
    Tier.HIGH: 2,
    Tier.ULTRA: 3,
}


class CatalogEntry(BaseModel):
    segment_id: str
    key: str
    english: str
    source_hash: str
    asset: str
    row_index: int
    family: str
    domain: str
    reference_translations: dict[str, str] = Field(default_factory=dict)
    baseline_tier: Tier
    risk_reasons: list[str] = Field(default_factory=list)


class ClassificationItem(BaseModel):
    segment_id: str
    tier: Tier
    domain: str
    speaker: str | None = None
    context_notes: str = ""
    ambiguity_notes: list[str] = Field(default_factory=list)


class ClassificationBatch(BaseModel):
    items: list[ClassificationItem]


class GlossaryCandidate(BaseModel):
    source: str
    target: str


class TranslationItem(BaseModel):
    segment_id: str
    translation: str
    confidence: float = Field(ge=0, le=1)
    notes: str = ""
    # Strict Structured Outputs does not support a free-form dictionary here;
    # represent proposed mappings as fixed-shape records.
    glossary_candidates: list[GlossaryCandidate] = Field(default_factory=list)


class TranslationBatch(BaseModel):
    items: list[TranslationItem]


class ReviewItem(BaseModel):
    segment_id: str
    verdict: Literal["pass", "revise", "reject"]
    revised_translation: str | None = None
    issues: list[str] = Field(default_factory=list)


class ReviewBatch(BaseModel):
    items: list[ReviewItem]


class SegmentState(BaseModel):
    segment_id: str
    key: str
    english: str
    source_hash: str
    family: str
    domain: str
    tier: Tier
    context: dict[str, Any] = Field(default_factory=dict)
    translation: str | None = None
    status: str = "pending"
    model: str | None = None
    reasoning_effort: str | None = None
    notes: str = ""
    validation_errors: list[str] = Field(default_factory=list)
