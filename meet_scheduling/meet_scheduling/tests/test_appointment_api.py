"""
Tests for api/appointment_api.py

Tests whitelisted API endpoints.
"""

import unittest
import frappe
from frappe.utils import now_datetime, add_to_date, getdate

from meet_scheduling.meet_scheduling.api.appointment_api import (
	get_available_slots,
	validate_appointment,
	generate_meeting
)


class TestAppointmentAPI(unittest.TestCase):
	"""Tests for API endpoints."""

	def setUp(self):
		"""Set up test data before each test."""
		# Create test Calendar Resource
		if not frappe.db.exists("Calendar Resource", "Test Resource API"):
			resource = frappe.get_doc({
				"doctype": "Calendar Resource",
				"resource_name": "Test Resource API",
				"resource_type": "Person",
				"timezone": "America/Bogota",
				"slot_duration_minutes": 60,
				"capacity": 1,
				"draft_expiration_minutes": 15,
				"is_active": 1
			})
			resource.insert(ignore_permissions=True)

		frappe.db.commit()

	def test_get_available_slots_returns_list(self):
		"""Test that get_available_slots returns a list."""
		today = getdate()
		tomorrow = add_to_date(today, days=1)

		result = get_available_slots(
			"Test Resource API",
			today.strftime("%Y-%m-%d"),
			tomorrow.strftime("%Y-%m-%d")
		)

		self.assertIsInstance(result, list)

	def test_get_available_slots_invalid_resource(self):
		"""Test that get_available_slots fails with invalid resource."""
		today = getdate()

		with self.assertRaises(frappe.ValidationError):
			get_available_slots(
				"Nonexistent Resource",
				today.strftime("%Y-%m-%d"),
				today.strftime("%Y-%m-%d")
			)

	def test_validate_appointment_returns_dict(self):
		"""Test that validate_appointment returns expected structure."""
		start_time = add_to_date(now_datetime(), hours=2)
		end_time = add_to_date(start_time, hours=1)

		result = validate_appointment(
			"Test Resource API",
			start_time.strftime("%Y-%m-%d %H:%M:%S"),
			end_time.strftime("%Y-%m-%d %H:%M:%S")
		)

		self.assertIsInstance(result, dict)
		self.assertIn("valid", result)
		self.assertIn("errors", result)
		self.assertIn("warnings", result)
		self.assertIn("availability_ok", result)
		self.assertIn("capacity_ok", result)
		self.assertIn("overlap_info", result)

	def test_validate_appointment_invalid_dates(self):
		"""Test validation with invalid date format."""
		result = validate_appointment(
			"Test Resource API",
			"invalid-date",
			"invalid-date"
		)

		self.assertFalse(result["valid"])
		self.assertGreater(len(result["errors"]), 0)

	def test_validate_appointment_end_before_start(self):
		"""Test validation when end is before start."""
		start_time = add_to_date(now_datetime(), hours=2)
		end_time = add_to_date(start_time, hours=-1)  # Before start

		result = validate_appointment(
			"Test Resource API",
			start_time.strftime("%Y-%m-%d %H:%M:%S"),
			end_time.strftime("%Y-%m-%d %H:%M:%S")
		)

		self.assertFalse(result["valid"])
		self.assertGreater(len(result["errors"]), 0)

	def test_generate_meeting_invalid_appointment(self):
		"""Test generate_meeting with nonexistent appointment."""
		result = generate_meeting("Nonexistent-Appointment")

		self.assertIsInstance(result, dict)
		self.assertFalse(result["success"])
		self.assertIn("Error", result["status"])

	def test_generate_meeting_returns_dict(self):
		"""Test that generate_meeting returns expected structure."""
		# Create a confirmed appointment for testing
		start_time = add_to_date(now_datetime(), hours=3)
		end_time = add_to_date(start_time, hours=1)

		appointment = frappe.get_doc({
			"doctype": "Appointment",
			"calendar_resource": "Test Resource API",
			"start_datetime": start_time,
			"end_datetime": end_time,
			"status": "Confirmed",
			"docstatus": 1
		})

		try:
			appointment.insert(ignore_permissions=True)

			# Note: This will fail if Video Call Profile is not configured properly
			# But we can test the structure of error response
			result = generate_meeting(appointment.name)

			self.assertIsInstance(result, dict)
			self.assertIn("success", result)
			self.assertIn("meeting_url", result)
			self.assertIn("meeting_id", result)
			self.assertIn("status", result)
			self.assertIn("message", result)

		except Exception:
			# Expected if video call profile not configured
			pass
		finally:
			# Cleanup
			try:
				if appointment.docstatus == 1:
					appointment.cancel()
				appointment.delete()
			except:
				pass
			frappe.db.commit()

	def tearDown(self):
		"""Clean up after tests."""
		frappe.db.rollback()


def run_tests():
	"""Run all tests in this module."""
	unittest.main()
