"""
University DataShield – Detection Engine
Phase 2: patterns.py

Regex-based value-pattern detection.

Design rules:
 - All regexes are compiled once at import time.
 - Each pattern entry is a (label, regex) pair.
 - No raw personal values are stored here – these are structural patterns
   that match synthetic example values like "student001@example.edu".
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
    # Matches: STU_DEMO_001, STU001, STUDENT_2023_42, UID_100
    ValuePattern(
        label="student_id",
        category="DIRECT_IDENTIFIER",
        regex=re.compile(
            r"\b(STU[_\-]?\w+|STUDENT[_\-]?\w+|UID[_\-]?\d+|S\d{5,})\b",
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
    Only the *first match* per pattern is checked (fullmatch not required).
    """
    if not value or not value.strip():
        return []
    return [p for p in VALUE_PATTERNS if p.regex.search(value)]
