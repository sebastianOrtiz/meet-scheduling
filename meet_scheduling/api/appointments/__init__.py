"""
Appointments API Domain

Handles appointment scheduling, validation, and user's appointment management.
"""

# Re-export endpoints from appointment_api for new-style imports
from meet_scheduling.api.appointment_api import (
    # Calendar Resources
    get_active_calendar_resources,
    get_available_slots,
    # Validation
    validate_appointment,
    # CRUD
    create_and_confirm_appointment,
    cancel_or_delete_appointment,
    generate_meeting,
    # User's appointments (authenticated)
    get_my_appointments,
    get_appointment_detail,
    cancel_my_appointment,
)

__all__ = [
    # Calendar Resources
    "get_active_calendar_resources",
    "get_available_slots",
    # Validation
    "validate_appointment",
    # CRUD
    "create_and_confirm_appointment",
    "cancel_or_delete_appointment",
    "generate_meeting",
    # User's appointments
    "get_my_appointments",
    "get_appointment_detail",
    "cancel_my_appointment",
]
