"""
University DataShield – Test Suite
Phase 4: Masking Policy Engine Tests (20+ tests)
"""

import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

import sys
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from policies.schemas import (
    ProtectionAction,
    ValidationStatus,
    FieldValidationInput,
    PolicyValidationRequest,
    MaskingPreviewRequest,
)
from policies.masking import (
    apply_masking,
    mask_email,
    mask_phone,
    mask_identifier,
    hash_sha256,
    generalize_date,
    generalize_salary,
)
from policies.policy_engine import PolicyEngine


# ---------------------------------------------------------------------------
# 1. Masking Transformation Tests (Tests 1-7)
# ---------------------------------------------------------------------------

class TestMaskingTransformations:
    def test_01_email_masking(self):
        email = "student001@example.edu"
        masked = mask_email(email)
        assert "@example.edu" in masked
        assert masked.startswith("s")
        assert "*" in masked
        assert masked == "s******@example.edu"

    def test_02_phone_masking(self):
        phone = "+91-9000000001"
        masked = mask_phone(phone)
        assert masked.endswith("01")
        assert "9000000" not in masked
        assert masked.startswith("********")

    def test_03_student_id_masking(self):
        stu_id = "STU_DEMO_001"
        masked = mask_identifier(stu_id)
        assert masked == "STU_****_001"

    def test_04_dob_generalization(self):
        dob = "1999-04-17"
        gen = generalize_date(dob)
        assert gen == "1999"

    def test_05_salary_generalization(self):
        salary = "850000"
        gen = generalize_salary(salary)
        assert gen == "800000-900000"

    def test_06_sha256_hashing(self):
        val = "STU_DEMO_001"
        expected = hashlib.sha256(val.encode("utf-8")).hexdigest()
        actual = hash_sha256(val)
        assert actual == expected
        assert len(actual) == 64

    def test_07_suppression(self):
        val = "sensitive-value"
        res = apply_masking(val, ProtectionAction.SUPPRESS)
        assert res == "[SUPPRESSED]"


# ---------------------------------------------------------------------------
# 2. Policy Validation Tests (Tests 8-14)
# ---------------------------------------------------------------------------

class TestPolicyValidation:
    @pytest.fixture
    def engine(self):
        return PolicyEngine()

    def test_08_correct_mask_passes(self, engine):
        item = FieldValidationInput(
            name="email",
            classification="DIRECT_IDENTIFIER",
            actual_action=ProtectionAction.MASK
        )
        res = engine.validate_field(item)
        assert res.status == ValidationStatus.PASS
        assert res.required_action == ProtectionAction.MASK
        assert "satisfied" in res.reason

    def test_09_missing_mask_fails(self, engine):
        item = FieldValidationInput(
            name="phone",
            classification="DIRECT_IDENTIFIER",
            actual_action=ProtectionAction.NONE
        )
        res = engine.validate_field(item)
        assert res.status == ValidationStatus.FAIL
        assert "unprotected" in res.reason

    def test_10_correct_generalize_passes(self, engine):
        item = FieldValidationInput(
            name="date_of_birth",
            classification="QUASI_IDENTIFIER",
            actual_action=ProtectionAction.GENERALIZE
        )
        res = engine.validate_field(item)
        assert res.status == ValidationStatus.PASS
        assert res.required_action == ProtectionAction.GENERALIZE

    def test_11_wrong_protection_triggers_review(self, engine):
        # Salary requires GENERALIZE, but MASK is applied -> REVIEW
        item = FieldValidationInput(
            name="salary",
            classification="SENSITIVE_ATTRIBUTE",
            actual_action=ProtectionAction.MASK
        )
        res = engine.validate_field(item)
        assert res.status == ValidationStatus.REVIEW
        assert "mismatch" in res.reason.lower() or "review" in res.reason.lower()

    def test_12_none_for_non_sensitive_passes(self, engine):
        item = FieldValidationInput(
            name="course_code",
            classification="NON_SENSITIVE",
            actual_action=ProtectionAction.NONE
        )
        res = engine.validate_field(item)
        assert res.status == ValidationStatus.PASS
        assert res.required_action == ProtectionAction.NONE

    def test_13_field_specific_override_takes_precedence(self, engine):
        # student_id has field override HASH, even though DIRECT_IDENTIFIER defaults to MASK
        item = FieldValidationInput(
            name="student_id",
            classification="DIRECT_IDENTIFIER",
            actual_action=ProtectionAction.HASH
        )
        res = engine.validate_field(item)
        assert res.is_field_override is True
        assert res.required_action == ProtectionAction.HASH
        assert res.status == ValidationStatus.PASS

    def test_14_classification_default_policy(self, engine):
        # Unknown direct identifier uses classification default MASK
        item = FieldValidationInput(
            name="random_identifier_xyz",
            classification="DIRECT_IDENTIFIER",
            actual_action=ProtectionAction.MASK
        )
        res = engine.validate_field(item)
        assert res.is_field_override is False
        assert res.required_action == ProtectionAction.MASK
        assert res.status == ValidationStatus.PASS


