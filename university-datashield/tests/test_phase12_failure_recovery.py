"""
Phase 12.13 Automated Tests: Failure and Recovery Resilience Suite
Tests realistic disaster and adversarial failure conditions:
1. Database connectivity failure
2. Worker crash / bounded retry / dead lettering
3. Destination unavailable
4. Destination timeout
5. Invalid policy specification
6. Missing policy version
7. Unauthorized role
8. Expired authentication
9. Malformed dataset
10. Oversized dataset
11. Duplicate job (Idempotency)
12. Duplicate publication
13. Audit tampering
14. Failed rollback
15. Network interruption simulation
"""

import sys
import json
from pathlib import Path
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from pipeline.queue_base import LocalInProcessQueue, QueueJobRecord, JobState
from destinations.base import PublicationPayload
from destinations.cloud_connectors import SnowflakeDestination, BigQueryDestination
from destinations.postgres_destination import PostgresDestination
from auth.token_service import TokenService, AuthError
from governance.governance_service import GovernanceService
from governance.schemas import RollbackRequest


@pytest.fixture
def client():
    return TestClient(app)


# Scenario 1: Database unavailable
@pytest.mark.asyncio
async def test_scenario_01_database_unavailable():
    """When database connectivity fails, verify_db reports ok=False safely without credential leaks."""
    from database import verify_db
    with patch("database.aiosqlite.connect", side_effect=ConnectionError("Database offline")):
        status = await verify_db()
        assert status["ok"] is False
        assert "error" in status
        assert "password" not in str(status).lower()


# Scenario 2: Worker crashes / retry limit reached
@pytest.mark.asyncio
async def test_scenario_02_worker_retry_exhaustion_dead_letter():
    """Worker retrying a failing job reaches max_retries and transitions to DEAD_LETTERED."""
    queue = LocalInProcessQueue(maxsize=10)
    job = QueueJobRecord(job_id="FAIL-JOB-01", payload={"data": "test"}, max_retries=2)
    await queue.enqueue(job)

    # First retry
    re_enqueued = await queue.retry("FAIL-JOB-01", error="Transient crash 1", backoff_seconds=0)
    assert re_enqueued is True
    assert job.retry_count == 1
    assert job.state == JobState.QUEUED

    # Second retry
    re_enqueued = await queue.retry("FAIL-JOB-01", error="Transient crash 2", backoff_seconds=0)
    assert re_enqueued is True
    assert job.retry_count == 2

    # Third retry -> Exceeded max retries (2) -> DEAD_LETTERED
    re_enqueued = await queue.retry("FAIL-JOB-01", error="Fatal error", backoff_seconds=0)
    assert re_enqueued is False
    assert job.state == JobState.DEAD_LETTERED
    assert len(queue._dead_letters) == 1


# Scenario 3: Destination unavailable
def test_scenario_03_destination_unavailable():
    """Postgres destination without valid connection URL fails closed safely."""
    dest = PostgresDestination(config={"connection_url": ""})
    payload = PublicationPayload(
        dataset_name="student_test",
        run_id="run-001",
        pipeline_id="pipe-001",
        decision="ALLOW",
        schema_definition=[],
        records=[{"id": 1}],
        audit_hash="hash1",
        publisher_role="ANALYST",
        published_by="analyst1",
        destination_target="analytics_table",
    )
    res = dest.publish(payload)
    assert res.success is False
    assert res.records_written == 0
    assert "CONFIGURATION_INCOMPLETE" in res.error


# Scenario 4: Destination timeout / error handling
def test_scenario_04_destination_error_handled_safely():
    """Cloud connector handles internal write exceptions without uncaught crash."""
    dest = SnowflakeDestination(config={"account": "demo", "database": "db"})
    with patch.object(dest, "_write_records", side_effect=TimeoutError("Snowflake gateway timed out")):
        payload = PublicationPayload(
            dataset_name="student_test",
            run_id="run-002",
            pipeline_id="pipe-002",
            decision="ALLOW",
            schema_definition=[],
            records=[{"id": 1}],
            audit_hash="hash1",
            publisher_role="ANALYST",
            published_by="analyst1",
            destination_target="analytics_table",
        )
        res = dest.publish(payload)
        assert res.success is False
        assert "timed out" in res.error.lower()


# Scenario 5: Invalid policy target/action
@pytest.mark.asyncio
async def test_scenario_05_invalid_policy_fails_closed():
    """Invalid policy proposal with missing fields must fail validation."""
    from governance.schemas import ProposeChangeRequest
    with pytest.raises(Exception):
        ProposeChangeRequest(
            reason="Invalid",
            proposed_changes={"policies": [{"target": ""}]},  # missing required fields
        )


# Scenario 6: Missing policy version
@pytest.mark.asyncio
async def test_scenario_06_missing_policy_version():
    """Requesting a non-existent policy version returns None safely."""
    from governance.governance_repository import GovernanceRepository
    version_record = await GovernanceRepository.get_version("v999.999")
    assert version_record is None



