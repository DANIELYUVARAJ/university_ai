"""
University DataShield – Detection Engine
Phase 2 & Phase 9: detector.py

Core detection orchestrator with Phase 9 advanced intelligence:
  1. Field-name normalization (camelCase, kebab-case, dot-notation)
  2. Alias resolution & pattern intelligence
  3. Value validation & invalidity detection
  4. Cross-field & dataset-level contextual signals
  5. Ambiguity evaluation & confidence decision model
  6. Actionable protection recommendations
  7. Dataset-level risk scoring and publication readiness

Design constraints:
  - 100% Deterministic: same input -> same output.
  - Explainable: every detection carries clear, human-readable reasons.
  - Fail-Closed: ambiguous/unresolved sensitive fields trigger review/block.
  - Privacy by Design: No real personal data consumed or stored.
"""

from __future__ import annotations
import logging
from typing import Optional

from .schemas import (
    Classification,
    FieldInput,
    FieldResult,
    SignalBreakdown,
    DatasetRiskSummary,
    confidence_band,
)
from .rules import FIELD_NAME_RULES, FieldNameRule
from .patterns import match_value_patterns, detect_invalid_value, ValuePattern
from .classifier import data_type_signal, best_classification
from .normalizer import normalize_field_name, resolve_alias
from .context import DatasetContext
from .ambiguity import evaluate_ambiguity
from .recommendations import generate_recommendation
from .risk import calculate_dataset_risk

logger = logging.getLogger(__name__)

# Maximum possible score (used for capping)
_MAX_SCORE = 100

# Minimum confidence to be considered "detected as sensitive"
SENSITIVE_THRESHOLD = 30


def _apply_field_name_rules(
    field_name: str,
    normalized_name: str,
) -> tuple[list[FieldNameRule], int, list[str]]:
    """
    Run FieldNameRules against both original and normalized field names.
    Returns (matched_rules, total_score, reasons).
    """
    matched: list[FieldNameRule] = []
    total_score = 0
    reasons: list[str] = []

    names_to_check = {field_name, normalized_name, resolve_alias(normalized_name)}

    for rule in FIELD_NAME_RULES:
        # Check exclusions across all name variations
        excluded = False
        for name in names_to_check:
            if any(excl.search(name) for excl in rule.exclusions):
                excluded = True
                break
        if excluded:
            continue

        # Check match across name variations
        fired = False
        for name in names_to_check:
            if any(pat.search(name) for pat in rule.name_patterns):
                matched.append(rule)
                total_score += rule.score
                reasons.append(rule.reason)
                fired = True
                break

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


