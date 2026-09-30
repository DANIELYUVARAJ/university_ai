"""
University DataShield - Destination Connectors
Phase 11: Production Security & Scalability
"""

from backend.destinations.base import (
    AnalyticsDestination,
    PublicationPayload,
    DestinationResult
)
from backend.destinations.mock_warehouse import MockWarehouseDestination
from backend.destinations.cloud_connectors import (
    SnowflakeDestination,
    BigQueryDestination,
    DatabricksDestination
)

__all__ = [
    "AnalyticsDestination",
    "PublicationPayload",
    "DestinationResult",
    "MockWarehouseDestination",
    "SnowflakeDestination",
    "BigQueryDestination",
    "DatabricksDestination",
]
