# backend/pipeline/ingestion.py
"""
Safe synthetic dataset ingestion service for Phase 10.
Supports CSV and JSON formats with strict data minimization:
  - In-memory parsing only
  - Zero permanent persistence of raw uploaded personal/student values
  - Extract schema (field names and inferred data types)
  - Extract representative synthetic pattern samples for detection rules
  - Strict validation of syntax with fail-closed error handling
"""

from __future__ import annotations
import csv
import io
import json
import re
from typing import List, Tuple, Optional, Union

from detection.schemas import FieldInput
from .schemas import DatasetFormat, ExtractedSchema, FieldIngestionInfo


_DATE_REGEX = re.compile(
    r"^(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})"
)
_INTEGER_REGEX = re.compile(r"^-?\d+$")
_FLOAT_REGEX = re.compile(r"^-?\d+\.\d+$")
_BOOL_STRINGS = {"true", "false", "1", "0", "yes", "no"}


def infer_data_type(values: List[str]) -> str:
    """Infer basic data type from non-empty string values."""
    clean_values = [v.strip() for v in values if v is not None and v.strip() != ""]
    if not clean_values:
        return "string"

    # Check boolean
    if all(v.lower() in _BOOL_STRINGS for v in clean_values[:10]):
        return "boolean"

    # Check integer
    if all(_INTEGER_REGEX.match(v) for v in clean_values[:10]):
        return "integer"

    # Check float
    if all(_FLOAT_REGEX.match(v) or _INTEGER_REGEX.match(v) for v in clean_values[:10]):
        return "number"

    # Check date
    if all(_DATE_REGEX.match(v) for v in clean_values[:10]):
        return "date"

    return "string"


class DatasetIngestionService:
    @staticmethod
    def detect_format(content: str, explicit_format: Optional[DatasetFormat] = None) -> DatasetFormat:
        """Detect or validate format of incoming dataset."""
        if explicit_format:
            return explicit_format

        stripped = content.strip()
        if not stripped:
            raise ValueError("Empty dataset: content cannot be empty")

        if stripped.startswith("{") or stripped.startswith("["):
            return DatasetFormat.JSON

        # Default or fallback check for CSV delimiters
        first_line = stripped.splitlines()[0]
        if "," in first_line or "\t" in first_line or ";" in first_line:
            return DatasetFormat.CSV

        # If it looks like a single column or plain text header
        return DatasetFormat.CSV

    @classmethod
    def ingest(
        cls,
        dataset_name: str,
        content: Union[str, bytes],
        explicit_format: Optional[Union[DatasetFormat, str]] = None,
    ) -> Tuple[ExtractedSchema, List[FieldInput]]:
        """
        Ingest synthetic raw content, parse schema, infer types, and produce detection inputs.
        Adheres to strict data minimization: raw row records are discarded immediately.
        Dispatches through the Phase 11 AdapterRegistry.
        """
        if not content:
            raise ValueError("Empty dataset: content cannot be empty")
        if isinstance(content, str) and not content.strip():
            raise ValueError("Empty dataset: content cannot be empty")

        from .adapters import AdapterRegistry
        fmt_hint = None
        if explicit_format:
            fmt_hint = explicit_format.value if hasattr(explicit_format, "value") else str(explicit_format)

        reader = AdapterRegistry.get_reader(content, filename=dataset_name, format_hint=fmt_hint)
        return reader.read(content, dataset_name=dataset_name)

    @classmethod
    def _ingest_json(
        cls, dataset_name: str, content: str
    ) -> Tuple[ExtractedSchema, List[FieldInput]]:
        try:
            data = json.loads(content)
        except Exception as exc:
            raise ValueError(f"Invalid JSON format: {str(exc)}") from exc

        records: List[dict] = []
        if isinstance(data, list):
            if not data:
                raise ValueError("Empty dataset: JSON array has no records")
            if not isinstance(data[0], dict):
                raise ValueError("Invalid JSON schema: array items must be objects")
            records = data
        elif isinstance(data, dict):
            # If enveloped, e.g. {"data": [...]} or single record
            if "data" in data and isinstance(data["data"], list) and data["data"]:
                records = data["data"]
            elif "records" in data and isinstance(data["records"], list) and data["records"]:
                records = data["records"]
            else:
                # Single record object
                records = [data]
        else:
            raise ValueError("Invalid JSON structure: expected list of objects or object")

        if not records:
            raise ValueError("Empty dataset: no record objects found")

        # Collect unique field names preserving order
        field_order: List[str] = []
        field_values: dict[str, List[str]] = {}

        for rec in records:
            for k, v in rec.items():
                if k not in field_values:
                    field_order.append(k)
                    field_values[k] = []
                if v is not None:
                    field_values[k].append(str(v))

        fields_info: List[FieldIngestionInfo] = []
        field_inputs: List[FieldInput] = []

        for fname in field_order:
            vals = field_values[fname]
            inferred_type = infer_data_type(vals)
            # Pick first non-empty representative sample for pattern detection
            rep_sample = next((v for v in vals if v.strip()), "")

            fields_info.append(
                FieldIngestionInfo(
                    field_name=fname,
                    data_type=inferred_type,
                    sample_value=rep_sample if rep_sample else None,
                )
            )
            field_inputs.append(
                FieldInput(
                    name=fname,
                    data_type=inferred_type,
                    sample_pattern=rep_sample,
                )
            )

        schema = ExtractedSchema(
            dataset_name=dataset_name,
            format=DatasetFormat.JSON,
            row_count=len(records),
            fields=fields_info,
        )
        return schema, field_inputs

    @classmethod
    def _ingest_csv(
        cls, dataset_name: str, content: str
    ) -> Tuple[ExtractedSchema, List[FieldInput]]:
        stripped = content.strip()
        if not stripped:
            raise ValueError("Empty dataset: CSV content is empty")

        stream = io.StringIO(stripped)
        try:
            reader = csv.reader(stream)
            headers = next(reader, None)
            if not headers:
                raise ValueError("Empty dataset: CSV contains no header row")
            headers = [h.strip() for h in headers if h is not None]
            if not headers or all(h == "" for h in headers):
                raise ValueError("Invalid CSV format: no valid column headers found")

            # Reset stream to parse records with DictReader
            stream.seek(0)
            dict_reader = csv.DictReader(stream)
            field_values: dict[str, List[str]] = {h: [] for h in headers}
            row_count = 0

            for row in dict_reader:
                row_count += 1
                for h in headers:
                    val = row.get(h, "")
                    if val:
                        field_values[h].append(str(val).strip())

        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Invalid CSV format: {str(exc)}") from exc

        fields_info: List[FieldIngestionInfo] = []
        field_inputs: List[FieldInput] = []

        for fname in headers:
            vals = field_values[fname]
            inferred_type = infer_data_type(vals)
            rep_sample = next((v for v in vals if v.strip()), "")

            fields_info.append(
                FieldIngestionInfo(
                    field_name=fname,
                    data_type=inferred_type,
                    sample_value=rep_sample if rep_sample else None,
                )
            )
            field_inputs.append(
                FieldInput(
                    name=fname,
                    data_type=inferred_type,
                    sample_pattern=rep_sample,
                )
            )

        schema = ExtractedSchema(
            dataset_name=dataset_name,
            format=DatasetFormat.CSV,
            row_count=row_count,
            fields=fields_info,
        )
        return schema, field_inputs
