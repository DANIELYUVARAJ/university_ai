# backend/policies/default_policies.py
"""
Default masking policies and field-specific overrides.
Policy Version: v1.0
"""

from typing import Dict
from .schemas import ProtectionAction, PolicyRule

POLICY_VERSION = "v1.0"

# Default protection action per classification category
CLASSIFICATION_DEFAULT_POLICIES: Dict[str, ProtectionAction] = {
    "DIRECT_IDENTIFIER": ProtectionAction.MASK,
    "QUASI_IDENTIFIER": ProtectionAction.GENERALIZE,
    "SENSITIVE_ATTRIBUTE": ProtectionAction.GENERALIZE,
    "ACADEMIC_DATA": ProtectionAction.NONE,
    "PLACEMENT_DATA": ProtectionAction.NONE,
    "NON_SENSITIVE": ProtectionAction.NONE,
}

# Field-specific overrides (these take strict precedence over classification defaults)
FIELD_SPECIFIC_OVERRIDES: Dict[str, ProtectionAction] = {
    "student_id": ProtectionAction.HASH,
    "student_identifier": ProtectionAction.HASH,
    "candidate_id": ProtectionAction.HASH,
    "email": ProtectionAction.MASK,
    "personal_email": ProtectionAction.MASK,
    "phone": ProtectionAction.MASK,
    "mobile_number": ProtectionAction.MASK,
    "guardian_contact": ProtectionAction.MASK,
    "date_of_birth": ProtectionAction.GENERALIZE,
    "birth_year": ProtectionAction.GENERALIZE,
    "salary": ProtectionAction.GENERALIZE,
    "placement_package": ProtectionAction.GENERALIZE,
}

def get_default_policy_rules() -> list[PolicyRule]:
    """Return all default policy rules as structured PolicyRule objects."""
    rules = []
    
    # Classification rules
    for classification, action in CLASSIFICATION_DEFAULT_POLICIES.items():
        rules.append(
            PolicyRule(
                policy_id=f"POL-CLS-{classification}",
                policy_version=POLICY_VERSION,
                target=classification,
                is_field_override=False,
                required_action=action,
                description=f"Default {action.value} policy for {classification}",
                enabled=True,
            )
        )
    
    # Field override rules
    for field_name, action in FIELD_SPECIFIC_OVERRIDES.items():
        rules.append(
            PolicyRule(
                policy_id=f"POL-FLD-{field_name}",
                policy_version=POLICY_VERSION,
                target=field_name,
                is_field_override=True,
                required_action=action,
                description=f"Field override: {field_name} requires {action.value}",
                enabled=True,
            )
        )
        
    return rules
