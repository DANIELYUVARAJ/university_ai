"""
Phase 12 PostgreSQL Integration Closure Automated Tests
Addresses Tasks 3-9 of the PostgreSQL Integration Closure:
- Environment configuration and safe handling
- Destination-level publication gate enforcement (BLOCK and REVIEW must never write)
- Idempotent retries and deduplication
- Database-unavailable behavior and fail-safe operation
- PostgresDatabaseAdapter parameterized query conversion and transaction safety
- Preserving SQLite baseline compatibility
"""

import sys
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from destinations.base import PublicationPayload, DestinationResult
from destinations.postgres_destination import PostgresDestination
from destinations.mock_warehouse import MockWarehouseDestination
from db_adapter import (
    PostgresDatabaseAdapter,
    DatabaseUnavailableError,
    get_database_adapter,
    SQLiteDatabaseAdapter,
)
from config import settings


class TestPostgresDestinationGateEnforcement:
    """Verifies that BLOCK and REVIEW decisions are strictly rejected inside the destination."""

    def test_block_decision_never_writes_via_publish(self):
        """Decision == BLOCK strictly rejected by template publish method."""
        dest = PostgresDestination(config={"connection_url": "postgresql://test:test@localhost:5432/test"})
        payload = PublicationPayload(
            dataset_name="student_grades_blocked",
            run_id="RUN-BLOCK-001",
            pipeline_id="PL-001",
            decision="BLOCK",
            schema_definition=[{"name": "student_id", "type": "STRING"}],
            records=[{"student_id": "STU001", "grade": "A"}],
            audit_hash="sha256-blocked-hash",
            publisher_role="ANALYST",
            published_by="analyst_alice",
            destination_target="analytics_grades",
        )
        result = dest.publish(payload)
        assert result.success is False
        assert result.records_written == 0
        assert "Non-ALLOW gate decision cannot be written" in result.error
        assert "RUN-BLOCK-001" not in dest._committed_runs

    def test_review_decision_never_writes_via_publish(self):
        """Decision == REVIEW strictly rejected by template publish method."""
        dest = PostgresDestination(config={"connection_url": "postgresql://test:test@localhost:5432/test"})
        payload = PublicationPayload(
            dataset_name="student_grades_review",
            run_id="RUN-REVIEW-001",
            pipeline_id="PL-002",
            decision="REVIEW",
            schema_definition=[{"name": "student_id", "type": "STRING"}],
            records=[{"student_id": "STU002", "grade": "B"}],
            audit_hash="sha256-review-hash",
            publisher_role="ANALYST",
            published_by="analyst_alice",
            destination_target="analytics_grades",
        )
        result = dest.publish(payload)
        assert result.success is False
        assert result.records_written == 0
        assert "Non-ALLOW gate decision cannot be written" in result.error
        assert "RUN-REVIEW-001" not in dest._committed_runs

    def test_defense_in_depth_internal_write_rejects_non_allow(self):
        """Even if _write_records is invoked directly, non-ALLOW decisions are blocked."""
        dest = PostgresDestination(config={"connection_url": "postgresql://test:test@localhost:5432/test"})
        for rejected_decision in ["BLOCK", "REVIEW", "DENY", "PENDING"]:
            payload = PublicationPayload(
                dataset_name="bypass_attempt",
                run_id=f"RUN-BYPASS-{rejected_decision}",
                pipeline_id="PL-BYPASS",
                decision=rejected_decision,
                schema_definition=[],
                records=[{"leaked": "data"}],
                audit_hash="hash",
                publisher_role="ANALYST",
                published_by="attacker",
                destination_target="secret_table",
            )
            result = dest._write_records(payload)
            assert result.success is False
            assert result.records_written == 0
            assert "FAIL_CLOSED" in result.error
            assert payload.run_id not in dest._committed_runs

    def test_unconfigured_postgres_destination_fails_closed(self):
        """PostgreSQL destination without configured URL returns CONFIGURATION_INCOMPLETE."""
        dest = PostgresDestination(config={"connection_url": ""})
        payload = PublicationPayload(
            dataset_name="unconfigured_test",
            run_id="RUN-UNCONF-001",
            pipeline_id="PL-UNCONF",
            decision="ALLOW",
            schema_definition=[],
            records=[{"valid": "record"}],
            audit_hash="hash",
            publisher_role="ANALYST",
            published_by="analyst_alice",
            destination_target="valid_target",
        )
        result = dest.publish(payload)
        assert result.success is False
        assert result.records_written == 0
        assert "CONFIGURATION_INCOMPLETE" in result.error

    def test_idempotent_duplicate_retry_handling(self):
        """Duplicate retry with the same run_id does not duplicate records or re-execute write."""
        dest = PostgresDestination(config={"connection_url": "postgresql://test:test@localhost:5432/test"})
        payload = PublicationPayload(
            dataset_name="idempotent_cohort",
            run_id="RUN-IDEMP-PG-001",
            pipeline_id="PL-IDEMP",
            decision="ALLOW",
            schema_definition=[{"name": "department", "type": "STRING"}],
            records=[{"department": "Computer Science"}],
            audit_hash="hash-123",
            publisher_role="ANALYST",
            published_by="analyst_alice",
            destination_target="analytics_cohorts",
        )
        # First write
        res1 = dest.publish(payload)
        assert res1.success is True
        assert res1.records_written == 1
        assert "RUN-IDEMP-PG-001" in dest._committed_runs

        # Second write (duplicate retry)
        res2 = dest.publish(payload)
        assert res2.success is True
        assert res2.records_written == 0
        assert "Duplicate retry ignored" in res2.message

    def test_mock_warehouse_defense_in_depth_internal_write(self):
        """MockWarehouseDestination internal _write_records also rejects non-ALLOW defensively."""
        dest = MockWarehouseDestination()
        payload = PublicationPayload(
            dataset_name="mock_bypass",
            run_id="RUN-MOCK-001",
            pipeline_id="PL-MOCK",
            decision="BLOCK",
            schema_definition=[],
            records=[{"secret": "data"}],
            audit_hash="hash",
            publisher_role="ANALYST",
            published_by="analyst",
            destination_target="mock_table",
        )
        res = dest._write_records(payload)
        assert res.success is False
        assert res.records_written == 0
        assert "FAIL_CLOSED" in res.error


