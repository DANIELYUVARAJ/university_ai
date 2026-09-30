# backend/audit/audit_repository.py
"""
Repository for immutable, append-only audit trail with SHA-256 hash chaining.
"""

from __future__ import annotations
import json
import hashlib
import asyncio
from datetime import datetime
from typing import List, Optional, Tuple

from database import get_db
from .schemas import AuditEventInput, AuditEventRecord, AuditFilterParams, AuditAction

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
    """Deterministic SHA-256 computation over event fields and previous hash."""
    payload = (
        f"{previous_hash}|{timestamp}|{actor_role}|{actor_id}|{action}|"
        f"{dataset}|{field_name}|{result}|{reason}|{policy_version}|"
        f"{change_id}|{metadata_str}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditRepository:
    _append_lock: Optional[asyncio.Lock] = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        if cls._append_lock is None:
            cls._append_lock = asyncio.Lock()
        return cls._append_lock

    @classmethod
    async def append_event(cls, event: AuditEventInput) -> AuditEventRecord:
        """
        Append an audit event with SHA-256 hash chaining.
        Append-only guarantee: Events cannot be modified once written.
        Protected by asyncio.Lock to guarantee hash chain serialization under concurrent pipelines.
        """
        async with cls._get_lock():
            timestamp = datetime.utcnow().isoformat() + "Z"
            metadata_str = json.dumps(event.metadata_json or {}, sort_keys=True)
            actor_id = event.actor_id or "system"
            dataset = event.dataset or ""
            field_name = event.field_name or ""
            reason = event.reason or ""
            policy_version = event.policy_version or "v1.0"
            change_id = event.change_id or ""

            db = await get_db()
            try:
                # Get latest event hash
                cursor = await db.execute(
                    "SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1"
                )
                row = await cursor.fetchone()
                previous_hash = row[0] if row else GENESIS_HASH

                # Compute current event hash
                event_hash = compute_event_hash(
                    previous_hash=previous_hash,
                    timestamp=timestamp,
                    actor_role=event.actor_role,
                    actor_id=actor_id,
                    action=event.action.value,
                    dataset=dataset,
                    field_name=field_name,
                    result=event.result,
                    reason=reason,
                    policy_version=policy_version,
                    change_id=change_id,
                    metadata_str=metadata_str,
                )

                insert_cur = await db.execute(
                    """
                    INSERT INTO audit_events (
                        timestamp, actor_role, actor_id, action, dataset,
                        field_name, result, reason, policy_version, change_id,
                        metadata_json, previous_hash, event_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        timestamp,
                        event.actor_role,
                        actor_id,
                        event.action.value,
                        dataset,
                        field_name,
                        event.result,
                        reason,
                        policy_version,
                        change_id,
                        metadata_str,
                        previous_hash,
                        event_hash,
                    ),
                )
                await db.commit()
                event_id = insert_cur.lastrowid

                return AuditEventRecord(
                    id=event_id,
                    timestamp=timestamp,
                    actor_role=event.actor_role,
                    actor_id=actor_id,
                    action=event.action,
                    dataset=dataset if dataset else None,
                    field_name=field_name if field_name else None,
                    result=event.result,
                    reason=reason if reason else None,
                    policy_version=policy_version if policy_version else None,
                    change_id=change_id if change_id else None,
                    metadata_json=event.metadata_json,
                    previous_hash=previous_hash,
                    event_hash=event_hash,
                )
            finally:
                await db.close()

    @staticmethod
    async def get_events(filters: Optional[AuditFilterParams] = None) -> List[AuditEventRecord]:
        """Query audit trail with optional filtering."""
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: list = []

        if filters:
            if filters.action:
                query += " AND action = ?"
                params.append(filters.action.value)
            if filters.actor_role:
                query += " AND actor_role = ?"
                params.append(filters.actor_role.upper().strip())
            if filters.result:
                query += " AND result = ?"
                params.append(filters.result.upper().strip())
            if filters.policy_version:
                query += " AND policy_version = ?"
                params.append(filters.policy_version.strip())
            if filters.dataset:
                query += " AND dataset LIKE ?"
                params.append(f"%{filters.dataset.strip()}%")

        query += " ORDER BY id DESC"
        if filters and filters.limit:
            query += " LIMIT ?"
            params.append(filters.limit)
        else:
            query += " LIMIT 100"

        db = await get_db()
        try:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            records = []
            for r in rows:
                meta = None
                if r["metadata_json"]:
                    try:
                        meta = json.loads(r["metadata_json"])
                    except Exception:
                        meta = None
                records.append(
                    AuditEventRecord(
                        id=r["id"],
                        timestamp=r["timestamp"],
                        actor_role=r["actor_role"],
                        actor_id=r["actor_id"],
                        action=AuditAction(r["action"]),
                        dataset=r["dataset"] if r["dataset"] else None,
                        field_name=r["field_name"] if r["field_name"] else None,
                        result=r["result"],
                        reason=r["reason"] if r["reason"] else None,
                        policy_version=r["policy_version"] if r["policy_version"] else None,
                        change_id=r["change_id"] if r["change_id"] else None,
                        metadata_json=meta,
                        previous_hash=r["previous_hash"],
                        event_hash=r["event_hash"],
                    )
                )
            return records
        finally:
            await db.close()

    @staticmethod
    async def verify_integrity() -> Tuple[bool, int, str, Optional[str]]:
        """
        Verify the complete cryptographic hash chain.
        Returns: (is_valid, count, details, head_hash)
        """
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM audit_events ORDER BY id ASC")
            rows = await cursor.fetchall()
            if not rows:
                return True, 0, "Audit log is empty (Genesis state valid)", GENESIS_HASH

            prev_expected_hash = GENESIS_HASH
            for idx, r in enumerate(rows):
                # Verify link
                if r["previous_hash"] != prev_expected_hash:
                    return (
                        False,
                        idx,
                        f"Hash break detected at event #{r['id']}: expected previous_hash {prev_expected_hash}, found {r['previous_hash']}",
                        r["event_hash"],
                    )

                # Re-compute hash
                meta_str = r["metadata_json"] or "{}"
                # Ensure valid JSON formatting matches standard string
                try:
                    meta_obj = json.loads(meta_str)
                    clean_meta_str = json.dumps(meta_obj, sort_keys=True)
                except Exception:
                    clean_meta_str = meta_str

                recalc = compute_event_hash(
                    previous_hash=r["previous_hash"],
                    timestamp=r["timestamp"],
                    actor_role=r["actor_role"],
                    actor_id=r["actor_id"],
                    action=r["action"],
                    dataset=r["dataset"] or "",
                    field_name=r["field_name"] or "",
                    result=r["result"],
                    reason=r["reason"] or "",
                    policy_version=r["policy_version"] or "",
                    change_id=r["change_id"] or "",
                    metadata_str=clean_meta_str,
                )

                if recalc != r["event_hash"]:
                    return (
                        False,
                        idx,
                        f"Hash mismatch at event #{r['id']}: computed {recalc}, recorded {r['event_hash']}",
                        r["event_hash"],
                    )

                prev_expected_hash = r["event_hash"]

            return (
                True,
                len(rows),
                f"All {len(rows)} audit events cryptographically verified with unbroken SHA-256 hash chain",
                prev_expected_hash,
            )
        finally:
            await db.close()
