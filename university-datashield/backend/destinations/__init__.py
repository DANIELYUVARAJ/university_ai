"""
University DataShield - Destination Connectors
Phase 11: Production Security & Scalability
"""

from .base import (
    AnalyticsDestination,
    PublicationPayload,
    DestinationResult,
)
from .mock_warehouse import MockWarehouseDestination
from .cloud_connectors import (
    SnowflakeDestination,
    BigQueryDestination,
    DatabricksDestination,
)
from .postgres_destination import PostgresDestination

__all__ = [
    "AnalyticsDestination",
    "PublicationPayload",
    "DestinationResult",
    "MockWarehouseDestination",
    "PostgresDestination",
    "SnowflakeDestination",
    "BigQueryDestination",
    "DatabricksDestination",
]