class TestPostgresDatabaseAdapterArchitecture:
    """Verifies PostgresDatabaseAdapter connection lifecycle, query conversion, and failure handling."""

    def test_query_placeholder_conversion(self):
        """PostgresDatabaseAdapter converts '?' to '$1', '$2', '$3' properly."""
        adapter = PostgresDatabaseAdapter("postgresql://user:pass@localhost:5432/db")
        q1 = "SELECT * FROM audit_events WHERE event_type = ? AND result = ?"
        converted1 = adapter._convert_placeholders(q1)
        assert converted1 == "SELECT * FROM audit_events WHERE event_type = $1 AND result = $2"

        q2 = "SELECT count(*) FROM table"
        assert adapter._convert_placeholders(q2) == q2

        q3 = "INSERT INTO users (id, name, role) VALUES (?, ?, ?)"
        assert adapter._convert_placeholders(q3) == "INSERT INTO users (id, name, role) VALUES ($1, $2, $3)"

    @pytest.mark.asyncio
    async def test_database_unavailable_safe_ping(self):
        """When database pool is not connected, ping() returns False safely without crashing or exposing credentials."""
        adapter = PostgresDatabaseAdapter("postgresql://user:secretpassword@localhost:5432/db")
        assert await adapter.ping() is False

    @pytest.mark.asyncio
    async def test_database_unavailable_operations_fail_closed(self):
        """When database pool is offline, CRUD operations raise typed DatabaseUnavailableError."""
        adapter = PostgresDatabaseAdapter("postgresql://user:secretpassword@localhost:5432/db")

        with pytest.raises(DatabaseUnavailableError):
            await adapter.execute("SELECT 1")

        with pytest.raises(DatabaseUnavailableError):
            await adapter.fetch_one("SELECT 1")

        with pytest.raises(DatabaseUnavailableError):
            await adapter.fetch_all("SELECT 1")

        with pytest.raises(DatabaseUnavailableError):
            async with adapter.transaction():
                pass

    @pytest.mark.asyncio
    async def test_mocked_pool_crud_and_transactions(self):
        """Verifies parameterized execution, transaction rollback, and read operations using a mock pool."""
        adapter = PostgresDatabaseAdapter("postgresql://mockuser:mockpass@localhost:5432/mockdb")

        # Mock asyncpg pool and connection
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 1
        mock_conn.fetchrow.return_value = {"id": 1, "dataset_name": "student_data", "decision": "ALLOW"}
        mock_conn.fetch.return_value = [
            {"id": 1, "dataset_name": "student_data"},
            {"id": 2, "dataset_name": "faculty_data"},
        ]
        mock_conn.execute.return_value = "INSERT 0 1"

        mock_tx_context = MagicMock()
        mock_tx_context.__aenter__ = AsyncMock(return_value=mock_tx_context)
        mock_tx_context.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=mock_tx_context)

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_pool.acquire.return_value.__aexit__.return_value = None
        mock_pool.close = AsyncMock()

        adapter._pool = mock_pool

        # 1. Ping
        assert await adapter.ping() is True
        mock_conn.fetchval.assert_called_with("SELECT 1")

        # 2. Parameterized fetch_one
        row = await adapter.fetch_one("SELECT * FROM runs WHERE id = ?", (1,))
        assert row["decision"] == "ALLOW"
        mock_conn.fetchrow.assert_called_with("SELECT * FROM runs WHERE id = $1", 1)

        # 3. Parameterized fetch_all
        rows = await adapter.fetch_all("SELECT * FROM runs")
        assert len(rows) == 2

        # 4. Parameterized execute
        res = await adapter.execute("INSERT INTO log (msg) VALUES (?)", ("test",))
        assert res == "INSERT 0 1"

        # 5. Transaction context manager
        async with adapter.transaction() as tx_conn:
            assert tx_conn == mock_conn

        # 6. Disconnect
        await adapter.disconnect()
        assert adapter._pool is None

    def test_database_adapter_factory_preserves_sqlite_by_default(self):
        """Factory returns SQLiteDatabaseAdapter by default when DATABASE_URL is SQLite."""
        with patch("config.settings.DATABASE_URL", "sqlite:///data/datashield.db"), \
             patch("backend.config.settings.DATABASE_URL", "sqlite:///data/datashield.db"):
            adapter = get_database_adapter()
            assert isinstance(adapter, SQLiteDatabaseAdapter)

    def test_database_adapter_factory_selects_postgres_when_configured(self):
        """Factory returns PostgresDatabaseAdapter when DATABASE_URL is postgresql://."""
        with patch("config.settings.DATABASE_URL", "postgresql://user:pass@localhost:5432/db"), \
             patch("backend.config.settings.DATABASE_URL", "postgresql://user:pass@localhost:5432/db"):
            adapter = get_database_adapter()
            assert isinstance(adapter, PostgresDatabaseAdapter)
