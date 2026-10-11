"""
Migration 002: Phase 12 Production Enhancements (Job Records, Metrics & Scalability Indexes)
University DataShield
"""

VERSION = "002"
NAME = "phase12_jobs_metrics_and_indexes"


async def up(conn):
    """Apply migration 002."""
    # 1. job_records: tracks lifecycle of asynchronous queue jobs
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_records (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id         TEXT UNIQUE NOT NULL,
            queue_name     TEXT NOT NULL DEFAULT 'default',
            status         TEXT NOT NULL,
            retry_count    INTEGER NOT NULL DEFAULT 0,
            max_retries    INTEGER NOT NULL DEFAULT 3,
            payload_json   TEXT NOT NULL,
            result_json    TEXT,
            error_message  TEXT,
            enqueued_at    TEXT NOT NULL,
            started_at     TEXT,
            completed_at   TEXT
        );
        """
    )

    # 2. operational_metrics: persistent operational metric points
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operational_metrics (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name    TEXT NOT NULL,
            metric_value   REAL NOT NULL,
            labels_json    TEXT,
            recorded_at    TEXT NOT NULL
        );
        """
    )

    # 3. Phase 12 Production Performance Indexes
    # Audit trail indexes
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_action ON audit_events(action);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_actor_role ON audit_events(actor_role);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_policy_version ON audit_events(policy_version);")

    # Pipeline runs indexes
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_decision ON pipeline_runs(decision);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_role ON pipeline_runs(role);")

    # Governance indexes
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_change_requests_status ON policy_change_requests(status);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_versions_active ON policy_versions(active);")

    # Publication attempts indexes
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_publication_attempts_decision ON publication_attempts(decision);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_publication_attempts_status ON publication_attempts(status);")

    # Job records indexes
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_job_records_status ON job_records(status);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_job_records_queue ON job_records(queue_name);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_job_records_enqueued ON job_records(enqueued_at);")

    # Metrics indexes
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_operational_metrics_name ON operational_metrics(metric_name);")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_operational_metrics_recorded ON operational_metrics(recorded_at);")


async def down(conn):
    """Rollback migration 002."""
    await conn.execute("DROP TABLE IF EXISTS operational_metrics;")
    await conn.execute("DROP TABLE IF EXISTS job_records;")
    indexes = [
        "idx_audit_events_action", "idx_audit_events_actor_role", "idx_audit_events_policy_version",
        "idx_pipeline_runs_decision", "idx_pipeline_runs_role", "idx_policy_change_requests_status",
        "idx_policy_versions_active", "idx_publication_attempts_decision", "idx_publication_attempts_status"
    ]
    for idx in indexes:
        await conn.execute(f"DROP INDEX IF EXISTS {idx};")