def scan_field(
    field: FieldInput,
    context: Optional[DatasetContext] = None,
) -> FieldResult:
    """
    Run the full detection pipeline for a single field with Phase 9 intelligence.
    Returns a FieldResult with classification, confidence, signals, reasons,
    normalized_name, confidence_level, ambiguity_status, and recommendation.
    """
    raw_name = field.name.strip()
    normalized_name = normalize_field_name(raw_name)
    sample = (field.sample_pattern or "").strip()
    data_type = (field.data_type or "string").lower().strip()

    # ── 1. Field-name & alias signal ──────────────────────────────────────────
    name_rules, name_score, name_reasons = _apply_field_name_rules(
        raw_name.lower(), normalized_name
    )
    name_fired = bool(name_rules)

    name_classifications: list[Classification] = [
        r.classification for r in name_rules  # type: ignore[misc]
    ]

    # ── 2. Value-pattern signal & validation ──────────────────────────────────
    pat_matches, pat_score, pat_reasons = (
        _apply_value_patterns(sample) if sample else ([], 0, [])
    )
    pat_fired = bool(pat_matches)

    pat_classifications: list[Classification] = [
        p.category for p in pat_matches  # type: ignore[misc]
    ]

    # Check for invalid / malformed sample values (Phase 9)
    is_invalid_val, invalid_reason = detect_invalid_value(raw_name, sample if sample else None)
    if is_invalid_val and invalid_reason:
        pat_reasons.append(invalid_reason)

    # ── 3. Data-type signal ───────────────────────────────────────────────────
    type_class_hint, type_score, type_reason = data_type_signal(data_type)
    type_fired = type_score > 0 and (name_fired or pat_fired)
    effective_type_score = type_score if type_fired else 0
    type_reasons = [type_reason] if type_fired and type_reason else []

    # ── 4. Cross-field contextual signal (Phase 9) ───────────────────────────
    context_boost = 0
    context_reasons: list[str] = []
    if context is not None:
        context_boost, context_reasons = context.get_field_context_signals(raw_name)
    context_fired = bool(context_boost > 0)

    # ── 5. Resolve classification ─────────────────────────────────────────────
    all_candidates: list[Classification] = name_classifications + pat_classifications

    # If ambiguous 'contact' has contextual or pattern support, upgrade
    if normalized_name == "contact":
        if pat_fired:
            # Pattern matched e.g. phone -> already in all_candidates
            pass
        elif context_fired:
            all_candidates.append("DIRECT_IDENTIFIER")

    if all_candidates:
        resolved: Classification = best_classification(*all_candidates)
    else:
        resolved = "NON_SENSITIVE"

    # Semantic classification bonus: +20 when resolved is sensitive
    semantic_fired = resolved != "NON_SENSITIVE"
    semantic_score = 20 if semantic_fired else 0
    semantic_reason = (
        f"Classified as {resolved.replace('_', ' ').title()}"
        if semantic_fired
        else None
    )

    # ── 6. Total confidence computation ───────────────────────────────────────
    raw_score = (
        name_score
        + pat_score
        + effective_type_score
        + semantic_score
        + context_boost
    )
    confidence = min(raw_score, _MAX_SCORE)

    # ── 7. Ambiguity & confidence decision model (Phase 9) ────────────────────
    ambiguity_status, confidence_level, ambiguity_reasons = evaluate_ambiguity(
        field_name=normalized_name,
        classification=resolved,
        confidence=confidence,
        has_pattern_match=pat_fired,
        value_is_invalid=is_invalid_val,
        has_context_support=context_fired,
    )

    # ── 8. Actionable recommendations (Phase 9) ───────────────────────────────
    recommendation = generate_recommendation(
        field_name=normalized_name,
        classification=resolved,
        confidence=confidence,
        is_ambiguous=(ambiguity_status == "REVIEW"),
    )

    # ── 9. Assemble reasons and signals ───────────────────────────────────────
    all_reasons: list[str] = (
        name_reasons
        + pat_reasons
        + type_reasons
        + context_reasons
        + ambiguity_reasons
    )
    if semantic_reason:
        all_reasons.append(semantic_reason)

    signals = SignalBreakdown(
        field_name_match=name_fired,
        pattern_match=pat_fired,
        data_type_match=type_fired,
        semantic_match=semantic_fired,
        context_match=context_fired,
    )

    logger.debug(
        "field=%s norm=%s classification=%s conf=%d level=%s signals=%s",
        raw_name, normalized_name, resolved, confidence, confidence_level, signals,
    )

    return FieldResult(
        field=field.name,
        data_type=field.data_type,
        classification=resolved,
        confidence=confidence,
        confidence_band=confidence_band(confidence),
        signals=signals,
        reasons=all_reasons if all_reasons else ["No sensitive signals detected"],
        normalized_name=normalized_name,
        confidence_level=confidence_level,
        ambiguity_status=ambiguity_status,
        contextual_signals=context_reasons,
        recommendation=recommendation,
    )


def scan_fields(fields: list[FieldInput]) -> list[FieldResult]:
    """
    Scan a list of fields and return detection results for each.
    Derives schema context from the full list before individual evaluation.
    This is the main public entry point used by the /scan endpoint.
    """
    context = DatasetContext(fields)
    return [scan_field(f, context=context) for f in fields]


def scan_fields_with_risk(
    fields: list[FieldInput],
) -> tuple[list[FieldResult], DatasetRiskSummary]:
    """
    Run detection on fields and calculate the dataset-level risk summary.
    """
    results = scan_fields(fields)
    risk_summary = calculate_dataset_risk(results)
    return results, risk_summary
