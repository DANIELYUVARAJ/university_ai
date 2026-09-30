"""
University DataShield – Phase 9 Test Suite
test_phase9_detection.py

Comprehensive tests for Advanced Detection & Dataset Intelligence:
1. Field-name normalization (camelCase, kebab-case, dot-notation, screaming snake)
2. Alias recognition & canonical mapping
3. Context-aware cross-field detection
4. Value-pattern intelligence (enhanced patterns)
5. Invalid / malformed value detection
6. Ambiguity handling & confidence decision model (HIGH/MEDIUM/LOW/REVIEW)
7. Actionable masking recommendations
8. Dataset-level risk scoring & publication readiness
9. False-positive trap preservation
10. Backward compatibility with Phase 1-8 APIs
11. Full /scan API response verification
12. Privacy validation (zero raw PII in generated metadata/logs)
"""

from __future__ import annotations
import sys
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from detection.schemas import FieldInput, ScanRequest
from detection.detector import scan_field, scan_fields, scan_fields_with_risk
from detection.normalizer import normalize_field_name, resolve_alias, get_field_tokens
from detection.patterns import detect_invalid_value, match_value_patterns
from detection.ambiguity import evaluate_ambiguity
from detection.recommendations import generate_recommendation
from detection.risk import calculate_dataset_risk
from detection.context import DatasetContext


# ── 1. Field-Name Normalization Tests ─────────────────────────────────────────

class TestFieldNameNormalization:
    def test_camel_case_normalization(self):
        assert normalize_field_name("studentId") == "student_id"
        assert normalize_field_name("dateOfBirth") == "date_of_birth"
        assert normalize_field_name("personalEmail") == "personal_email"
        assert normalize_field_name("annualSalary") == "annual_salary"
        assert normalize_field_name("absenceCount") == "absence_count"

    def test_kebab_case_normalization(self):
        assert normalize_field_name("student-id") == "student_id"
        assert normalize_field_name("birth-date") == "birth_date"
        assert normalize_field_name("guardian-contact") == "guardian_contact"
        assert normalize_field_name("email-address") == "email_address"

    def test_screaming_snake_normalization(self):
        assert normalize_field_name("STUDENT_ID") == "student_id"
        assert normalize_field_name("DATE_OF_BIRTH") == "date_of_birth"
        assert normalize_field_name("PHONE_NUMBER") == "phone_number"

    def test_dot_notation_normalization(self):
        assert normalize_field_name("student.identifier") == "student_identifier"
        assert normalize_field_name("guardian.contact.number") == "guardian_contact_number"

    def test_whitespace_and_mixed_separators(self):
        assert normalize_field_name("  student id  ") == "student_id"
        assert normalize_field_name("student---id") == "student_id"
        assert normalize_field_name("candidate_reference.id") == "candidate_reference_id"

    def test_acronym_handling(self):
        assert normalize_field_name("SSNNumber") == "ssn_number"
        assert normalize_field_name("studentUID") == "student_uid"


# ── 2. Alias Recognition Tests ────────────────────────────────────────────────

class TestAliasRecognition:
    def test_email_aliases(self):
        assert resolve_alias("email_address") == "email"
        assert resolve_alias("personal_email") == "email"
        assert resolve_alias("student_email") == "email"
        assert resolve_alias("mail") == "email"

    def test_phone_aliases(self):
        assert resolve_alias("phone_number") == "phone"
        assert resolve_alias("mobile_number") == "phone"
        assert resolve_alias("contact_number") == "phone"
        assert resolve_alias("telephone") == "phone"

    def test_student_id_aliases(self):
        assert resolve_alias("student_identifier") == "student_id"
        assert resolve_alias("registration_number") == "student_id"
        assert resolve_alias("roll_number") == "student_id"
        assert resolve_alias("candidate_id") == "student_id"

    def test_dob_aliases(self):
        assert resolve_alias("dob") == "date_of_birth"
        assert resolve_alias("birth_date") == "date_of_birth"
        assert resolve_alias("birth_year") == "date_of_birth"


# ── 3. Normalized Field Detection Integration Tests ───────────────────────────

class TestNormalizedFieldDetection:
    def test_camel_case_field_detected_as_sensitive(self):
        res = scan_field(FieldInput(name="studentId", sample_pattern="STU_9912"))
        assert res.classification == "DIRECT_IDENTIFIER"
        assert res.normalized_name == "student_id"
        assert res.confidence >= 70

    def test_kebab_case_field_detected_as_sensitive(self):
        res = scan_field(FieldInput(name="birth-date", sample_pattern="2002-05-19", data_type="date"))
        assert res.classification == "QUASI_IDENTIFIER"
        assert res.normalized_name == "birth_date"
        assert res.confidence >= 50

    def test_dot_notation_field_detected(self):
        res = scan_field(FieldInput(name="student.identifier", sample_pattern="UID-101"))
        assert res.classification == "DIRECT_IDENTIFIER"
        assert res.normalized_name == "student_identifier"


# ── 4. Cross-Field Contextual Detection Tests ─────────────────────────────────

