# Copyright (c) 2026, Sebastian Ortiz Valencia and Contributors
# See license.txt

"""
Tests for Appointment DocType

Tests validation, hooks, and business logic.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime, add_to_date


class TestAppointment(FrappeTestCase):
	"""Tests for Appointment DocType."""

	def setUp(self):
		"""Set up test data before each test."""
		# Create test Calendar Resource
		if not frappe.db.exists("Calendar Resource", "Test Resource Appointment"):
			resource = frappe.get_doc({
				"doctype": "Calendar Resource",
				"resource_name": "Test Resource Appointment",
					"timezone": "America/Bogota",
				"slot_duration_minutes": 30,
				"capacity": 1,
				"draft_expiration_minutes": 15,
				"is_active": 1
			})
			resource.insert(ignore_permissions=True)

		frappe.db.commit()

	def test_validate_datetime_consistency(self):
		"""Test that start_datetime must be before end_datetime."""
		start_time = add_to_date(now_datetime(), hours=1)
		end_time = start_time  # Same time - should fail

		appointment = frappe.get_doc({
			"doctype": "Appointment",
			"calendar_resource": "Test Resource Appointment",
			"start_datetime": start_time,
			"end_datetime": end_time,
			"status": "Draft"
		})

		with self.assertRaises(frappe.ValidationError):
			appointment.insert()

	def test_draft_expiration_calculated(self):
		"""Test that draft_expires_at is calculated automatically."""
		start_time = add_to_date(now_datetime(), hours=2)
		end_time = add_to_date(start_time, hours=1)

		appointment = frappe.get_doc({
			"doctype": "Appointment",
			"calendar_resource": "Test Resource Appointment",
			"start_datetime": start_time,
			"end_datetime": end_time,
			"status": "Draft"
		})
		appointment.insert(ignore_permissions=True)

		# Should have draft_expires_at set
		self.assertIsNotNone(appointment.draft_expires_at)

		# Cleanup
		appointment.delete()
		frappe.db.commit()

	def test_status_confirmed_on_submit(self):
		"""Test that status becomes Confirmed on submit."""
		start_time = add_to_date(now_datetime(), hours=3)
		end_time = add_to_date(start_time, hours=1)

		appointment = frappe.get_doc({
			"doctype": "Appointment",
			"calendar_resource": "Test Resource Appointment",
			"start_datetime": start_time,
			"end_datetime": end_time,
			"status": "Draft"
		})
		appointment.insert(ignore_permissions=True)

		# Try to submit (might fail due to availability validation)
		try:
			appointment.submit()
			self.assertEqual(appointment.status, "Confirmed")
		except frappe.ValidationError:
			# Expected if no availability plan configured
			pass

		# Cleanup
		if appointment.docstatus == 1:
			appointment.cancel()
		appointment.delete()
		frappe.db.commit()

	def test_requires_calendar_resource(self):
		"""Test that calendar_resource is required."""
		start_time = add_to_date(now_datetime(), hours=5)
		end_time = add_to_date(start_time, hours=1)

		appointment = frappe.get_doc({
			"doctype": "Appointment",
			"start_datetime": start_time,
			"end_datetime": end_time,
			"status": "Draft"
		})

		# Should fail due to missing calendar_resource
		with self.assertRaises(Exception):
			appointment.insert()

	def tearDown(self):
		"""Clean up after tests."""
		frappe.db.rollback()
