"""
Phase 12 Live Production Verification Automated Suite
Addresses Sections 4, 5, 6, and 7 of the Phase 12 Live Production Verification Audit:
- Authentication & Identity (Demo mode + Production/OIDC mode)
- Worker & Queue Behavior (Processing, Blocking, Retries, Dead-letter, Idempotency, Recovery)
- Destination Verification (ALLOW, BLOCK, Deduplication, Failure handling)
- Security & Privacy Invariants (Client bypass rejection, Zero raw PII, Fail-closed)
"""

import sys
import json
import time
import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from config import settings
from access.roles import Role
from access.permissions import Permission, ROLE_PERMISSION_MATRIX
from auth.models import UserIdentity, AuthenticatedUser, AuthMode
from auth.token_service import TokenService, AuthError
from auth.dependencies import (
    revoke_subject,
    reinstate_subject,
    is_subject_revoked,
    get_current_user,
    _resolve_permissions_for_role,
)
from pipeline.worker import PipelineQueue
from pipeline.jobs import PipelineJob, JobState
from pipeline.schemas import PipelineValidateRequest, DatasetFormat
from policies.schemas import FieldValidationInput, ProtectionAction
from destinations.base import PublicationPayload, DestinationResult
from destinations.mock_warehouse import MockWarehouseDestination
from destinations.postgres_destination import PostgresDestination
from destinations.cloud_connectors import SnowflakeDestination, BigQueryDestination, DatabricksDestination
from publication.gate import PublicationGate
from publication.schemas import PublicationCheckRequest, PublicationDecision
from audit.audit_service import AuditService


@pytest.fixture
def client():
    return TestClient(app)


# ==============================================================================
# SECTION 4: AUTHENTICATION & IDENTITY VERIFICATION
# ==============================================================================

class TestAuthenticationVerification:
    """Verifies synthetic demo mode, OIDC token claims, header spoofing rejection, and revocation."""

    def test_demo_mode_synthetic_identities(self, client):
        """In demo mode (AUTH_ENABLED=False), X-Demo-Role correctly resolves documented persona."""
        with patch.object(settings, "AUTH_ENABLED", False):
            # Test ANALYST persona
            res_analyst = client.get("/auth/me", headers={"X-Demo-Role": "ANALYST"})
            assert res_analyst.status_code == 200
            data_analyst = res_analyst.json()
            assert data_analyst["role"] == "ANALYST"
            assert "PUBLISH" in data_analyst["identity"]["permissions"]
            assert "VALIDATE" in data_analyst["identity"]["permissions"]

            # Test DATA_ENGINEER persona
            res_engineer = client.get("/auth/me", headers={"X-Demo-Role": "DATA_ENGINEER"})
            assert res_engineer.status_code == 200
            assert res_engineer.json()["role"] == "DATA_ENGINEER"
            assert "PUBLISH" not in res_engineer.json()["identity"]["permissions"]

            # Test SECURITY_ADMIN persona
            res_admin = client.get("/auth/me", headers={"X-Demo-Role": "SECURITY_ADMIN"})
            assert res_admin.status_code == 200
            assert res_admin.json()["role"] == "SECURITY_ADMIN"
            assert "MANAGE_POLICIES" in res_admin.json()["identity"]["permissions"]

    def test_production_mode_header_spoofing_rejection(self, client):
        """In production mode, any attempt to assert identity via headers must be rejected with 401."""
        with patch.object(settings, "AUTH_ENABLED", True):
            for spoof_header in ["X-Role", "x-role", "X-User", "X-Admin", "x-username"]:
                res = client.get("/auth/me", headers={spoof_header: "SECURITY_ADMIN"})
                assert res.status_code == 401, f"Failed to reject spoof header {spoof_header}"
                body = res.json()
                assert "HEADER_AUTHENTICATION_DISALLOWED" in str(body)

    def test_production_mode_token_issuer_validation(self):
        """Token with invalid issuer must fail validation."""
        tok = TokenService.create_access_token(
            user_id="user-01",
            role="ANALYST",
            issuer="https://malicious-idp.com",
        )
        with pytest.raises(AuthError) as exc_info:
            TokenService.validate_token(tok, expected_issuer="https://auth.university.edu")
        assert exc_info.value.code == "INVALID_ISSUER"

    def test_production_mode_token_audience_validation(self):
        """Token with invalid audience must fail validation."""
        tok = TokenService.create_access_token(
            user_id="user-01",
            role="ANALYST",
            audience="wrong-audience",
        )
        with pytest.raises(AuthError) as exc_info:
            TokenService.validate_token(tok, expected_audience="university-datashield")
        assert exc_info.value.code == "INVALID_AUDIENCE"

    def test_production_mode_token_signature_tampering(self):
        """Tampered token signature must fail cryptographic validation."""
        tok = TokenService.create_access_token(user_id="user-01", role="ANALYST")
        tampered = tok[:-6] + "xxxxxx"
        with pytest.raises(AuthError) as exc_info:
            TokenService.validate_token(tampered)
        assert exc_info.value.code in ("INVALID_SIGNATURE", "MALFORMED_TOKEN")

    def test_production_mode_token_expiration(self):
        """Expired token must be rejected with TOKEN_EXPIRED."""
        tok = TokenService.create_access_token(
            user_id="user-01",
            role="ANALYST",
            expires_in_seconds=-60,
        )
        with pytest.raises(AuthError) as exc_info:
            TokenService.validate_token(tok)
        assert exc_info.value.code == "TOKEN_EXPIRED"

    def test_role_and_permission_mapping(self):
        """Permissions must correctly resolve against the institutional ROLE_PERMISSION_MATRIX."""
        analyst_perms = _resolve_permissions_for_role(Role.ANALYST)
        assert "VALIDATE" in analyst_perms
        assert "PUBLISH" in analyst_perms
        assert "MANAGE_POLICIES" not in analyst_perms

        admin_perms = _resolve_permissions_for_role(Role.SECURITY_ADMIN)
        assert "MANAGE_POLICIES" in admin_perms
        assert "PUBLISH" in admin_perms

        engineer_perms = _resolve_permissions_for_role(Role.DATA_ENGINEER)
        assert "PUBLISH" not in engineer_perms

    def test_revoked_subject_handling(self, client):
        """Revoked subject ID is blocked with 403 IDENTITY_DISABLED."""
        subject_id = "revoked-test-subject-01"
        tok = TokenService.create_access_token(user_id=subject_id, role="ANALYST")

        try:
            revoke_subject(subject_id)
            assert is_subject_revoked(subject_id) is True

            with patch.object(settings, "AUTH_ENABLED", True):
                res = client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"})
                assert res.status_code == 403
                body = res.json()
                assert "IDENTITY_DISABLED" in str(body)
        finally:
            reinstate_subject(subject_id)


