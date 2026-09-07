"""
University DataShield – Test Suite
Phase 6: Complete Audit Trail, Policy Governance, Versioning, and Rollback Tests (30+ tests)
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from database import get_db, init_db
from audit.schemas import AuditAction
from policies.schemas import ProtectionAction, FieldValidationInput
from governance.governance_repository import GovernanceRepository


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
        # Trigger startup lifespan events (initial version seeding)
        with TestClient(app) as test_client:
            yield test_client
    finally:
        asyncio.run(reset())


# ---------------------------------------------------------------------------
# 1. Audit Trail Integration Tests (Tests 1-8)
# ---------------------------------------------------------------------------

class TestAuditTrailIntegration:
    def test_01_scan_creates_audit_event(self, client: TestClient):
        scan_payload = {
            "dataset_name": "audit_test_scan_dataset",
            "fields": [
                {"name": "student_name", "data_type": "string", "sample_pattern": "John Doe"},
                {"name": "department", "data_type": "string", "sample_pattern": "Computer Science"},
            ],
        }
        res = client.post("/scan", json=scan_payload)
        assert res.status_code == 200

        # Query audit log for SCAN action
        audit_res = client.get("/audit", params={"action": "SCAN", "dataset": "audit_test_scan_dataset"})
        assert audit_res.status_code == 200
        events = audit_res.json()
        assert len(events) >= 1
        ev = events[0]
        assert ev["action"] == "SCAN"
        assert ev["dataset"] == "audit_test_scan_dataset"
        assert "sensitive" in ev["reason"].lower()
        assert ev["actor_role"] == "DATA_ENGINEER"

    def test_02_policy_validation_creates_audit_event(self, client: TestClient):
        val_payload = {
            "dataset_name": "audit_test_val_dataset",
            "fields": [
                {
                    "name": "student_name",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "MASK",
                    "sample_value": "Jane Doe",
                }
            ],
        }
        res = client.post("/policies/validate", json=val_payload)
        assert res.status_code == 200

        audit_res = client.get("/audit", params={"action": "POLICY_VALIDATION", "dataset": "audit_test_val_dataset"})
        assert audit_res.status_code == 200
        events = audit_res.json()
        assert len(events) >= 1
        ev = events[0]
        assert ev["action"] == "POLICY_VALIDATION"
        assert ev["result"] in ("PASS", "FAIL", "REVIEW")
        assert ev["policy_version"] is not None

    def test_03_publication_check_creates_audit_event(self, client: TestClient):
        check_payload = {
            "dataset_name": "audit_test_pub_check",
            "role": "ANALYST",
            "fields": [
                {
                    "name": "phone",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "NONE",  # should trigger BLOCK
                }
            ],
        }
        res = client.post("/publish-check", json=check_payload)
        assert res.status_code == 200
        assert res.json()["decision"] == "BLOCK"

        audit_res = client.get("/audit", params={"action": "PUBLICATION_CHECK", "dataset": "audit_test_pub_check"})
        assert audit_res.status_code == 200
        events = audit_res.json()
        assert len(events) >= 1
        ev = events[0]
        assert ev["action"] == "PUBLICATION_CHECK"
        assert ev["result"] == "BLOCK"
        assert ev["actor_role"] == "ANALYST"
        assert "phone" in ev["reason"]

    def test_04_successful_publication_creates_audit_event(self, client: TestClient):
        pub_payload = {
            "dataset_name": "audit_test_safe_pub",
            "role": "ANALYST",
            "target_destination": "analytics_dw",
            "fields": [
                {
                    "name": "student_id",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "HASH",
                },
                {
                    "name": "email",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "MASK",
                },
            ],
        }
        res = client.post("/publish", json=pub_payload)
        assert res.status_code == 200
        assert res.json()["decision"] == "ALLOW"

        audit_res = client.get("/audit", params={"action": "PUBLICATION", "dataset": "audit_test_safe_pub"})
        assert audit_res.status_code == 200
        events = audit_res.json()
        assert len(events) >= 1
        assert any(e["result"] == "ALLOW" for e in events)

    def test_05_blocked_publication_creates_audit_event(self, client: TestClient):
        pub_payload = {
            "dataset_name": "audit_test_blocked_pub",
            "role": "ANALYST",
            "target_destination": "public_portal",
            "fields": [
                {
                    "name": "phone",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "NONE",
                }
            ],
        }
        res = client.post("/publish", json=pub_payload)
        assert res.status_code == 200
        assert res.json()["decision"] == "BLOCK"

        audit_res = client.get("/audit", params={"action": "PUBLICATION", "dataset": "audit_test_blocked_pub"})
        assert audit_res.status_code == 200
        events = audit_res.json()
        assert len(events) >= 1
        assert any(e["result"] == "BLOCK" for e in events)

    def test_06_unauthorized_publication_creates_access_denial(self, client: TestClient):
        pub_payload = {
            "dataset_name": "audit_test_unauth_pub",
            "role": "FACULTY",  # Faculty has no publish permission
            "target_destination": "faculty_portal",
            "fields": [
                {
                    "name": "student_id",
                    "classification": "DIRECT_IDENTIFIER",
                    "actual_action": "HASH",
                }
            ],
        }
        res = client.post("/publish", json=pub_payload)
        assert res.status_code == 200
        assert res.json()["decision"] == "BLOCK"
        assert res.json()["status"] == "UNAUTHORIZED"

        audit_res = client.get("/audit", params={"action": "ACCESS_DENIAL", "dataset": "audit_test_unauth_pub"})
        assert audit_res.status_code == 200
        events = audit_res.json()
        assert len(events) >= 1
        assert any(e["actor_role"] == "FACULTY" for e in events)

    def test_07_audit_trail_filtering(self, client: TestClient):
        res = client.get("/audit", params={"limit": 10})
        assert res.status_code == 200
        events = res.json()
        assert isinstance(events, list)
        assert len(events) <= 10

    def test_08_cryptographic_audit_integrity_verification(self, client: TestClient):
        res = client.get("/audit/integrity")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "VALID"
        assert data["events_checked"] >= 5
        assert "hash chain" in data["details"].lower()


# ---------------------------------------------------------------------------
# 2. Policy Change Proposal & Security Admin Control (Tests 9-16)
# ---------------------------------------------------------------------------

class TestPolicyChangeWorkflow:
    def test_09_propose_policy_change_creates_pending(self, client: TestClient):
        propose_payload = {
            "target": "phone",
            "is_field_override": True,
            "proposed_action": "GENERALIZE",
            "reason": "Testing generalized contact numbers for cohort research",
            "requested_by_role": "DATA_ENGINEER",
            "requested_by_actor": "engineer-demo",
        }
        res = client.post("/policies/propose", json=propose_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "PENDING"
        assert data["current_version"] == "v1.0"
        assert data["proposed_version"] == "v1.1"
        assert data["proposed_change"]["target"] == "phone"
        assert data["proposed_change"]["proposed_action"] == "GENERALIZE"

    def test_10_proposed_change_does_not_immediately_alter_active_policy(self, client: TestClient):
        # Active policy must still require MASK for phone (not GENERALIZE)
        policies_res = client.get("/policies")
        assert policies_res.status_code == 200
        policies = policies_res.json()
        assert policies["version"] == "v1.0"
        assert policies["field_overrides"].get("phone") == "MASK"

    def test_11_non_security_admin_cannot_approve(self, client: TestClient):
        changes = client.get("/policy-changes").json()
        pending = [c for c in changes if c["status"] == "PENDING"]
        assert len(pending) > 0
        change_id = pending[0]["id"]

        approve_payload = {
            "change_id": change_id,
            "reviewed_by_role": "DATA_ENGINEER",  # Unauthorized role
            "reviewed_by_actor": "engineer-reviewer",
            "review_reason": "Trying to approve without authorization",
        }
        res = client.post("/policies/approve", json=approve_payload)
        assert res.status_code == 403
        assert "GOVERNANCE_ROLE_REQUIRED" in res.json()["detail"]

    def test_12_no_self_approval_enforced(self, client: TestClient):
        # Even if role is SECURITY_ADMIN, if actor is same as proposer, must be rejected
        # Propose a change as security-admin-demo
        prop_res = client.post(
            "/policies/propose",
            json={
                "target": "gpa",
                "is_field_override": True,
                "proposed_action": "GENERALIZE",
                "reason": "Proposing self approval test",
                "requested_by_role": "SECURITY_ADMIN",
                "requested_by_actor": "admin-self-tester",
            },
        )
        assert prop_res.status_code == 200
        chg_id = prop_res.json()["id"]

        # Attempt to approve with the exact same actor
        res = client.post(
            "/policies/approve",
            json={
                "change_id": chg_id,
                "reviewed_by_role": "SECURITY_ADMIN",
                "reviewed_by_actor": "admin-self-tester",  # SAME ACTOR -> BLOCKED
                "review_reason": "Approving my own proposal",
            },
        )
        assert res.status_code == 409
        assert "SELF_APPROVAL_BLOCKED" in res.json()["detail"]

    def test_13_security_admin_can_reject_change(self, client: TestClient):
        prop_res = client.post(
            "/policies/propose",
            json={
                "target": "bank_account",
                "is_field_override": True,
                "proposed_action": "NONE",
                "reason": "Unsafe proposal to test rejection",
                "requested_by_role": "ANALYST",
                "requested_by_actor": "analyst-tester",
            },
        )
        chg_id = prop_res.json()["id"]

        reject_res = client.post(
            "/policies/reject",
            json={
                "change_id": chg_id,
                "reviewed_by_role": "SECURITY_ADMIN",
                "reviewed_by_actor": "security-admin-demo",
                "review_reason": "Bank accounts must always be encrypted/masked",
            },
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["status"] == "REJECTED"

    def test_14_cannot_approve_already_rejected_request(self, client: TestClient):
        changes = client.get("/policy-changes").json()
        rejected = [c for c in changes if c["status"] == "REJECTED"]
        assert len(rejected) > 0
        chg_id = rejected[0]["id"]

        res = client.post(
            "/policies/approve",
            json={
                "change_id": chg_id,
                "reviewed_by_role": "SECURITY_ADMIN",
                "reviewed_by_actor": "security-admin-demo",
                "review_reason": "Trying to approve rejected item",
            },
        )
        assert res.status_code == 409
        assert "CHANGE_ALREADY_REVIEWED" in res.json()["detail"]

    def test_15_nonexistent_change_request_returns_404(self, client: TestClient):
        res = client.post(
            "/policies/approve",
            json={
                "change_id": "CHG-9999",
                "reviewed_by_role": "SECURITY_ADMIN",
                "reviewed_by_actor": "security-admin-demo",
                "review_reason": "Test non existent",
            },
        )
        assert res.status_code == 404
        assert "CHANGE_NOT_FOUND" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Versioning, Diff, and Publication Impact (Tests 16-21)
# ---------------------------------------------------------------------------

class TestPolicyVersioningAndDiff:
    def test_16_security_admin_approval_creates_new_version(self, client: TestClient):
        # Find the pending change for phone -> GENERALIZE proposed by engineer-demo
        changes = client.get("/policy-changes").json()
        pending = [c for c in changes if c["status"] == "PENDING" and c["proposed_change"]["target"] == "phone"]
        assert len(pending) > 0
        chg = pending[0]

        approve_res = client.post(
            "/policies/approve",
            json={
                "change_id": chg["id"],
                "reviewed_by_role": "SECURITY_ADMIN",
                "reviewed_by_actor": "security-admin-demo",
                "review_reason": "Approved for testing aggregate statistics",
            },
        )
        assert approve_res.status_code == 200
        new_version = approve_res.json()
        assert new_version["version"] == "v1.1"
        assert new_version["status"] == "ACTIVE"
        assert new_version["parent_version"] == "v1.0"
        assert new_version["policy_snapshot"]["field_overrides"]["phone"] == "GENERALIZE"

    def test_17_historical_version_v1_0_remains_unchanged(self, client: TestClient):
        versions = client.get("/policies/versions").json()
        v1_0 = next(v for v in versions if v["version"] == "v1.0")
        assert v1_0["policy_snapshot"]["field_overrides"]["phone"] == "MASK"
        assert v1_0["status"] == "SUPERSEDED"

    def test_18_active_policies_reflects_new_version(self, client: TestClient):
        active = client.get("/policies").json()
        assert active["version"] == "v1.1"
        assert active["field_overrides"]["phone"] == "GENERALIZE"

    def test_19_policy_diff_highlights_exact_changes(self, client: TestClient):
        diff_res = client.get("/policies/diff", params={"from_version": "v1.0", "to_version": "v1.1"})
        assert diff_res.status_code == 200
        diff_data = diff_res.json()
        assert diff_data["from_version"] == "v1.0"
        assert diff_data["to_version"] == "v1.1"
        assert diff_data["changes_count"] == 1

        phone_diff = next(d for d in diff_data["diffs"] if d["target"] == "phone")
        assert phone_diff["changed"] is True
        assert phone_diff["from_action"] == "MASK"
        assert phone_diff["to_action"] == "GENERALIZE"

    def test_20_publication_uses_new_policy_version(self, client: TestClient):
        # Under v1.1, phone requires GENERALIZE.
        # So a phone with actual GENERALIZE should now PASS the publication check!
        pub_check = client.post(
            "/publish-check",
            json={
                "dataset_name": "test_v1_1_compliance",
                "role": "ANALYST",
                "fields": [
                    {
                        "name": "phone",
                        "classification": "DIRECT_IDENTIFIER",
                        "actual_action": "GENERALIZE",  # Matches new v1.1 policy
                    }
                ],
            },
        )
        assert pub_check.status_code == 200
        res = pub_check.json()
        assert res["policy_version"] == "v1.1"
        assert res["decision"] == "ALLOW"
        assert res["policy_compliant"] is True


# ---------------------------------------------------------------------------
# 4. Rollback and Automatic Post-Rollback Revalidation (Tests 21-26)
# ---------------------------------------------------------------------------

class TestPolicyRollbackAndRevalidation:
    def test_21_non_security_admin_cannot_rollback(self, client: TestClient):
        res = client.post(
            "/policies/rollback",
            json={
                "target_version": "v1.0",
                "actor_role": "ANALYST",
                "actor_id": "analyst-demo",
                "reason": "Unauthorized rollback attempt",
            },
        )
        assert res.status_code == 403
        assert "GOVERNANCE_ROLE_REQUIRED" in res.json()["detail"]

    def test_22_cannot_rollback_to_nonexistent_version(self, client: TestClient):
        res = client.post(
            "/policies/rollback",
            json={
                "target_version": "v9.9",
                "actor_role": "SECURITY_ADMIN",
                "actor_id": "security-admin-demo",
                "reason": "Invalid target version",
            },
        )
        assert res.status_code == 404
        assert "POLICY_VERSION_NOT_FOUND" in res.json()["detail"]

    def test_23_cannot_rollback_to_currently_active_version(self, client: TestClient):
        active = client.get("/policies").json()
        res = client.post(
            "/policies/rollback",
            json={
                "target_version": active["version"],
                "actor_role": "SECURITY_ADMIN",
                "actor_id": "security-admin-demo",
                "reason": "Attempting to rollback to active version",
            },
        )
        assert res.status_code == 409
        assert "ROLLBACK_NOT_ALLOWED" in res.json()["detail"]

    def test_24_security_admin_executes_rollback_with_post_validation(self, client: TestClient):
        # Roll back from v1.1 to v1.0
        res = client.post(
            "/policies/rollback",
            json={
                "target_version": "v1.0",
                "actor_role": "SECURITY_ADMIN",
                "actor_id": "security-admin-demo",
                "reason": "Cohort research complete; reverting phone to mandatory MASK",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "rollback" in data["resulting_active_version"].lower()
        assert data["target_version"] == "v1.0"
        assert data["revalidation_status"] == "PASS"

        # Check audit trail recorded POLICY_ROLLBACK
        audit_res = client.get("/audit", params={"action": "POLICY_ROLLBACK"})
        assert audit_res.status_code == 200
        assert len(audit_res.json()) >= 1

    def test_25_post_rollback_policy_behavior_matches_target_v1_0(self, client: TestClient):
        # Active policy should now be the rollback version containing v1.0 rules
        active = client.get("/policies").json()
        assert "rollback" in active["version"].lower()
        # In v1.0, phone override was MASK
        assert active["field_overrides"]["phone"] == "MASK"

        # Under rolled back policy, phone with GENERALIZE should now be BLOCKED again!
        pub_check = client.post(
            "/publish-check",
            json={
                "dataset_name": "test_post_rollback",
                "role": "ANALYST",
                "fields": [
                    {
                        "name": "phone",
                        "classification": "DIRECT_IDENTIFIER",
                        "actual_action": "GENERALIZE",
                    }
                ],
            },
        )
        assert pub_check.status_code == 200
        res = pub_check.json()
        assert res["decision"] == "BLOCK"
        assert "phone" in str(res["reasons"])

    def test_26_history_is_preserved_after_rollback(self, client: TestClient):
        versions = client.get("/policies/versions").json()
        version_tags = [v["version"] for v in versions]
        assert "v1.0" in version_tags
        assert "v1.1" in version_tags
        assert any("rollback" in tag for tag in version_tags)


# ---------------------------------------------------------------------------
# 5. Database Privacy Requirement (Tests 27-30)
# ---------------------------------------------------------------------------

class TestDatabasePrivacyNoRawPII:
    """
    Scans relevant SQLite tables to prove that raw synthetic PII is never stored.
    Only metadata, field names, classifications, decisions, and hash digests are stored.
    """
    @pytest.mark.asyncio
    async def test_27_no_raw_pii_in_audit_events_table(self):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM audit_events")
            rows = await cursor.fetchall()
            forbidden_raw_values = [
                "student001@example.edu",
                "john.doe@university.edu",
                "+91-9876543210",
                "+1-555-0199",
                "987654321",
                "Jane Doe",
                "SecretPass123",
            ]
            for row in rows:
                row_str = " ".join(str(val) for val in row)
                for secret in forbidden_raw_values:
                    assert secret not in row_str, f"Privacy violation: Found raw value '{secret}' in audit_events!"
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_28_no_raw_pii_in_policy_versions_table(self):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM policy_versions")
            rows = await cursor.fetchall()
            forbidden_raw_values = [
                "student001@example.edu",
                "+91-9876543210",
                "John Doe",
            ]
            for row in rows:
                row_str = " ".join(str(val) for val in row)
                for secret in forbidden_raw_values:
                    assert secret not in row_str, f"Privacy violation: Found raw value '{secret}' in policy_versions!"
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_29_no_raw_pii_in_policy_change_requests_table(self):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM policy_change_requests")
            rows = await cursor.fetchall()
            forbidden_raw_values = [
                "student001@example.edu",
                "+91-9876543210",
                "John Doe",
            ]
            for row in rows:
                row_str = " ".join(str(val) for val in row)
                for secret in forbidden_raw_values:
                    assert secret not in row_str, f"Privacy violation: Found raw value '{secret}' in policy_change_requests!"
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_30_no_raw_pii_in_publication_attempts_table(self):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM publication_attempts")
            rows = await cursor.fetchall()
            forbidden_raw_values = [
                "student001@example.edu",
                "+91-9876543210",
                "John Doe",
            ]
            for row in rows:
                row_str = " ".join(str(val) for val in row)
                for secret in forbidden_raw_values:
                    assert secret not in row_str, f"Privacy violation: Found raw value '{secret}' in publication_attempts!"
        finally:
            await db.close()
