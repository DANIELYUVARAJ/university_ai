"""
University DataShield – Backend
Phase 1 & 2: Foundation + Sensitive Field Discovery

Database connection utilities using aiosqlite (async SQLite).
"""

import aiosqlite
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Database file lives in a `data/` directory one level above `backend/`
# i.e.  university-datashield/data/datashield.db
_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent
DB_PATH = _REPO_ROOT / "data" / "datashield.db"

# Ensure the directory exists at import time so we fail fast with a clear message
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


async def get_db() -> aiosqlite.Connection:
    """Open an async SQLite connection and enable WAL mode."""
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA foreign_keys=ON;")
    return conn


async def init_db() -> None:
    """
    Create the Phase 1 schema.

    Phase 1 schema is intentionally minimal – it stores only the
    bare infrastructure tables that later phases will build on.
    """
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")

        # -- Phase 1 tables --------------------------------------------------
        # system_events: a generic log table for backend events.
        # Later phases will add: datasets, fields, policies, audit_log, etc.
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS system_events (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                event     TEXT    NOT NULL,
                detail    TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Record that the DB was initialised (idempotent: no duplicate on re-run)
        await db.execute(
            """
            INSERT OR IGNORE INTO system_events (id, event, detail)
            VALUES (1, 'db_init', 'Phase 1 schema initialised')
            """
        )

        # -- Phase 2 tables --------------------------------------------------
        # scan_results: one row per POST /scan call.
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_results (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_name    TEXT    NOT NULL,
                fields_scanned  INTEGER NOT NULL DEFAULT 0,
                sensitive_count INTEGER NOT NULL DEFAULT 0,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # field_results: one row per field per scan.
        # Raw sample values are NOT stored — only metadata.
        await db.execute(
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
            )
            """
        )

        # -- Phase 3 tables --------------------------------------------------
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluation_runs (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                total_fields        INTEGER NOT NULL,
                baseline_f1         REAL NOT NULL,
                datashield_f1       REAL NOT NULL,
                baseline_accuracy   REAL NOT NULL,
                datashield_accuracy REAL NOT NULL,
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # -- Phase 4 tables --------------------------------------------------
        await db.execute(
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
            )
            """
        )

        await db.execute(
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
            )
            """
        )

        # -- Phase 5 tables --------------------------------------------------
        await db.execute(
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
            )
            """
        )

        # -- Phase 6 tables --------------------------------------------------
        await db.execute(
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
            )
            """
        )

        await db.execute(
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
            )
            """
        )

        await db.execute(
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
            )
            """
        )

        # -- Phase 10 tables -------------------------------------------------
        # pipeline_runs: one row per pipeline execution validation.
        # Zero raw PII retention: only stores metadata, schemas, summary metrics,
        # decisions, and explainability reports.
        await db.execute(
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
            )
            """
        )

        # Phase 11 indexes for production query scalability
        await db.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_id ON pipeline_runs(pipeline_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created ON pipeline_runs(created_at);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp);")

        await db.commit()

    logger.info("SQLite database initialised at %s", DB_PATH)


async def verify_db() -> dict:
    """
    Run a lightweight self-check and return status information.
    Used by the /health endpoint.
    """
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) as cnt FROM system_events"
            )
            row = await cursor.fetchone()
            event_count = row[0] if row else 0
        return {"ok": True, "path": str(DB_PATH), "event_count": event_count}
    except Exception as exc:  # pragma: no cover
        logger.error("DB verify failed: %s", exc)
        return {"ok": False, "error": str(exc)}
