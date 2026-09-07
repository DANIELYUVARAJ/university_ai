"""
University DataShield – Detection Package
Phase 2: Sensitive Field Discovery Engine

Public API of this package:
    scan_fields(fields: list[FieldInput]) -> list[FieldResult]
"""

from .detector import scan_fields
from .schemas import FieldInput, FieldResult, ScanRequest, ScanResponse

__all__ = [
    "scan_fields",
    "FieldInput",
    "FieldResult",
    "ScanRequest",
    "ScanResponse",
]
