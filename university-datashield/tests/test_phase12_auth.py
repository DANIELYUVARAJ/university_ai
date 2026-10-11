"""
Phase 12.3 Automated Tests: Production Authentication & Identity Model
Tests comprehensive JWT/OIDC validation, claims verification, role mapping,
header spoofing rejection, identity lifecycle, and demo vs production modes.
"""

import time
import pytest
import jwt
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from fastapi import Request, HTTPException
from fastapi.testclient import TestClient

from main import app
from config import settings
from access.roles import Role
from access.permissions import Permission
from auth.token_service import TokenService, AuthError
from auth.dependencies import (
    get_current_user,
    revoke_subject,
    reinstate_subject,
    require_role,
    require_permission,
)
from auth.models import AuthenticatedUser, AuthMode



@pytest.fixture
def test_client():
    return TestClient(app)


def test_valid_token_decoding_and_identity():
    token = TokenService.create_access_token(
        user_id="usr-analyst-42",
        role="ANALYST",
        email="analyst42@university.edu",
        name="Dr. Jane Smith",
    )
    payload = TokenService.validate_token(token)
    assert payload.sub == "usr-analyst-42"
    assert payload.role == "ANALYST"
    assert payload.email == "analyst42@university.edu"
    assert payload.iss == settings.AUTH_ISSUER
    assert payload.aud == settings.AUTH_AUDIENCE


def test_token_missing():
    with pytest.raises(AuthError) as exc_info:
        TokenService.validate_token("")
    assert exc_info.value.code == "MISSING_TOKEN"


def test_token_malformed():
    with pytest.raises(AuthError) as exc_info:
        TokenService.validate_token("not.a.valid.jwt.token.string")
    assert exc_info.value.code == "MALFORMED_TOKEN"


def test_token_expired():
    token = TokenService.create_access_token(
        user_id="usr-expired-01",
        role="DATA_ENGINEER",
        expires_in_seconds=-60,  # Expired 60s ago
    )
    with pytest.raises(AuthError) as exc_info:
        TokenService.validate_token(token)
    assert exc_info.value.code == "TOKEN_EXPIRED"


def test_token_invalid_signature():
    wrong_key = "wrong-" + "signature-test-" * 3
    token = TokenService.create_access_token(
        user_id="usr-tampered-01",
        role="SECURITY_ADMIN",
        secret_key=wrong_key,
    )

    with pytest.raises(AuthError) as exc_info:
        TokenService.validate_token(token)
    assert exc_info.value.code == "INVALID_SIGNATURE"


def test_token_wrong_issuer():
    token = TokenService.create_access_token(
        user_id="usr-spoof-iss",
        role="ANALYST",
        issuer="https://malicious-idp.attacker.com",
    )
    with pytest.raises(AuthError) as exc_info:
        TokenService.validate_token(token)
    assert exc_info.value.code == "INVALID_ISSUER"


def test_token_wrong_audience():
    token = TokenService.create_access_token(
        user_id="usr-spoof-aud",
        role="ANALYST",
        audience="different-app-identifier",
    )
    with pytest.raises(AuthError) as exc_info:
        TokenService.validate_token(token)
    assert exc_info.value.code == "INVALID_AUDIENCE"


def test_token_missing_role():
    now = int(time.time())
    bad_payload = {
        "sub": "usr-no-role",
        "iss": settings.AUTH_ISSUER,
        "aud": settings.AUTH_AUDIENCE,
        "iat": now,
        "exp": now + 3600,
        # 'role' is omitted
    }
    raw_token = jwt.encode(bad_payload, settings.AUTH_SECRET_KEY, algorithm=settings.AUTH_ALGORITHM)
    with pytest.raises(AuthError) as exc_info:
        TokenService.validate_token(raw_token)
    assert exc_info.value.code == "MISSING_ROLE"


def test_token_unknown_role():
    token = TokenService.create_access_token(
        user_id="usr-unknown-role",
        role="SUPER_GOD_ADMIN_ROLE_DOES_NOT_EXIST",
    )
    payload = TokenService.validate_token(token)
    with pytest.raises(AuthError) as exc_info:
        TokenService.resolve_role(payload.role)
    assert exc_info.value.code == "UNKNOWN_ROLE"


@pytest.mark.asyncio
async def test_disabled_identity_rejection():
    subject_id = "usr-revoked-steward"
    token = TokenService.create_access_token(user_id=subject_id, role="SECURITY_ADMIN")
    revoke_subject(subject_id)

    try:
        req = Request(scope={
            "type": "http",
            "headers": [(b"authorization", f"Bearer {token}".encode("utf-8"))],
            "method": "GET",
            "path": "/test",
        })
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(req)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error_code"] == "IDENTITY_DISABLED"
    finally:
        reinstate_subject(subject_id)


@pytest.mark.asyncio
async def test_header_spoofing_rejected_in_production():
    # Temporarily set AUTH_ENABLED = True
    orig_auth = settings.AUTH_ENABLED
    settings.AUTH_ENABLED = True

    try:
        # Attacker tries to inject X-Admin / X-Role without token
        for spoof_hdr in ["x-admin", "x-role", "x-user"]:
            req = Request(scope={
                "type": "http",
                "headers": [(spoof_hdr.encode("utf-8"), b"SECURITY_ADMIN")],
                "method": "POST",
                "path": "/policies/approve",
            })
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(req)
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["error_code"] == "HEADER_AUTHENTICATION_DISALLOWED"
    finally:
        settings.AUTH_ENABLED = orig_auth


@pytest.mark.asyncio
async def test_demo_mode_local_identity():
    orig_auth = settings.AUTH_ENABLED
    settings.AUTH_ENABLED = False

    try:
        req = Request(scope={
            "type": "http",
            "headers": [(b"x-demo-role", b"ANALYST")],
            "method": "GET",
            "path": "/test",
        })
        user = await get_current_user(req)
        assert user.role == Role.ANALYST
        assert user.auth_mode == AuthMode.DEMO
        assert user.identity is not None
        assert user.identity.authentication_method == "DEMO_LOCAL"
        assert "PUBLISH" in user.identity.permissions
    finally:
        settings.AUTH_ENABLED = orig_auth


@pytest.mark.asyncio
async def test_role_and_permission_enforcement():
    # Construct an analyst user
    analyst_user = AuthenticatedUser(
        user_id="usr-analyst",
        role=Role.ANALYST,
        auth_mode=AuthMode.OIDC_JWT,
    )
    # Analyst cannot MANAGE_POLICIES
    checker = require_permission(Permission.MANAGE_POLICIES)
    with pytest.raises(HTTPException) as exc_info:
        await checker(analyst_user)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_code"] == "PERMISSION_DENIED"

    # Require role check
    role_checker = require_role([Role.SECURITY_ADMIN])
    with pytest.raises(HTTPException) as exc_info:
        await role_checker(analyst_user)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error_code"] == "ROLE_DENIED"
