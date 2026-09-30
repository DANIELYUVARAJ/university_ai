"""
University DataShield – Detection Engine
Phase 2 & Phase 9: schemas.py

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
ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW", "REVIEW"]
AmbiguityStatus = Literal["CLEAR", "REVIEW"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
PublicationReadiness = Literal["READY", "NEEDS_PROTECTION", "BLOCKED"]


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
    context_match: bool = False  # Phase 9: Cross-field context match


class FieldResult(BaseModel):
    """Detection result for a single field."""
    field: str
    data_type: str
    classification: Classification
    confidence: int = Field(ge=0, le=100)
    confidence_band: ConfidenceBand
    signals: SignalBreakdown
    reasons: list[str]

    # Phase 9 Extensions (with backward-compatible defaults)
    normalized_name: str | None = None
    confidence_level: str | None = None
    ambiguity_status: str | None = None
    contextual_signals: list[str] = Field(default_factory=list)
    recommendation: str | None = None


class DatasetRiskSummary(BaseModel):
    """Dataset-level synthetic risk summary (Phase 9)."""
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel = "LOW"
    publication_readiness: PublicationReadiness = "READY"
    direct_identifiers_count: int = 0
    quasi_identifiers_count: int = 0
    sensitive_attributes_count: int = 0
    academic_data_count: int = 0
    placement_data_count: int = 0
    non_sensitive_count: int = 0
    review_fields_count: int = 0
    risk_factors: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Synthetic prototype risk indicator based on heuristic schema composition. "
        "Not a formal cryptographic or regulatory compliance audit."
    )


class ScanResponse(BaseModel):
    """Response body for POST /scan."""
    dataset_name: str
    scan_id: int | None = None          # DB row id when persisted
    fields_scanned: int
    sensitive_count: int
    results: list[FieldResult]

    # Phase 9 Extensions:
    dataset_risk: DatasetRiskSummary | None = None
    publication_readiness: str | None = None
