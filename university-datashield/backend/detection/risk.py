"""
University DataShield – Detection Engine
Phase 9: risk.py

Dataset-Level Risk Assessment and Publication Readiness.
Calculates synthetic risk scores (0–100), risk levels (LOW, MEDIUM, HIGH, CRITICAL),
and publication readiness based on discovered schema composition.

Explicit Disclaimer:
This is a synthetic prototype risk indicator based on heuristic schema composition,
not a formal regulatory or mathematical differential privacy audit standard.
"""

from __future__ import annotations
from typing import List, Literal
from .schemas import FieldResult, DatasetRiskSummary


def calculate_dataset_risk(results: List[FieldResult]) -> DatasetRiskSummary:
    """
    Computes dataset-level risk metrics from individual field scan results.
    """
    direct_count = sum(1 for r in results if r.classification == "DIRECT_IDENTIFIER")
    quasi_count = sum(1 for r in results if r.classification == "QUASI_IDENTIFIER")
    sensitive_count = sum(1 for r in results if r.classification == "SENSITIVE_ATTRIBUTE")
    academic_count = sum(1 for r in results if r.classification == "ACADEMIC_DATA")
    placement_count = sum(1 for r in results if r.classification == "PLACEMENT_DATA")
    non_sensitive_count = sum(1 for r in results if r.classification == "NON_SENSITIVE")
    review_count = sum(1 for r in results if getattr(r, "ambiguity_status", None) == "REVIEW")

    total_fields = len(results)
    risk_factors: List[str] = []

    # Risk score calculation (0 to 100)
    # Direct IDs: 25 pts each (max 50)
    # Quasi IDs: 15 pts each (max 25)
    # Sensitive attributes: 15 pts each (max 25)
    # Academic/Placement: 5 pts each (max 15)
    # Review fields: 10 pts each (max 20)
    direct_score = min(direct_count * 25, 50)
    quasi_score = min(quasi_count * 15, 25)
    sensitive_score = min(sensitive_count * 15, 25)
    domain_score = min((academic_count + placement_count) * 5, 15)
    review_score = min(review_count * 10, 20)

    raw_risk = direct_score + quasi_score + sensitive_score + domain_score + review_score
    risk_score = min(raw_risk, 100)

    # Document risk factors
    if direct_count > 0:
        risk_factors.append(f"Contains {direct_count} direct personal identifier(s)")
    if quasi_count >= 2:
        risk_factors.append(f"Contains {quasi_count} quasi-identifiers (potential external linkage risk)")
    elif quasi_count == 1:
        risk_factors.append("Contains 1 quasi-identifier")
    if sensitive_count > 0:
        risk_factors.append(f"Contains {sensitive_count} sensitive financial/legal attribute(s)")
    if review_count > 0:
        risk_factors.append(f"Contains {review_count} ambiguous/review field(s) requiring manual verification")
    if non_sensitive_count == total_fields:
        risk_factors.append("All fields are non-sensitive institutional/course metadata")

    # Risk level categorization
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    if risk_score >= 80 or direct_count >= 3:
        risk_level = "CRITICAL"
    elif risk_score >= 50 or direct_count >= 1:
        risk_level = "HIGH"
    elif risk_score >= 25 or quasi_count >= 1 or review_count >= 1:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    # Publication readiness assessment
    publication_readiness: Literal["READY", "NEEDS_PROTECTION", "BLOCKED"]
    if direct_count > 0 or sensitive_count > 0 or review_count > 0:
        publication_readiness = "NEEDS_PROTECTION"
    elif quasi_count > 0 or academic_count > 0 or placement_count > 0:
        publication_readiness = "NEEDS_PROTECTION"
    else:
        publication_readiness = "READY"

    return DatasetRiskSummary(
        risk_score=risk_score,
        risk_level=risk_level,
        publication_readiness=publication_readiness,
        direct_identifiers_count=direct_count,
        quasi_identifiers_count=quasi_count,
        sensitive_attributes_count=sensitive_count,
        academic_data_count=academic_count,
        placement_data_count=placement_count,
        non_sensitive_count=non_sensitive_count,
        review_fields_count=review_count,
        risk_factors=risk_factors,
    )
