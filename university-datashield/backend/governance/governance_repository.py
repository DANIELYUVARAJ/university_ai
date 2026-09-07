# backend/governance/governance_repository.py
"""
Repository for policy versions and change requests.
Enforces immutable version history.
"""

from __future__ import annotations
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from database import get_db
from policies.schemas import ProtectionAction
from policies.default_policies import (
    POLICY_VERSION,
    CLASSIFICATION_DEFAULT_POLICIES,
    FIELD_SPECIFIC_OVERRIDES,
)
from .schemas import (
    PolicyVersionRecord,
    PolicyChangeRecord,
    PolicyChangeStatus,
    VersionStatus,
    PolicySnapshot,
    ProposedChangeDetail,
)


class GovernanceRepository:
    @classmethod
    async def ensure_initial_version(cls) -> PolicyVersionRecord:
        """Seed initial immutable version v1.0 if not present."""
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM policy_versions WHERE version = ?", (POLICY_VERSION,)
            )
            row = await cursor.fetchone()
            if row:
                snapshot_data = json.loads(row["policy_snapshot"])
                return PolicyVersionRecord(
                    id=row["id"],
                    version=row["version"],
                    created_at=row["created_at"],
                    created_by=row["created_by"],
                    status=VersionStatus(row["status"]),
                    parent_version=row["parent_version"],
                    change_id=row["change_id"],
                    description=row["description"],
                    policy_snapshot=PolicySnapshot(**snapshot_data),
                    active=bool(row["active"]),
                )

            # Insert initial version v1.0
            now = datetime.utcnow().isoformat() + "Z"
            snapshot = PolicySnapshot(
                classification_defaults={
                    k: v.value for k, v in CLASSIFICATION_DEFAULT_POLICIES.items()
                },
                field_overrides={
                    k: v.value for k, v in FIELD_SPECIFIC_OVERRIDES.items()
                },
            )
            snapshot_json = json.dumps(snapshot.model_dump())

            cur = await db.execute(
                """
                INSERT INTO policy_versions (
                    version, created_at, created_by, status,
                    parent_version, change_id, description, policy_snapshot, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    POLICY_VERSION,
                    now,
                    "system-init",
                    VersionStatus.ACTIVE.value,
                    None,
                    None,
                    "Initial baseline institutional masking policy",
                    snapshot_json,
                    1,
                ),
            )
            await db.commit()
            vid = cur.lastrowid
            return PolicyVersionRecord(
                id=vid,
                version=POLICY_VERSION,
                created_at=now,
                created_by="system-init",
                status=VersionStatus.ACTIVE,
                parent_version=None,
                change_id=None,
                description="Initial baseline institutional masking policy",
                policy_snapshot=snapshot,
                active=True,
            )
        finally:
            await db.close()

    @classmethod
    async def get_active_version(cls) -> PolicyVersionRecord:
        """Retrieve the currently active policy version."""
        await cls.ensure_initial_version()
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM policy_versions WHERE active = 1 ORDER BY id DESC LIMIT 1"
            )
            row = await cursor.fetchone()
            if not row:
                return await cls.ensure_initial_version()

            snapshot_data = json.loads(row["policy_snapshot"])
            return PolicyVersionRecord(
                id=row["id"],
                version=row["version"],
                created_at=row["created_at"],
                created_by=row["created_by"],
                status=VersionStatus(row["status"]),
                parent_version=row["parent_version"],
                change_id=row["change_id"],
                description=row["description"],
                policy_snapshot=PolicySnapshot(**snapshot_data),
                active=bool(row["active"]),
            )
        finally:
            await db.close()

    @classmethod
    async def get_version(cls, version_str: str) -> Optional[PolicyVersionRecord]:
        """Fetch a specific version by its version string."""
        await cls.ensure_initial_version()
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM policy_versions WHERE version = ?", (version_str.strip(),)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            snapshot_data = json.loads(row["policy_snapshot"])
            return PolicyVersionRecord(
                id=row["id"],
                version=row["version"],
                created_at=row["created_at"],
                created_by=row["created_by"],
                status=VersionStatus(row["status"]),
                parent_version=row["parent_version"],
                change_id=row["change_id"],
                description=row["description"],
                policy_snapshot=PolicySnapshot(**snapshot_data),
                active=bool(row["active"]),
            )
        finally:
            await db.close()

    @classmethod
    async def get_all_versions(cls) -> List[PolicyVersionRecord]:
        """Fetch all policy versions ordered chronologically."""
        await cls.ensure_initial_version()
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM policy_versions ORDER BY id ASC")
            rows = await cursor.fetchall()
            versions = []
            for r in rows:
                snapshot_data = json.loads(r["policy_snapshot"])
                versions.append(
                    PolicyVersionRecord(
                        id=r["id"],
                        version=r["version"],
                        created_at=r["created_at"],
                        created_by=r["created_by"],
                        status=VersionStatus(r["status"]),
                        parent_version=r["parent_version"],
                        change_id=r["change_id"],
                        description=r["description"],
                        policy_snapshot=PolicySnapshot(**snapshot_data),
                        active=bool(r["active"]),
                    )
                )
            return versions
        finally:
            await db.close()

    @classmethod
    async def create_version(
        cls,
        version: str,
        created_by: str,
        description: str,
        snapshot: PolicySnapshot,
        parent_version: Optional[str] = None,
        change_id: Optional[str] = None,
        status: VersionStatus = VersionStatus.ACTIVE,
    ) -> PolicyVersionRecord:
        """Create a new immutable policy version and set it active."""
        now = datetime.utcnow().isoformat() + "Z"
        snapshot_json = json.dumps(snapshot.model_dump())

        db = await get_db()
        try:
            # Set all existing versions to inactive and superseded
            await db.execute("UPDATE policy_versions SET active = 0, status = 'SUPERSEDED'")

            cur = await db.execute(
                """
                INSERT INTO policy_versions (
                    version, created_at, created_by, status,
                    parent_version, change_id, description, policy_snapshot, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    version,
                    now,
                    created_by,
                    status.value,
                    parent_version,
                    change_id,
                    description,
                    snapshot_json,
                ),
            )
            await db.commit()
            vid = cur.lastrowid
            return PolicyVersionRecord(
                id=vid,
                version=version,
                created_at=now,
                created_by=created_by,
                status=status,
                parent_version=parent_version,
                change_id=change_id,
                description=description,
                policy_snapshot=snapshot,
                active=True,
            )
        finally:
            await db.close()

    # ── Change Requests ──────────────────────────────────────────────────────

    @classmethod
    async def create_change_request(
        cls,
        change_id: str,
        requested_by_role: str,
        requested_by_actor: str,
        reason: str,
        current_version: str,
        proposed_version: str,
        change_detail: ProposedChangeDetail,
    ) -> PolicyChangeRecord:
        """Store a pending policy change proposal."""
        now = datetime.utcnow().isoformat() + "Z"
        change_json = json.dumps(change_detail.model_dump())

        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO policy_change_requests (
                    id, requested_at, requested_by_role, requested_by_actor,
                    reason, current_version, proposed_version, proposed_change_json,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    change_id,
                    now,
                    requested_by_role.upper().strip(),
                    requested_by_actor.strip(),
                    reason,
                    current_version,
                    proposed_version,
                    change_json,
                    PolicyChangeStatus.PENDING.value,
                ),
            )
            await db.commit()
            return PolicyChangeRecord(
                id=change_id,
                requested_at=now,
                requested_by_role=requested_by_role,
                requested_by_actor=requested_by_actor,
                reason=reason,
                current_version=current_version,
                proposed_version=proposed_version,
                proposed_change=change_detail,
                status=PolicyChangeStatus.PENDING,
            )
        finally:
            await db.close()

    @classmethod
    async def get_change_request(cls, change_id: str) -> Optional[PolicyChangeRecord]:
        """Fetch change request by ID."""
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM policy_change_requests WHERE id = ?", (change_id.strip(),)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            detail = json.loads(row["proposed_change_json"])
            return PolicyChangeRecord(
                id=row["id"],
                requested_at=row["requested_at"],
                requested_by_role=row["requested_by_role"],
                requested_by_actor=row["requested_by_actor"],
                reason=row["reason"],
                current_version=row["current_version"],
                proposed_version=row["proposed_version"],
                proposed_change=ProposedChangeDetail(**detail),
                status=PolicyChangeStatus(row["status"]),
                reviewed_by_role=row["reviewed_by_role"],
                reviewed_by_actor=row["reviewed_by_actor"],
                reviewed_at=row["reviewed_at"],
                review_reason=row["review_reason"],
            )
        finally:
            await db.close()

    @classmethod
    async def get_all_change_requests(cls) -> List[PolicyChangeRecord]:
        """Fetch all policy change requests ordered newest first."""
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM policy_change_requests ORDER BY requested_at DESC"
            )
            rows = await cursor.fetchall()
            records = []
            for r in rows:
                detail = json.loads(r["proposed_change_json"])
                records.append(
                    PolicyChangeRecord(
                        id=r["id"],
                        requested_at=r["requested_at"],
                        requested_by_role=r["requested_by_role"],
                        requested_by_actor=r["requested_by_actor"],
                        reason=r["reason"],
                        current_version=r["current_version"],
                        proposed_version=r["proposed_version"],
                        proposed_change=ProposedChangeDetail(**detail),
                        status=PolicyChangeStatus(r["status"]),
                        reviewed_by_role=r["reviewed_by_role"],
                        reviewed_by_actor=r["reviewed_by_actor"],
                        reviewed_at=r["reviewed_at"],
                        review_reason=r["review_reason"],
                    )
                )
            return records
        finally:
            await db.close()

    @classmethod
    async def update_change_status(
        cls,
        change_id: str,
        status: PolicyChangeStatus,
        reviewed_by_role: str,
        reviewed_by_actor: str,
        review_reason: str,
    ) -> None:
        """Mark a change request as APPROVED, REJECTED, or ROLLED_BACK."""
        now = datetime.utcnow().isoformat() + "Z"
        db = await get_db()
        try:
            await db.execute(
                """
                UPDATE policy_change_requests
                SET status = ?, reviewed_by_role = ?, reviewed_by_actor = ?,
                    reviewed_at = ?, review_reason = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    reviewed_by_role.upper().strip(),
                    reviewed_by_actor.strip(),
                    now,
                    review_reason,
                    change_id.strip(),
                ),
            )
            await db.commit()
        finally:
            await db.close()
