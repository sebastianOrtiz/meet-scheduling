"""
Security Utilities for Public APIs

Provides rate limiting, honeypot validation, and input sanitization
for APIs that allow guest access.

Token authentication functions are imported from common_configurations.
"""

import re
import frappe
from frappe import _
from frappe.utils import cint

# Import token authentication from common_configurations
from common_configurations.api.security import (
    get_current_user_contact,
    require_user_contact,
    validate_user_contact_ownership,
    AUTH_HEADER
)


# ===================
# Rate Limiting
# ===================

def check_rate_limit(action: str, limit: int = 10, seconds: int = 60) -> None:
    """
    Check rate limit for an action by IP address.

    Uses Frappe's cache (Redis) to track request counts per IP.

    Args:
        action: Identifier for the action being rate limited
        limit: Maximum number of requests allowed
        seconds: Time window in seconds

    Raises:
        frappe.TooManyRequestsError: If rate limit exceeded
    """
    ip = get_client_ip()
    cache_key = f"rate_limit:meet_scheduling:{action}:{ip}"

    # Get current count from cache
    current = cint(frappe.cache.get_value(cache_key) or 0)

    if current >= limit:
        # Log the rate limit hit
        frappe.log_error(
            title=_("Rate Limit Exceeded"),
            message=f"IP: {ip}, Action: {action}, Limit: {limit}/{seconds}s"
        )
        frappe.throw(
            _("Too many requests. Please wait a moment and try again."),
            frappe.TooManyRequestsError
        )

    # Increment counter
    frappe.cache.set_value(cache_key, current + 1, expires_in_sec=seconds)


def get_client_ip() -> str:
    """
    Get the real client IP address, handling proxies.

    Returns:
        str: Client IP address
    """
    # Check for forwarded IP (behind proxy/load balancer)
    forwarded_for = frappe.request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_for.split(',')[0].strip()

    # Check for real IP header
    real_ip = frappe.request.headers.get('X-Real-IP', '')
    if real_ip:
        return real_ip.strip()

    # Fall back to remote address
    return frappe.request.remote_addr or 'unknown'


# ===================
# Honeypot Validation
# ===================

def check_honeypot(honeypot_value: str = None) -> None:
    """
    Check honeypot field to detect bot submissions.

    Bots typically fill all form fields, including hidden ones.
    If the honeypot field has a value, it's likely a bot.

    Args:
        honeypot_value: Value of the honeypot field

    Raises:
        frappe.ValidationError: If honeypot is filled (bot detected)
    """
    if honeypot_value:
        ip = get_client_ip()
        # Log potential bot activity
        frappe.log_error(
            title=_("Bot Detected (Honeypot)"),
            message=f"IP: {ip}, Honeypot value: {honeypot_value[:100]}"
        )
        # Return generic error to not reveal detection
        frappe.throw(_("Invalid request"), frappe.ValidationError)


# ===================
# Input Validation
# ===================

def sanitize_string(value: str, max_length: int = 500) -> str:
    """
    General string sanitization.

    Args:
        value: String to sanitize
        max_length: Maximum allowed length

    Returns:
        str: Sanitized string
    """
    if not value:
        return None

    value = str(value).strip()

    # Truncate if too long
    if len(value) > max_length:
        value = value[:max_length]

    # Remove null bytes and other control characters
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)

    return value


def validate_date_string(date_str: str, field_name: str = "date") -> str:
    """
    Validate date string format (YYYY-MM-DD).

    Args:
        date_str: Date string to validate
        field_name: Name of field for error messages

    Returns:
        str: Validated date string

    Raises:
        frappe.ValidationError: If date format is invalid
    """
    if not date_str:
        frappe.throw(_(f"{field_name} is required"), frappe.ValidationError)

    date_str = str(date_str).strip()

    # Basic format check
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        frappe.throw(_(f"Invalid {field_name} format. Use YYYY-MM-DD"), frappe.ValidationError)

    return date_str


def validate_datetime_string(datetime_str: str, field_name: str = "datetime") -> str:
    """
    Validate datetime string format (YYYY-MM-DD HH:MM:SS).

    Args:
        datetime_str: Datetime string to validate
        field_name: Name of field for error messages

    Returns:
        str: Validated datetime string

    Raises:
        frappe.ValidationError: If datetime format is invalid
    """
    if not datetime_str:
        frappe.throw(_(f"{field_name} is required"), frappe.ValidationError)

    datetime_str = str(datetime_str).strip()

    # Basic format check
    if not re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', datetime_str):
        frappe.throw(_(f"Invalid {field_name} format. Use YYYY-MM-DD HH:MM:SS"), frappe.ValidationError)

    return datetime_str


def validate_docname(name: str, field_name: str = "name") -> str:
    """
    Validate a document name (ID).

    Args:
        name: Document name to validate
        field_name: Name of field for error messages

    Returns:
        str: Validated document name

    Raises:
        frappe.ValidationError: If name is invalid
    """
    if not name:
        frappe.throw(_(f"{field_name} is required"), frappe.ValidationError)

    name = str(name).strip()

    # Length check
    if len(name) > 140:
        frappe.throw(_(f"{field_name} is too long"), frappe.ValidationError)

    # Block obvious injection attempts
    dangerous_patterns = [
        r'<script', r'javascript:', r'onclick', r'onerror',
        r'SELECT\s+', r'INSERT\s+', r'UPDATE\s+', r'DELETE\s+',
        r'DROP\s+', r'UNION\s+', r'--', r';'
    ]

    name_lower = name.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, name_lower, re.IGNORECASE):
            frappe.throw(_(f"Invalid {field_name}"), frappe.ValidationError)

    return name