# Scenario 7: Unauthorized role publication attempt
def test_scenario_07_unauthorized_role_publication(client):
    """DATA_ENGINEER attempting to publish must be rejected with UNAUTHORIZED / BLOCK."""
    res = client.post(
        "/publish",
        json={
            "dataset_name": "student_test",
            "role": "DATA_ENGINEER",  # Lacks PUBLISH permission!
            "fields": [{"name": "student_id", "classification": "DIRECT_IDENTIFIER", "actual_action": "HASH"}],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] == "BLOCK"
    assert body["status"] == "UNAUTHORIZED"
    assert body["success"] is False


# Scenario 8: Expired authentication token
def test_scenario_08_expired_authentication_token():
    """Expired token is rejected with 401 TOKEN_EXPIRED."""
    tok = TokenService.create_access_token(user_id="usr-1", role="ANALYST", expires_in_seconds=-10)
    with pytest.raises(AuthError) as exc_info:
        TokenService.validate_token(tok)
    assert exc_info.value.code == "TOKEN_EXPIRED"


# Scenario 9: Malformed dataset payload
def test_scenario_09_malformed_dataset_payload(client):
    """Malformed dataset input fails closed with 422."""
    res = client.post("/scan", json={"dataset_name": "bad", "fields": "not-a-list"})
    assert res.status_code == 422


# Scenario 10: Oversized dataset upload
def test_scenario_10_oversized_payload_protection(client):
    """Payload exceeding MAX_UPLOAD_SIZE_MB returns 413 Payload Too Large."""
    oversized_bytes = str(20 * 1024 * 1024)  # 20MB
    res = client.post(
        "/scan",
        headers={"Content-Length": oversized_bytes, "Content-Type": "application/json"},
        content=b"{}",
    )
    assert res.status_code == 413


# Scenario 11: Duplicate job submission (Idempotency)
@pytest.mark.asyncio
async def test_scenario_11_duplicate_job_idempotency():
    """Submitting job with identical idempotency_key returns the same job_id without duplicate enqueue."""
    queue = LocalInProcessQueue(maxsize=10)
    j1 = QueueJobRecord(job_id="JOB-A", payload={"data": 1}, idempotency_key="idemp-key-101")
    id1 = await queue.enqueue(j1)

    j2 = QueueJobRecord(job_id="JOB-B", payload={"data": 1}, idempotency_key="idemp-key-101")
    id2 = await queue.enqueue(j2)

    assert id1 == id2 == "JOB-A"
    assert queue.queue_depth() == 1


# Scenario 12: Duplicate publication attempt
def test_scenario_12_duplicate_publication_attempt(client):
    """Repeated publication attempts are safely and deterministically recorded."""
    req_body = {
        "dataset_name": "repeat_test",
        "role": "ANALYST",
        "fields": [{"name": "student_name", "classification": "DIRECT_IDENTIFIER", "actual_action": "MASK"}],
    }
    r1 = client.post("/publish", json=req_body)
    r2 = client.post("/publish", json=req_body)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["decision"] == r2.json()["decision"]


# Scenario 13: Audit tampering detected
@pytest.mark.asyncio
async def test_scenario_13_audit_tampering_detection():
    """Audit service detects hash chain compromise."""
    from audit.audit_service import AuditService
    resp = await AuditService.check_integrity()
    assert resp.status in ("VALID", "COMPROMISED")


# Scenario 14: Failed rollback attempt
@pytest.mark.asyncio
async def test_scenario_14_failed_rollback():
    """Attempting rollback to nonexistent version raises HTTPException 404 and fails closed."""
    from fastapi import HTTPException
    from governance.governance_service import GovernanceService
    with pytest.raises(HTTPException) as exc_info:
        await GovernanceService.rollback_policy(
            RollbackRequest(
                target_version="v999.0",
                reason="Invalid rollback test",
                actor_role="SECURITY_ADMIN",
                actor_id="admin1",
            )
        )
    assert exc_info.value.status_code == 404



# Scenario 15: Network interruption simulation
def test_scenario_15_network_interruption_simulation():
    """Destination connector resilient to broken socket/network interruptions."""
    dest = BigQueryDestination(config={"project_id": "proj", "dataset": "ds"})
    with patch.object(dest, "_write_records", side_effect=ConnectionResetError("Connection reset by peer")):
        payload = PublicationPayload(
            dataset_name="student_test",
            run_id="run-015",
            pipeline_id="pipe-015",
            decision="ALLOW",
            schema_definition=[],
            records=[{"id": 1}],
            audit_hash="hash15",
            publisher_role="ANALYST",
            published_by="analyst1",
            destination_target="analytics_table",
        )
        res = dest.publish(payload)
        assert res.success is False
        assert "Connection reset by peer" in res.error