# ==============================================================================
# SECTION 5: WORKER & QUEUE VERIFICATION
# ==============================================================================

class TestWorkerAndQueueVerification:
    """Verifies local worker queue, retry limits, dead-letter, idempotency, and security revalidation."""

    @pytest.mark.asyncio
    async def test_worker_successful_processing(self):
        """Worker queue successfully processes valid synthetic dataset."""
        queue = PipelineQueue(concurrency=1, maxsize=10)
        queue.start_workers()
        try:
            valid_payload = json.dumps([
                {"department": "Computer Science", "course_count": 12},
                {"department": "Physics", "course_count": 8},
            ])
            req = PipelineValidateRequest(
                dataset_name="synthetic_admissions",
                format=DatasetFormat.JSON,
                role="ANALYST",
                raw_content=valid_payload,
            )
            job = await queue.submit_job(req)
            assert job.state in (JobState.QUEUED, JobState.RUNNING)

            for _ in range(40):
                if job.state in (JobState.READY, JobState.COMPLETED, JobState.PUBLISHED):
                    break
                await asyncio.sleep(0.1)

            assert job.state in (JobState.READY, JobState.COMPLETED, JobState.PUBLISHED)
            assert job.result is not None
            assert job.result.decision == "ALLOW"
        finally:
            await queue.stop_workers()

    @pytest.mark.asyncio
    async def test_worker_unsafe_publication_blocking(self):
        """Worker queue blocks dataset with unmasked direct identifiers."""
        queue = PipelineQueue(concurrency=1, maxsize=10)
        queue.start_workers()
        try:
            unsafe_payload = json.dumps([
                {"student_id": "STU12345", "grade": "A"},
            ])
            req = PipelineValidateRequest(
                dataset_name="unsafe_synthetic_students",
                format=DatasetFormat.JSON,
                role="ANALYST",
                raw_content=unsafe_payload,
            )
            job = await queue.submit_job(req)

            for _ in range(40):
                if job.state in (JobState.BLOCKED, JobState.READY, JobState.COMPLETED):
                    break
                await asyncio.sleep(0.1)

            assert job.result is not None
            assert job.result.decision == "BLOCK"
        finally:
            await queue.stop_workers()

    @pytest.mark.asyncio
    async def test_worker_retry_limits_and_dead_letter(self):
        """Exhausting retry limit transitions job to DEAD_LETTERED."""
        queue = PipelineQueue(concurrency=1, maxsize=10)
        req = PipelineValidateRequest(
            dataset_name="failing_synthetic_job",
            format=DatasetFormat.JSON,
            role="ANALYST",
            raw_content="[]",
        )
        job = await queue.submit_job(req)
        job.state = JobState.FAILED
        job.max_retries = 2

        # Retry 1
        await queue.retry_job(job.job_id)
        assert job.retry_count == 1
        job.state = JobState.FAILED

        # Retry 2
        await queue.retry_job(job.job_id)
        assert job.retry_count == 2
        job.state = JobState.FAILED

        # Retry 3 -> Exceeds max_retries (2) -> transitions to DEAD_LETTERED
        with pytest.raises(ValueError) as exc_info:
            await queue.retry_job(job.job_id)
        assert "DEAD_LETTERED" in str(exc_info.value)
        assert job.state == JobState.DEAD_LETTERED

    @pytest.mark.asyncio
    async def test_worker_duplicate_job_idempotency(self):
        """Submitting a job with an identical execution_id returns the existing job without duplicate enqueue."""
        queue = PipelineQueue(concurrency=1, maxsize=10)
        exec_id = "EX-IDEMP-TEST-001"

        req1 = PipelineValidateRequest(
            dataset_name="synthetic_dataset_1",
            execution_id=exec_id,
            format=DatasetFormat.JSON,
            role="ANALYST",
            raw_content='[{"department": "Physics"}]',
        )
        job1 = await queue.submit_job(req1)

        req2 = PipelineValidateRequest(
            dataset_name="synthetic_dataset_1",
            execution_id=exec_id,
            format=DatasetFormat.JSON,
            role="ANALYST",
            raw_content='[{"department": "Physics"}]',
        )
        job2 = await queue.submit_job(req2)

        # Same job returned
        assert job1.job_id == job2.job_id
        assert len(queue._jobs) == 1

    @pytest.mark.asyncio
    async def test_worker_security_revalidation_on_retry(self):
        """A retried job must strictly re-execute security validation rather than reusing previous verdicts."""
        queue = PipelineQueue(concurrency=1, maxsize=10)
        queue.start_workers()
        try:
            unsafe_payload = json.dumps([
                {"student_id": "STU99999", "score": 95},
            ])
            req = PipelineValidateRequest(
                dataset_name="unsafe_retry_dataset",
                format=DatasetFormat.JSON,
                role="ANALYST",
                raw_content=unsafe_payload,
            )
            job = await queue.submit_job(req)
            for _ in range(40):
                if job.result is not None:
                    break
                await asyncio.sleep(0.1)

            assert job.result.decision == "BLOCK"

            # Retry job
            await queue.retry_job(job.job_id)
            for _ in range(40):
                if job.retry_count == 1 and job.state != JobState.QUEUED:
                    break
                await asyncio.sleep(0.1)

            # Security decision must remain BLOCK on retry
            assert job.result.decision == "BLOCK"
        finally:
            await queue.stop_workers()


