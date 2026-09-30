# backend/pipeline/adapters/json_adapter.py
"""
Hardened JSON dataset reader adapter for Phase 11.
Includes nesting-depth validation and schema structure checking.
"""

from __future__ import annotations
import json
from typing import Tuple, List, Union, Any

from config import settings
from detection.schemas import FieldInput
from pipeline.schemas import ExtractedSchema, DatasetFormat, FieldIngestionInfo
from .base import DatasetReader
from .csv_adapter import infer_data_type


def check_nesting_depth(obj: Any, current_depth: int = 1, max_depth: int = 10) -> None:
    """Validate JSON nesting depth to protect against deeply nested recursion attacks."""
    if current_depth > max_depth:
        raise ValueError(f"JSON nesting depth exceeds maximum allowed limit of {max_depth} levels.")
    if isinstance(obj, dict):
        for v in obj.values():
            check_nesting_depth(v, current_depth + 1, max_depth)
    elif isinstance(obj, list):
        for item in obj[:10]:  # Check first few items
            check_nesting_depth(item, current_depth + 1, max_depth)


class JSONReader(DatasetReader):
    @property
    def format_name(self) -> str:
        return "JSON"

    def can_read(self, content: Union[str, bytes], filename: str = "") -> bool:
        if filename.lower().endswith(".json"):
            return True
        if isinstance(content, bytes):
            try:
                content = content.decode("utf-8", errors="ignore")
            except Exception:
                return False
        stripped = content.strip()
        return stripped.startswith("{") or stripped.startswith("[")

    def read(
        self, content: Union[str, bytes], dataset_name: str
    ) -> Tuple[ExtractedSchema, List[FieldInput]]:
        if isinstance(content, bytes):
            try:
                content = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Invalid JSON encoding: Must be valid UTF-8. ({str(exc)})") from exc

        if not content or not content.strip():
            raise ValueError("Empty dataset: content cannot be empty")

        try:
            data = json.loads(content)
        except Exception as exc:
            raise ValueError(f"Invalid JSON format: {str(exc)}") from exc

        # Protect against deeply nested JSON payloads
        check_nesting_depth(data, current_depth=1, max_depth=settings.MAX_JSON_DEPTH)

        records: List[dict] = []
        if isinstance(data, list):
            if not data:
                raise ValueError("Empty dataset: JSON array has no records")
            if not isinstance(data[0], dict):
                raise ValueError("Invalid JSON schema: array items must be objects")
            records = data
        elif isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list) and data["data"]:
                records = data["data"]
            elif "records" in data and isinstance(data["records"], list) and data["records"]:
                records = data["records"]
            else:
                records = [data]
        else:
            raise ValueError("Invalid JSON structure: expected list of objects or object")

        if not records:
            raise ValueError("Empty dataset: no record objects found")

        if len(records) > settings.MAX_RECORDS_INGEST:
            raise ValueError(f"Dataset exceeds maximum row limit of {settings.MAX_RECORDS_INGEST} records.")

        field_order: List[str] = []
        field_values: dict[str, List[str]] = {}

        for rec in records:
            for k, v in rec.items():
                if k not in field_values:
                    field_order.append(k)
                    field_values[k] = []
                if v is not None and len(field_values[k]) < 10:
                    field_values[k].append(str(v))

        if len(field_order) > 500:
            raise ValueError(f"Exceeded maximum column count limit (found {len(field_order)} columns; limit: 500)")

        fields_info: List[FieldIngestionInfo] = []
        field_inputs: List[FieldInput] = []

        for fname in field_order:
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
            format=DatasetFormat.JSON,
            row_count=len(records),
            fields=fields_info,
        )
        return schema, field_inputs
