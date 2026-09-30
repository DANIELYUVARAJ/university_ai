"""
University DataShield – Detection Engine
Phase 9: ambiguity.py

Confidence Decision Model and Ambiguity Handling.
Defines explicit thresholds, confidence levels (HIGH, MEDIUM, LOW, REVIEW),
and handling for ambiguous or conflicting fields.
"""

from __future__ import annotations
from typing import Literal, Tuple, List

AmbiguityStatus = Literal["CLEAR", "REVIEW"]
ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW", "REVIEW"]

# Generic or ambiguous tokens that should not be classified without supporting evidence
AMBIGUOUS_FIELD_NAMES = {
    "contact",
    "record",
    "data",
    "info",
    "reference",
    "id",
    "code",
    "value",
    "detail",
    "entry",
    "status",
    "type",
    "category",
    "number",
}


def evaluate_ambiguity(
    field_name: str,
    classification: str,
    confidence: int,
    has_pattern_match: bool,
    value_is_invalid: bool,
    has_context_support: bool = False,
) -> Tuple[AmbiguityStatus, ConfidenceLevel, List[str]]:
    """
    Evaluates whether a field is ambiguous or requires human review.

    Documented Decision Model:
      - HIGH: confidence >= 70 and not ambiguous.
      - MEDIUM: 40 <= confidence < 70 and not ambiguous.
      - LOW: 0 < confidence < 40 and not ambiguous.
      - REVIEW:
          1) Field name is in AMBIGUOUS_FIELD_NAMES and lacks validating value pattern / context.
          2) Field name suggests sensitivity but sample value is malformed / invalid.
          3) Conflicting signals where protection requirements cannot be safely established.
    """
    norm = field_name.lower().strip()
    reasons: List[str] = []

    # Case 1: Ambiguous field name without validating pattern or context
    if norm in AMBIGUOUS_FIELD_NAMES and not has_pattern_match and not has_context_support:
        reasons.append(
            f"Field name '{norm}' is generic/ambiguous; requires value pattern verification or manual confirmation"
        )
        return "REVIEW", "REVIEW", reasons

    # Case 2: Sensitive field with malformed / invalid sample value
    if value_is_invalid:
        reasons.append(
            "Sample value does not match expected format for detected category; flagged for review"
        )
        return "REVIEW", "REVIEW", reasons

    # Case 3: Clear confidence bands
    if confidence >= 70:
        return "CLEAR", "HIGH", reasons
    elif confidence >= 40:
        return "CLEAR", "MEDIUM", reasons
    elif confidence > 0:
        return "CLEAR", "LOW", reasons
    else:
        return "CLEAR", "LOW", reasons
