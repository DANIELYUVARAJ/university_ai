"""
University DataShield – Phase 2 Tests
test_detection_engine.py

Tests for the Sensitive Field Discovery Engine.

Run:
    pytest tests/test_detection_engine.py -v

All test inputs use SYNTHETIC data only. No real PII.
"""

from __future__ import annotations
import sys
import os

# Add backend to path so we can import detection directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from detection.schemas import FieldInput
from detection.detector import scan_field, scan_fields


# ── Helper ────────────────────────────────────────────────────────────────────

def field(name: str, data_type: str = "string", sample: str | None = None) -> FieldInput:
    return FieldInput(name=name, data_type=data_type, sample_pattern=sample)


# ── Test 1: Email detection ────────────────────────────────────────────────────

class TestEmailDetection:
    def test_email_field_name_direct(self):
        result = scan_field(field("email", sample="student001@example.edu"))
        assert result.classification == "DIRECT_IDENTIFIER"
        assert result.confidence >= 70
        assert result.signals.field_name_match is True
        assert result.signals.pattern_match is True

    def test_email_address_variation(self):
        result = scan_field(field("email_address", sample="demo@university.ac.in"))
        assert result.classification == "DIRECT_IDENTIFIER"
        assert result.confidence >= 50

    def test_personal_email(self):
        result = scan_field(field("personal_email", sample="test@example.com"))
        assert result.classification == "DIRECT_IDENTIFIER"
        assert result.signals.field_name_match is True


# ── Test 2: Phone detection ────────────────────────────────────────────────────

class TestPhoneDetection:
    def test_phone_field(self):
        result = scan_field(field("phone", sample="+91-9000000001"))
        assert result.classification == "DIRECT_IDENTIFIER"
        assert result.confidence >= 70
        assert result.signals.field_name_match is True

    def test_mobile_number_variation(self):
        result = scan_field(field("mobile_number", sample="+91-9000000001"))
        assert result.classification == "DIRECT_IDENTIFIER"

    def test_contact_number_variation(self):
        result = scan_field(field("contact_number", sample="9000000001"))
        assert result.classification == "DIRECT_IDENTIFIER"


# ── Test 3: Student ID detection ──────────────────────────────────────────────

class TestStudentIdDetection:
    def test_student_id_exact(self):
        result = scan_field(field("student_id", sample="STU_DEMO_001"))
        assert result.classification == "DIRECT_IDENTIFIER"
        assert result.confidence >= 70
        assert result.signals.field_name_match is True
        assert result.signals.pattern_match is True

    def test_roll_number(self):
        result = scan_field(field("roll_number", sample="STU_DEMO_042"))
        assert result.classification == "DIRECT_IDENTIFIER"

    def test_enrolment_number(self):
        result = scan_field(field("enrolment_number", sample="STU_DEMO_099"))
        assert result.classification == "DIRECT_IDENTIFIER"


# ── Test 4: Date of birth detection ───────────────────────────────────────────

class TestDateOfBirthDetection:
    def test_date_of_birth_exact(self):
        result = scan_field(field("date_of_birth", data_type="date", sample="1999-04-17"))
        assert result.classification in ("QUASI_IDENTIFIER", "DIRECT_IDENTIFIER")
        assert result.confidence >= 50
        assert result.signals.field_name_match is True

    def test_dob_abbreviation(self):
        result = scan_field(field("dob", data_type="date", sample="1999-04-17"))
        assert result.classification in ("QUASI_IDENTIFIER", "DIRECT_IDENTIFIER")
        assert result.signals.field_name_match is True

    def test_birth_year(self):
        result = scan_field(field("birth_year"))
        assert result.classification in ("QUASI_IDENTIFIER", "DIRECT_IDENTIFIER")
        assert result.signals.field_name_match is True


# ── Test 5: Salary / placement package detection ──────────────────────────────

class TestSalaryPlacementDetection:
    def test_placement_package(self):
        result = scan_field(field("placement_package", data_type="number", sample="850000"))
        assert result.classification in ("PLACEMENT_DATA", "SENSITIVE_ATTRIBUTE")
        assert result.confidence >= 30

    def test_salary_field(self):
        result = scan_field(field("salary", data_type="number"))
        assert result.classification == "SENSITIVE_ATTRIBUTE"
        assert result.signals.field_name_match is True


# ── Test 6: Academic field classification ─────────────────────────────────────

class TestAcademicFieldClassification:
    def test_attendance_percentage(self):
        result = scan_field(field("attendance_percentage", data_type="number", sample="92"))
        assert result.classification == "ACADEMIC_DATA"
        assert result.signals.field_name_match is True

    def test_exam_score(self):
        result = scan_field(field("exam_score", data_type="number", sample="78"))
        assert result.classification == "ACADEMIC_DATA"

    def test_gpa(self):
        result = scan_field(field("gpa", data_type="number"))
        assert result.classification == "ACADEMIC_DATA"


# ── Test 7: Non-sensitive field classification ────────────────────────────────

class TestNonSensitiveFields:
    def test_course_code(self):
        result = scan_field(field("course_code", data_type="string", sample="CS401"))
        assert result.classification == "NON_SENSITIVE"
        # Confidence should be low — no real sensitive signals
        assert result.confidence < 40

    def test_semester(self):
        result = scan_field(field("semester", data_type="number"))
        assert result.classification == "NON_SENSITIVE"

    def test_department(self):
        result = scan_field(field("department", data_type="string"))
        assert result.classification == "NON_SENSITIVE"


# ── Test 8: Ambiguous 'contact' field resolved by value pattern ───────────────

