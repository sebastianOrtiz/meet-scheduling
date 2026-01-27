"""
Meet Scheduling API

This module provides a modular API structure for appointment scheduling.

Structure:
    api/
    ├── __init__.py              # This file
    ├── appointments/            # Appointments domain
    │   ├── __init__.py          # Re-exports endpoints
    │   └── endpoints.py         # HTTP endpoints
    └── shared/                  # Shared utilities
        ├── __init__.py          # Re-exports from common_configurations
        └── validators.py        # Appointment-specific validators

Usage:
    frappe.call("meet_scheduling.api.appointments.get_my_appointments", ...)
    frappe.call("meet_scheduling.api.appointments.get_available_slots", ...)

Note:
    All shared utilities (rate limiting, security, validation) are imported
    from common_configurations.api.shared to avoid code duplication.
"""

# Re-export domains for convenient access
from . import appointments
from . import shared

__all__ = [
    "appointments",
    "shared",
]
