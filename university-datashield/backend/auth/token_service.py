# backend/auth/token_service.py
"""
OAuth2 / OIDC JSON Web Token validation service for Phase 11.
Provides deterministic cryptographic verification of tokens with strict
issuer, audience, signature, expiration, and role claims checking.
"""

from __future__ import annotations
import time
from typing import Optional, Dict, Any
import jwt

from config import settings
from access.roles import Role
from .models import TokenPayload, AuthenticatedUser, AuthMode


class AuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 401):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class TokenService:
    @staticmethod
    def create_access_token(
        user_id: str,
        role: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        expires_in_seconds: Optional[int] = None,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        secret_key: Optional[str] = None,
        algorithm: Optional[str] = None,
    ) -> str:
        """Create a signed JWT token for testing and authentication flows."""
        now = int(time.time())
        exp_seconds = expires_in_seconds if expires_in_seconds is not None else (settings.TOKEN_EXPIRE_MINUTES * 60)
        exp = now + exp_seconds

        payload: Dict[str, Any] = {
            "sub": user_id,
            "role": role.upper().strip(),
            "iss": issuer or settings.AUTH_ISSUER,
            "aud": audience or settings.AUTH_AUDIENCE,
            "iat": now,
            "exp": exp,
        }
        if email:
            payload["email"] = email
        if name:
            payload["name"] = name

        key = secret_key or settings.AUTH_SECRET_KEY
        algo = algorithm or settings.AUTH_ALGORITHM
        return jwt.encode(payload, key, algorithm=algo)

    @classmethod
    def validate_token(
        cls,
        token: str,
        expected_issuer: Optional[str] = None,
        expected_audience: Optional[str] = None,
        secret_key: Optional[str] = None,
    ) -> TokenPayload:
        """
        Validate signature, expiration, issuer, audience, and required claims.
        Fail-Closed: Any ambiguity or invalid claim raises a typed AuthError.
        """
        if not token or not token.strip():
            raise AuthError("MISSING_TOKEN", "Authentication token must not be empty", 401)

        clean_token = token.strip()
        if clean_token.lower().startswith("bearer "):
            clean_token = clean_token[7:].strip()

        key = secret_key or settings.AUTH_SECRET_KEY
        issuer = expected_issuer or settings.AUTH_ISSUER
        audience = expected_audience or settings.AUTH_AUDIENCE

        try:
            decoded = jwt.decode(
                clean_token,
                key,
                algorithms=[settings.AUTH_ALGORITHM],
                issuer=issuer,
                audience=audience,
                options={
                    "require": ["exp", "iat", "sub", "iss", "aud"],
                    "verify_exp": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("TOKEN_EXPIRED", "Authentication token has expired", 401) from exc
        except jwt.InvalidSignatureError as exc:
            raise AuthError("INVALID_SIGNATURE", "Token signature verification failed", 401) from exc
        except jwt.InvalidIssuerError as exc:
            raise AuthError("INVALID_ISSUER", f"Token issuer mismatch (expected: {issuer})", 401) from exc
        except jwt.InvalidAudienceError as exc:
            raise AuthError("INVALID_AUDIENCE", f"Token audience mismatch (expected: {audience})", 401) from exc
        except jwt.DecodeError as exc:
            raise AuthError("MALFORMED_TOKEN", f"Malformed token: {str(exc)}", 401) from exc
        except Exception as exc:
            raise AuthError("TOKEN_VALIDATION_FAILED", f"Token validation failed: {str(exc)}", 401) from exc

        role_str = decoded.get("role")
        if not role_str:
            raise AuthError("MISSING_ROLE", "Token does not contain required 'role' claim", 403)

        return TokenPayload(
            sub=decoded["sub"],
            role=role_str,
            email=decoded.get("email"),
            name=decoded.get("name"),
            iss=decoded["iss"],
            aud=decoded["aud"],
            exp=decoded["exp"],
            iat=decoded["iat"],
        )

    @classmethod
    def resolve_role(cls, role_str: str) -> Role:
        """Map token role string to authoritative Role enum."""
        clean = role_str.strip().upper().replace(" ", "_").replace("-", "_")
        try:
            return Role(clean)
        except ValueError as exc:
            raise AuthError("UNKNOWN_ROLE", f"Unrecognized role claim: '{role_str}'", 403) from exc
