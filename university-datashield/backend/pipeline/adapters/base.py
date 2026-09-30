# backend/pipeline/adapters/base.py
"""
Base abstraction for Phase 11 multi-format analytical dataset ingestion.
All analytical formats normalize into a standard schema and field inputs
for reuse by the Phase 9 detection engine and Phase 10 publication gate.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Tuple, List, Union

from detection.schemas import FieldInput
from pipeline.schemas import ExtractedSchema


class DatasetReader(ABC):
    @property
    @abstractmethod
    def format_name(self) -> str:
        """Name of the format (e.g. 'CSV', 'JSON', 'PARQUET', 'ARROW', 'ORC', 'AVRO')."""
        pass

    @abstractmethod
    def can_read(self, content: Union[str, bytes], filename: str = "") -> bool:
        """Return True if content matches format signatures or filename extensions."""
        pass

    @abstractmethod
    def read(
        self, content: Union[str, bytes], dataset_name: str
    ) -> Tuple[ExtractedSchema, List[FieldInput]]:
        """
        Parse dataset content into normalized ExtractedSchema and FieldInput objects.
        Enforces strict data minimization: raw records are NOT permanently stored.
        """
        pass
