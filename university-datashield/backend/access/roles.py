# backend/access/roles.py
"""
Demo roles for Phase 5 Role-Based Access Control.
Simulated authentication without real user PII.
"""

from enum import Enum
from typing import Dict, Any


class Role(str, Enum):
    DATA_ENGINEER = "DATA_ENGINEER"
    ANALYST = "ANALYST"
    FACULTY = "FACULTY"
    PLACEMENT_ADMIN = "PLACEMENT_ADMIN"
    SECURITY_ADMIN = "SECURITY_ADMIN"


ROLE_METADATA: Dict[Role, Dict[str, Any]] = {
    Role.DATA_ENGINEER: {
        "title": "Data Engineer",
        "description": "Builds and maintains analytical pipelines. Ingests schemas and tests transformations.",
        "can_publish": False,
        "badge_color": "blue",
    },
    Role.ANALYST: {
        "title": "Data Analyst",
        "description": "Performs institutional research and prepares reports. Authorized to publish compliant datasets.",
        "can_publish": True,
        "badge_color": "emerald",
    },
    Role.FACULTY: {
        "title": "Faculty Member",
        "description": "Academic researcher viewing aggregate reports. No publication authority for public release.",
        "can_publish": False,
        "badge_color": "amber",
    },
    Role.PLACEMENT_ADMIN: {
        "title": "Placement Administrator",
        "description": "Handles student recruitment statistics. Limited publication scope under strict supervision.",
        "can_publish": False,
        "badge_color": "purple",
    },
    Role.SECURITY_ADMIN: {
        "title": "Security Administrator",
        "description": "Manages masking policies, audits access, and oversees enterprise data protection.",
        "can_publish": True,
        "badge_color": "red",
    },
}
