# backend/pipeline/adapters/csv_adapter.py
"""
Hardened CSV dataset reader adapter for Phase 11.
"""

from __future__ import annotations
import csv
import io
import re
from typing import Tuple, List, Union

from config import settings
from detection.schemas import FieldInput
from pipeline.schemas import ExtractedSchema, DatasetFormat, FieldIngestionInfo
from .base import DatasetReader

_DATE_REGEX = re.compile(
    r"^(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})"
)
_INTEGER_REGEX = re.compile(r"^-?\d+$")
_FLOAT_REGEX = re.compile(r"^-?\d+\.\d+$")
_BOOL_STRINGS = {"true", "false", "1", "0", "yes", "no"}


def infer_data_type(values: List[str]) -> str:
    clean_values = [v.strip() for v in values if v is not None and v.strip() != ""]
    if not clean_values:
        return "string"
    if all(v.lower() in _BOOL_STRINGS for v in clean_values[:10]):
        return "boolean"
    if all(_INTEGER_REGEX.match(v) for v in clean_values[:10]):
        return "integer"
    if all(_FLOAT_REGEX.match(v) or _INTEGER_REGEX.match(v) for v in clean_values[:10]):
        return "number"
    if all(_DATE_REGEX.match(v) for v in clean_values[:10]):
        return "date"
    return "string"


class CSVReader(DatasetReader):
    @property
    def format_name(self) -> str:
        return "CSV"

    def can_read(self, content: Union[str, bytes], filename: str = "") -> bool:
        if filename.lower().endswith(".csv"):
            return True
        if isinstance(content, bytes):
            try:
                content = content.decode("utf-8", errors="ignore")
            except Exception:
                return False
        stripped = content.strip()
        if not stripped:
            return False
        first_line = stripped.splitlines()[0]
        return ("," in first_line or "\t" in first_line or ";" in first_line) and not stripped.startswith(("{", "["))

    def read(
        self, content: Union[str, bytes], dataset_name: str
    ) -> Tuple[ExtractedSchema, List[FieldInput]]:
        if isinstance(content, bytes):
            try:
                content = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Invalid CSV encoding: Must be valid UTF-8. ({str(exc)})") from exc

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

            # Check column bounds
            if len(headers) > 500:
                raise ValueError(f"Exceeded maximum column count limit (found {len(headers)} columns; limit: 500)")

            stream.seek(0)
            dict_reader = csv.DictReader(stream)
            field_values: dict[str, List[str]] = {h: [] for h in headers}
            row_count = 0

            for row in dict_reader:
                row_count += 1
                if row_count > settings.MAX_RECORDS_INGEST:
                    raise ValueError(
                        f"Dataset exceeds maximum row limit of {settings.MAX_RECORDS_INGEST} records."
                    )
                for h in headers:
                    val = row.get(h, "")
                    if val and len(field_values[h]) < 10:  # Sample up to 10 non-empty values for inference
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
