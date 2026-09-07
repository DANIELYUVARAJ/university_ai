# backend/access/__init__.py
from .roles import Role, ROLE_METADATA
from .permissions import Permission, ROLE_PERMISSION_MATRIX
from .access_engine import AccessEngine

__all__ = [
    "Role",
    "ROLE_METADATA",
    "Permission",
    "ROLE_PERMISSION_MATRIX",
    "AccessEngine",
]
