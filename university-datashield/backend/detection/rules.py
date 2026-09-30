"""
University DataShield – Detection Engine
Phase 2 & Phase 9: rules.py

Field-name matching rules.

Design:
 - Rules are pure data — no logic here.
 - Each RuleEntry maps a set of name tokens/patterns to a classification
   and a base score contribution.
 - The matcher in detector.py applies these rules.
 - Edge-case handling baked into the rules:
   * "email_template_id" must NOT match as a personal email field.
   * "phone_model" must NOT match as a phone field.
   * "salary_range_code" must NOT match as a salary field.
   * "address_type", "contact_type" must NOT match as direct identifiers.
   * "student_count", "course_code" must NOT match as sensitive.
   Achieved via an EXCLUSION token list per rule.
"""

from __future__ import annotations
import re
from dataclasses import dataclass


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
            r"\bstudent[_\-\s]?reference\b",
            r"\broll[_\-\s]?number\b",
            r"\broll[_\-\s]?no\b",
            r"\benrolment[_\-\s]?(no|number|id)?\b",
            r"\buniversity[_\-\s]?id\b",
            r"\bmatriculation\b",
            r"\bcandidate[_\-\s]?(id|identifier|number|code|ref|reference)\b",
            r"\bapplicant[_\-\s]?(id|number|code|ref)?\b",
        ),
        exclusions=_p(r"\bcount\b", r"\btemplate\b"),
        classification="DIRECT_IDENTIFIER",
        score=40,
        reason="Field name indicates student or candidate identifier",
    ),

    FieldNameRule(
        name_patterns=_p(
            r"\bemail[_\-\s]?address\b",
            r"\bpersonal[_\-\s]?email\b",
            r"\bstudent[_\-\s]?email\b",
            r"\bcontact[_\-\s]?email\b",
            r"\bemail\b",
            r"\bmail[_\-\s]?id\b",
        ),
        # "email_template_id" → disqualified because 'template' appears
        exclusions=_p(r"\btemplate\b", r"\btype\b", r"\bformat\b", r"\bconfig\b", r"\bcount\b"),
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
            r"\bpersonal[_\-\s]?contact\b",
        ),
        # "phone_model" → disqualified because 'model' appears
        exclusions=_p(r"\btype\b", r"\bformat\b", r"\bprefix\b", r"\bmodel\b", r"\bcount\b"),
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
        exclusions=_p(
            r"\bcourse\b",
            r"\bsubject\b",
            r"\binstitut\b",
            r"\bdepartment\b",
            r"\bcompany\b",
            r"\btemplate\b",
        ),
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
        exclusions=_p(r"\bip[_\-\s]?address\b", r"\burl\b", r"\bweb\b", r"\btype\b"),
        classification="DIRECT_IDENTIFIER",
        score=35,
        reason="Field name indicates physical address / postal identifier",
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
            r"\bgraduation[_\-\s]?year\b",
            r"\bgrad[_\-\s]?year\b",
            r"\bpassing[_\-\s]?year\b",
            r"\bcompletion[_\-\s]?year\b",
        ),
        exclusions=_p(r"\bcourse\b", r"\bpublication\b", r"\bfound(ed|ing)\b", r"\bcount\b"),
        classification="QUASI_IDENTIFIER",
        score=40,
        reason="Field name indicates date of birth / age / graduation cohort",
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
        exclusions=_p(r"\bcourse\b", r"\bsystem\b", r"\brange[_\-\s]?code\b", r"\bcode\b"),
        classification="SENSITIVE_ATTRIBUTE",
        score=40,
        reason="Field name indicates sensitive financial / legal attribute",
    ),

    # ── ACADEMIC DATA ───────────────────────────────────────────────────────

    FieldNameRule(
        name_patterns=_p(
            r"(?:^|[_\-\s])attendance(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])attendance[_\-\s]?percentage(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])absence[_\-\s]?count(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])absent[_\-\s]?days(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])grade(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])gpa(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])cgpa(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])sgpa(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])marks(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])internal[_\-\s]?mark(?:s)?(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])internal[_\-\s]?score(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])score(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])exam[_\-\s]?score(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])result(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])percentage(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])credits?(?:[_\-\s]|$)",
            r"(?:^|[_\-\s])academic[_\-\s]?record(?:[_\-\s]|$)",
        ),
        exclusions=_p(r"\bcompletion[_\-\s]?percentage\b"),
        classification="ACADEMIC_DATA",
        score=35,
        reason="Field name indicates academic performance or attendance data",
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
            r"\bcourse[_\-\s]?count\b",
            r"\bsemester[_\-\s]?count\b",
            r"\bclassroom[_\-\s]?capacity\b",
            r"\bacademic[_\-\s]?year\b",
            r"\bcourse[_\-\s]?duration\b",
            r"\bdepartment[_\-\s]?code\b",
            r"\bstudent[_\-\s]?count\b",
            r"\bcompany[_\-\s]?code\b",
            r"\baddress[_\-\s]?type\b",
            r"\bcontact[_\-\s]?type\b",
            r"\bphone[_\-\s]?model\b",
            r"\bsalary[_\-\s]?range[_\-\s]?code\b",
            r"\bemail[_\-\s]?template[_\-\s]?(id|name)\b",
        ),
        exclusions=_p(),
        classification="NON_SENSITIVE",
        score=20,
        reason="Field name indicates institutional / curriculum structure or aggregate metric",
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
            r"\boffer[_\-\s]?status\b",
            r"\bcompany[_\-\s]?name\b",
            r"\bemployer\b",
        ),
        exclusions=_p(r"\bsoftware[_\-\s]?package\b", r"\bcompany[_\-\s]?code\b"),
        classification="PLACEMENT_DATA",
        score=35,
        reason="Field name indicates placement / employment data",
    ),

    # ── CONTACT (ambiguous — low score, value pattern or context resolves) ──

    FieldNameRule(
        name_patterns=_p(r"\bcontact\b"),
        exclusions=_p(r"\bnumber\b", r"\bphone\b", r"\bdetail\b", r"\btype\b", r"\bemail\b"),
        classification="NON_SENSITIVE",  # tentative; pattern or context upgrades
        score=10,
        reason="Field name 'contact' is ambiguous — value pattern or context checked",
    ),
]
