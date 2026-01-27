"""
Shared utilities for Meet Scheduling API.

This module re-exports utilities from common_configurations and provides
appointment-specific validators.

All common utilities (rate limiting, security, sanitization) come from
common_configurations.api.shared to avoid code duplication.
"""

# Re-export everything from common_configurations
from common_configurations.api.shared import (
    # Rate limiting
    check_rate_limit,
    get_client_ip,
    # Security
    check_honeypot,
    create_user_contact_token,
    get_current_user_contact,
    require_user_contact,
    validate_user_contact_ownership,
    AUTH_HEADER,
    TOKEN_EXPIRY_DAYS,
    # Validators
    sanitize_string,
    validate_document_number,
    validate_email,
    validate_phone,
    validate_name,
)

# Import appointment-specific validators
from .validators import (
    validate_date_string,
    validate_datetime_string,
    validate_docname,
)

__all__ = [
    # From common_configurations
    "check_rate_limit",
    "get_client_ip",
    "check_honeypot",
    "create_user_contact_token",
    "get_current_user_contact",
    "require_user_contact",
    "validate_user_contact_ownership",
    "AUTH_HEADER",
    "TOKEN_EXPIRY_DAYS",
    "sanitize_string",
    "validate_document_number",
    "validate_email",
    "validate_phone",
    "validate_name",
    # Appointment-specific
    "validate_date_string",
    "validate_datetime_string",
    "validate_docname",
]
