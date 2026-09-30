# backend/auth/dependencies.py
"""
FastAPI dependencies for user authentication and role-based authorization.
Bridges token verification to the existing DataShield AccessEngine.
"""

from __future__ import annotations
from typing import Optional, List, Callable
from fastapi import Request, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from access.roles import Role
from access.permissions import Permission
from access.access_engine import AccessEngine
from .models import AuthenticatedUser, AuthMode
from .token_service import TokenService, AuthError

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> AuthenticatedUser:
    """
    Authenticate request via OAuth2/OIDC Bearer token or development demo switcher.
    In production (AUTH_ENABLED=True), Bearer token is strictly mandatory.
    """
    token_str = None
    if credentials:
        token_str = credentials.credentials
    elif "authorization" in request.headers:
        auth_hdr = request.headers.get("authorization", "")
        if auth_hdr.lower().startswith("bearer "):
            token_str = auth_hdr[7:].strip()

    # ── 1. If Bearer Token is present: Validate Cryptographically ──────────────
    if token_str:
        try:
            payload = TokenService.validate_token(token_str)
            role = TokenService.resolve_role(payload.role)
            return AuthenticatedUser(
                user_id=payload.sub,
                email=payload.email,
                name=payload.name,
                role=role,
                auth_mode=AuthMode.OIDC_JWT,
                is_authenticated=True,
            )
        except AuthError as err:
            raise HTTPException(
                status_code=err.status_code,
                detail={"error_code": err.code, "message": err.message},
            )

    # ── 2. If Auth is mandatory and token is missing -> Reject (Fail Closed) ───
    if settings.AUTH_ENABLED:
        raise HTTPException(
            status_code=401,
            detail={
                "error_code": "AUTHENTICATION_REQUIRED",
                "message": "Production security requires a valid OAuth2/OIDC Bearer token in the Authorization header.",
            },
        )

    # ── 3. Development / Demo Mode (AUTH_ENABLED=False) ───────────────────────
    # Reads demo role from X-Demo-Role header or fallback to DATA_ENGINEER
    demo_role_hdr = request.headers.get("X-Demo-Role") or request.headers.get("x-demo-role")
    role_to_use = Role.DATA_ENGINEER
    if demo_role_hdr:
        try:
            clean = demo_role_hdr.strip().upper().replace(" ", "_").replace("-", "_")
            role_to_use = Role(clean)
        except ValueError:
            role_to_use = Role.DATA_ENGINEER

    return AuthenticatedUser(
        user_id="demo-persona-01",
        email="demo.persona@university.edu",
        name=f"Demo User ({role_to_use.value})",
        role=role_to_use,
        auth_mode=AuthMode.DEMO,
        is_authenticated=True,
    )


def require_permission(permission: Permission) -> Callable:
    """Dependency factory checking permissions via the authoritative AccessEngine."""
    async def _checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        is_allowed = AccessEngine.can_perform(user.role.value, permission)
        if not is_allowed:
            raise HTTPException(
                status_code=403,
                detail={
                    "error_code": "PERMISSION_DENIED",
                    "message": f"Role '{user.role.value}' lacks required permission '{permission.value}'",
                },
            )
        return user

    return _checker


def require_role(allowed_roles: List[Role]) -> Callable:
    """Dependency factory checking role membership."""
    async def _checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            role_names = [r.value for r in allowed_roles]
            raise HTTPException(
                status_code=403,
                detail={
                    "error_code": "ROLE_DENIED",
                    "message": f"Role '{user.role.value}' is not authorized (requires one of: {role_names})",
                },
            )
        return user

    return _checker
