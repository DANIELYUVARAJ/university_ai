# backend/pipeline/adapters/__init__.py
"""
Analytical dataset format adapters package (Phase 11).
"""

from .base import DatasetReader
from .csv_adapter import CSVReader
from .json_adapter import JSONReader
from .binary_adapters import ParquetReader, ArrowReader, ORCReader, AvroReader
from .registry import AdapterRegistry

__all__ = [
    "DatasetReader",
    "CSVReader",
    "JSONReader",
    "ParquetReader",
    "ArrowReader",
    "ORCReader",
    "AvroReader",
    "AdapterRegistry",
]
