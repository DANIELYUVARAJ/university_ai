# backend/access/access_engine.py
"""
Access Engine for evaluating role permissions.
Implements Default Deny security principle.
"""

from typing import Dict, List, Any, Optional
from .roles import Role, ROLE_METADATA
from .permissions import Permission, ROLE_PERMISSION_MATRIX


class AccessEngine:
    @staticmethod
    def parse_role(role_str: str) -> Optional[Role]:
        """Safely parse role string, case-insensitively."""
        clean = role_str.strip().upper()
        try:
            return Role(clean)
        except ValueError:
            return None

    @classmethod
    def can_perform(cls, role: str | Role, permission: Permission | str) -> bool:
        """
        Check if a given role is allowed to perform an action.
        Follows DEFAULT DENY: Any unknown role or unmapped action returns False.
        """
        if isinstance(role, str):
            parsed_role = cls.parse_role(role)
            if not parsed_role:
                return False
            role = parsed_role

        if isinstance(permission, str):
            try:
                permission = Permission(permission.strip().upper())
            except ValueError:
                return False

        role_perms = ROLE_PERMISSION_MATRIX.get(role)
        if not role_perms:
            return False

        perm_val = role_perms.get(permission, False)
        # Returns True only if explicitly boolean True (CONTROLLED is not unrestricted True)
        return perm_val is True

    @classmethod
    def is_authorized_to_publish(cls, role: str | Role) -> bool:
        """Helper to determine whether role has publication privileges."""
        return cls.can_perform(role, Permission.PUBLISH)

    @classmethod
    def get_role_details(cls, role: str | Role) -> Dict[str, Any]:
        """Retrieve complete metadata and permissions for a role."""
        if isinstance(role, str):
            parsed = cls.parse_role(role)
            if not parsed:
                raise ValueError(f"Unknown role: {role}")
            role = parsed

        meta = ROLE_METADATA[role]
        perms = ROLE_PERMISSION_MATRIX[role]

        return {
            "role": role.value,
            "title": meta["title"],
            "description": meta["description"],
            "badge_color": meta["badge_color"],
            "can_publish": meta["can_publish"],
            "permissions": {p.value: v for p, v in perms.items()},
        }

    @classmethod
    def get_all_roles(cls) -> List[Dict[str, Any]]:
        """Return list of all configured roles and their capabilities."""
        return [cls.get_role_details(r) for r in Role]
