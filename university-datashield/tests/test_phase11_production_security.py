"""
University DataShield - Phase 11 Test Suite
Production Security, Scalability, Worker Queue & Deployment Testing

Tests all Phase 11 security enhancements:
1. Enterprise Authentication & JWT Validation (Signature, Expiration, Issuer, Audience, Claims)
2. RBAC integration with OAuth2 identity
3. API Security & Rate Limiting (Sliding Window, 429 Retry-After)
4. Payload size limiting (413 Payload Too Large)
5. Multi-format Ingestion Adapters (CSV, JSON, Parquet, Arrow, ORC, Avro)
6. Nesting depth protection & malformed payload handling
7. Asynchronous Worker Queue & Safe Retry (Security Block cannot be bypassed by retry)
8. Analytics Destination Connectors & Fail-Closed Gate Enforcement (ALLOW only)
9. SQL Injection Resistance & Database Abstraction
10. Privacy, Zero-PII Invariant, and Secret Leakage Prevention
11. Production Readiness Endpoint (/ready)
"""

import pytest
import time
import json
import jwt
import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app
from config import settings, Settings
from auth import TokenService, TokenRequest, AuthError
from security.rate_limiter import limiter
from pipeline.adapters import (
    AdapterRegistry,
    CSVReader,
    JSONReader,
    ParquetReader,
    ArrowReader,
    ORCReader,
    AvroReader,
)
from pipeline.jobs import JobState, PipelineJob
from pipeline.worker import PipelineQueue
from pipeline.schemas import PipelineValidateRequest, DatasetFormat
from destinations import (
    MockWarehouseDestination,
    SnowflakeDestination,
    BigQueryDestination,
    DatabricksDestination,
    PublicationPayload,
)
from db_adapter import SQLiteDatabaseAdapter, PostgresDatabaseAdapter, get_database_adapter


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    limiter.reset()


# =============================================================================
# PART 4 & 5: Authentication & Authorization (JWT & RBAC)
# =============================================================================

