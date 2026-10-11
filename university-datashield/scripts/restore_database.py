#!/usr/bin/env python3
"""
University DataShield - Database Restore Utility (Phase 12)
Safely restores a database from verified backup with pre-flight integrity check,
pre-restore safety snapshots, and post-restore cryptographic audit verification.
"""

import argparse
import json
import logging
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("restore")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "datashield.db"

# Import backup verifier
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from verify_backup import verify_backup_integrity


def restore_database(backup_path: Path, target_path: Path, force: bool = False) -> dict:
    """
    Restore target database from backup_path.
    1. Pre-flight verification of backup file.
    2. Safety copy of existing target database.
    3. Safe restore via SQLite backup API.
    4. Post-restore verification of policies, audit chain, pipeline, publication.
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found at {backup_path}")

    # 1. Pre-flight integrity check
    logger.info("Running pre-flight integrity check on backup %s...", backup_path.name)
    pre_check = verify_backup_integrity(backup_path)
    if not pre_check["overall_valid"]:
        raise ValueError(f"Backup failed pre-flight verification! Refusing to restore. Details: {pre_check}")
    logger.info("Backup pre-flight check PASSED.")

    # 2. Safety copy of current database if target exists
    safety_backup_path = None
    if target_path.exists():
        if not force:
            logger.warning("Target database exists at %s. Creating pre-restore snapshot.", target_path)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safety_backup_path = target_path.parent / f"{target_path.name}.pre_restore_{timestamp}.bak"
        logger.info("Saving safety copy of target DB to %s...", safety_backup_path)
        shutil.copy2(target_path, safety_backup_path)

    # 3. Perform restore using SQLite backup API to ensure clean page writing
    logger.info("Restoring database to %s...", target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    source_conn = sqlite3.connect(str(backup_path))
    dest_conn = sqlite3.connect(str(target_path))
    try:
        source_conn.backup(dest_conn)
        dest_conn.commit()
    finally:
        dest_conn.close()
        source_conn.close()

    # 4. Post-restore verification
    logger.info("Verifying restored target database...")
    post_check = verify_backup_integrity(target_path)
    if not post_check["overall_valid"]:
        raise RuntimeError(f"Post-restore verification failed! Target database may be inconsistent. {post_check}")

    # Additional Post-restore invariants:
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM policy_versions WHERE active = 1")
        active_policies = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM audit_events")
        audit_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM pipeline_runs")
        pipeline_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM publication_attempts")
        publication_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM policy_change_requests")
        change_requests_count = cur.fetchone()[0]
    finally:
        conn.close()

    report = {
        "status": "RESTORE_SUCCESS",
        "restored_from": str(backup_path.resolve()),
        "target_db": str(target_path.resolve()),
        "safety_copy": str(safety_backup_path.resolve()) if safety_backup_path else None,
        "active_policies_count": active_policies,
        "audit_events_count": audit_count,
        "pipeline_runs_count": pipeline_count,
        "publication_attempts_count": publication_count,
        "change_requests_count": change_requests_count,
        "audit_chain_valid": post_check["audit_chain_valid"],
        "sqlite_integrity_ok": post_check["sqlite_integrity_ok"]
    }
    logger.info("Database restore completed successfully.")
    return report


def main():
    parser = argparse.ArgumentParser(description="University DataShield Database Restore Utility")
    parser.add_argument("backup_file", type=Path, help="Path to backup .db file")
    parser.add_argument("--target-db", type=Path, default=DEFAULT_DB_PATH, help="Target database path")
    parser.add_argument("--force", action="store_true", help="Force overwrite without prompt")
    args = parser.parse_args()

    try:
        res = restore_database(args.backup_file, args.target_db, force=args.force)
        print(json.dumps(res, indent=2))
        sys.exit(0)
    except Exception as exc:
        logger.error("Restore failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
