"""
Security Utilities - Legacy Compatibility Layer

This module maintains backwards compatibility with the original security module.
All utilities are now provided by common_configurations.api.shared and
meet_scheduling.api.shared.

New code should import directly from shared:
    from meet_scheduling.api.shared import check_rate_limit, validate_docname
    from common_configurations.api.shared import get_current_user_contact
"""

# Re-export everything from common_configurations shared utilities
from common_configurations.api.shared import (
    # Rate limiting
    check_rate_limit,
    get_client_ip,
    # Security
    check_honeypot,
    get_current_user_contact,
    require_user_contact,
    validate_user_contact_ownership,
    AUTH_HEADER,
    # Generic validators
    sanitize_string,
)

# Re-export appointment-specific validators
from meet_scheduling.api.shared.validators import (
    validate_date_string,
    validate_datetime_string,
    validate_docname,
)

__all__ = [
    # Rate limiting
    "check_rate_limit",
    "get_client_ip",
    # Security
    "check_honeypot",
    "get_current_user_contact",
    "require_user_contact",
    "validate_user_contact_ownership",
    "AUTH_HEADER",
    # Validators
    "sanitize_string",
    "validate_date_string",
    "validate_datetime_string",
    "validate_docname",
]
