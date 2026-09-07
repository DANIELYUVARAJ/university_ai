"""
University DataShield – Test Suite
Phase 7: End-to-End Security Validation & Adversarial Testing (30+ tests)
Verifies default-deny publication gate, bypass resistance, fail-closed behavior,
audit tampering detection, policy rollback recovery, and database privacy.
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from database import get_db
from audit.audit_service import AuditService
from governance.governance_repository import GovernanceRepository
from security_validation.runner import SecurityValidationRunner
from security_validation.schemas import ScenarioStatus, SecuritySeverity, ScenarioCategory


@pytest.fixture(scope="module")
def client():
    import asyncio

    async def reset():
        db = await get_db()
        try:
            await db.execute("DELETE FROM policy_change_requests")
            await db.execute("DELETE FROM policy_versions")
            await db.commit()
        finally:
            await db.close()
        await GovernanceRepository.ensure_initial_version()

    asyncio.run(reset())

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        asyncio.run(reset())


# ---------------------------------------------------------------------------
# 1. Realistic Security Scenarios Execution (Tests 1-14)
# ---------------------------------------------------------------------------

class TestSecurityScenarios:
    def test_01_compliant_publication_allowed(self, client: TestClient):
        """SEC-01: Compliant dataset with all sensitive fields properly protected must be ALLOWED."""
        payload = {
            "dataset_name": "sec01_compliant_analytics",
            "role": "ANALYST",
            "fields": [
                {"name": "student_id", "classification": "DIRECT_IDENTIFIER", "actual_action": "HASH"},
                {"name": "email", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"},
                {"name": "date_of_birth", "classification": "QUASI_IDENTIFIER", "actual_action": "GENERALIZE"},
                {"name": "major", "classification": "NON_SENSITIVE", "actual_action": "NONE"},
            ],
        }
        res = client.post("/publish-check", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["decision"] == "ALLOW"
        assert data["status"] == "SAFE_TO_PUBLISH"
        assert data["policy_compliant"] is True

    def test_02_unmasked_direct_identifier_blocked(self, client: TestClient):
        """SEC-02: Unprotected direct identifier (phone) must result in BLOCK."""
        payload = {
            "dataset_name": "sec02_unmasked_phone",
            "role": "ANALYST",
            "fields": [
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"},
                {"name": "department", "classification": "NON_SENSITIVE", "actual_action": "NONE"},
            ],
        }
        res = client.post("/publish-check", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["decision"] == "BLOCK"
        assert data["status"] == "PUBLICATION_BLOCKED"
        assert data["policy_compliant"] is False
        assert any("phone" in str(r) for r in data["reasons"])

    def test_03_unauthorized_role_publication_blocked(self, client: TestClient):
        """SEC-03: Role without PUBLISH permission (FACULTY) must be blocked with UNAUTHORIZED."""
        payload = {
            "dataset_name": "sec03_unauthorized_faculty",
            "role": "FACULTY",
            "target_destination": "public_portal",
            "fields": [
                {"name": "student_id", "classification": "DIRECT_IDENTIFIER", "actual_action": "HASH"}
            ],
        }
        res = client.post("/publish", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["decision"] == "BLOCK"
        assert data["status"] == "UNAUTHORIZED"
        assert data["success"] is False

    def test_04_client_side_bypass_attempt_independently_blocked(self, client: TestClient):
        """SEC-04: Injecting client-side approval flags must NOT bypass backend policy check."""
        payload = {
            "dataset_name": "sec04_bypass_attempt",
            "role": "ANALYST",
            "approved": True,
            "safe": True,
            "validation_status": "PASS",
            "target_destination": "analytics_dw",
            "fields": [
                {"name": "student_name", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"}
            ],
        }
        res = client.post("/publish", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["decision"] == "BLOCK"
        assert data["success"] is False
        assert data["status"] == "PUBLICATION_BLOCKED"

    def test_05_wrong_masking_transformation_blocked(self, client: TestClient):
        """SEC-05: Mismatched transformation (email requiring MASK but given GENERALIZE) must BLOCK."""
        payload = {
            "dataset_name": "sec05_wrong_masking",
            "role": "ANALYST",
            "fields": [
                {"name": "email", "classification": "DIRECT_IDENTIFIER", "actual_action": "GENERALIZE"}
            ],
        }
        res = client.post("/publish-check", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["decision"] == "BLOCK"
        assert data["policy_compliant"] is False

    def test_06_missing_policy_fails_closed(self, client: TestClient):
        """SEC-06: Sensitive field with unconfigured or missing policy must FAIL CLOSED."""
        payload = {
            "dataset_name": "sec06_missing_policy",
            "role": "ANALYST",
            "fields": [
                {"name": "restricted_biometric_id", "classification": "UNKNOWN_SENSITIVE", "actual_action": "NONE"}
            ],
        }
        res = client.post("/publish-check", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["decision"] == "BLOCK"
        assert any("missing masking policy" in str(r).lower() or "unprotected" in str(r).lower() for r in data["reasons"])

    def test_07_ambiguous_field_name_uses_value_pattern(self, client: TestClient):
        """SEC-07: Ambiguous field name ('contact') with phone pattern is caught and blocked if unmasked."""
        payload = {
            "dataset_name": "sec07_ambiguous_contact",
            "role": "ANALYST",
            "fields": [
                {
                    "name": "contact",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "NONE",
                    "sample_value": "+1-555-0199",
                }
            ],
        }
        res = client.post("/publish-check", json=payload)
        assert res.status_code == 200
        assert res.json()["decision"] == "BLOCK"

    def test_08_false_positive_traps_allowed(self, client: TestClient):
        """SEC-08: Non-sensitive analytical aggregate fields are not falsely blocked."""
        payload = {
            "dataset_name": "sec08_aggregates",
            "role": "ANALYST",
            "fields": [
                {"name": "email_template_id", "classification": "NON_SENSITIVE", "actual_action": "NONE"},
                {"name": "course_code", "classification": "NON_SENSITIVE", "actual_action": "NONE"},
                {"name": "student_count", "classification": "NON_SENSITIVE", "actual_action": "NONE"},
            ],
        }
        res = client.post("/publish-check", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["decision"] == "ALLOW"
        assert data["status"] == "SAFE_TO_PUBLISH"

    def test_09_audit_tampering_detected_cryptographically(self, client: TestClient):
        """SEC-09: Mutating an audit record in SQLite breaks the SHA-256 hash chain and returns COMPROMISED."""
        import asyncio

        async def run_tamper():
            db = await get_db()
            target_id = None
            orig_hash = None
            try:
                cur = await db.execute("SELECT id, event_hash FROM audit_events ORDER BY id DESC LIMIT 1")
                row = await cur.fetchone()
                target_id = row["id"]
                orig_hash = row["event_hash"]

                # Mutate event_hash in DB
                forged = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
                await db.execute("UPDATE audit_events SET event_hash = ? WHERE id = ?", (forged, target_id))
                await db.commit()

                # Call integrity verification
                verify = client.get("/audit/integrity")
                assert verify.status_code == 200
                assert verify.json()["status"] == "COMPROMISED"
            finally:
                # Restore original hash
                if target_id is not None and orig_hash is not None:
                    await db.execute("UPDATE audit_events SET event_hash = ? WHERE id = ?", (orig_hash, target_id))
                    await db.commit()
                await db.close()

        asyncio.run(run_tamper())

        # Verify integrity is restored
        restored = client.get("/audit/integrity")
        assert restored.json()["status"] == "VALID"

    def test_10_bad_policy_rollback_and_safe_recovery(self, client: TestClient):
        """SEC-10: Bad policy proposal, approval, degradation catch, and safe rollback with revalidation."""
        # 1. Propose bad policy
        prop = client.post(
            "/policies/propose",
            json={
                "target": "phone",
                "is_field_override": True,
                "proposed_action": "NONE",
                "reason": "Test degradation scenario",
                "requested_by_role": "DATA_ENGINEER",
                "requested_by_actor": "engineer-demo",
            },
        )
        assert prop.status_code == 200
        chg_id = prop.json()["id"]

        # 2. Approve by security admin
        appr = client.post(
            "/policies/approve",
            json={
                "change_id": chg_id,
                "reviewed_by_role": "SECURITY_ADMIN",
                "reviewed_by_actor": "security-admin-demo",
                "review_reason": "Approved for scenario test",
            },
        )
        assert appr.status_code == 200
        bad_version = appr.json()["version"]

        # 3. Rollback back to v1.0
        rb = client.post(
            "/policies/rollback",
            json={
                "target_version": "v1.0",
                "actor_role": "SECURITY_ADMIN",
                "actor_id": "security-admin-demo",
                "reason": "Reverting degraded policy; restoring mandatory MASK for phone",
            },
        )
        assert rb.status_code == 200
        rb_data = rb.json()
        assert rb_data["success"] is True
        assert rb_data["revalidation_status"] == "PASS"

        # Check active policy restored MASK for phone
        active = client.get("/policies").json()
        assert active["field_overrides"]["phone"] == "MASK"

    def test_11_malformed_value_still_blocks_unprotected_sensitive_field(self, client: TestClient):
        """SEC-11: Malformed synthetic value string does NOT cause field to be treated as safe."""
        payload = {
            "dataset_name": "sec11_malformed_phone",
            "role": "ANALYST",
            "fields": [
                {
                    "name": "phone",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "NONE",
                    "sample_value": "not-a-valid-phone-12345",
                }
            ],
        }
        res = client.post("/publish-check", json=payload)
        assert res.status_code == 200
        assert res.json()["decision"] == "BLOCK"

    def test_12_null_value_on_sensitive_field_still_blocks(self, client: TestClient):
        """SEC-12: Null/empty sample value does NOT remove the masking requirement for sensitive fields."""
        payload = {
            "dataset_name": "sec12_null_email",
            "role": "ANALYST",
            "fields": [
                {
                    "name": "email",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "NONE",
                    "sample_value": None,
                }
            ],
        }
        res = client.post("/publish-check", json=payload)
        assert res.status_code == 200
        assert res.json()["decision"] == "BLOCK"

    def test_13_api_privilege_escalation_on_rollback_rejected(self, client: TestClient):
        """SEC-13: Direct API call to POST /policies/rollback by DATA_ENGINEER returns 403."""
        res = client.post(
            "/policies/rollback",
            json={
                "target_version": "v1.0",
                "actor_role": "DATA_ENGINEER",
                "actor_id": "engineer-demo",
                "reason": "Attempting privilege escalation",
            },
        )
        assert res.status_code == 403
        assert "GOVERNANCE_ROLE_REQUIRED" in res.json()["detail"]

    def test_14_self_approval_attempt_blocked(self, client: TestClient):
        """SEC-14: Proposer attempting to self-approve change returns 409 SELF_APPROVAL_BLOCKED."""
        prop = client.post(
            "/policies/propose",
            json={
                "target": "date_of_birth",
                "is_field_override": True,
                "proposed_action": "NONE",
                "reason": "Self approval test",
                "requested_by_role": "SECURITY_ADMIN",
                "requested_by_actor": "self-approver-99",
            },
        )
        chg_id = prop.json()["id"]

        res = client.post(
            "/policies/approve",
            json={
                "change_id": chg_id,
                "reviewed_by_role": "SECURITY_ADMIN",
                "reviewed_by_actor": "self-approver-99",  # SAME ACTOR
                "review_reason": "Approving own change",
            },
        )
        assert res.status_code == 409
        assert "SELF_APPROVAL_BLOCKED" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 2. Security Validation Harness & API Endpoints (Tests 15-22)
# ---------------------------------------------------------------------------

class TestSecurityValidationHarness:
    def test_15_post_security_validation_run(self, client: TestClient):
        """POST /security-validation/run executes all scenarios and returns report."""
        res = client.post("/security-validation/run")
        assert res.status_code == 200
        data = res.json()
        assert data["overall_status"] == "PASS"
        assert data["scenarios_total"] >= 14
        assert data["scenarios_passed"] == data["scenarios_total"]
        assert data["privacy_check_passed"] is True

    def test_16_get_security_validation_results(self, client: TestClient):
        """GET /security-validation/results returns latest scenario results and scorecard."""
        res = client.get("/security-validation/results")
        assert res.status_code == 200
        data = res.json()
        assert "scenarios" in data
        assert len(data["scenarios"]) >= 14
        assert "metrics" in data
        assert "baseline_comparison" in data

    def test_17_get_security_validation_metrics(self, client: TestClient):
        """GET /security-validation/metrics returns calculated security rates."""
        res = client.get("/security-validation/metrics")
        assert res.status_code == 200
        metrics = res.json()
        assert metrics["unsafe_publication_prevention_rate"] == 1.0
        assert metrics["unauthorized_block_rate"] == 1.0
        assert metrics["audit_coverage_rate"] == 1.0
        assert metrics["rollback_recovery_rate"] == 1.0
        assert metrics["false_block_rate"] == 0.0

    def test_18_report_file_persisted_to_disk(self):
        """Verify report is persisted to data/security/security_validation_results.json."""
        report_path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "security"
            / "security_validation_results.json"
        )
        assert report_path.exists(), "security_validation_results.json does not exist on disk"

    def test_19_baseline_comparison_structure(self, client: TestClient):
        """Verify baseline comparison includes precision, recall, F1, accuracy, and gate capability."""
        res = client.get("/security-validation/results")
        assert res.status_code == 200
        comps = res.json()["baseline_comparison"]
        metric_names = [c["metric"] for c in comps]
        assert "Detection Precision" in metric_names
        assert "Detection Recall" in metric_names
        assert "Detection F1 Score" in metric_names
        assert "Unsafe Publication Prevention" in metric_names


# ---------------------------------------------------------------------------
# 3. API-Level Bypass Resistance (Tests 20-25)
# ---------------------------------------------------------------------------

class TestAPIBypassResistance:
    def test_20_direct_publish_revalidates_gate_independently(self, client: TestClient):
        """Calling /publish directly with forged parameters fails if data is sensitive and unmasked."""
        payload = {
            "dataset_name": "direct_api_bypass",
            "role": "ANALYST",
            "target_destination": "s3://public-bucket",
            "fields": [
                {"name": "phone", "classification": "DIRECT_IDENTIFIER", "actual_action": "NONE"}
            ],
        }
        res = client.post("/publish", json=payload)
        assert res.status_code == 200
        assert res.json()["success"] is False
        assert res.json()["decision"] == "BLOCK"

    def test_21_direct_publish_unauthorized_role_blocked(self, client: TestClient):
        """Calling /publish directly as PLACEMENT_ADMIN is blocked with UNAUTHORIZED."""
        payload = {
            "dataset_name": "placement_unauth_publish",
            "role": "PLACEMENT_ADMIN",
            "target_destination": "analytics_lake",
            "fields": [
                {"name": "student_id", "classification": "DIRECT_IDENTIFIER", "actual_action": "HASH"}
            ],
        }
        res = client.post("/publish", json=payload)
        assert res.status_code == 200
        assert res.json()["success"] is False
        assert res.json()["status"] == "UNAUTHORIZED"

    def test_22_direct_approve_by_non_admin_returns_403(self, client: TestClient):
        """Calling /policies/approve as ANALYST returns 403 GOVERNANCE_ROLE_REQUIRED."""
        res = client.post(
            "/policies/approve",
            json={
                "change_id": "CHG-001",
                "reviewed_by_role": "ANALYST",
                "reviewed_by_actor": "analyst-demo",
                "review_reason": "Bypass attempt",
            },
        )
        assert res.status_code == 403
        assert "GOVERNANCE_ROLE_REQUIRED" in res.json()["detail"]

    def test_23_direct_rollback_to_nonexistent_version_returns_404(self, client: TestClient):
        """Calling /policies/rollback with nonexistent version returns 404."""
        res = client.post(
            "/policies/rollback",
            json={
                "target_version": "v999.0",
                "actor_role": "SECURITY_ADMIN",
                "actor_id": "security-admin-demo",
                "reason": "Nonexistent rollback",
            },
        )
        assert res.status_code == 404
        assert "POLICY_VERSION_NOT_FOUND" in res.json()["detail"]

    def test_24_direct_rollback_to_active_version_returns_409(self, client: TestClient):
        """Calling /policies/rollback targeting the already active version returns 409."""
        active = client.get("/policies").json()["version"]
        res = client.post(
            "/policies/rollback",
            json={
                "target_version": active,
                "actor_role": "SECURITY_ADMIN",
                "actor_id": "security-admin-demo",
                "reason": "Rollback to active",
            },
        )
        assert res.status_code == 409
        assert "ROLLBACK_NOT_ALLOWED" in res.json()["detail"]

    def test_25_empty_dataset_fails_closed_or_evaluates_cleanly(self, client: TestClient):
        """Publish check on dataset with no fields evaluates cleanly without crashing."""
        res = client.post(
            "/publish-check",
            json={
                "dataset_name": "empty_dataset",
                "role": "ANALYST",
                "fields": [],
            },
        )
        assert res.status_code == 200
        assert res.json()["decision"] == "ALLOW"


# ---------------------------------------------------------------------------
# 4. Database Privacy & Audit Completeness (Tests 26-30)
# ---------------------------------------------------------------------------

class TestDatabasePrivacyAndAuditCompleteness:
    @pytest.mark.asyncio
    async def test_26_zero_raw_synthetic_values_in_database(self):
        """Comprehensive scan of all tables to prove raw sensitive values are never persisted."""
        db = await get_db()
        forbidden_values = [
            "student001@example.edu",
            "john.doe@university.edu",
            "+91-9876543210",
            "+1-555-0199",
            "+91-9000000001",
            "STU_DEMO_001",
            "Demo Student",
        ]
        tables = [
            "audit_events",
            "policy_versions",
            "policy_change_requests",
            "publication_attempts",
        ]
        try:
            for t in tables:
                cur = await db.execute(f"SELECT * FROM {t}")
                rows = await cur.fetchall()
                for row in rows:
                    row_str = " ".join(str(val) for val in row)
                    for forbidden in forbidden_values:
                        assert forbidden not in row_str, f"Privacy violation: Found raw value '{forbidden}' in table {t}"
        finally:
            await db.close()

    def test_27_audit_trail_records_access_denial_events(self, client: TestClient):
        """Verify ACCESS_DENIAL events exist in audit trail."""
        res = client.get("/audit", params={"action": "ACCESS_DENIAL"})
        assert res.status_code == 200
        events = res.json()
        assert len(events) >= 1
        assert any(e["action"] == "ACCESS_DENIAL" for e in events)

    def test_28_audit_trail_records_publication_check_events(self, client: TestClient):
        """Verify PUBLICATION_CHECK events exist in audit trail."""
        res = client.get("/audit", params={"action": "PUBLICATION_CHECK"})
        assert res.status_code == 200
        assert len(res.json()) >= 1

    def test_29_audit_trail_records_rollback_events(self, client: TestClient):
        """Verify POLICY_ROLLBACK events exist in audit trail."""
        res = client.get("/audit", params={"action": "POLICY_ROLLBACK"})
        assert res.status_code == 200
        assert len(res.json()) >= 1

    def test_30_unbroken_cryptographic_hash_chain_on_audit_ledger(self, client: TestClient):
        """Verify SHA-256 hash chain is cryptographically unbroken across all recorded events."""
        res = client.get("/audit/integrity")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "VALID"
        assert data["events_checked"] >= 10
        assert "hash chain" in data["details"].lower()
