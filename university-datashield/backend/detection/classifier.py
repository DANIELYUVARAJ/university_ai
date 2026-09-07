"""
University DataShield – Detection Engine
Phase 2: classifier.py

Semantic classification and data-type signal logic.

Responsibilities:
  1. Map field data_type to a classification signal.
  2. Resolve the "winning" classification when multiple rules/patterns fire.
  3. Provide a priority ordering so the most-specific classification wins.
"""

from __future__ import annotations
from .schemas import Classification


# ── Classification priority (lower index = higher priority) ──────────────────
#
# When multiple signals suggest different classifications, the one with the
# lower priority index wins.

PRIORITY: dict[Classification, int] = {
    "DIRECT_IDENTIFIER":  0,
    "QUASI_IDENTIFIER":   1,
    "SENSITIVE_ATTRIBUTE": 2,
    "PLACEMENT_DATA":     3,
    "ACADEMIC_DATA":      4,
    "NON_SENSITIVE":      5,
}


def best_classification(*candidates: Classification) -> Classification:
    """Return the highest-priority classification from a set of candidates."""
    return min(candidates, key=lambda c: PRIORITY.get(c, 99))


# ── Data-type → classification signal ───────────────────────────────────────
#
# Data type alone never classifies a field as sensitive.
# It contributes +10 to confidence only when paired with other signals.

_TYPE_HINTS: dict[str, tuple[Classification, int, str]] = {
    # type_key: (likely classification, score_contribution, reason)
    "date":    ("QUASI_IDENTIFIER",   10, "Date data type (potential DOB/temporal PII)"),
    "string":  ("DIRECT_IDENTIFIER",  10, "String data type (common for identifiers)"),
    "number":  ("SENSITIVE_ATTRIBUTE", 5, "Numeric data type (common for financial/academic values)"),
    "numeric": ("SENSITIVE_ATTRIBUTE", 5, "Numeric data type"),
    "integer": ("SENSITIVE_ATTRIBUTE", 5, "Integer data type"),
    "float":   ("SENSITIVE_ATTRIBUTE", 5, "Float data type"),
    "boolean": ("NON_SENSITIVE",       0, "Boolean type — low sensitivity"),
    "unknown": ("NON_SENSITIVE",       0, "Unknown type — no type signal"),
}


def data_type_signal(
    data_type: str,
) -> tuple[Classification | None, int, str | None]:
    """
    Return (classification_hint, score_contribution, reason) for a data type.
    Returns (None, 0, None) for types with no classification hint.
    """
    key = data_type.lower().strip()
    entry = _TYPE_HINTS.get(key)
    if entry is None:
        # Try a loose match (e.g. "varchar" → string)
        for k, v in _TYPE_HINTS.items():
            if k in key:
                return v
        return None, 0, None
    return entry
