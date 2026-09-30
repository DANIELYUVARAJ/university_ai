# backend/pipeline/adapters/registry.py
"""
Registry for analytical dataset format adapters.
Discovers and dispatches to appropriate DatasetReader based on signature or file extension.
"""

from __future__ import annotations
from typing import List, Optional, Union

from .base import DatasetReader
from .csv_adapter import CSVReader
from .json_adapter import JSONReader
from .binary_adapters import ParquetReader, ArrowReader, ORCReader, AvroReader


class AdapterRegistry:
    _readers: List[DatasetReader] = [
        CSVReader(),
        JSONReader(),
        ParquetReader(),
        ArrowReader(),
        ORCReader(),
        AvroReader(),
    ]

    @classmethod
    def list_supported_formats(cls) -> List[str]:
        """Return list of supported analytical dataset formats."""
        return [r.format_name for r in cls._readers]

    @classmethod
    def get_reader(
        cls,
        content: Union[str, bytes],
        filename: str = "",
        format_hint: Optional[str] = None,
    ) -> DatasetReader:
        """
        Find matching reader for dataset content or explicit format hint.
        Raises ValueError if unsupported or empty.
        """
        if format_hint:
            hint_clean = format_hint.upper().strip()
            for r in cls._readers:
                if r.format_name == hint_clean:
                    return r

        # Try by content signature or filename extension
        for r in cls._readers:
            if r.can_read(content, filename=filename):
                return r

        # Default fallback to CSV reader if text-like
        if isinstance(content, str) and not content.startswith(("{", "[")):
            return cls._readers[0]  # CSVReader

        raise ValueError(
            f"Unsupported dataset format. Supported formats: {', '.join(cls.list_supported_formats())}"
        )
