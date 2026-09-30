"""
University DataShield – Detection Package
Phase 2 & Phase 9: Sensitive Field Discovery Engine & Dataset Intelligence

Public API of this package:
    scan_fields(fields: list[FieldInput]) -> list[FieldResult]
    scan_fields_with_risk(fields: list[FieldInput]) -> tuple[list[FieldResult], DatasetRiskSummary]
"""

from .detector import scan_fields, scan_field, scan_fields_with_risk
from .schemas import (
    FieldInput,
    FieldResult,
    ScanRequest,
    ScanResponse,
    DatasetRiskSummary,
    Classification,
    ConfidenceLevel,
)
from .normalizer import normalize_field_name, resolve_alias
from .context import DatasetContext
from .risk import calculate_dataset_risk
from .recommendations import generate_recommendation

__all__ = [
    "scan_fields",
    "scan_field",
    "scan_fields_with_risk",
    "FieldInput",
    "FieldResult",
    "ScanRequest",
    "ScanResponse",
    "DatasetRiskSummary",
    "Classification",
    "ConfidenceLevel",
    "normalize_field_name",
    "resolve_alias",
    "DatasetContext",
    "calculate_dataset_risk",
    "generate_recommendation",
]
