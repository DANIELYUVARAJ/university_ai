"""
Migration 001: Initial Core Schema (Phases 1-11 Baseline)
University DataShield
"""

VERSION = "001"
NAME = "initial_core_schema"


async def up(conn):
    """Apply migration 001."""
    # Ensure WAL & Foreign Keys
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA foreign_keys=ON;")

    # 1. system_events
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS system_events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            event     TEXT    NOT NULL,
            detail    TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 2. scan_results
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scan_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_name    TEXT    NOT NULL,
            fields_scanned  INTEGER NOT NULL DEFAULT 0,
            sensitive_count INTEGER NOT NULL DEFAULT 0,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 3. field_results
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS field_results (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id        INTEGER NOT NULL REFERENCES scan_results(id),
            field_name     TEXT    NOT NULL,
            data_type      TEXT,
            classification TEXT    NOT NULL,
            confidence     INTEGER NOT NULL,
            reasons        TEXT,
            created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 4. evaluation_runs
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluation_runs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            total_fields        INTEGER NOT NULL,
            baseline_f1         REAL NOT NULL,
            datashield_f1       REAL NOT NULL,
            baseline_accuracy   REAL NOT NULL,
            datashield_accuracy REAL NOT NULL,
            created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 5. policies
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS policies (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id          TEXT UNIQUE NOT NULL,
            policy_version     TEXT NOT NULL,
            target             TEXT NOT NULL,
            is_field_override  BOOLEAN NOT NULL DEFAULT 0,
            required_action    TEXT NOT NULL,
            description        TEXT,
            enabled            BOOLEAN NOT NULL DEFAULT 1,
            created_at         DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 6. policy_validations
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS policy_validations (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_version     TEXT NOT NULL,
            dataset_name       TEXT,
            overall_status     TEXT NOT NULL,
            total_evaluated    INTEGER NOT NULL,
            violations         INTEGER NOT NULL,
            compliance         REAL NOT NULL,
            created_at         DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 7. publication_attempts
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS publication_attempts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_name   TEXT NOT NULL,
            role           TEXT NOT NULL,
            decision       TEXT NOT NULL,
            status         TEXT NOT NULL,
            reasons_json   TEXT,
            policy_version TEXT NOT NULL,
            created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 8. audit_events
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT NOT NULL,
            actor_role       TEXT NOT NULL,
            actor_id         TEXT,
            action           TEXT NOT NULL,
            dataset          TEXT,
            field_name       TEXT,
            result           TEXT NOT NULL,
            reason           TEXT,
            policy_version   TEXT,
            change_id        TEXT,
            metadata_json    TEXT,
            previous_hash    TEXT,
            event_hash       TEXT
        );
        """
    )

    # 9. policy_versions
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS policy_versions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            version          TEXT UNIQUE NOT NULL,
            created_at       TEXT NOT NULL,
            created_by       TEXT NOT NULL,
            status           TEXT NOT NULL,
            parent_version   TEXT,
            change_id        TEXT,
            description      TEXT,
            policy_snapshot  TEXT NOT NULL,
            active           BOOLEAN NOT NULL DEFAULT 0
        );
        """
    )

    # 10. policy_change_requests
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS policy_change_requests (
            id                   TEXT PRIMARY KEY,
            requested_at         TEXT NOT NULL,
            requested_by_role    TEXT NOT NULL,
            requested_by_actor   TEXT NOT NULL,
            reason               TEXT NOT NULL,
            current_version      TEXT NOT NULL,
            proposed_version     TEXT NOT NULL,
            proposed_change_json TEXT NOT NULL,
            status               TEXT NOT NULL,
            reviewed_by_role     TEXT,
            reviewed_by_actor    TEXT,
            reviewed_at          TEXT,
            review_reason        TEXT
        );
        """
    )

    # 11. pipeline_runs
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id        TEXT UNIQUE NOT NULL,
            execution_id       TEXT NOT NULL,
            dataset_name       TEXT NOT NULL,
            format             TEXT NOT NULL,
            status             TEXT NOT NULL,
            risk_level         TEXT NOT NULL,
            risk_score         INTEGER NOT NULL DEFAULT 0,
            fields_count       INTEGER NOT NULL DEFAULT 0,
            sensitive_count    INTEGER NOT NULL DEFAULT 0,
            violations_count   INTEGER NOT NULL DEFAULT 0,
            decision           TEXT NOT NULL,
            role               TEXT NOT NULL,
            policy_version     TEXT NOT NULL,
            target_destination TEXT,
            summary_json       TEXT NOT NULL,
            report_markdown    TEXT,
            audit_reference    TEXT,
            created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at       DATETIME
        );
        """
    )

    # Phase 11 baseline indexes
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_id ON pipeline_runs(pipeline_id);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created ON pipeline_runs(created_at);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp);")


async def down(conn):
    """Rollback migration 001 (drop tables in reverse dependency order)."""
    tables = [
        "pipeline_runs", "policy_change_requests", "policy_versions",
        "audit_events", "publication_attempts", "policy_validations",
        "policies", "evaluation_runs", "field_results", "scan_results",
        "system_events"
    ]
    for table in tables:
        await conn.execute(f"DROP TABLE IF EXISTS {table};")
