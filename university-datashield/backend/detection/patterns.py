"""
University DataShield – Detection Engine
Phase 2 & Phase 9: patterns.py

Regex-based value-pattern detection and validation intelligence.

Design rules:
 - All regexes are compiled once at import time.
 - Each pattern entry is a (label, regex) pair.
 - No raw personal values are stored here – these are structural patterns
   that match synthetic example values like "student001@example.edu".
 - Phase 9 additions:
   * Registration / candidate numbers
   * Postal / PIN codes
   * Salary / placement package formats
   * URL format identification
   * Invalid / malformed sample value detection
"""

from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ValuePattern:
    label: str              # Human-readable name e.g. "email"
    category: str           # Maps to Classification
    regex: re.Pattern[str]
    score_contribution: int = 30  # Points added to confidence when matched


# ── Compiled patterns ─────────────────────────────────────────────────────────

VALUE_PATTERNS: list[ValuePattern] = [
    # Email  ──────────────────────────────────────────────────────────────────
    ValuePattern(
        label="email",
        category="DIRECT_IDENTIFIER",
        regex=re.compile(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
            re.IGNORECASE,
        ),
        score_contribution=30,
    ),

    # Phone (international / local)
    # Requires: starts with +, or has parentheses, or 10-digit clusters
    # Specifically avoids matching dates like 2023-01-15
    ValuePattern(
        label="phone",
        category="DIRECT_IDENTIFIER",
        regex=re.compile(
            # +CC-NNNNNNNNNN  or  +CC NNNNNNNNNN
            r"\+\d{1,3}[\s\-]\d{5,15}"
            r"|"
            # (0XX) NNNNNNNN
            r"\(\d{2,4}\)[\s\-]?\d{6,10}"
            r"|"
            # plain 10-digit number (no hyphens to avoid dates)
            r"(?<!\d)\d{10}(?!\d)",
            re.IGNORECASE,
        ),
        score_contribution=25,
    ),

    # Student-style identifier  ───────────────────────────────────────────────
    # Matches: STU_DEMO_001, STU001, STUDENT_2023_42, UID_100, S12345
    ValuePattern(
        label="student_id",
        category="DIRECT_IDENTIFIER",
        regex=re.compile(
            r"\b(STU[_\-]?\w+|STUDENT[_\-]?\w+|UID[_\-]?\d+|S\d{5,})\b",
            re.IGNORECASE,
        ),
        score_contribution=30,
    ),

    # Registration / Candidate identifier (Phase 9)  ──────────────────────────
    ValuePattern(
        label="registration_number",
        category="DIRECT_IDENTIFIER",
        regex=re.compile(
            r"\b(REG[_\-]?\d{3,8}|ENR[_\-]?\d{3,8}|ROLL[_\-]?\d{3,8}|CAND[_\-]?\d{3,8}|APP[_\-]?\d{3,8})\b",
            re.IGNORECASE,
        ),
        score_contribution=30,
    ),

    # Date of birth  ───────────────────────────────────────────────────
    # Matches realistic birth years only: 194x–200x
    # (Avoids matching generic timestamps like 2023-01-15 for 'created_at')
    ValuePattern(
        label="date_of_birth",
        category="QUASI_IDENTIFIER",
        regex=re.compile(
            r"\b(194|195|196|197|198|199|200)\d[\-/\.](0?[1-9]|1[0-2])[\-/\.](0?[1-9]|[12]\d|3[01])\b"
            r"|"
            r"\b(0?[1-9]|[12]\d|3[01])[\-/\.](0?[1-9]|1[0-2])[\-/\.](194|195|196|197|198|199|200)\d\b"
            r"|"
            r"\b(0?[1-9]|[12]\d|3[01])[\-\s](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\-\s](194|195|196|197|198|199|200)\d\b",
            re.IGNORECASE,
        ),
        score_contribution=30,
    ),


    # Salary / CTC package notation (Phase 9)  ────────────────────────────────
    ValuePattern(
        label="salary",
        category="SENSITIVE_ATTRIBUTE",
        regex=re.compile(
            r"(\$|₹|€|£)\s?\d{1,3}(,\d{3})*(\.\d{2})?"
            r"|"
            r"\b\d+(\.\d+)?\s?(LPA|lpa|CTC|ctc)\b"
            r"|"
            r"\b(4[0-9]|5[0-9]|6[0-9]|7[0-9]|8[0-9]|9[0-9]|\d{2,3}),000\b",
            re.IGNORECASE,
        ),
        score_contribution=25,
    ),

    # Account / IBAN-like numeric string  ─────────────────────────────────────
    # Matches long digit strings (8–20 digits) that look like bank/ID numbers
    ValuePattern(
        label="account_number",
        category="SENSITIVE_ATTRIBUTE",
        regex=re.compile(
            r"\b\d{8,20}\b",
            re.IGNORECASE,
        ),
        score_contribution=20,
    ),
]


def match_value_patterns(value: str) -> list[ValuePattern]:
    """
    Return all ValuePattern entries whose regex matches `value`.
    """
    if not value or not value.strip():
        return []
    return [p for p in VALUE_PATTERNS if p.regex.search(value)]


# ── Phase 9: Value Validation & Invalidity Detection ────────────────────────

INVALID_INDICATORS = {
    "not-a-phone",
    "not_a_phone",
    "invalid-phone",
    "invalid-email",
    "invalid_email",
    "fake-phone",
    "dummy",
    "unknown",
    "n/a",
    "na",
    "none",
    "null",
}


def detect_invalid_value(field_name: str, sample_value: str | None) -> tuple[bool, str | None]:
    """
    Checks if a sample value is explicitly invalid, malformed, or placeholder.
    Returns (is_invalid, explanation).
    """
    if sample_value is None:
        return False, None

    cleaned = sample_value.strip().lower()
    if not cleaned:
        return False, None

    if cleaned in INVALID_INDICATORS:
        return True, f"Sample value '{sample_value}' is a known placeholder/invalid test pattern"

    norm_name = field_name.lower().replace("-", "_").replace(" ", "_")

    # Mismatch check: Phone field with letters or non-numeric tokens
    if any(k in norm_name for k in ("phone", "mobile", "telephone", "cell")):
        if re.search(r"[a-zA-Z]{3,}", sample_value):
            return True, f"Phone column contains alphabetic string ('{sample_value}')"

    # Mismatch check: Email field without @ or domain
    if any(k in norm_name for k in ("email", "mail_id")) and "template" not in norm_name:
        if "@" not in sample_value or "." not in sample_value:
            return True, f"Email column value lacks valid email format ('{sample_value}')"

    return False, None
