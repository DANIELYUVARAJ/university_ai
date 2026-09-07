# backend/policies/masking.py
"""
Deterministic synthetic masking transformations for Phase 4.
Transforms synthetic data values according to required protection actions.
Privacy guarantee: Operates only on synthetic values; never exposes raw PII.
"""

from __future__ import annotations
import re
import hashlib
from typing import Optional
from .schemas import ProtectionAction


def mask_email(val: str) -> str:
    """e.g. student001@example.edu -> s******@example.edu"""
    val = val.strip()
    if not val:
        return ""
    if "@" in val:
        local, domain = val.split("@", 1)
        if len(local) <= 1:
            masked_local = "*"
        else:
            masked_local = local[0] + ("*" * min(len(local) - 1, 6))
        return f"{masked_local}@{domain}"
    # Fallback for email-like string without @
    return val[0] + ("*" * max(len(val) - 1, 4))


def mask_phone(val: str) -> str:
    """e.g. +91-9000000001 -> ********01 (preserve last 2 digits)"""
    val = val.strip()
    if not val:
        return ""
    # Extract digits or preserve last 2 characters
    if len(val) <= 2:
        return "**"
    suffix = val[-2:]
    return ("*" * 8) + suffix


def mask_identifier(val: str) -> str:
    """e.g. STU_DEMO_001 -> STU_****_001"""
    val = val.strip()
    if not val:
        return ""
    parts = val.split("_")
    if len(parts) >= 3:
        # Mask middle segment
        return f"{parts[0]}_****_{parts[-1]}"
    if len(val) > 6:
        return val[:3] + "_****_" + val[-3:]
    return val[:1] + "****" + val[-1:]


def mask_text(val: str, field_name: str = "") -> str:
    """Apply field-appropriate partial masking."""
    fname = field_name.lower()
    if "email" in fname or "@" in val:
        return mask_email(val)
    if "phone" in fname or "mobile" in fname or "contact" in fname:
        return mask_phone(val)
    if "id" in fname or "identifier" in fname or "_" in val:
        return mask_identifier(val)
    if len(val) <= 3:
        return "***"
    return val[0] + ("*" * (len(val) - 2)) + val[-1]


def hash_sha256(val: str) -> str:
    """Convert value to deterministic SHA-256 hex digest."""
    val = val.strip()
    if not val:
        return ""
    return hashlib.sha256(val.encode("utf-8")).hexdigest()


def generalize_date(val: str) -> str:
    """e.g. 1999-04-17 -> 1999 (year extraction)"""
    val = val.strip()
    # Match 4 digit year
    match = re.search(r"\b(19\d\d|20\d\d)\b", val)
    if match:
        return match.group(1)
    return val


def generalize_salary(val: str) -> str:
    """e.g. 850000 -> 800000-900000"""
    clean = re.sub(r"[^\d]", "", val)
    if not clean:
        return val
    try:
        num = int(clean)
        bracket = 100000 if num >= 100000 else 10000
        low = (num // bracket) * bracket
        high = low + bracket
        return f"{low}-{high}"
    except ValueError:
        return val


def generalize_value(val: str, field_name: str = "") -> str:
    """Reduce precision of synthetic value."""
    fname = field_name.lower()
    if "birth" in fname or "date" in fname or "dob" in fname or re.search(r"\b\d{4}-\d{2}-\d{2}\b", val):
        return generalize_date(val)
    if "salary" in fname or "package" in fname or "amount" in fname:
        return generalize_salary(val)
    if re.match(r"^\d{4,7}$", val.strip()):
        return generalize_salary(val)
    # Generalize text (e.g. address) -> "City/Region Level"
    if "address" in fname:
        parts = [p.strip() for p in val.split(",")]
        return parts[-1] if len(parts) > 1 else "Regional Area"
    return val


def apply_masking(
    val: str,
    action: ProtectionAction,
    field_name: str = "",
    data_type: str = "string"
) -> str:
    """
    Main dispatch function for synthetic masking transformations.
    Safely handles empty strings, already-masked values, and invalid types.
    """
    if not val:
        return ""

    # If already masked, avoid double-masking
    if val == "[SUPPRESSED]" or "****" in val:
        return val

    if action == ProtectionAction.NONE:
        return val

    if action == ProtectionAction.SUPPRESS:
        return "[SUPPRESSED]"

    if action == ProtectionAction.HASH:
        return hash_sha256(val)

    if action == ProtectionAction.GENERALIZE:
        return generalize_value(val, field_name)

    if action == ProtectionAction.MASK:
        return mask_text(val, field_name)

    return val