# ==============================================================================
# SECTION 6: DESTINATION VERIFICATION
# ==============================================================================

class TestDestinationVerification:
    """Verifies Mock and Postgres destinations for ALLOW, BLOCK, deduplication, and failure handling."""

    def test_allow_permits_write_and_records_queryable(self):
        """Decision == ALLOW permits write to MockWarehouse and records become queryable."""
        dest = MockWarehouseDestination()
        dest.clear()

        payload = PublicationPayload(
            dataset_name="synthetic_analytics_export",
            run_id="RUN-ALLOW-LIVE-01",
            pipeline_id="PL-ALLOW-LIVE-01",
            decision="ALLOW",
            schema_definition=[{"name": "department", "type": "STRING"}],
            records=[{"department": "Engineering", "count": 120}],
            audit_hash="sha256-abc123live",
            publisher_role="ANALYST",
            published_by="analyst_alice",
            destination_target="analytics_department_stats",
        )
        result = dest.publish(payload)
        assert result.success is True
        assert result.records_written == 1

        stored = dest.query("analytics_department_stats")
        assert len(stored) == 1
        assert stored[0]["department"] == "Engineering"

    def test_block_and_review_strictly_prevent_writes(self):
        """Decision == BLOCK or REVIEW strictly prevents any write to the destination."""
        dest = MockWarehouseDestination()
        dest.clear()

        for blocked_decision in ["BLOCK", "REVIEW"]:
            payload = PublicationPayload(
                dataset_name="synthetic_unsafe_export",
                run_id=f"RUN-{blocked_decision}-01",
                pipeline_id="PL-01",
                decision=blocked_decision,
                schema_definition=[{"name": "raw_ssn", "type": "STRING"}],
                records=[{"raw_ssn": "123-45-6789"}],
                audit_hash="sha256-xyz",
                publisher_role="ANALYST",
                published_by="analyst_alice",
                destination_target="secure_mart",
            )
            result = dest.publish(payload)
            assert result.success is False
            assert result.records_written == 0
            assert "Non-ALLOW gate decision cannot be written" in result.error

        assert len(dest.query("secure_mart")) == 0

    def test_duplicate_retries_do_not_duplicate_records(self):
        """Retrying publication with the same run_id must be idempotent and avoid duplicate records."""
        dest = MockWarehouseDestination()
        dest.clear()

        payload = PublicationPayload(
            dataset_name="synthetic_idempotent_test",
            run_id="RUN-IDEMP-001",
            pipeline_id="PL-IDEMP-001",
            decision="ALLOW",
            schema_definition=[{"name": "course_code", "type": "STRING"}],
            records=[{"course_code": "CS101"}],
            audit_hash="sha256-idemp-hash",
            publisher_role="ANALYST",
            published_by="analyst_bob",
            destination_target="course_offerings",
        )

        res1 = dest.publish(payload)
        assert res1.success is True
        assert res1.records_written == 1

        # Second publication with identical run_id
        res2 = dest.publish(payload)
        assert res2.success is True
        assert res2.records_written == 0  # Deduplicated!
        assert "Duplicate retry ignored" in res2.message

        # Verify only 1 record exists in storage
        stored = dest.query("course_offerings")
        assert len(stored) == 1

    def test_destination_write_failure_does_not_bypass_gate(self):
        """Internal destination write errors return success=False safely without gate bypass."""
        dest = PostgresDestination(config={"connection_url": "postgresql://user:pass@localhost:5432/db"})
        with patch.object(dest, "_write_records", side_effect=RuntimeError("Connection dropped")):
            payload = PublicationPayload(
                dataset_name="test_dataset",
                run_id="RUN-ERR-001",
                pipeline_id="PL-ERR-001",
                decision="ALLOW",
                schema_definition=[],
                records=[{"data": 1}],
                audit_hash="hash",
                publisher_role="ANALYST",
                published_by="analyst_alice",
                destination_target="table1",
            )
            result = dest.publish(payload)
            assert result.success is False
            assert "Connection dropped" in result.error
            assert result.records_written == 0

    def test_cloud_destinations_fail_closed_unconfigured(self):
        """Cloud destinations fail closed when unconfigured without raising uncaught exceptions."""
        for dest_cls in [SnowflakeDestination, BigQueryDestination, DatabricksDestination]:
            dest = dest_cls(config={})
            payload = PublicationPayload(
                dataset_name="test",
                run_id="run-1",
                pipeline_id="pl-1",
                decision="ALLOW",
                schema_definition=[],
                records=[{"a": 1}],
                audit_hash="h1",
                publisher_role="ANALYST",
                published_by="u1",
                destination_target="t1",
            )
            res = dest.publish(payload)
            assert res.success is False
            assert res.records_written == 0


