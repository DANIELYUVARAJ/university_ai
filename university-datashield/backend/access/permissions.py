# backend/access/permissions.py
"""
Permission actions and Role-Permission Matrix.
"""

from enum import Enum
from typing import Dict, Any
from .roles import Role


class Permission(str, Enum):
    VIEW_SCHEMA = "VIEW_SCHEMA"
    VIEW_MASKED_DATA = "VIEW_MASKED_DATA"
    VIEW_RAW_SENSITIVE_DATA = "VIEW_RAW_SENSITIVE_DATA"
    VALIDATE = "VALIDATE"
    PUBLISH = "PUBLISH"
    MANAGE_POLICIES = "MANAGE_POLICIES"


# Role-Policy Matrix defined in Section 2 of requirements
ROLE_PERMISSION_MATRIX: Dict[Role, Dict[Permission, Any]] = {
    Role.DATA_ENGINEER: {
        Permission.VIEW_SCHEMA: True,
        Permission.VIEW_MASKED_DATA: True,
        Permission.VIEW_RAW_SENSITIVE_DATA: False,
        Permission.VALIDATE: True,
        Permission.PUBLISH: False,
        Permission.MANAGE_POLICIES: False,
    },
    Role.ANALYST: {
        Permission.VIEW_SCHEMA: True,
        Permission.VIEW_MASKED_DATA: True,
        Permission.VIEW_RAW_SENSITIVE_DATA: False,
        Permission.VALIDATE: True,
        Permission.PUBLISH: True,
        Permission.MANAGE_POLICIES: False,
    },
    Role.FACULTY: {
        Permission.VIEW_SCHEMA: True,
        Permission.VIEW_MASKED_DATA: True,
        Permission.VIEW_RAW_SENSITIVE_DATA: False,
        Permission.VALIDATE: True,
        Permission.PUBLISH: False,
        Permission.MANAGE_POLICIES: False,
    },
    Role.PLACEMENT_ADMIN: {
        Permission.VIEW_SCHEMA: True,
        Permission.VIEW_MASKED_DATA: True,
        Permission.VIEW_RAW_SENSITIVE_DATA: False,
        Permission.VALIDATE: True,
        Permission.PUBLISH: False,  # LIMITED / default deny for general public release
        Permission.MANAGE_POLICIES: False,
    },
    Role.SECURITY_ADMIN: {
        Permission.VIEW_SCHEMA: True,
        Permission.VIEW_MASKED_DATA: True,
        Permission.VIEW_RAW_SENSITIVE_DATA: "CONTROLLED",
        Permission.VALIDATE: True,
        Permission.PUBLISH: True,
        Permission.MANAGE_POLICIES: True,
    },
}
