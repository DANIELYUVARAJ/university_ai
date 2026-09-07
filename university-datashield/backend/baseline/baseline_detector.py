# backend/baseline/baseline_detector.py
"""
Simple keyword-only baseline detector.
Detects sensitive fields by basic substring matching on field names only.
Does NOT use value patterns, data types, confidence scores, or semantic rules.
"""

from typing import Dict, Any
from .keywords import BASELINE_KEYWORDS

class BaselineDetector:
    def __init__(self, keywords=None):
        self.keywords = [k.lower() for k in (keywords or BASELINE_KEYWORDS)]

    def predict(self, field_name: str) -> Dict[str, Any]:
        """
        Evaluate a field name using only keyword matching.
        Returns:
            is_sensitive: bool
            matched_keyword: str or None
            classification: "SENSITIVE_KEYWORD" or "NON_SENSITIVE"
        """
        field_lower = field_name.lower().strip()
        matched = None
        for kw in self.keywords:
            if kw in field_lower:
                matched = kw
                break
        
        is_sensitive = matched is not None
        return {
            "field_name": field_name,
            "is_sensitive": is_sensitive,
            "matched_keyword": matched,
            "classification": "SENSITIVE_KEYWORD" if is_sensitive else "NON_SENSITIVE"
        }