# ---------------------------------------------------------------------------
# 3. Edge Cases & Resilience Tests (Tests 15-20)
# ---------------------------------------------------------------------------

class TestEdgeCases:
    @pytest.fixture
    def engine(self):
        return PolicyEngine()

    def test_15_empty_synthetic_value(self):
        assert apply_masking("", ProtectionAction.MASK) == ""
        assert apply_masking("", ProtectionAction.HASH) == ""
        assert apply_masking("", ProtectionAction.GENERALIZE) == ""

    def test_16_unknown_field_autodetects_or_defaults(self, engine):
        item = FieldValidationInput(
            name="completely_unknown_metric",
            classification="NON_SENSITIVE",
            actual_action=ProtectionAction.NONE
        )
        res = engine.validate_field(item)
        assert res.status == ValidationStatus.PASS
        assert res.required_action == ProtectionAction.NONE

    def test_17_unknown_classification_defaults_to_none(self, engine):
        item = FieldValidationInput(
            name="custom_field",
            classification="UNKNOWN_CLASSIFICATION",
            actual_action=ProtectionAction.NONE
        )
        res = engine.validate_field(item)
        assert res.required_action == ProtectionAction.NONE
        assert res.status == ValidationStatus.PASS

    def test_18_invalid_action_gracefully_handled(self):
        # apply_masking with action NONE
        res = apply_masking("sample_val", ProtectionAction.NONE)
        assert res == "sample_val"

    def test_19_already_masked_value_idempotent(self):
        val = "s******@example.edu"
        res = apply_masking(val, ProtectionAction.MASK)
        assert res == val

        suppressed = "[SUPPRESSED]"
        assert apply_masking(suppressed, ProtectionAction.SUPPRESS) == suppressed

    def test_20_policy_disabled_handling(self, engine):
        # Disable student_id override
        engine.disabled_policies.add("POL-FLD-student_id")
        action, is_override, _ = engine.get_required_action("student_id", "DIRECT_IDENTIFIER")
        # Falls back to classification default MASK
        assert is_override is False
        assert action == ProtectionAction.MASK


# ---------------------------------------------------------------------------
# 4. API Endpoints Tests (Tests 21-23)
# ---------------------------------------------------------------------------

class TestPolicyAPIs:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_21_get_policies_endpoint(self, client):
        resp = client.get("/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["policy_version"] == "v1.0"
        assert "DIRECT_IDENTIFIER" in data["classification_defaults"]
        assert data["field_overrides"]["student_id"] == "HASH"

    def test_22_post_policies_validate_endpoint(self, client):
        payload = {
            "dataset_name": "test_dataset",
            "fields": [
                {
                    "name": "email",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "MASK",
                    "sample_value": "student001@example.edu"
                },
                {
                    "name": "phone",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "NONE",
                    "sample_value": "+91-9000000001"
                }
            ]
        }
        resp = client.post("/policies/validate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_status"] == "FAIL"
        assert data["summary"]["violations"] == 1
        assert data["summary"]["protected_count"] == 1
        assert len(data["field_results"]) == 2

    def test_23_post_policies_preview_endpoint(self, client):
        payload = {
            "field_name": "email",
            "action": "MASK",
            "value": "student001@example.edu"
        }
        resp = client.post("/policies/preview", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["masked_value"] == "s******@example.edu"
        assert data["is_synthetic"] is True
