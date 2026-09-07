# backend/audit/audit_service.py
"""
High-level service interface for logging explainable, privacy-safe audit events.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List

from .schemas import (
    AuditAction,
    AuditEventInput,
    AuditEventRecord,
    AuditFilterParams,
    AuditIntegrityResponse,
)
from .audit_repository import AuditRepository


class AuditService:
    @staticmethod
    async def log_event(
        action: AuditAction,
        actor_role: str,
        result: str,
        actor_id: str = "system",
        dataset: Optional[str] = None,
        field_name: Optional[str] = None,
        reason: Optional[str] = None,
        policy_version: Optional[str] = "v1.0",
        change_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEventRecord:
        """Centralized logging helper ensuring zero PII persistence."""
        event_in = AuditEventInput(
            action=action,
            actor_role=actor_role.upper().strip(),
            actor_id=actor_id,
            dataset=dataset,
            field_name=field_name,
            result=result,
            reason=reason,
            policy_version=policy_version,
            change_id=change_id,
            metadata_json=metadata or {},
        )
        return await AuditRepository.append_event(event_in)

    @staticmethod
    async def get_audit_trail(
        filters: Optional[AuditFilterParams] = None,
    ) -> List[AuditEventRecord]:
        return await AuditRepository.get_events(filters)

    @classmethod
    async def get_events(
        cls,
        filters: Optional[AuditFilterParams] = None,
    ) -> List[AuditEventRecord]:
        return await AuditRepository.get_events(filters)

    @staticmethod
    async def check_integrity() -> AuditIntegrityResponse:
        is_valid, count, details, head_hash = await AuditRepository.verify_integrity()
        return AuditIntegrityResponse(
            status="VALID" if is_valid else "COMPROMISED",
            events_checked=count,
            head_hash=head_hash,
            details=details,
        )