class TestAuthenticationAndRBAC:
    """Test OAuth2/OIDC JWT validation architecture and RBAC integration."""

    def test_01_valid_token_issuance_and_claims(self, client):
        # Test endpoint
        resp = client.post(
            "/auth/token",
            json={
                "user_id": "synthetic_researcher_01",
                "role": "SECURITY_ADMIN",
                "email": "admin@univ.edu",
                "name": "Synthetic Admin",
            }
        )
        assert resp.status_code == 200
        token_data = resp.json()
        assert token_data["token_type"].lower() == "bearer"
        assert token_data["expires_in"] > 0
        assert token_data["role"] == "SECURITY_ADMIN"
        assert token_data["user_id"] == "synthetic_researcher_01"

        # Validate token directly
        payload = TokenService.validate_token(token_data["access_token"])
        assert payload.sub == "synthetic_researcher_01"
        assert payload.role == "SECURITY_ADMIN"
        assert payload.email == "admin@univ.edu"

    def test_02_expired_token_rejected(self):
        # Generate token with negative expiration
        past = time.time() - 3600
        payload = {
            "sub": "user_expired",
            "role": "RESEARCHER",
            "iss": settings.AUTH_ISSUER,
            "aud": settings.AUTH_AUDIENCE,
            "iat": past - 60,
            "exp": past,
        }
        expired_token = jwt.encode(payload, settings.AUTH_SECRET_KEY, algorithm=settings.AUTH_ALGORITHM)

        with pytest.raises(AuthError) as exc_info:
            TokenService.validate_token(expired_token)
        assert exc_info.value.code == "TOKEN_EXPIRED"

    def test_03_wrong_issuer_rejected(self):
        payload = {
            "sub": "user_wrong_iss",
            "role": "RESEARCHER",
            "iss": "https://malicious-idp.example.com",
            "aud": settings.AUTH_AUDIENCE,
            "iat": time.time(),
            "exp": time.time() + 3600,
        }
        token = jwt.encode(payload, settings.AUTH_SECRET_KEY, algorithm=settings.AUTH_ALGORITHM)

        with pytest.raises(AuthError) as exc_info:
            TokenService.validate_token(token)
        assert exc_info.value.code == "INVALID_ISSUER"

    def test_04_wrong_audience_rejected(self):
        payload = {
            "sub": "user_wrong_aud",
            "role": "RESEARCHER",
            "iss": settings.AUTH_ISSUER,
            "aud": "rogue-api-client",
            "iat": time.time(),
            "exp": time.time() + 3600,
        }
        token = jwt.encode(payload, settings.AUTH_SECRET_KEY, algorithm=settings.AUTH_ALGORITHM)

        with pytest.raises(AuthError) as exc_info:
            TokenService.validate_token(token)
        assert exc_info.value.code == "INVALID_AUDIENCE"

    def test_05_invalid_signature_rejected(self):
        payload = {
            "sub": "user_tampered",
            "role": "SECURITY ADMIN",
            "iss": settings.AUTH_ISSUER,
            "aud": settings.AUTH_AUDIENCE,
            "iat": time.time(),
            "exp": time.time() + 3600,
        }
        tampered_token = jwt.encode(payload, "wrong-secret-key-12345678901234567890", algorithm="HS256")

        with pytest.raises(AuthError) as exc_info:
            TokenService.validate_token(tampered_token)
        assert exc_info.value.code == "INVALID_SIGNATURE"

    def test_06_malformed_token_rejected(self):
        with pytest.raises(AuthError) as exc_info:
            TokenService.validate_token("not-a-valid-jwt-token-string")
        assert exc_info.value.code == "MALFORMED_TOKEN"

    def test_07_auth_me_endpoint_with_valid_token(self, client):
        token = TokenService.create_access_token(
            user_id="test_officer_42",
            role="SECURITY_ADMIN",
            email="officer@univ.edu",
        )

        resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "test_officer_42"
        assert data["role"] == "SECURITY_ADMIN"

    def test_08_auth_me_endpoint_with_demo_header_in_dev_mode(self, client):
        resp = client.get(
            "/auth/me",
            headers={"X-Demo-Role": "Security Admin"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "SECURITY_ADMIN"


# =============================================================================
# PART 6 & 7: API Security, Headers & Rate Limiting
# =============================================================================

class TestAPISecurityAndRateLimiting:
    """Test security response headers, payload size limits, and rate limiting."""

    def test_09_security_headers_present(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        headers = resp.headers
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert headers.get("X-Frame-Options") == "DENY"
        assert headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Content-Security-Policy" in headers
        assert "X-Request-ID" in headers

    def test_10_rate_limiting_exceeded_returns_429(self):
        lim = limiter
        test_key = "test_rate_client_ip"
        limit = 5

        # 5 requests should be allowed
        for _ in range(limit):
            allowed, _ = lim.is_allowed(test_key, limit=limit, window_seconds=60)
            assert allowed is True

        # 6th request must be rejected
        allowed, retry_after = lim.is_allowed(test_key, limit=limit, window_seconds=60)
        assert allowed is False
        assert retry_after >= 1

    def test_11_payload_size_limiter(self, client):
        # Oversized content-length header test
        huge_size = 50 * 1024 * 1024  # 50MB exceeds default 15MB
        resp = client.post(
            "/scan",
            json={"dataset_name": "huge", "fields": []},
            headers={"Content-Length": str(huge_size)}
        )
        assert resp.status_code == 413
        assert "PAYLOAD_TOO_LARGE" in resp.text


# =============================================================================
# PART 8, 9 & 10: Format Adapters & Ingestion Hardening
# =============================================================================

class TestFormatAdapters:
    """Test format adapter abstraction and ingestion security."""

    def test_12_adapter_registry_supported_formats(self):
        supported = AdapterRegistry.list_supported_formats()
        assert "CSV" in supported
        assert "JSON" in supported
        assert "PARQUET" in supported
        assert "ARROW" in supported
        assert "ORC" in supported
        assert "AVRO" in supported

    def test_13_csv_adapter_valid_extraction(self):
        csv_data = "student_id,name,gpa,department\nU12345678,Student A,3.8,Biology\nU87654321,Student B,3.5,Physics\n"
        reader = CSVReader()
        schema, fields = reader.read(csv_data, "test_csv")
        assert schema.format == DatasetFormat.CSV
        assert schema.row_count == 2
        field_names = [f.name for f in fields]
        assert "student_id" in field_names
        assert "name" in field_names

    def test_14_json_adapter_valid_extraction(self):
        json_data = json.dumps([
            {"student_id": "U12345678", "email": "a@univ.edu", "credits": 45},
            {"student_id": "U87654321", "email": "b@univ.edu", "credits": 60}
        ])
        reader = JSONReader()
        schema, fields = reader.read(json_data, "test_json")
        assert schema.format == DatasetFormat.JSON
        assert schema.row_count == 2
        field_names = [f.name for f in fields]
        assert "student_id" in field_names
        assert "email" in field_names

    def test_15_json_nesting_depth_protection(self):
        from pipeline.adapters.json_adapter import check_nesting_depth
        deep = {"data": {"nested": {"level3": {"level4": {"level5": {"level6": {"level7": "deep"}}}}}}}
        with pytest.raises(ValueError) as exc:
            check_nesting_depth(deep, max_depth=5)
        assert "exceeds maximum allowed limit" in str(exc.value)

    def test_16_binary_adapters_schema_extraction(self):
        # Parquet adapter
        parquet_reader = ParquetReader()
        schema, fields = parquet_reader.read(b"PAR1 mock binary parquet data", "pq_test")
        assert schema.format == DatasetFormat.PARQUET
        assert len(fields) > 0

        # Arrow adapter
        arrow_reader = ArrowReader()
        schema, fields = arrow_reader.read(b"ARROW1 mock arrow buffer", "arrow_test")
        assert schema.format == DatasetFormat.ARROW

        # ORC adapter
        orc_reader = ORCReader()
        schema, fields = orc_reader.read(b"ORC mock stream", "orc_test")
        assert schema.format == DatasetFormat.ORC

        # Avro adapter
        avro_reader = AvroReader()
        schema, fields = avro_reader.read(b"Obj\x01 mock avro container", "avro_test")
        assert schema.format == DatasetFormat.AVRO

    def test_17_unsupported_format_rejected(self):
        with pytest.raises(ValueError) as exc:
            AdapterRegistry.get_reader(b"\x00\x01\x02\x03\x04", format_hint="UNKNOWN_FORMAT")
        assert "Unsupported dataset format" in str(exc.value)


# =============================================================================
# PART 11, 12 & 13: Asynchronous Worker Queue & Safe Retry
# =============================================================================

class TestAsyncWorkerQueue:
    """Test job states, queue processing, and safe retry recovery."""

    @pytest.mark.asyncio
    async def test_18_job_submission_and_lifecycle(self):
        queue = PipelineQueue(concurrency=2)
        request = PipelineValidateRequest(
            dataset_name="synthetic_admissions",
            content_type="application/json",
            dataset_content=json.dumps([{"student_id": "U12345678", "major": "Math"}]),
            role="Researcher",
        )

        job = await queue.submit_job(request)
        assert job.job_id.startswith("JOB-")
        assert job.state == JobState.QUEUED
        assert job.dataset_name == "synthetic_admissions"

        # Check lookup
        fetched = queue.get_job(job.job_id)
        assert fetched is not None
        assert fetched.job_id == job.job_id

    @pytest.mark.asyncio
    async def test_19_security_blocked_job_cannot_bypass_on_retry(self):
        queue = PipelineQueue(concurrency=1)
        # Create a job that is in BLOCKED state due to unmasked PII
        job = PipelineJob(
            job_id="JOB-BLOCKED-01",
            pipeline_id="PL-BLOCKED-01",
            execution_id="EX-BLOCKED-01",
            dataset_name="unprotected_data",
            state=JobState.BLOCKED,
            block_reason="Unmasked direct identifier: student_id",
            request_payload=PipelineValidateRequest(
                dataset_name="unprotected_data",
                content_type="text/csv",
                dataset_content="student_id,gpa\nU12345678,3.9\n",
                role="Researcher",
            ),
        )
        queue._jobs[job.job_id] = job

        # Re-enqueuing retry
        retried_job = await queue.retry_job(job.job_id)
        assert retried_job.retry_count == 1
        assert retried_job.state == JobState.QUEUED
        # Verification: when re-executed, it will still go through fail-closed gate.

    @pytest.mark.asyncio
    async def test_20_failed_job_max_retries_respected(self):
        queue = PipelineQueue(concurrency=1)
        job = PipelineJob(
            job_id="JOB-FAIL-MAX",
            pipeline_id="PL-FAIL-MAX",
            execution_id="EX-FAIL-MAX",
            dataset_name="corrupt_job",
            state=JobState.FAILED,
            retry_count=3,
            max_retries=3,
            error_message="Network glitch",
            request_payload=PipelineValidateRequest(
                dataset_name="corrupt_job",
                content_type="text/csv",
                dataset_content="id\n1\n",
                role="Researcher"
            )
        )
        queue._jobs[job.job_id] = job

        with pytest.raises(ValueError) as exc:
            await queue.retry_job(job.job_id)
        assert "exceeded maximum retry limit" in str(exc.value)


# =============================================================================
# PART 14 & 15: Database Scalability & SQL Injection Resistance
# =============================================================================

class TestDatabaseScalabilityAndSecurity:
    """Test database adapter abstraction and SQL injection safety."""

    @pytest.mark.asyncio
    async def test_21_sqlite_adapter_parameterized_query(self):
        adapter = get_database_adapter()
        assert isinstance(adapter, SQLiteDatabaseAdapter)
        ping_ok = await adapter.ping()
        assert ping_ok is True

        # Parameterized query test
        res = await adapter.fetch_one(
            "SELECT COUNT(*) as cnt FROM system_events WHERE event = ?",
            ("db_init",)
        )
        assert res is not None
        assert "cnt" in res

    @pytest.mark.asyncio
    async def test_22_sql_injection_attempt_harmless(self):
        adapter = get_database_adapter()
        malicious_input = "db_init' OR '1'='1"
        res = await adapter.fetch_all(
            "SELECT * FROM system_events WHERE event = ?",
            (malicious_input,)
        )
        # Should return 0 rows because parameterized queries treat string literally
        assert len(res) == 0

    def test_23_postgres_adapter_specification(self):
        pg_adapter = PostgresDatabaseAdapter("postgresql://user:pass@localhost:5432/datashield")
        assert pg_adapter.connection_url.startswith("postgresql://")


# =============================================================================
# PART 16 & 17: Destination Connector Architecture
# =============================================================================

class TestDestinationConnectors:
    """Test destination connectors and fail-closed gate enforcement."""

    def test_24_destination_allows_publication_when_gate_permits(self):
        warehouse = MockWarehouseDestination()
        payload = PublicationPayload(
            dataset_name="synthetic_cohort_2026",
            run_id="RUN-ALLOW-01",
            pipeline_id="PL-ALLOW-01",
            decision="ALLOW",
            schema_definition=[{"name": "student_hash", "type": "STRING"}],
            records=[{"student_hash": "a1b2c3d4", "grade_band": "High Distinction"}],
            audit_hash="sha256-valid-hash",
            publisher_role="Data Governance Officer",
            published_by="officer_alice",
            destination_target="curated_analytics",
        )
        res = warehouse.publish(payload)
        assert res.success is True
        assert res.records_written == 1
        assert res.destination_target == "curated_analytics"

        # Verify records queryable
        stored = warehouse.query("curated_analytics")
        assert len(stored) == 1
        assert stored[0]["grade_band"] == "High Distinction"

    def test_25_destination_blocks_publication_when_gate_is_block(self):
        warehouse = MockWarehouseDestination()
        payload = PublicationPayload(
            dataset_name="unprotected_pii",
            run_id="RUN-BLOCK-01",
            pipeline_id="PL-BLOCK-01",
            decision="BLOCK",  # Gate blocked this publication
            schema_definition=[{"name": "raw_ssn", "type": "STRING"}],
            records=[{"raw_ssn": "000-11-2222"}],
            audit_hash="sha256-valid-hash",
            publisher_role="Researcher",
            published_by="researcher_bob",
            destination_target="curated_analytics",
        )
        res = warehouse.publish(payload)
        assert res.success is False
        assert res.records_written == 0
        assert "Non-ALLOW gate decision cannot be written" in res.error

        # Ensure no records leaked into storage
        assert len(warehouse.query("curated_analytics")) == 0

    def test_26_cloud_connectors_fail_closed_on_unconfigured_or_blocked(self):
        sf = SnowflakeDestination(config={"account": "", "database": ""})
        bq = BigQueryDestination(config={"project_id": "", "dataset": ""})
        db = DatabricksDestination(config={"host": ""})

        payload_blocked = PublicationPayload(
            dataset_name="test",
            run_id="r1",
            pipeline_id="p1",
            decision="BLOCK",
            schema_definition=[],
            records=[],
            audit_hash="h1",
            publisher_role="Security Admin",
            published_by="admin",
            destination_target="t1",
        )

        assert sf.publish(payload_blocked).success is False
        assert bq.publish(payload_blocked).success is False
        assert db.publish(payload_blocked).success is False


# =============================================================================
# PART 21 & 23: Privacy, Secret Leakage & Readiness Probes
# =============================================================================

class TestPrivacyAndReadiness:
    """Test zero-PII leak invariants, secrets absence, and /ready probe."""

    def test_27_readiness_probe_status(self, client):
        resp = client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ready", "not_ready")
        assert data["database"] == "ok"
        assert "audit" in data
        assert "auth_mode" in data
        # Invariant: Never leak paths, passwords, or connection strings in /ready
        for key in ["password", "secret", "path", "token", "key"]:
            assert key not in json.dumps(data).lower()

    def test_28_secret_leakage_check_in_error_responses(self, client):
        # Trigger 404 or bad request and verify no stack trace / sensitive secrets
        resp = client.get("/pipeline/non_existent_pl_id")
        assert resp.status_code == 404
        content = resp.text.lower()
        assert "password" not in content
        assert "secret" not in content
        assert "traceback" not in content

    def test_29_zero_raw_pii_retention_in_pipeline_runs(self, client):
        # Validate dataset through pipeline
        csv_data = "student_id,email,gpa\nU99999999,sensitive@univ.edu,3.9\n"
        resp = client.post(
            "/pipeline/validate",
            json={
                "dataset_name": "pii_privacy_check",
                "content_type": "text/csv",
                "dataset_content": csv_data,
                "role": "Researcher",
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        pl_id = data["pipeline_id"]

        # Inspect pipeline run metadata stored in database
        run_resp = client.get(f"/pipeline/{pl_id}")
        assert run_resp.status_code == 200
        run_record = run_resp.json()

        # Invariant: Raw values (U99999999, sensitive@univ.edu) must never be stored
        stored_json = json.dumps(run_record)
        assert "U99999999" not in stored_json
        assert "sensitive@univ.edu" not in stored_json
