"""
University DataShield – Detection Engine
Phase 2: rules.py

Field-name matching rules.

Design:
 - Rules are pure data — no logic here.
 - Each RuleEntry maps a set of name tokens/patterns to a classification
   and a base score contribution.
 - The matcher in detector.py applies these rules.
 - To extend: add entries to FIELD_NAME_RULES. No code changes needed.

Edge-case handling baked into the rules:
 - "email_template_id" must NOT match as a personal email field.
   Achieved via an EXCLUSION token list per rule.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldNameRule:
    """
    Maps field-name signals to a classification and confidence contribution.

    name_patterns   – compiled regex list; ANY match triggers this rule.
    exclusions      – compiled regex list; ANY match in the field name
                      DISQUALIFIES this rule (prevents false positives).
    classification  – the category if this rule fires.
    score           – points added to the confidence score.
    reason          – human-readable explanation fragment.
    """
    name_patterns: tuple[re.Pattern[str], ...]
    exclusions: tuple[re.Pattern[str], ...]
    classification: str
    score: int
    reason: str


def _p(*exprs: str) -> tuple[re.Pattern[str], ...]:
    """Compile a list of regex strings into a frozen tuple of patterns."""
    return tuple(re.compile(e, re.IGNORECASE) for e in exprs)


# ── Rules — ordered from most-specific to least-specific ────────────────────
#
# Scoring guide (max from field-name signal = 40 pts):
#   Exact / very specific match  → 40
#   Close variation              → 35
#   Partial / generic token      → 25

FIELD_NAME_RULES: list[FieldNameRule] = [

    # ── DIRECT IDENTIFIERS ──────────────────────────────────────────────────

    FieldNameRule(
        name_patterns=_p(
            r"\bstudent[_\-\s]?id\b",
            r"\bstudent[_\-\s]?identifier\b",
            r"\bstudent[_\-\s]?number\b",
            r"\bstudent[_\-\s]?code\b",
            r"\broll[_\-\s]?number\b",
            r"\broll[_\-\s]?no\b",
            r"\benrolment[_\-\s]?(no|number|id)?\b",
            r"\buniversity[_\-\s]?id\b",
            r"\bmatriculation\b",
        ),
        exclusions=_p(),          # no exclusions needed
        classification="DIRECT_IDENTIFIER",
        score=40,
        reason="Field name indicates student identifier",
    ),

    FieldNameRule(
        name_patterns=_p(
            r"\bemail[_\-\s]?address\b",
            r"\bpersonal[_\-\s]?email\b",
            r"\bemail\b",
        ),
        # "email_template_id" → disqualified because 'template' appears
        exclusions=_p(r"\btemplate\b", r"\btype\b", r"\bformat\b", r"\bconfig\b"),
        classification="DIRECT_IDENTIFIER",
        score=40,
        reason="Field name indicates email address",
    ),

    FieldNameRule(
        name_patterns=_p(
            r"\bphone\b",
            r"\bmobile[_\-\s]?number\b",
            r"\bmobile\b",
            r"\bcell[_\-\s]?number\b",
            r"\btelephone\b",
            r"\bcontact[_\-\s]?number\b",
        ),
        exclusions=_p(r"\btype\b", r"\bformat\b", r"\bprefix\b"),
        classification="DIRECT_IDENTIFIER",
        score=40,
        reason="Field name indicates phone / mobile number",
    ),

    FieldNameRule(
        name_patterns=_p(
            r"\bstudent[_\-\s]?name\b",
            r"\bfull[_\-\s]?name\b",
            r"\bfirst[_\-\s]?name\b",
            r"\blast[_\-\s]?name\b",
            r"\bsurname\b",
            r"\bname\b",
        ),
        exclusions=_p(r"\bcourse\b", r"\bsubject\b", r"\binstitut\b", r"\bdepartment\b"),
        classification="DIRECT_IDENTIFIER",
        score=35,
        reason="Field name indicates person name",
    ),

    FieldNameRule(
        name_patterns=_p(
            r"\bguardian[_\-\s]?contact\b",
            r"\bparent[_\-\s]?contact\b",
            r"\bemergency[_\-\s]?contact\b",
            r"\bguardian[_\-\s]?phone\b",
            r"\bparent[_\-\s]?phone\b",
        ),
        exclusions=_p(),
        classification="DIRECT_IDENTIFIER",
        score=40,
        reason="Field name indicates guardian / emergency contact",
    ),

    FieldNameRule(
        name_patterns=_p(
            r"\baddress\b",
            r"\bresidence\b",
            r"\bhome[_\-\s]?address\b",
            r"\bpermanent[_\-\s]?address\b",
            r"\bcity\b",
            r"\bpincode\b",
            r"\bzip[_\-\s]?code\b",
            r"\bpostal[_\-\s]?code\b",
        ),
        exclusions=_p(r"\bip[_\-\s]?address\b", r"\burl\b", r"\bweb\b"),
        classification="DIRECT_IDENTIFIER",
        score=35,
        reason="Field name indicates physical address",
    ),

    # ── QUASI IDENTIFIERS ───────────────────────────────────────────────────

    FieldNameRule(
        name_patterns=_p(
            r"\bdob\b",
            r"\bdate[_\-\s]?of[_\-\s]?birth\b",
            r"\bbirth[_\-\s]?date\b",
            r"\bbirth[_\-\s]?year\b",
            r"\byear[_\-\s]?of[_\-\s]?birth\b",
            r"\bage\b",
        ),
        exclusions=_p(r"\bcourse\b", r"\bpublication\b", r"\bfound(ed|ing)\b"),
        classification="QUASI_IDENTIFIER",
        score=40,
        reason="Field name indicates date of birth / age",
    ),

    FieldNameRule(
        name_patterns=_p(
            r"\bgender\b",
            r"\bsex\b",
            r"\bcaste\b",
            r"\bethnicity\b",
            r"\bnationality\b",
            r"\breligion\b",
        ),
        exclusions=_p(r"\bstudent[_\-\s]?sex\b"),  # keep student_sex as quasi
        classification="QUASI_IDENTIFIER",
        score=35,
        reason="Field name indicates demographic quasi-identifier",
    ),

    # ── SENSITIVE ATTRIBUTES ────────────────────────────────────────────────

    FieldNameRule(
        name_patterns=_p(
            r"\bsalary\b",
            r"\bincome\b",
            r"\bbank[_\-\s]?account\b",
            r"\baccount[_\-\s]?number\b",
            r"\bifsc\b",
            r"\bpan\b",
            r"\baadhar\b",
            r"\bssn\b",
            r"\bpassport\b",
            r"\bdriving[_\-\s]?licen(c|s)e\b",
        ),
        exclusions=_p(r"\bcourse\b", r"\bsystem\b"),
        classification="SENSITIVE_ATTRIBUTE",
        score=40,
        reason="Field name indicates sensitive financial / legal attribute",
    ),

    # ── ACADEMIC DATA ───────────────────────────────────────────────────────

    FieldNameRule(
        name_patterns=_p(
            r"(?:^|[_\-\s])attendance(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])grade(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])gpa(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])cgpa(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])sgpa(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])marks(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])score(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])exam[_\-\s]?score(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])result(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])percentage(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])credits?(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])academic[_\-\s]?record(?:[_\-\s]|$)",
        ),
        exclusions=_p(r"\bcompletion[_\-\s]?percentage\b"),  # could be non-academic
        classification="ACADEMIC_DATA",
        score=35,
        reason="Field name indicates academic performance data",
    ),

    FieldNameRule(
        name_patterns=_p(
            r"\bcourse[_\-\s]?code\b",
            r"\bcourse[_\-\s]?name\b",
            r"\bcourse[_\-\s]?id\b",
            r"\bsubject[_\-\s]?code\b",
            r"\bsubject\b",
            r"\bdepartment\b",
            r"\bbranch\b",
            r"\bsemester\b",
            r"\bsection\b",
        ),
        exclusions=_p(),
        classification="NON_SENSITIVE",
        score=15,
        reason="Field name indicates course / department identifier",
    ),

    # ── PLACEMENT DATA ──────────────────────────────────────────────────────

    FieldNameRule(
        name_patterns=_p(
            r"\bplacement[_\-\s]?status\b",
            r"\bplaced\b",
            r"\bplacement[_\-\s]?package\b",
            r"\bpackage\b",
            r"\bctc\b",
            r"\boffer[_\-\s]?letter\b",
            r"\bcompany[_\-\s]?name\b",
            r"\bemployer\b",
        ),
        exclusions=_p(r"\bsoftware[_\-\s]?package\b"),
        classification="PLACEMENT_DATA",
        score=35,
        reason="Field name indicates placement / employment data",
    ),

    # ── CONTACT (ambiguous — low score, value pattern resolves) ─────────────

    FieldNameRule(
        name_patterns=_p(r"\bcontact\b"),
        exclusions=_p(r"\bnumber\b", r"\bphone\b", r"\bdetail\b"),
        classification="NON_SENSITIVE",  # tentative; value pattern may upgrade
        score=10,
        reason="Field name 'contact' is ambiguous — value pattern checked",
    ),
]