class TestContextualDetection:
    def test_ambiguous_contact_boosted_by_context(self):
        fields = [
            FieldInput(name="contact", sample_pattern=""),
            FieldInput(name="email", sample_pattern="student@example.edu"),
            FieldInput(name="phone", sample_pattern="+91-9000000001"),
        ]
        results = scan_fields(fields)
        contact_res = next(r for r in results if r.field == "contact")
        # In context of email and phone, contact receives context boost and direct ID classification
        assert contact_res.classification == "DIRECT_IDENTIFIER"
        assert contact_res.signals.context_match is True
        assert any("contact identifiers" in s for s in contact_res.contextual_signals)

    def test_placement_context_reinforces_salary_and_offer(self):
        fields = [
            FieldInput(name="salary", sample_pattern="85000", data_type="number"),
            FieldInput(name="placement_package", sample_pattern="850000", data_type="number"),
            FieldInput(name="company_name", sample_pattern="Acme Corp"),
            FieldInput(name="offer_status", sample_pattern="Accepted"),
        ]
        results = scan_fields(fields)
        salary_res = next(r for r in results if r.field == "salary")
        offer_res = next(r for r in results if r.field == "offer_status")
        assert salary_res.signals.context_match is True
        assert offer_res.classification == "PLACEMENT_DATA"

    def test_academic_context_reinforces_absence_and_marks(self):
        fields = [
            FieldInput(name="course_code", sample_pattern="CS101"),
            FieldInput(name="semester", sample_pattern="4", data_type="number"),
            FieldInput(name="absence_count", sample_pattern="2", data_type="number"),
            FieldInput(name="internal_mark", sample_pattern="28", data_type="number"),
        ]
        results = scan_fields(fields)
        abs_res = next(r for r in results if r.field == "absence_count")
        mark_res = next(r for r in results if r.field == "internal_mark")
        assert abs_res.classification == "ACADEMIC_DATA"
        assert mark_res.classification == "ACADEMIC_DATA"
        assert abs_res.signals.context_match is True


# ── 5. Value Pattern Intelligence & Invalid Value Tests ────────────────────────

class TestValuePatternIntelligence:
    def test_registration_number_pattern(self):
        matches = match_value_patterns("REG-2024-9988")
        labels = [m.label for m in matches]
        assert "registration_number" in labels

    def test_salary_pattern_currency(self):
        matches = match_value_patterns("$95,000")
        labels = [m.label for m in matches]
        assert "salary" in labels

    def test_salary_pattern_lpa(self):
        matches = match_value_patterns("14.5 LPA")
        labels = [m.label for m in matches]
        assert "salary" in labels

    def test_detect_invalid_phone_value(self):
        is_invalid, reason = detect_invalid_value("phone", "not-a-phone")
        assert is_invalid is True
        assert reason is not None

    def test_detect_invalid_placeholder(self):
        is_invalid, reason = detect_invalid_value("email", "n/a")
        assert is_invalid is True

    def test_valid_phone_not_flagged_invalid(self):
        is_invalid, _ = detect_invalid_value("phone", "+91-9000000001")
        assert is_invalid is False


# ── 6. Ambiguity Handling & Confidence Decision Model Tests ───────────────────

class TestAmbiguityDecisionModel:
    def test_ambiguous_contact_without_pattern_marked_review(self):
        status, level, reasons = evaluate_ambiguity(
            field_name="contact",
            classification="NON_SENSITIVE",
            confidence=10,
            has_pattern_match=False,
            value_is_invalid=False,
            has_context_support=False,
        )
        assert status == "REVIEW"
        assert level == "REVIEW"
        assert any("generic/ambiguous" in r for r in reasons)

    def test_clear_high_confidence(self):
        status, level, _ = evaluate_ambiguity(
            field_name="student_id",
            classification="DIRECT_IDENTIFIER",
            confidence=85,
            has_pattern_match=True,
            value_is_invalid=False,
        )
        assert status == "CLEAR"
        assert level == "HIGH"

    def test_invalid_value_triggers_review(self):
        status, level, reasons = evaluate_ambiguity(
            field_name="phone",
            classification="DIRECT_IDENTIFIER",
            confidence=40,
            has_pattern_match=False,
            value_is_invalid=True,
        )
        assert status == "REVIEW"
        assert level == "REVIEW"
        assert any("does not match expected format" in r for r in reasons)


# ── 7. Recommendations Tests ──────────────────────────────────────────────────

class TestRecommendations:
    def test_student_id_recommends_hash(self):
        rec = generate_recommendation("student_id", "DIRECT_IDENTIFIER", 90)
        assert rec.startswith("HASH")

    def test_email_recommends_mask(self):
        rec = generate_recommendation("email", "DIRECT_IDENTIFIER", 90)
        assert rec.startswith("MASK")

    def test_dob_recommends_generalize(self):
        rec = generate_recommendation("date_of_birth", "QUASI_IDENTIFIER", 80)
        assert rec.startswith("GENERALIZE")

    def test_salary_recommends_generalize(self):
        rec = generate_recommendation("salary", "SENSITIVE_ATTRIBUTE", 75)
        assert rec.startswith("GENERALIZE")

    def test_ambiguous_recommends_review(self):
        rec = generate_recommendation("contact", "DIRECT_IDENTIFIER", 40, is_ambiguous=True)
        assert rec.startswith("REVIEW")

    def test_non_sensitive_recommends_none(self):
        rec = generate_recommendation("course_code", "NON_SENSITIVE", 0)
        assert rec.startswith("NONE")


