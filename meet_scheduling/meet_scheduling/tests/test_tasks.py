"""
Tests for scheduling/tasks.py

Tests scheduled tasks like cleanup_expired_drafts.
"""

import unittest
import frappe
from frappe.utils import now_datetime, add_to_date

from meet_scheduling.meet_scheduling.scheduling.tasks import cleanup_expired_drafts


class TestTasks(unittest.TestCase):
	"""Tests for scheduled task functions."""

	def setUp(self):
		"""Set up test data before each test."""
		# Create test Calendar Resource
		if not frappe.db.exists("Calendar Resource", "Test Resource Tasks"):
			resource = frappe.get_doc({
				"doctype": "Calendar Resource",
				"resource_name": "Test Resource Tasks",
					"timezone": "America/Bogota",
				"slot_duration_minutes": 30,
				"capacity": 1,
				"draft_expiration_minutes": 15,
				"is_active": 1
			})
			resource.insert(ignore_permissions=True)

		frappe.db.commit()

	def test_cleanup_expired_drafts_returns_count(self):
		"""Test that cleanup_expired_drafts returns a count."""
		result = cleanup_expired_drafts()
		self.assertIsInstance(result, int)
		self.assertGreaterEqual(result, 0)

	def test_cleanup_expired_drafts_cancels_expired(self):
		"""Test that expired drafts are cancelled."""
		# Create expired draft
		start_time = add_to_date(now_datetime(), hours=1)
		end_time = add_to_date(start_time, hours=1)
		expired_time = add_to_date(now_datetime(), minutes=-10)

		draft = frappe.get_doc({
			"doctype": "Appointment",
			"calendar_resource": "Test Resource Tasks",
			"start_datetime": start_time,
			"end_datetime": end_time,
			"status": "Draft",
			"draft_expires_at": expired_time,
			"docstatus": 0
		})
		draft.insert(ignore_permissions=True)
		draft_name = draft.name
		frappe.db.commit()

		# Run cleanup
		count = cleanup_expired_drafts()

		# Should have cancelled at least 1 draft
		self.assertGreaterEqual(count, 1)

		# Verify draft is now Cancelled
		draft_after = frappe.get_doc("Appointment", draft_name)
		self.assertEqual(draft_after.status, "Cancelled")

		# Cleanup
		draft_after.delete()
		frappe.db.commit()

	def test_cleanup_does_not_cancel_active_drafts(self):
		"""Test that non-expired drafts are not cancelled."""
		# Create active draft (expires in the future)
		start_time = add_to_date(now_datetime(), hours=2)
		end_time = add_to_date(start_time, hours=1)
		future_expiration = add_to_date(now_datetime(), minutes=10)

		draft = frappe.get_doc({
			"doctype": "Appointment",
			"calendar_resource": "Test Resource Tasks",
			"start_datetime": start_time,
			"end_datetime": end_time,
			"status": "Draft",
			"draft_expires_at": future_expiration,
			"docstatus": 0
		})
		draft.insert(ignore_permissions=True)
		draft_name = draft.name
		frappe.db.commit()

		# Run cleanup
		cleanup_expired_drafts()

		# Verify draft is still Draft
		draft_after = frappe.get_doc("Appointment", draft_name)
		self.assertEqual(draft_after.status, "Draft")

		# Cleanup
		draft_after.delete()
		frappe.db.commit()

	def test_cleanup_does_not_cancel_non_draft(self):
		"""Test that drafts without draft_expires_at are not affected."""
		# Create draft without draft_expires_at using db.insert to bypass validation
		start_time = add_to_date(now_datetime(), hours=3)
		end_time = add_to_date(start_time, hours=1)

		# Insert directly into DB to avoid auto-setting draft_expires_at
		appointment_name = frappe.db.sql("""
			INSERT INTO `tabAppointment`
			(name, calendar_resource, start_datetime, end_datetime, status, docstatus, creation, modified, owner, modified_by)
			VALUES (UUID(), %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s)
		""", ("Test Resource Tasks", start_time, end_time, "Draft", 0, "Administrator", "Administrator"))
		frappe.db.commit()

		# Get the inserted appointment name
		appointments = frappe.get_all("Appointment",
			filters={"calendar_resource": "Test Resource Tasks", "start_datetime": start_time, "status": "Draft"},
			fields=["name"])
		if not appointments:
			self.fail("Failed to create test appointment")
		appointment_name = appointments[0].name

		# Run cleanup
		cleanup_expired_drafts()

		# Verify appointment is still Draft (not cancelled)
		appointment_after = frappe.get_doc("Appointment", appointment_name)
		self.assertEqual(appointment_after.status, "Draft")

		# Cleanup
		appointment_after.delete()
		frappe.db.commit()

	def tearDown(self):
		"""Clean up after tests."""
		frappe.db.rollback()


def run_tests():
	"""Run all tests in this module."""
	unittest.main()
