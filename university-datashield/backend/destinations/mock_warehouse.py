"""
University DataShield - Mock Analytics Warehouse
Phase 11: Production Security & Scalability

In-memory queryable mock analytics warehouse for integration testing and
demonstrating pipeline-to-destination flow without external dependencies.
"""

from typing import Dict, Any, List, Optional
from backend.destinations.base import (
    AnalyticsDestination,
    PublicationPayload,
    DestinationResult
)
import logging

logger = logging.getLogger("datashield.destinations.mock")


class MockWarehouseDestination(AnalyticsDestination):
    """
    Mock analytics warehouse storing published datasets in-memory by table name.
    Strictly verifies gate verdict is ALLOW before accepting any records.
    """

    def __init__(self, name: str = "mock_warehouse", config: Optional[Dict[str, Any]] = None):
        super().__init__(name=name, config=config)
        self.tables: Dict[str, List[Dict[str, Any]]] = {}
        self.schemas: Dict[str, List[Dict[str, Any]]] = {}
        self.publication_history: List[Dict[str, Any]] = []

    def _write_records(self, payload: PublicationPayload) -> DestinationResult:
        table_name = payload.destination_target or payload.dataset_name

        if table_name not in self.tables:
            self.tables[table_name] = []
            self.schemas[table_name] = payload.schema_definition

        # Append records (sanitized/masked analytical data only)
        self.tables[table_name].extend(payload.records)

        history_entry = {
            "dataset_name": payload.dataset_name,
            "table_name": table_name,
            "run_id": payload.run_id,
            "pipeline_id": payload.pipeline_id,
            "record_count": len(payload.records),
            "audit_hash": payload.audit_hash,
            "publisher": payload.published_by,
            "timestamp": payload.timestamp
        }
        self.publication_history.append(history_entry)

        logger.info(
            f"[MOCK_WAREHOUSE] Successfully committed {len(payload.records)} records "
            f"to table '{table_name}'. Run: {payload.run_id}."
        )

        return DestinationResult(
            success=True,
            destination_type=self.name,
            destination_target=table_name,
            records_written=len(payload.records),
            execution_time_ms=0.0,
            message=f"Successfully written {len(payload.records)} records to mock warehouse table '{table_name}'.",
            audit_ref=payload.audit_hash
        )

    def query(self, table_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Query stored records from the mock warehouse."""
        records = self.tables.get(table_name, [])
        return records[:limit]

    def get_table_schema(self, table_name: str) -> Optional[List[Dict[str, Any]]]:
        """Get schema of stored table."""
        return self.schemas.get(table_name)

    def get_history(self) -> List[Dict[str, Any]]:
        """Get publication history log."""
        return list(self.publication_history)

    def clear(self):
        """Clear all stored data (for test isolation)."""
        self.tables.clear(
            )
        self.schemas.clear()
        self.publication_history.clear()

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "destination": self.name,
            "tables_count": len(self.tables),
            "total_publications": len(self.publication_history)
        }