# ── 8. Dataset Risk Calculation Tests ─────────────────────────────────────────

class TestDatasetRiskCalculation:
    def test_high_risk_dataset_with_direct_identifiers(self):
        fields = [
            FieldInput(name="student_id", sample_pattern="STU001"),
            FieldInput(name="student_name", sample_pattern="Jane Doe"),
            FieldInput(name="email", sample_pattern="jane@example.edu"),
            FieldInput(name="date_of_birth", sample_pattern="2000-01-01", data_type="date"),
        ]
        results, risk = scan_fields_with_risk(fields)
        assert risk.risk_score >= 50
        assert risk.risk_level in ("HIGH", "CRITICAL")
        assert risk.publication_readiness == "NEEDS_PROTECTION"
        assert risk.direct_identifiers_count >= 3

    def test_clean_analytical_dataset_low_risk(self):
        fields = [
            FieldInput(name="course_code", sample_pattern="CS101"),
            FieldInput(name="department", sample_pattern="Engineering"),
            FieldInput(name="semester", sample_pattern="4", data_type="number"),
            FieldInput(name="classroom_capacity", sample_pattern="50", data_type="number"),
        ]
        results, risk = scan_fields_with_risk(fields)
        assert risk.risk_score < 25
        assert risk.risk_level == "LOW"
        assert risk.publication_readiness == "READY"
        assert risk.direct_identifiers_count == 0


# ── 9. False-Positive Trap Regression Tests ───────────────────────────────────

class TestFalsePositiveTrapsRegression:
    def test_email_template_id_remains_non_sensitive(self):
        res = scan_field(FieldInput(name="email_template_id", sample_pattern="TPL_99"))
        assert res.classification == "NON_SENSITIVE"

    def test_phone_model_remains_non_sensitive(self):
        res = scan_field(FieldInput(name="phone_model", sample_pattern="Galaxy S24"))
        assert res.classification == "NON_SENSITIVE"

    def test_student_count_remains_non_sensitive(self):
        res = scan_field(FieldInput(name="student_count", sample_pattern="150", data_type="number"))
        assert res.classification == "NON_SENSITIVE"

    def test_course_code_remains_non_sensitive(self):
        res = scan_field(FieldInput(name="course_code", sample_pattern="MATH201"))
        assert res.classification == "NON_SENSITIVE"

    def test_salary_range_code_remains_non_sensitive(self):
        res = scan_field(FieldInput(name="salary_range_code", sample_pattern="BAND_4"))
        assert res.classification == "NON_SENSITIVE"


# ── 10. API Integration & Backward Compatibility Tests ────────────────────────

class TestScanAPIPhase9:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_scan_api_includes_phase9_extensions(self, client):
        payload = {
            "dataset_name": "phase9_api_test",
            "fields": [
                {"name": "studentId", "data_type": "string", "sample_pattern": "STU12345"},
                {"name": "personalEmail", "data_type": "string", "sample_pattern": "alex@example.edu"},
                {"name": "courseCode", "data_type": "string", "sample_pattern": "CS101"},
            ],
        }
        resp = client.post("/scan", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        # Backward compatible fields
        assert data["dataset_name"] == "phase9_api_test"
        assert data["fields_scanned"] == 3
        assert data["sensitive_count"] == 2

        # Phase 9 extensions present
        assert "dataset_risk" in data
        assert data["dataset_risk"]["risk_level"] in ("HIGH", "MEDIUM", "LOW", "CRITICAL")
        assert "publication_readiness" in data

        # Per-field Phase 9 extensions present
        res0 = data["results"][0]
        assert res0["normalized_name"] == "student_id"
        assert res0["confidence_level"] in ("HIGH", "MEDIUM", "LOW", "REVIEW")
        assert "recommendation" in res0
        assert res0["recommendation"].startswith("HASH") or res0["recommendation"].startswith("MASK")


# ── 11. Privacy & Synthetic Data Validation ───────────────────────────────────

class TestPhase9PrivacyValidation:
    def test_synthetic_data_integrity_in_validation_dataset(self):
        import json
        p9_dataset_path = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "phase9_validation_dataset.json"
        assert p9_dataset_path.exists()

        with open(p9_dataset_path, "r", encoding="utf-8") as f:
            items = json.load(f)

        assert len(items) >= 60

        for item in items:
            pattern = item.get("sample_pattern", "")
            # Ensure no real phone numbers or emails
            if "@" in pattern:
                assert "example.edu" in pattern or "example.com" in pattern
            # Ensure names are generic synthetic placeholders
            assert "real" not in pattern.lower()
