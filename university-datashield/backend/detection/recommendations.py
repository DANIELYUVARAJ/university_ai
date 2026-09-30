"""
University DataShield – Detection Engine
Phase 9: recommendations.py

Generates actionable masking recommendations aligned with University DataShield's
policy engine (MASK, HASH, GENERALIZE, SUPPRESS, REVIEW, NONE).
Does NOT automatically modify data; provides prescriptive guidance.
"""

from __future__ import annotations


def generate_recommendation(
    field_name: str,
    classification: str,
    confidence: int,
    is_ambiguous: bool = False,
) -> str:
    """
    Produce an actionable masking recommendation for a given field based on
    classification, confidence, and ambiguity status.
    """
    norm = field_name.lower().strip()

    if is_ambiguous:
        return "REVIEW — Manual policy review required before analytics release"

    if classification == "DIRECT_IDENTIFIER":
        # Identifier fields -> HASH for consistent joining
        if any(tok in norm for tok in ("id", "roll", "enrolment", "registration", "identifier", "reference", "reg_no")):
            return "HASH — Cryptographic SHA-256 pseudonymization recommended for analytical linkage"
        # Contact info -> MASK for format preservation
        if any(tok in norm for tok in ("email", "mail")):
            return "MASK — Partial email masking (e.g. s***@example.edu) required"
        if any(tok in norm for tok in ("phone", "mobile", "contact", "cell")):
            return "MASK — Partial phone number masking (e.g. +91-***-***-0001) required"
        if "name" in norm:
            return "MASK or HASH — Pseudonymization or suppression required for personal names"
        if "address" in norm:
            return "GENERALIZE or MASK — Street address redaction or city-level generalization required"
        return "MASK or HASH — Direct identifier requires format-preserving protection"

    elif classification == "QUASI_IDENTIFIER":
        if any(tok in norm for tok in ("dob", "birth", "date_of_birth")):
            return "GENERALIZE — Birth year / decade generalization recommended"
        if any(tok in norm for tok in ("year", "graduation")):
            return "GENERALIZE — Graduation year / cohort bucketing recommended"
        if any(tok in norm for tok in ("zip", "pin", "postal")):
            return "GENERALIZE — 3-digit postal code aggregation recommended"
        return "GENERALIZE — Attribute generalization required to prevent quasi-identifier linkage"

    elif classification == "SENSITIVE_ATTRIBUTE":
        if any(tok in norm for tok in ("salary", "income", "compensation", "package")):
            return "GENERALIZE — Salary range/band bucketing recommended (e.g. $80k-$90k)"
        if any(tok in norm for tok in ("account", "bank", "ifsc", "pan", "ssn", "aadhaar")):
            return "MASK or SUPPRESS — Financial/legal credential suppression required"
        return "GENERALIZE or MASK — Sensitive attribute protection mandated"

    elif classification == "ACADEMIC_DATA":
        if any(tok in norm for tok in ("gpa", "cgpa", "percentage", "marks", "score", "grade", "absence")):
            return "GENERALIZE — Score/grade bucketing recommended for external analytical release"
        return "GENERALIZE — Academic record generalization recommended"

    elif classification == "PLACEMENT_DATA":
        if any(tok in norm for tok in ("package", "salary", "offer", "ctc")):
            return "GENERALIZE — Placement compensation band generalization recommended"
        return "GENERALIZE — Employment status generalization recommended"

    elif classification == "NON_SENSITIVE":
        return "NONE — Standard analytical release permitted (no masking required)"

    return "REVIEW — Unknown classification; review recommended"
