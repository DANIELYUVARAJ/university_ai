"""
University DataShield – Test Suite
Phase 5: Role-Based Access Control and Publication Gate Tests (25+ tests)
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

import sys
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from access.roles import Role
from access.permissions import Permission
from access.access_engine import AccessEngine
from policies.schemas import ProtectionAction, FieldValidationInput
from publication.schemas import (
    PublicationDecision,
    PublicationStatus,
    PublicationCheckRequest,
    PublishExecutionRequest,
)
from publication.gate import PublicationGate


# ---------------------------------------------------------------------------
# 1. Role Permission Tests (Tests 1-5)
# ---------------------------------------------------------------------------

class TestRolePermissions:
    def test_01_analyst_permissions(self):
        assert AccessEngine.can_perform(Role.ANALYST, Permission.VIEW_SCHEMA) is True
        assert AccessEngine.can_perform(Role.ANALYST, Permission.VALIDATE) is True
        assert AccessEngine.can_perform(Role.ANALYST, Permission.PUBLISH) is True
        assert AccessEngine.can_perform(Role.ANALYST, Permission.MANAGE_POLICIES) is False
        assert AccessEngine.can_perform(Role.ANALYST, Permission.VIEW_RAW_SENSITIVE_DATA) is False

    def test_02_faculty_permissions(self):
        assert AccessEngine.can_perform(Role.FACULTY, Permission.VIEW_SCHEMA) is True
        assert AccessEngine.can_perform(Role.FACULTY, Permission.VALIDATE) is True
        assert AccessEngine.can_perform(Role.FACULTY, Permission.PUBLISH) is False
        assert AccessEngine.can_perform(Role.FACULTY, Permission.MANAGE_POLICIES) is False

    def test_03_data_engineer_permissions(self):
        assert AccessEngine.can_perform(Role.DATA_ENGINEER, Permission.VIEW_SCHEMA) is True
        assert AccessEngine.can_perform(Role.DATA_ENGINEER, Permission.VALIDATE) is True
        assert AccessEngine.can_perform(Role.DATA_ENGINEER, Permission.PUBLISH) is False
        assert AccessEngine.can_perform(Role.DATA_ENGINEER, Permission.MANAGE_POLICIES) is False

    def test_04_placement_admin_permissions(self):
        assert AccessEngine.can_perform(Role.PLACEMENT_ADMIN, Permission.VIEW_SCHEMA) is True
        assert AccessEngine.can_perform(Role.PLACEMENT_ADMIN, Permission.VALIDATE) is True
        # Limited / not authorized for general public release gate
        assert AccessEngine.can_perform(Role.PLACEMENT_ADMIN, Permission.PUBLISH) is False

    def test_05_security_admin_permissions(self):
        assert AccessEngine.can_perform(Role.SECURITY_ADMIN, Permission.MANAGE_POLICIES) is True
        assert AccessEngine.can_perform(Role.SECURITY_ADMIN, Permission.PUBLISH) is True
        assert AccessEngine.can_perform(Role.SECURITY_ADMIN, Permission.VALIDATE) is True


# ---------------------------------------------------------------------------
# 2. Publication Gate Decision Tests (Tests 6-15)
# ---------------------------------------------------------------------------

class TestPublicationGateDecisions:
    @pytest.fixture
    def gate(self):
        return PublicationGate()

    def test_06_compliant_analyst_allowed(self, gate):
        req = PublicationCheckRequest(
            dataset_name="clean_dataset",
            role="ANALYST",
            fields=[
                FieldValidationInput(name="email", classification="DIRECT_IDENTIFIER", actual_action=ProtectionAction.MASK),
                FieldValidationInput(name="course_code", classification="NON_SENSITIVE", actual_action=ProtectionAction.NONE)
            ]
        )
        res = gate.evaluate(req)
        assert res.decision == PublicationDecision.ALLOW
        assert res.status == PublicationStatus.SAFE_TO_PUBLISH
        assert res.authorized is True
        assert res.policy_compliant is True

    def test_07_unmasked_email_blocked(self, gate):
        req = PublicationCheckRequest(
            dataset_name="leaky_email",
            role="ANALYST",
            fields=[
                FieldValidationInput(name="email", classification="DIRECT_IDENTIFIER", actual_action=ProtectionAction.NONE)
            ]
        )
        res = gate.evaluate(req)
        assert res.decision == PublicationDecision.BLOCK
        assert res.status == PublicationStatus.PUBLICATION_BLOCKED
        assert res.policy_compliant is False

    def test_08_unmasked_phone_blocked(self, gate):
        req = PublicationCheckRequest(
            dataset_name="leaky_phone",
            role="ANALYST",
            fields=[
                FieldValidationInput(name="phone", classification="DIRECT_IDENTIFIER", actual_action=ProtectionAction.NONE)
            ]
        )
        res = gate.evaluate(req)
        assert res.decision == PublicationDecision.BLOCK
        assert res.status == PublicationStatus.PUBLICATION_BLOCKED

    def test_09_policy_fail_blocks_publication(self, gate):
        req = PublicationCheckRequest(
            dataset_name="failed_policy",
            role="ANALYST",
            fields=[
                FieldValidationInput(name="student_id", classification="DIRECT_IDENTIFIER", actual_action=ProtectionAction.NONE)
            ]
        )
        res = gate.evaluate(req)
        assert res.decision == PublicationDecision.BLOCK

    def test_10_policy_review_blocks_publication(self, gate):
        # Salary requires GENERALIZE, but actual is MASK -> status REVIEW -> must BLOCK
        req = PublicationCheckRequest(
            dataset_name="review_dataset",
            role="ANALYST",
            fields=[
                FieldValidationInput(name="salary", classification="SENSITIVE_ATTRIBUTE", actual_action=ProtectionAction.MASK)
            ]
        )
        res = gate.evaluate(req)
        assert res.decision == PublicationDecision.BLOCK
        assert res.policy_compliant is False

    def test_11_faculty_publication_blocked(self, gate):
        # Faculty role lacks PUBLISH permission -> must BLOCK even if dataset is compliant
        req = PublicationCheckRequest(
            dataset_name="faculty_attempt",
            role="FACULTY",
            fields=[
                FieldValidationInput(name="email", classification="DIRECT_IDENTIFIER", actual_action=ProtectionAction.MASK)
            ]
        )
        res = gate.evaluate(req)
        assert res.decision == PublicationDecision.BLOCK
        assert res.authorized is False
        assert res.status == PublicationStatus.UNAUTHORIZED

    def test_12_data_engineer_publication_blocked(self, gate):
        req = PublicationCheckRequest(
            dataset_name="de_attempt",
            role="DATA_ENGINEER",
            fields=[
                FieldValidationInput(name="course_code", classification="NON_SENSITIVE", actual_action=ProtectionAction.NONE)
            ]
        )
        res = gate.evaluate(req)
        assert res.decision == PublicationDecision.BLOCK
        assert res.authorized is False
        assert res.status == PublicationStatus.UNAUTHORIZED

    def test_13_authorized_analyst_allows_non_sensitive(self, gate):
        req = PublicationCheckRequest(
            dataset_name="catalog",
            role="ANALYST",
            fields=[
                FieldValidationInput(name="course_code", classification="NON_SENSITIVE", actual_action=ProtectionAction.NONE),
                FieldValidationInput(name="semester", classification="NON_SENSITIVE", actual_action=ProtectionAction.NONE)
            ]
        )
        res = gate.evaluate(req)
        assert res.decision == PublicationDecision.ALLOW
        assert res.status == PublicationStatus.SAFE_TO_PUBLISH

    def test_14_unknown_role_default_deny(self, gate):
        req = PublicationCheckRequest(
            dataset_name="hacker_role",
            role="EXTERNAL_GUEST",
            fields=[]
        )
        res = gate.evaluate(req)
        assert res.decision == PublicationDecision.BLOCK
        assert res.authorized is False

    def test_15_unknown_state_default_deny(self, gate):
        # Unrecognized empty / malformed role
        req = PublicationCheckRequest(
            dataset_name="unknown_state",
            role="",
            fields=[]
        )
        res = gate.evaluate(req)
        assert res.decision == PublicationDecision.BLOCK


# ---------------------------------------------------------------------------
# 3. Security & Backend Enforcement Tests (Tests 16-20)
# ---------------------------------------------------------------------------

class TestSecurityEnforcement:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_16_frontend_cannot_bypass_backend_authorization(self, client):
        # Even if a client sends a publish request claiming approval, backend rejects FACULTY
        payload = {
            "dataset_name": "bypass_test",
            "role": "FACULTY",
            "fields": [
                {"name": "email", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"}
            ]
        }
        resp = client.post("/publish", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["decision"] == "BLOCK"
        assert data["status"] == "UNAUTHORIZED"

    def test_17_publish_endpoint_independently_revalidates_policy(self, client):
        # POST /publish with unmasked phone must fail on the backend
        payload = {
            "dataset_name": "leaky_publish",
            "role": "ANALYST",
            "fields": [
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"}
            ]
        }
        resp = client.post("/publish", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["decision"] == "BLOCK"
        assert data["status"] == "PUBLICATION_BLOCKED"

    def test_18_invalid_role_rejected_by_api(self, client):
        resp = client.get("/roles/NON_EXISTENT_ROLE")
        assert resp.status_code == 404

    def test_19_security_admin_cannot_bypass_policy_violation(self, client):
        # Even SECURITY_ADMIN cannot publish data with unmasked direct identifiers
        payload = {
            "dataset_name": "admin_leak",
            "role": "SECURITY_ADMIN",
            "fields": [
                {"name": "student_id", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"}
            ]
        }
        resp = client.post("/publish-check", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "BLOCK"
        assert data["policy_compliant"] is False

    def test_20_missing_field_protection_rejected(self, client):
        payload = {
            "dataset_name": "missing_protection",
            "role": "ANALYST",
            "fields": [
                {"name": "personal_email", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"}
            ]
        }
        resp = client.post("/publish", json=payload)
        data = resp.json()
        assert data["decision"] == "BLOCK"


# ---------------------------------------------------------------------------
# 4. End-to-End Integration & Killer Demo Workflows (Tests 21-25)
# ---------------------------------------------------------------------------

class TestIntegrationWorkflows:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_21_detection_to_policy_to_publication_flow(self, client):
        # Test detection of an unclassified field: candidate_id (direct identifier)
        payload = {
            "dataset_name": "auto_detect_dataset",
            "role": "ANALYST",
            "fields": [
                {"name": "candidate_id", "actual_action": "NONE", "sample_value": "CAND_DEMO_001"}
            ]
        }
        resp = client.post("/publish-check", json=payload)
        data = resp.json()
        # candidate_id requires HASH -> actual NONE -> must BLOCK
        assert data["decision"] == "BLOCK"

    def test_22_correct_masking_allows_simulation(self, client):
        payload = {
            "dataset_name": "compliant_simulation",
            "role": "ANALYST",
            "fields": [
                {"name": "email", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
                {"name": "student_id", "classification": "DIRECT_IDENTIFIER", "actual_action": "HASH"},
                {"name": "salary", "classification": "SENSITIVE_ATTRIBUTE", "actual_action": "GENERALIZE"},
                {"name": "course_code", "classification": "NON_SENSITIVE", "actual_action": "NONE"}
            ]
        }
        resp = client.post("/publish", json=payload)
        data = resp.json()
        assert data["success"] is True
        assert data["decision"] == "ALLOW"
        assert data["status"] == "SAFE_TO_PUBLISH"
        assert "Simulated successfully" in data["message"]

    def test_23_incorrect_masking_blocks_simulation(self, client):
        payload = {
            "dataset_name": "bad_mask_simulation",
            "role": "ANALYST",
            "fields": [
                {"name": "email", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"}
            ]
        }
        resp = client.post("/publish", json=payload)
        data = resp.json()
        assert data["success"] is False
        assert data["decision"] == "BLOCK"

    def test_24_role_and_policy_combined_failure(self, client):
        # Faculty + unmasked phone
        payload = {
            "dataset_name": "double_failure",
            "role": "FACULTY",
            "fields": [
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"}
            ]
        }
        resp = client.post("/publish-check", json=payload)
        data = resp.json()
        assert data["decision"] == "BLOCK"
        assert data["authorized"] is False
        assert data["policy_compliant"] is False

    def test_25_killer_demo_unsafe_fix_safe_workflow(self, client):
        # Step 1: Unsafe dataset with unmasked phone
        unsafe_payload = {
            "dataset_name": "university_demo",
            "role": "ANALYST",
            "fields": [
                {"name": "email", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"},
                {"name": "attendance_percentage", "classification": "ACADEMIC_DATA", "actual_action": "NONE"},
                {"name": "salary", "classification": "SENSITIVE_ATTRIBUTE", "actual_action": "GENERALIZE"}
            ]
        }
        resp1 = client.post("/publish-check", json=unsafe_payload)
        data1 = resp1.json()
        assert data1["decision"] == "BLOCK"
        assert data1["status"] == "PUBLICATION_BLOCKED"

        # Step 2: Fix the violation by setting phone -> MASK
        fixed_payload = {
            "dataset_name": "university_demo",
            "role": "ANALYST",
            "fields": [
                {"name": "email", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
                {"name": "attendance_percentage", "classification": "ACADEMIC_DATA", "actual_action": "NONE"},
                {"name": "salary", "classification": "SENSITIVE_ATTRIBUTE", "actual_action": "GENERALIZE"}
            ]
        }
        resp2 = client.post("/publish-check", json=fixed_payload)
        data2 = resp2.json()
        assert data2["decision"] == "ALLOW"
        assert data2["status"] == "SAFE_TO_PUBLISH"

        # Step 3: Now simulate publication with the fixed dataset
        resp3 = client.post("/publish", json=fixed_payload)
        data3 = resp3.json()
        assert data3["success"] is True
        assert data3["decision"] == "ALLOW"
