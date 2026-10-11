#!/usr/bin/env python3
"""
University DataShield - Database Backup Verification Utility (Phase 12)
Cryptographically verifies backup files, checking file integrity, SQLite page
consistency, table inventories, and full SHA-256 audit hash-chain continuity.
"""

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_backup")

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


def compute_event_hash(
    previous_hash: str,
    timestamp: str,
    actor_role: str,
    actor_id: str,
    action: str,
    dataset: str,
    field_name: str,
    result: str,
    reason: str,
    policy_version: str,
    change_id: str,
    metadata_str: str,
) -> str:
    payload = (
        f"{previous_hash}|{timestamp}|{actor_role}|{actor_id}|{action}|"
        f"{dataset}|{field_name}|{result}|{reason}|{policy_version}|"
        f"{change_id}|{metadata_str}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_backup_integrity(backup_path: Path, manifest_path: Path = None) -> dict:
    """Validate backup file integrity, SQLite structure, and cryptographic audit chain."""
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found at {backup_path}")

    # Check manifest if present
    manifest = None
    if manifest_path is None:
        candidate_manifest = backup_path.with_suffix(".manifest.json")
        if candidate_manifest.exists():
            manifest_path = candidate_manifest

    if manifest_path and manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    # 1. File Checksum Verification
    hasher = hashlib.sha256()
    with open(backup_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    computed_sha256 = hasher.hexdigest()

    checksum_matched = True
    if manifest and "sha256" in manifest:
        checksum_matched = (computed_sha256 == manifest["sha256"])
        if not checksum_matched:
            logger.error("Checksum mismatch! Manifest: %s vs Computed: %s", manifest["sha256"], computed_sha256)

    # 2. SQLite Page & Structural Integrity
    sqlite_integrity = False
    audit_rows = []
    inventories = {}
    chain_valid = True
    compromised_event_id = None

    try:
        conn = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            res = cur.fetchall()
            sqlite_integrity = (len(res) == 1 and res[0][0] == "ok")

            # 3. Table Inventories
            tables_to_check = [
                "system_events", "scan_results", "field_results", "evaluation_runs",
                "policies", "policy_validations", "publication_attempts",
                "audit_events", "policy_versions", "policy_change_requests",
                "pipeline_runs", "schema_migrations", "job_records"
            ]
            for tbl in tables_to_check:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                    inventories[tbl] = cur.fetchone()[0]
                except sqlite3.OperationalError:
                    inventories[tbl] = 0

            # 4. Cryptographic SHA-256 Audit Trail Verification
            cur.execute(
                """
                SELECT id, timestamp, actor_role, actor_id, action, dataset,
                       field_name, result, reason, policy_version, change_id,
                       metadata_json, previous_hash, event_hash
                FROM audit_events
                ORDER BY id ASC
                """
            )
            audit_rows = cur.fetchall()
            expected_prev = GENESIS_HASH

            for row in audit_rows:
                ev_id = row["id"]
                prev_hash = row["previous_hash"]
                ev_hash = row["event_hash"]
                meta_json = row["metadata_json"] or "{}"

                if prev_hash != expected_prev:
                    chain_valid = False
                    compromised_event_id = ev_id
                    logger.error("Audit chain break at event %s: expected prev %s, found %s", ev_id, expected_prev[:8], prev_hash[:8])
                    break

                try:
                    parsed_meta = json.loads(meta_json) if isinstance(meta_json, str) else meta_json
                    meta_str = json.dumps(parsed_meta, sort_keys=True)
                except Exception:
                    meta_str = "{}"

                expected_hash = compute_event_hash(
                    previous_hash=prev_hash,
                    timestamp=row["timestamp"],
                    actor_role=row["actor_role"],
                    actor_id=row["actor_id"] or "system",
                    action=row["action"],
                    dataset=row["dataset"] or "",
                    field_name=row["field_name"] or "",
                    result=row["result"],
                    reason=row["reason"] or "",
                    policy_version=row["policy_version"] or "v1.0",
                    change_id=row["change_id"] or "",
                    metadata_str=meta_str,
                )

                if ev_hash != expected_hash:
                    chain_valid = False
                    compromised_event_id = ev_id
                    logger.error("Audit event hash mismatch at event %s: expected %s, found %s", ev_id, expected_hash[:8], ev_hash[:8])
                    break

                expected_prev = ev_hash

        finally:
            conn.close()
    except (sqlite3.DatabaseError, sqlite3.OperationalError) as db_err:
        logger.error("SQLite database error during backup verification: %s", db_err)
        sqlite_integrity = False
        chain_valid = False


    overall_valid = checksum_matched and sqlite_integrity and chain_valid

    report = {
        "backup_path": str(backup_path),
        "overall_valid": overall_valid,
        "checksum_verified": checksum_matched,
        "computed_sha256": computed_sha256,
        "sqlite_integrity_ok": sqlite_integrity,
        "audit_chain_valid": chain_valid,
        "audit_events_count": len(audit_rows),
        "compromised_event_id": compromised_event_id,
        "table_inventories": inventories,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="University DataShield Backup Integrity Verifier")
    parser.add_argument("backup_file", type=Path, help="Path to backup .db file")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to .manifest.json (optional)")
    args = parser.parse_args()

    try:
        report = verify_backup_integrity(args.backup_file, args.manifest)
        print(json.dumps(report, indent=2))
        if report["overall_valid"]:
            logger.info("Backup integrity verification: PASSED")
            sys.exit(0)
        else:
            logger.error("Backup integrity verification: FAILED")
            sys.exit(1)
    except Exception as exc:
        logger.error("Verification error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
