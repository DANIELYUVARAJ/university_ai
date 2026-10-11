"""
Phase 12.2 Automated Tests: Database Backup and Restore Verification
Tests backup creation, integrity validation, tamper detection, and post-restore invariant retention.
"""

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
import pytest

from scripts.backup_database import create_backup
from scripts.verify_backup import verify_backup_integrity, compute_event_hash, GENESIS_HASH
from scripts.restore_database import restore_database


@pytest.fixture
def populated_temp_db(tmp_path):
    """Fixture producing a temporary SQLite database with valid baseline schemas, audit chain, and governance."""
    db_path = tmp_path / "source_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")

    # Run minimal schemas required
    conn.execute("""
        CREATE TABLE system_events (id INTEGER PRIMARY KEY, event TEXT, detail TEXT);
    """)
    conn.execute("""
        CREATE TABLE policies (id INTEGER PRIMARY KEY, policy_id TEXT, policy_version TEXT, target TEXT, is_field_override INT, required_action TEXT, description TEXT, enabled INT);
    """)
    conn.execute("""
        CREATE TABLE policy_versions (id INTEGER PRIMARY KEY, version TEXT, created_at TEXT, created_by TEXT, status TEXT, parent_version TEXT, change_id TEXT, description TEXT, policy_snapshot TEXT, active INT);
    """)
    conn.execute("""
        CREATE TABLE policy_change_requests (id TEXT PRIMARY KEY, requested_at TEXT, requested_by_role TEXT, requested_by_actor TEXT, reason TEXT, current_version TEXT, proposed_version TEXT, proposed_change_json TEXT, status TEXT);
    """)
    conn.execute("""
        CREATE TABLE pipeline_runs (id INTEGER PRIMARY KEY, pipeline_id TEXT, execution_id TEXT, dataset_name TEXT, format TEXT, status TEXT, risk_level TEXT, risk_score INT, fields_count INT, sensitive_count INT, violations_count INT, decision TEXT, role TEXT, policy_version TEXT, target_destination TEXT, summary_json TEXT, report_markdown TEXT, audit_reference TEXT, created_at DATETIME, completed_at DATETIME);
    """)
    conn.execute("""
        CREATE TABLE publication_attempts (id INTEGER PRIMARY KEY, dataset_name TEXT, role TEXT, decision TEXT, status TEXT, reasons_json TEXT, policy_version TEXT, created_at DATETIME);
    """)
    conn.execute("""
        CREATE TABLE audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actor_role TEXT NOT NULL,
            actor_id TEXT,
            action TEXT NOT NULL,
            dataset TEXT,
            field_name TEXT,
            result TEXT NOT NULL,
            reason TEXT,
            policy_version TEXT,
            change_id TEXT,
            metadata_json TEXT,
            previous_hash TEXT,
            event_hash TEXT
        );
    """)

    # Populate policy
    conn.execute("INSERT INTO policy_versions VALUES (1, 'v1.0', '2026-10-01T00:00:00Z', 'admin', 'ACTIVE', NULL, NULL, 'Base', '{}', 1)")
    conn.execute("INSERT INTO policy_change_requests VALUES ('cr-101', '2026-10-01T00:00:00Z', 'DATA_STEWARD', 'steward1', 'Tighten SSN', 'v1.0', 'v1.1', '{}', 'APPROVED')")
    conn.execute("INSERT INTO publication_attempts VALUES (1, 'student_cohort', 'ANALYST', 'ALLOW', 'SUCCESS', '[]', 'v1.0', '2026-10-01T00:00:00Z')")
    conn.execute("INSERT INTO pipeline_runs VALUES (1, 'pipe-001', 'exec-001', 'student_cohort', 'csv', 'COMPLETED', 'LOW', 10, 5, 1, 0, 'ALLOW', 'ANALYST', 'v1.0', 'mock_warehouse', '{}', '# Report', 'audit-001', '2026-10-01T00:00:00Z', '2026-10-01T00:01:00Z')")

    # Populate valid cryptographic audit chain (3 events)
    prev = GENESIS_HASH
    events = [
        ("2026-10-01T00:00:01Z", "ADMIN", "system", "SYSTEM_START", "system", "", "SUCCESS", "Initialized", "v1.0", "", "{}"),
        ("2026-10-01T00:00:02Z", "DATA_STEWARD", "steward1", "POLICY_APPROVED", "governance", "", "APPROVED", "Approved CR", "v1.0", "cr-101", "{}"),
        ("2026-10-01T00:00:03Z", "ANALYST", "analyst1", "PUBLICATION_PERMITTED", "student_cohort", "", "ALLOW", "Gate cleared", "v1.0", "", "{}"),
    ]
    for ts, role, actor, action, ds, field, res, reason, pv, cid, meta in events:
        h = compute_event_hash(prev, ts, role, actor, action, ds, field, res, reason, pv, cid, meta)
        conn.execute(
            """
            INSERT INTO audit_events (timestamp, actor_role, actor_id, action, dataset, field_name, result, reason, policy_version, change_id, metadata_json, previous_hash, event_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ts, role, actor, action, ds, field, res, reason, pv, cid, meta, prev, h)
        )
        prev = h

    conn.commit()
    conn.close()
    return db_path


def test_backup_creation_and_manifest(populated_temp_db, tmp_path):
    backup_dir = tmp_path / "backups"
    manifest = create_backup(populated_temp_db, backup_dir, note="Phase 12 Test Backup")

    assert Path(manifest["backup_path"]).exists()
    assert manifest["sha256"] is not None
    assert manifest["integrity_status"] == "ok"
    assert manifest["table_inventories"]["audit_events"] == 3
    assert manifest["table_inventories"]["policy_versions"] == 1
    assert manifest["table_inventories"]["pipeline_runs"] == 1


def test_verify_backup_integrity_valid(populated_temp_db, tmp_path):
    backup_dir = tmp_path / "backups"
    manifest = create_backup(populated_temp_db, backup_dir)
    backup_file = Path(manifest["backup_path"])

    report = verify_backup_integrity(backup_file)
    assert report["overall_valid"] is True
    assert report["checksum_verified"] is True
    assert report["sqlite_integrity_ok"] is True
    assert report["audit_chain_valid"] is True
    assert report["audit_events_count"] == 3


def test_verify_backup_detects_tampered_file(populated_temp_db, tmp_path):
    backup_dir = tmp_path / "backups"
    manifest = create_backup(populated_temp_db, backup_dir)
    backup_file = Path(manifest["backup_path"])

    # Corrupt backup file slightly
    with open(backup_file, "r+b") as f:
        f.seek(100)
        f.write(b"\xFF\xFF")

    report = verify_backup_integrity(backup_file)
    assert report["overall_valid"] is False
    assert report["checksum_verified"] is False


def test_verify_backup_detects_tampered_audit_chain(populated_temp_db, tmp_path):
    backup_dir = tmp_path / "backups"
    manifest = create_backup(populated_temp_db, backup_dir)
    backup_file = Path(manifest["backup_path"])

    # Tamper with an audit record in the backup
    conn = sqlite3.connect(str(backup_file))
    conn.execute("UPDATE audit_events SET reason = 'Tampered reason' WHERE id = 2")
    conn.commit()
    conn.close()

    # Recompute manifest sha256 to isolate audit chain failure
    manifest_file = backup_file.with_suffix(".manifest.json")
    hasher = hashlib.sha256()
    with open(backup_file, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    new_sha = hasher.hexdigest()
    with open(manifest_file, "w") as f:
        json.dump({"sha256": new_sha}, f)

    report = verify_backup_integrity(backup_file)
    assert report["overall_valid"] is False
    assert report["audit_chain_valid"] is False
    assert report["compromised_event_id"] == 2


def test_restore_workflow(populated_temp_db, tmp_path):
    backup_dir = tmp_path / "backups"
    manifest = create_backup(populated_temp_db, backup_dir)
    backup_file = Path(manifest["backup_path"])

    # Simulate disaster: wipe the source database
    conn = sqlite3.connect(str(populated_temp_db))
    conn.execute("DELETE FROM audit_events;")
    conn.execute("DELETE FROM policy_versions;")
    conn.commit()
    conn.close()

    # Restore from backup
    restore_report = restore_database(backup_file, populated_temp_db, force=True)

    assert restore_report["status"] == "RESTORE_SUCCESS"
    assert restore_report["active_policies_count"] == 1
    assert restore_report["audit_events_count"] == 3
    assert restore_report["pipeline_runs_count"] == 1
    assert restore_report["audit_chain_valid"] is True
    assert restore_report["safety_copy"] is not None


def test_restore_refuses_corrupted_backup(populated_temp_db, tmp_path):
    backup_dir = tmp_path / "backups"
    manifest = create_backup(populated_temp_db, backup_dir)
    backup_file = Path(manifest["backup_path"])

    # Tamper with backup
    with open(backup_file, "r+b") as f:
        f.seek(50)
        f.write(b"CORRUPTED")

    # Attempt restore: must raise ValueError and refuse
    with pytest.raises(ValueError, match="failed pre-flight verification"):
        restore_database(backup_file, populated_temp_db, force=True)
