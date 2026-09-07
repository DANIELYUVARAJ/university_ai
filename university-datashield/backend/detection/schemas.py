"""
University DataShield – Detection Engine
Phase 2: schemas.py

Pydantic models for the /scan API request and response.
No real personal data is ever required — all sample_pattern values
must be synthetic or schema-level metadata.
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


# ── Classification categories ────────────────────────────────────────────────

Classification = Literal[
    "DIRECT_IDENTIFIER",
    "QUASI_IDENTIFIER",
    "SENSITIVE_ATTRIBUTE",
    "ACADEMIC_DATA",
    "PLACEMENT_DATA",
    "NON_SENSITIVE",
]

ConfidenceBand = Literal["HIGH", "MEDIUM", "LOW", "NONE"]


def confidence_band(score: int) -> ConfidenceBand:
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "NONE"


# ── Input models ─────────────────────────────────────────────────────────────

class FieldInput(BaseModel):
    """A single field in a dataset schema to be scanned."""
    name: str = Field(..., description="Column / field name")
    data_type: str = Field(
        default="string",
        description="Data type: string | number | date | boolean | unknown",
    )
    sample_pattern: str | None = Field(
        default=None,
        description=(
            "An optional SYNTHETIC example value used for pattern detection. "
            "Must never be real personal data."
        ),
    )


class ScanRequest(BaseModel):
    """Request body for POST /scan."""
    dataset_name: str = Field(..., description="Logical name for this dataset scan")
    fields: list[FieldInput] = Field(..., min_length=1)


# ── Output models ─────────────────────────────────────────────────────────────

class SignalBreakdown(BaseModel):
    """Which detection signals fired."""
    field_name_match: bool = False
    pattern_match: bool = False
    data_type_match: bool = False
    semantic_match: bool = False


class FieldResult(BaseModel):
    """Detection result for a single field."""
    field: str
    data_type: str
    classification: Classification
    confidence: int = Field(ge=0, le=100)
    confidence_band: ConfidenceBand
    signals: SignalBreakdown
    reasons: list[str]


class ScanResponse(BaseModel):
    """Response body for POST /scan."""
    dataset_name: str
    scan_id: int | None = None          # DB row id when persisted
    fields_scanned: int
    sensitive_count: int
    results: list[FieldResult]
