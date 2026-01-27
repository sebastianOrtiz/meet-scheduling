"""
Appointment-specific Validators

Validation utilities specific to meet_scheduling domain.
Generic validators are imported from common_configurations.api.shared.
"""

import re
import frappe
from frappe import _


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
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        frappe.throw(
            _(f"Invalid {field_name} format. Use YYYY-MM-DD"), frappe.ValidationError
        )

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
    if not re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", datetime_str):
        frappe.throw(
            _(f"Invalid {field_name} format. Use YYYY-MM-DD HH:MM:SS"),
            frappe.ValidationError,
        )

    return datetime_str


def validate_docname(name: str, field_name: str = "name") -> str:
    """
    Validate a document name (ID).

    Ensures the name is not too long and doesn't contain injection patterns.

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
        r"<script",
        r"javascript:",
        r"onclick",
        r"onerror",
        r"SELECT\s+",
        r"INSERT\s+",
        r"UPDATE\s+",
        r"DELETE\s+",
        r"DROP\s+",
        r"UNION\s+",
        r"--",
        r";",
    ]

    name_lower = name.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, name_lower, re.IGNORECASE):
            frappe.throw(_(f"Invalid {field_name}"), frappe.ValidationError)

    return name