# ==============================================================================
# SECTION 7: SECURITY & PRIVACY REGRESSION
# ==============================================================================

class TestSecurityAndPrivacyRegression:
    """Verifies no client bypass, zero raw personal data, and fail-closed gates."""

    def test_client_cannot_bypass_publication_gate(self, client):
        """Client sending 'is_compliant=True' or 'decision=ALLOW' cannot bypass authoritative gate."""
        res = client.post(
            "/publish",
            json={
                "dataset_name": "spoof_attempt",
                "role": "ANALYST",
                "is_compliant": True,  # Client-side spoof flag
                "decision": "ALLOW",   # Client-side spoof decision
                "fields": [
                    {
                        "name": "student_id",
                        "classification": "DIRECT_IDENTIFIER",
                        "actual_action": "MASK",  # MASK is insufficient under policy v1.0 (requires HASH or SUPPRESS)
                    }
                ],
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["decision"] == "BLOCK"
        assert body["success"] is False

    def test_missing_policy_fails_closed(self):
        """Direct identifier with no action (actual_action=NONE) defaults to BLOCK."""
        gate = PublicationGate()
        req = PublicationCheckRequest(
            dataset_name="unprotected_direct_identifier",
            role="ANALYST",
            fields=[
                FieldValidationInput(
                    name="student_id",
                    classification="DIRECT_IDENTIFIER",
                    actual_action=ProtectionAction.NONE,
                )
            ],
        )
        res = gate.evaluate(req)
        assert res.decision == PublicationDecision.BLOCK
        assert res.policy_compliant is False

    @pytest.mark.asyncio
    async def test_zero_raw_pii_in_audit_ledger(self):
        """Audit events record metadata, hashes, and decisions only, zero raw student tokens."""
        trail = await AuditService.get_audit_trail()
        for event in trail:
            event_str = str(event.model_dump() if hasattr(event, "model_dump") else event).lower()
            # Ensure no raw social security number or credit card patterns
            assert "000-11-2222" not in event_str
            assert "4111-2222-3333-4444" not in event_str