class TestAmbiguousContactField:
    def test_contact_with_email_value(self):
        """contact + email value → DIRECT_IDENTIFIER (value pattern resolves)"""
        result = scan_field(field("contact", data_type="string", sample="student001@example.edu"))
        assert result.classification == "DIRECT_IDENTIFIER"
        assert result.signals.pattern_match is True

    def test_contact_with_phone_value(self):
        """contact + phone value → DIRECT_IDENTIFIER"""
        result = scan_field(field("contact", data_type="string", sample="+91-9000000001"))
        assert result.classification == "DIRECT_IDENTIFIER"
        assert result.signals.pattern_match is True

    def test_contact_with_neutral_value(self):
        """contact + non-PII value → NON_SENSITIVE or LOW confidence"""
        result = scan_field(field("contact", data_type="string", sample="See admin office"))
        assert result.confidence < 40


# ── Test 9: email_template_id false-positive prevention ───────────────────────

class TestEmailTemplateIdFalsePositive:
    def test_email_template_id_not_personal_email(self):
        """email_template_id must NOT be classified as a personal email identifier."""
        result = scan_field(field("email_template_id", data_type="string", sample="TPL_001"))
        # Must NOT be DIRECT_IDENTIFIER just because field name contains 'email'
        assert result.classification != "DIRECT_IDENTIFIER"
        # Confidence must be low
        assert result.confidence < 40

    def test_email_type_not_personal_identifier(self):
        result = scan_field(field("email_format", data_type="string", sample="HTML"))
        assert result.classification != "DIRECT_IDENTIFIER"


# ── Test 10: student_identifier variation ─────────────────────────────────────

class TestStudentIdentifierVariation:
    def test_student_identifier(self):
        """student_identifier → DIRECT_IDENTIFIER"""
        result = scan_field(
            field("student_identifier", data_type="string", sample="STU_DEMO_001")
        )
        assert result.classification == "DIRECT_IDENTIFIER"
        assert result.confidence >= 70
        assert result.signals.field_name_match is True

    def test_guardian_contact(self):
        """guardian_contact → DIRECT_IDENTIFIER"""
        result = scan_field(
            field("guardian_contact", data_type="string", sample="+91-9000000002")
        )
        assert result.classification == "DIRECT_IDENTIFIER"
        assert result.signals.field_name_match is True


# ── Test 11: Full scan of synthetic schema ────────────────────────────────────

class TestFullSyntheticScan:
    def test_all_fields_scanned(self):
        from synthetic_schema import SYNTHETIC_SCHEMA
        inputs = [FieldInput(**f) for f in SYNTHETIC_SCHEMA["fields"]]
        results = scan_fields(inputs)
        assert len(results) == len(inputs)

    def test_sensitive_fields_detected_in_synthetic(self):
        from synthetic_schema import SYNTHETIC_SCHEMA
        inputs = [FieldInput(**f) for f in SYNTHETIC_SCHEMA["fields"]]
        results = scan_fields(inputs)
        sensitive = [r for r in results if r.classification != "NON_SENSITIVE"]
        # email, phone, student_id, student_name, date_of_birth, contact,
        # student_identifier, guardian_contact, placement_package, placement_status,
        # attendance, exam_score are all sensitive
        assert len(sensitive) >= 8, f"Expected ≥8 sensitive fields, got {len(sensitive)}"

    def test_email_template_id_not_in_sensitive(self):
        from synthetic_schema import SYNTHETIC_SCHEMA
        inputs = [FieldInput(**f) for f in SYNTHETIC_SCHEMA["fields"]]
        results = scan_fields(inputs)
        eti = next(r for r in results if r.field == "email_template_id")
        assert eti.classification != "DIRECT_IDENTIFIER"

    def test_reasons_populated_for_sensitive_fields(self):
        from synthetic_schema import SYNTHETIC_SCHEMA
        inputs = [FieldInput(**f) for f in SYNTHETIC_SCHEMA["fields"]]
        results = scan_fields(inputs)
        for r in results:
            assert len(r.reasons) >= 1, f"No reasons for field {r.field}"

    def test_determinism(self):
        """Same input must produce identical output on repeated calls."""
        from synthetic_schema import SYNTHETIC_SCHEMA
        inputs = [FieldInput(**f) for f in SYNTHETIC_SCHEMA["fields"]]
        r1 = scan_fields(inputs)
        r2 = scan_fields(inputs)
        for a, b in zip(r1, r2):
            assert a.classification == b.classification
            assert a.confidence == b.confidence


# ── Test 12: Confidence score bounds ─────────────────────────────────────────

class TestConfidenceScoreBounds:
    def test_score_never_exceeds_100(self):
        from synthetic_schema import SYNTHETIC_SCHEMA
        inputs = [FieldInput(**f) for f in SYNTHETIC_SCHEMA["fields"]]
        results = scan_fields(inputs)
        for r in results:
            assert 0 <= r.confidence <= 100, f"{r.field} confidence={r.confidence}"

    def test_email_score_is_100(self):
        """email field with email sample value should achieve max confidence."""
        result = scan_field(field("email", sample="test@university.edu"))
        assert result.confidence == 100

    def test_non_sensitive_score_low(self):
        result = scan_field(field("course_code", sample="CS401"))
        assert result.confidence < 40


# ── Test 13: Data-type alone does NOT classify as sensitive ───────────────────

class TestDataTypeAloneNotSensitive:
    def test_date_type_alone_is_not_sensitive(self):
        """A 'date' field with no sensitive name or value → not directly sensitive."""
        result = scan_field(field("created_at", data_type="date", sample="2023-01-15"))
        # type_score should only contribute if another signal fired
        assert result.classification == "NON_SENSITIVE"

    def test_number_type_alone_is_not_sensitive(self):
        result = scan_field(field("record_count", data_type="number", sample="42"))
        assert result.classification == "NON_SENSITIVE"
