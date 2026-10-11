#!/usr/bin/env python3
"""
University DataShield - Database Backup Utility (Phase 12)
Creates consistent, online point-in-time backups of the database with SHA-256
checksums, metadata manifests, and table row count inventories.
"""

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backup")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "datashield.db"
DEFAULT_BACKUP_DIR = REPO_ROOT / "data" / "backups"


def create_backup(db_path: Path, output_dir: Path, note: str = "") -> dict:
    """
    Perform a consistent online backup of SQLite database using sqlite3 backup API.
    Computes SHA-256 checksum and produces a JSON manifest.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Source database not found at {db_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"datashield_backup_{timestamp}.db"
    backup_path = output_dir / backup_filename
    manifest_path = output_dir / f"datashield_backup_{timestamp}.manifest.json"

    logger.info("Initiating online backup from %s to %s...", db_path, backup_path)

    # Online backup using SQLite Backup API (safe with active WAL readers/writers)
    source_conn = sqlite3.connect(str(db_path))
    dest_conn = sqlite3.connect(str(backup_path))
    try:
        source_conn.backup(dest_conn)
        dest_conn.commit()
    finally:
        dest_conn.close()
        source_conn.close()

    # Calculate SHA-256 checksum of the backup file
    hasher = hashlib.sha256()
    with open(backup_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    sha256_hash = hasher.hexdigest()

    # Gather table inventories and verify integrity
    verify_conn = sqlite3.connect(str(backup_path))
    verify_conn.row_factory = sqlite3.Row
    try:
        cur = verify_conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        integrity_row = cur.fetchone()
        integrity_status = integrity_row[0] if integrity_row else "unknown"

        # Count key operational & audit tables
        tables_to_check = [
            "system_events", "scan_results", "field_results", "evaluation_runs",
            "policies", "policy_validations", "publication_attempts",
            "audit_events", "policy_versions", "policy_change_requests",
            "pipeline_runs", "schema_migrations", "job_records"
        ]
        inventories = {}
        for tbl in tables_to_check:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                inventories[tbl] = cur.fetchone()[0]
            except sqlite3.OperationalError:
                inventories[tbl] = 0

        # Latest audit hash
        latest_audit_hash = None
        try:
            cur.execute("SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                latest_audit_hash = row[0]
        except sqlite3.OperationalError:
            pass

        # Latest migration version
        latest_migration = None
        try:
            cur.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                latest_migration = row[0]
        except sqlite3.OperationalError:
            pass

    finally:
        verify_conn.close()

    manifest = {
        "backup_filename": backup_filename,
        "backup_path": str(backup_path.resolve()),
        "source_db": str(db_path.resolve()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": sha256_hash,
        "size_bytes": backup_path.stat().st_size,
        "integrity_status": integrity_status,
        "latest_migration": latest_migration,
        "latest_audit_hash": latest_audit_hash,
        "table_inventories": inventories,
        "note": note
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Backup complete: %s (SHA-256: %s)", backup_path.name, sha256_hash[:12])
    logger.info("Manifest created: %s", manifest_path.name)
    return manifest


def main():
    parser = argparse.ArgumentParser(description="University DataShield Database Backup")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="Path to database")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_BACKUP_DIR, help="Backup output directory")
    parser.add_argument("--note", type=str, default="", help="Optional description/note")
    args = parser.parse_args()

    try:
        manifest = create_backup(args.db_path, args.output_dir, args.note)
        print(json.dumps(manifest, indent=2))
        sys.exit(0)
    except Exception as exc:
        logger.error("Backup failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
