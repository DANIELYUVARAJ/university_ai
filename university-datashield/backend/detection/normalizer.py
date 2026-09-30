"""
University DataShield – Detection Engine
Phase 9: normalizer.py

Field-name normalization and tokenization logic.
Normalizes camelCase, PascalCase, kebab-case, SCREAMING_SNAKE, dot.notation,
and whitespace variations into clean, deterministic snake_case tokens.
"""

from __future__ import annotations
import re


def normalize_field_name(name: str) -> str:
    """
    Normalizes field names across diverse naming conventions:
      - camelCase -> snake_case (e.g. 'studentId' -> 'student_id')
      - PascalCase -> snake_case (e.g. 'DateOfBirth' -> 'date_of_birth')
      - kebab-case -> snake_case (e.g. 'student-id' -> 'student_id')
      - SCREAMING_SNAKE -> lowercase (e.g. 'STUDENT_ID' -> 'student_id')
      - dot.notation -> snake_case (e.g. 'student.identifier' -> 'student_identifier')
      - whitespace -> snake_case (e.g. 'student id' -> 'student_id')
      - mixed separators -> snake_case (e.g. 'guardian-contact.number' -> 'guardian_contact_number')

    Returns lowercased snake_case string.
    """
    if not name:
        return ""

    s = name.strip()

    # 1. Acronym boundary: e.g. SSNNumber -> SSN_Number
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)

    # 2. camelCase boundary: e.g. studentId -> student_Id
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)

    # 3. Replace non-alphanumeric separators (hyphen, dot, space, slash, colon) with underscore
    s = re.sub(r"[\-\.\s/\\:]+", "_", s)

    # 4. Collapse consecutive underscores
    s = re.sub(r"_+", "_", s)

    # 5. Strip leading/trailing underscores and lowercase
    return s.strip("_").lower()


def get_field_tokens(name: str) -> list[str]:
    """Tokenize a field name into lowercased token components."""
    norm = normalize_field_name(name)
    return [t for t in norm.split("_") if t]


# Common synthetic alias mappings for university fields
ALIAS_CANONICAL_MAP: dict[str, str] = {
    # Email aliases
    "email_address": "email",
    "personal_email": "email",
    "student_email": "email",
    "inst_email": "email",
    "contact_email": "email",
    "mail": "email",
    "mail_id": "email",
    # Phone aliases
    "phone_number": "phone",
    "mobile": "phone",
    "mobile_number": "phone",
    "contact_number": "phone",
    "cell_number": "phone",
    "cell": "phone",
    "telephone": "phone",
    # Student ID aliases
    "student_identifier": "student_id",
    "student_no": "student_id",
    "student_number": "student_id",
    "registration_number": "student_id",
    "reg_no": "student_id",
    "roll_number": "student_id",
    "roll_no": "student_id",
    "enrolment_no": "student_id",
    "enrolment_number": "student_id",
    "candidate_id": "student_id",
    "candidate_reference": "student_id",
    "student_reference": "student_id",
    # DOB aliases
    "dob": "date_of_birth",
    "birth_date": "date_of_birth",
    "birth_year": "date_of_birth",
    "year_of_birth": "date_of_birth",
}


def resolve_alias(normalized_name: str) -> str:
    """Return the canonical term for a known alias, or the normalized name itself."""
    return ALIAS_CANONICAL_MAP.get(normalized_name, normalized_name)
