# tests/test_phase8_integration.py
"""
Phase 8 Integration Tests:
- Dashboard Summary Endpoint (real-time metrics)
- Demo Reset Endpoint (deterministic baseline restoration)
- Evaluator Demo Journey End-to-End Execution
- Privacy by Design & Zero Raw PII Verification
"""

import sys
from pathlib import Path
import pytest
from starlette.testclient import TestClient
import aiosqlite
import os

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from database import DB_PATH


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestPhase8ExecutiveEndpoints:
    def test_01_health_endpoint_phase8(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == 8
        assert data["version"] == "0.8.0"
        assert data["database"]["ok"] is True

    def test_02_dashboard_summary_endpoint(self, client):
        resp = client.get("/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["phase"] == 8
        assert data["environment"] == "Evaluator Field Demo"

        # System health indicators
        health = data["system_health"]
        assert health["backend_connected"] is True
        assert health["database_connected"] is True
        assert health["policy_engine_active"] is True
        assert health["publication_gate_active"] is True
        assert health["audit_integrity_valid"] is True
        assert health["synthetic_data_mode"] is True

        # Metrics
        metrics = data["metrics"]
        assert metrics["sensitive_fields_detected"] >= 0
        assert metrics["security_scenarios_passed"] >= 14
        assert metrics["audit_integrity_status"] == "VALID"
        assert metrics["unsafe_publication_prevention_rate"] == 1.0
        assert metrics["unauthorized_block_rate"] == 1.0
        assert metrics["audit_coverage"] == 1.0
        assert metrics["rollback_recovery_rate"] == 1.0
        assert metrics["false_block_rate"] == 0.0

    def test_03_demo_reset_endpoint(self, client):
        resp = client.post("/demo/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "RESET_COMPLETE"
        assert data["active_version"] == "v1.0"
        assert data["integrity_status"] == "VALID"
        assert "reset to pristine baseline" in data["message"]

    def test_04_audit_integrity_after_reset(self, client):
        resp = client.get("/audit/integrity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "VALID"


class TestPhase8EvaluatorJourneyWorkflow:
    def test_05_step1_scan_schema(self, client):
        payload = {
            "dataset_name": "student_evaluator_demo",
            "fields": [
                {"name": "student_id", "data_type": "VARCHAR(20)", "sample_pattern": "STU12345"},
                {"name": "email", "data_type": "VARCHAR(100)", "sample_pattern": "demo@univ.edu"},
                {"name": "phone", "data_type": "VARCHAR(20)", "sample_pattern": "+91-9876543210"},
                {"name": "course_code", "data_type": "VARCHAR(10)", "sample_pattern": "CS101"},
            ]
        }
        resp = client.post("/scan", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["sensitive_count"] >= 3

    def test_06_step2_validate_policy(self, client):
        payload = {
            "dataset_name": "student_evaluator_demo",
            "fields": [
                {"name": "student_id", "classification": "DIRECT_IDENTIFIER", "actual_action": "HASH"},
                {"name": "email", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
                {"name": "course_code", "classification": "ACADEMIC_DATA", "actual_action": "NONE"},
            ]
        }
        resp = client.post("/policies/validate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_status"] in ("PASS", "REVIEW")

    def test_07_step3_attempt_unsafe_publication(self, client):
        # Unmasked phone must be blocked
        payload = {
            "dataset_name": "student_evaluator_demo",
            "role": "SECURITY_ADMIN",
            "fields": [
                {"name": "student_id", "classification": "DIRECT_IDENTIFIER", "actual_action": "HASH"},
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"},
            ]
        }
        resp = client.post("/publish", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "BLOCK"
        assert data["status"] == "PUBLICATION_BLOCKED"
        assert data["success"] is False

    def test_08_step4_fix_protection_and_publish_allowed(self, client):
        # Properly masked data is allowed
        payload = {
            "dataset_name": "student_evaluator_demo",
            "role": "SECURITY_ADMIN",
            "fields": [
                {"name": "student_id", "classification": "DIRECT_IDENTIFIER", "actual_action": "HASH"},
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
            ]
        }
        resp = client.post("/publish", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "ALLOW"
        assert data["success"] is True

    def test_09_step5_unauthorized_role_publish_blocked(self, client):
        payload = {
            "dataset_name": "student_evaluator_demo",
            "role": "FACULTY",
            "fields": [
                {"name": "student_id", "classification": "DIRECT_IDENTIFIER", "actual_action": "HASH"},
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
            ]
        }
        resp = client.post("/publish", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "BLOCK"
        assert data["status"] == "UNAUTHORIZED"
        assert data["success"] is False

    def test_10_step6_governance_propose_and_approve(self, client):
        # Propose
        prop_payload = {
            "target": "guardian_contact",
            "is_field_override": True,
            "proposed_action": "MASK",
            "reason": "Phase 8 evaluator demonstration test",
            "requested_by_role": "DATA_ENGINEER",
            "requested_by_actor": "engineer_alice"
        }
        p_resp = client.post("/policies/propose", json=prop_payload)
        assert p_resp.status_code == 200
        change_id = p_resp.json()["id"]

        # Self-approval blocked
        self_app_payload = {
            "change_id": change_id,
            "reviewed_by_role": "SECURITY_ADMIN",
            "reviewed_by_actor": "engineer_alice",  # same actor!
            "review_reason": "Trying to self approve"
        }
        sa_resp = client.post("/policies/approve", json=self_app_payload)
        assert sa_resp.status_code == 409

        # Proper admin approval
        app_payload = {
            "change_id": change_id,
            "reviewed_by_role": "SECURITY_ADMIN",
            "reviewed_by_actor": "admin_bob",
            "review_reason": "Approved by security team"
        }
        a_resp = client.post("/policies/approve", json=app_payload)
        assert a_resp.status_code == 200
        new_ver = a_resp.json()["version"]
        assert new_ver is not None

        # Clean reset back to v1.0
        r_resp = client.post("/demo/reset")
        assert r_resp.status_code == 200
        assert r_resp.json()["active_version"] == "v1.0"


class TestPhase8PrivacyAndDataMinimization:
    @pytest.mark.asyncio
    async def test_11_zero_raw_pii_in_all_governance_records(self):
        forbidden_pii = [
            "student001@example.edu",
            "+91-9000000001",
            "STU_DEMO_001",
            "STU12345",
            "demo@univ.edu",
            "+91-9876543210",
        ]
        async with aiosqlite.connect(str(DB_PATH)) as db:
            tables = [
                ("audit_events", ["dataset", "field_name", "result", "reason", "metadata_json"]),
                ("policy_change_requests", ["reason", "proposed_change_json", "review_reason"]),
                ("policy_versions", ["description", "policy_snapshot"]),
                ("publication_attempts", ["reasons_json"]),
            ]
            for table, cols in tables:
                col_sql = ", ".join(cols)
                cursor = await db.execute(f"SELECT {col_sql} FROM {table}")
                rows = await cursor.fetchall()
                for row in rows:
                    for val in row:
                        if val is None:
                            continue
                        text = str(val).lower()
                        for pii in forbidden_pii:
                            assert pii.lower() not in text, (
                                f"Raw PII token '{pii}' leaked in table '{table}'!"
                            )
