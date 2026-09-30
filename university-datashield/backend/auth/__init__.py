# backend/auth/__init__.py
"""
University DataShield – Authentication & Identity Subsystem (Phase 11).
"""

from .models import (
    AuthMode,
    TokenPayload,
    AuthenticatedUser,
    TokenRequest,
    TokenResponse,
)
from .token_service import TokenService, AuthError
from .dependencies import (
    get_current_user,
    require_permission,
    require_role,
)

__all__ = [
    "AuthMode",
    "TokenPayload",
    "AuthenticatedUser",
    "TokenRequest",
    "TokenResponse",
    "TokenService",
    "AuthError",
    "get_current_user",
    "require_permission",
    "require_role",
]
