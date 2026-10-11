# backend/auth/models.py
"""
Data models and schemas for Phase 11 Enterprise Authentication & Identity.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

from access.roles import Role


class AuthMode(str, Enum):
    DEMO = "DEMO"
    OIDC_JWT = "OIDC_JWT"


class UserIdentity(BaseModel):
    """
    Phase 12 Production Identity Model.
    Strict privacy: Only minimal security tokens and entitlements are retained.
    """
    subject_id: str = Field(..., description="Subject identifier (unique UUID or synthetic identifier)")
    issuer: str = Field(..., description="Identity Provider (IdP) issuer URI")
    roles: List[str] = Field(default_factory=list, description="Assigned role names")
    permissions: List[str] = Field(default_factory=list, description="Resolved granular permissions")
    authentication_method: str = Field("OIDC_JWT", description="Authentication method (OIDC_JWT, DEMO_LOCAL)")
    is_active: bool = Field(True, description="Identity active status (revocation support)")


class TokenPayload(BaseModel):
    sub: str = Field(..., description="Subject identifier (unique user ID)")
    role: str = Field(..., description="Assigned role string")
    email: Optional[str] = Field(None, description="User email address")
    name: Optional[str] = Field(None, description="Display name")
    iss: str = Field(..., description="Issuer identifier")
    aud: str = Field(..., description="Audience identifier")
    exp: int = Field(..., description="Expiration timestamp (Unix epoch)")
    iat: int = Field(..., description="Issued at timestamp (Unix epoch)")


class AuthenticatedUser(BaseModel):
    user_id: str
    role: Role
    email: Optional[str] = None
    name: Optional[str] = None
    auth_mode: AuthMode
    is_authenticated: bool = True
    identity: Optional[UserIdentity] = None



class TokenRequest(BaseModel):
    user_id: str = Field("usr-analytics-01", description="Synthetic test user identifier")
    role: str = Field("DATA_ENGINEER", description="Role to assign in token claims")
    email: Optional[str] = Field("analyst@university.edu", description="Synthetic email")
    name: Optional[str] = Field("Demo Analyst", description="Display name")
    expires_in_minutes: Optional[int] = Field(60, description="Token lifetime in minutes")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user_id: str
    role: str
    auth_mode: AuthMode
