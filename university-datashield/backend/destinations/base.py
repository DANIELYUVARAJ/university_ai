"""
University DataShield - Destination Connector Base
Phase 11: Production Security & Scalability

Defines the abstract interface for downstream analytics destinations.
CRITICAL SECURITY INVARIANT:
Destination publication can happen ONLY after DataShield's publication gate
returns ALLOW. No destination adapter can bypass this check.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import logging

logger = logging.getLogger("datashield.destinations")


class PublicationPayload(BaseModel):
    """Payload to be published to a downstream destination."""
    dataset_name: str
    run_id: str
    pipeline_id: str
    decision: str  # Must be "ALLOW"
    schema_definition: List[Dict[str, Any]]
    records: List[Dict[str, Any]]
    audit_hash: str
    publisher_role: str
    published_by: str
    destination_target: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DestinationResult(BaseModel):
    """Result of a destination publication attempt."""
    success: bool
    destination_type: str
    destination_target: str
    records_written: int
    execution_time_ms: float
    message: str
    audit_ref: Optional[str] = None
    error: Optional[str] = None


class AnalyticsDestination(ABC):
    """
    Abstract base class for all downstream analytics storage/warehouse destinations.
    Enforces the fail-closed security rule: publication is strictly blocked unless
    decision == 'ALLOW'.
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}

    def publish(self, payload: PublicationPayload) -> DestinationResult:
        """
        Public template method that enforces gate check before calling internal write.
        """
        if payload.decision != "ALLOW":
            logger.warning(
                f"[SECURITY_VIOLATION] Destination write attempted with decision '{payload.decision}'. "
                f"Dataset: '{payload.dataset_name}', Destination: '{self.name}'. Publishing BLOCKED."
            )
            return DestinationResult(
                success=False,
                destination_type=self.name,
                destination_target=payload.destination_target,
                records_written=0,
                execution_time_ms=0.0,
                message="Destination publication rejected: gate decision is not ALLOW.",
                error="FAIL_CLOSED: Non-ALLOW gate decision cannot be written to destination."
            )

        start = datetime.now(timezone.utc)
        try:
            result = self._write_records(payload)
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000.0
            result.execution_time_ms = elapsed
            return result
        except Exception as e:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000.0
            logger.error(f"[DESTINATION_ERROR] Destination {self.name} write failed: {e}", exc_info=True)
            return DestinationResult(
                success=False,
                destination_type=self.name,
                destination_target=payload.destination_target,
                records_written=0,
                execution_time_ms=elapsed,
                message=f"Destination write failed: {str(e)}",
                error=str(e)
            )

    @abstractmethod
    def _write_records(self, payload: PublicationPayload) -> DestinationResult:
        """Internal write logic implemented by specific destination adapter."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Verify connectivity to destination."""
        pass
