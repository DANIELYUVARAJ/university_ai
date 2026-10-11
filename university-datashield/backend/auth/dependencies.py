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
from access.permissions import Permission, ROLE_PERMISSION_MATRIX
from access.access_engine import AccessEngine
from .models import AuthenticatedUser, AuthMode, UserIdentity
from .token_service import TokenService, AuthError

security_scheme = HTTPBearer(auto_error=False)

# In-memory revocation / disabled identities registry
REVOKED_SUBJECTS = set()


def revoke_subject(subject_id: str) -> None:
    """Revoke/disable a subject identifier."""
    REVOKED_SUBJECTS.add(subject_id)


def reinstate_subject(subject_id: str) -> None:
    """Reinstate a disabled subject identifier."""
    REVOKED_SUBJECTS.discard(subject_id)


def is_subject_revoked(subject_id: str) -> bool:
    """Check if subject identifier has been revoked."""
    return subject_id in REVOKED_SUBJECTS


def _resolve_permissions_for_role(role: Role) -> List[str]:
    """Retrieve permission string list from authoritative matrix."""
    matrix_entry = ROLE_PERMISSION_MATRIX.get(role, {})
    return [perm.value for perm, allowed in matrix_entry.items() if allowed]


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> AuthenticatedUser:
    """
    Authenticate request via OAuth2/OIDC Bearer token or development demo switcher.
    In production (AUTH_ENABLED=True), Bearer token is strictly mandatory.
    Arbitrary headers such as X-Role, X-User, X-Admin are strictly disallowed.
    """
    # ── Check for forbidden spoofing headers in production ────────────────────
    spoofing_headers = ["x-role", "x-user", "x-admin", "x-auth-user", "x-username"]
    for hdr in spoofing_headers:
        if hdr in request.headers and settings.AUTH_ENABLED:
            raise HTTPException(
                status_code=401,
                detail={
                    "error_code": "HEADER_AUTHENTICATION_DISALLOWED",
                    "message": f"Direct identity assertion via '{hdr}' is forbidden in production. Use OAuth2/OIDC Bearer token.",
                },
            )

    token_str = None
    if credentials and isinstance(credentials, HTTPAuthorizationCredentials):
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

            # Check if identity is disabled / revoked
            if is_subject_revoked(payload.sub):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error_code": "IDENTITY_DISABLED",
                        "message": f"Subject identifier '{payload.sub}' has been disabled or revoked.",
                    },
                )

            perms = _resolve_permissions_for_role(role)
            identity = UserIdentity(
                subject_id=payload.sub,
                issuer=payload.iss,
                roles=[role.value],
                permissions=perms,
                authentication_method="OIDC_JWT",
                is_active=True,
            )

            return AuthenticatedUser(
                user_id=payload.sub,
                email=payload.email,
                name=payload.name,
                role=role,
                auth_mode=AuthMode.OIDC_JWT,
                is_authenticated=True,
                identity=identity,
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

    perms = _resolve_permissions_for_role(role_to_use)
    identity = UserIdentity(
        subject_id="demo-persona-01",
        issuer="https://auth.local.demo",
        roles=[role_to_use.value],
        permissions=perms,
        authentication_method="DEMO_LOCAL",
        is_active=True,
    )

    return AuthenticatedUser(
        user_id="demo-persona-01",
        email="demo.persona@university.edu",
        name=f"Demo User ({role_to_use.value})",
        role=role_to_use,
        auth_mode=AuthMode.DEMO,
        is_authenticated=True,
        identity=identity,
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
