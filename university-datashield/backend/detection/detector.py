"""
University DataShield – Detection Engine
Phase 2: detector.py

Core detection orchestrator.

The scan pipeline for each field:
  1. Apply field-name rules  → classification candidate + score
  2. Apply value patterns    → classification candidate + score
  3. Apply data-type signal  → classification hint + score
  4. Resolve final classification (highest priority wins)
  5. Compute total confidence (capped at 100)
  6. Build explanation (reasons list)

Design constraints:
  - Deterministic: same input → same output.
  - Explainable: every positive detection carries human-readable reasons.
  - No real personal data is consumed or stored.
"""

from __future__ import annotations
import logging

from .schemas import (
    Classification,
    FieldInput,
    FieldResult,
    SignalBreakdown,
    confidence_band,
)
from .rules import FIELD_NAME_RULES, FieldNameRule
from .patterns import match_value_patterns, ValuePattern
from .classifier import data_type_signal, best_classification

logger = logging.getLogger(__name__)

# Maximum possible score (used for capping)
_MAX_SCORE = 100

# Minimum confidence to be considered "detected as sensitive"
SENSITIVE_THRESHOLD = 30


def _apply_field_name_rules(
    field_name: str,
) -> tuple[list[FieldNameRule], int, list[str]]:
    """
    Run every FieldNameRule against `field_name`.
    Returns (matched_rules, total_score, reasons).
    """
    matched: list[FieldNameRule] = []
    total_score = 0
    reasons: list[str] = []

    for rule in FIELD_NAME_RULES:
        # Check exclusions first — any exclusion match skips this rule
        if any(excl.search(field_name) for excl in rule.exclusions):
            continue

        if any(pat.search(field_name) for pat in rule.name_patterns):
            matched.append(rule)
            total_score += rule.score
            reasons.append(rule.reason)

    return matched, total_score, reasons


def _apply_value_patterns(
    sample: str,
) -> tuple[list[ValuePattern], int, list[str]]:
    """
    Run compiled value patterns against `sample`.
    Returns (matched_patterns, total_score, reasons).
    """
    matched = match_value_patterns(sample)
    total_score = sum(p.score_contribution for p in matched)
    reasons = [f"Value matches {p.label} pattern" for p in matched]
    return matched, total_score, reasons


def scan_field(field: FieldInput) -> FieldResult:
    """
    Run the full detection pipeline for a single field.
    Returns a FieldResult with classification, confidence, signals, and reasons.
    """
    field_name = field.name.lower().strip()
    sample = (field.sample_pattern or "").strip()
    data_type = (field.data_type or "string").lower().strip()

    # ── 1. Field-name signal ─────────────────────────────────────────────────
    name_rules, name_score, name_reasons = _apply_field_name_rules(field_name)
    name_fired = bool(name_rules)

    # Derive classification candidates from name rules
    name_classifications: list[Classification] = [
        r.classification for r in name_rules  # type: ignore[misc]
    ]

    # ── 2. Value-pattern signal ──────────────────────────────────────────────
    pat_matches, pat_score, pat_reasons = (
        _apply_value_patterns(sample) if sample else ([], 0, [])
    )
    pat_fired = bool(pat_matches)

    # Derive classification candidates from patterns
    pat_classifications: list[Classification] = [
        p.category for p in pat_matches  # type: ignore[misc]
    ]

    # ── 3. Data-type signal ───────────────────────────────────────────────────
    type_class_hint, type_score, type_reason = data_type_signal(data_type)
    type_fired = type_score > 0 and (name_fired or pat_fired)
    # Data type alone must NOT trigger detection → only scores if another signal fired
    effective_type_score = type_score if type_fired else 0
    type_reasons = [type_reason] if type_fired and type_reason else []

    # ── 4. Resolve classification ─────────────────────────────────────────────
    all_candidates: list[Classification] = (
        name_classifications + pat_classifications
    )

    if all_candidates:
        resolved: Classification = best_classification(*all_candidates)
    else:
        resolved = "NON_SENSITIVE"

    # Semantic classification bonus: +20 when resolved is not NON_SENSITIVE
    semantic_fired = resolved != "NON_SENSITIVE"
    semantic_score = 20 if semantic_fired else 0
    semantic_reason = (
        f"Classified as {resolved.replace('_', ' ').title()}"
        if semantic_fired
        else None
    )

    # ── 5. Total confidence ───────────────────────────────────────────────────
    raw_score = name_score + pat_score + effective_type_score + semantic_score
    confidence = min(raw_score, _MAX_SCORE)

    # ── 6. Assemble result ────────────────────────────────────────────────────
    all_reasons: list[str] = name_reasons + pat_reasons + type_reasons
    if semantic_reason:
        all_reasons.append(semantic_reason)

    signals = SignalBreakdown(
        field_name_match=name_fired,
        pattern_match=pat_fired,
        data_type_match=type_fired,
        semantic_match=semantic_fired,
    )

    logger.debug(
        "field=%s classification=%s confidence=%d signals=%s",
        field.name, resolved, confidence, signals,
    )

    return FieldResult(
        field=field.name,
        data_type=field.data_type,
        classification=resolved,
        confidence=confidence,
        confidence_band=confidence_band(confidence),
        signals=signals,
        reasons=all_reasons if all_reasons else ["No sensitive signals detected"],
    )


def scan_fields(fields: list[FieldInput]) -> list[FieldResult]:
    """
    Scan a list of fields and return detection results for each.
    This is the main public entry point used by the /scan endpoint.
    """
    return [scan_field(f) for f in fields]
