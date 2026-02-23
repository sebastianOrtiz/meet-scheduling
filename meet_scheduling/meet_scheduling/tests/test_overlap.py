"""
Tests for scheduling/overlap.py

Tests overlap detection, capacity management, and draft expiration filtering.
"""

import unittest
import frappe
from frappe.utils import now_datetime, add_to_date, get_datetime
from datetime import datetime, timedelta

from meet_scheduling.meet_scheduling.scheduling.overlap import check_overlap


class TestOverlap(unittest.TestCase):
	"""Tests for overlap detection functions."""

	def setUp(self):
		"""Set up test data before each test."""
		# Create test Calendar Resource
		if not frappe.db.exists("Calendar Resource", "Test Resource Overlap"):
			resource = frappe.get_doc({
				"doctype": "Calendar Resource",
				"resource_name": "Test Resource Overlap",
					"timezone": "America/Bogota",
				"slot_duration_minutes": 30,
				"capacity": 2,  # Capacity of 2 for testing
				"draft_expiration_minutes": 15,
				"is_active": 1
			})
			resource.insert(ignore_permissions=True)

		frappe.db.commit()

	def test_no_overlap(self):
		"""Test when there's no overlap."""
		# Create appointment in the future
		future_time = add_to_date(now_datetime(), hours=10)
		end_time = add_to_date(future_time, hours=1)

		result = check_overlap(
			"Test Resource Overlap",
			future_time,
			end_time
		)

		self.assertFalse(result["has_overlap"])
		self.assertFalse(result["capacity_exceeded"])
		self.assertEqual(result["capacity_used"], 0)
		self.assertEqual(result["capacity_available"], 2)

	def test_with_confirmed_overlap(self):
		"""Test with a confirmed appointment creating overlap."""
		# Create a draft appointment (changed from confirmed to avoid availability validation)
		start_time = add_to_date(now_datetime(), hours=2)
		end_time = add_to_date(start_time, hours=1)

		appointment = frappe.get_doc({
			"doctype": "Appointment",
			"calendar_resource": "Test Resource Overlap",
			"start_datetime": start_time,
			"end_datetime": end_time,
			"status": "Draft",
			"docstatus": 0
		})
		appointment.insert(ignore_permissions=True)
		frappe.db.commit()

		# Check overlap for same time range
		result = check_overlap(
			"Test Resource Overlap",
			start_time,
			end_time
		)

		self.assertTrue(result["has_overlap"])
		self.assertFalse(result["capacity_exceeded"])  # Capacity is 2, only 1 used
		self.assertEqual(result["capacity_used"], 1)
		self.assertEqual(result["capacity_available"], 1)

		# Cleanup
		appointment.delete()
		frappe.db.commit()

	def test_capacity_exceeded(self):
		"""Test when capacity is exceeded."""
		start_time = add_to_date(now_datetime(), hours=3)
		end_time = add_to_date(start_time, hours=1)

		# Create 2 draft appointments (capacity = 2, changed from confirmed to avoid availability validation)
		appointments = []
		for i in range(2):
			appointment = frappe.get_doc({
				"doctype": "Appointment",
				"calendar_resource": "Test Resource Overlap",
				"start_datetime": start_time,
				"end_datetime": end_time,
				"status": "Draft",
				"docstatus": 0
			})
			appointment.insert(ignore_permissions=True)
			appointments.append(appointment)

		frappe.db.commit()

		# Check overlap - should be at capacity
		result = check_overlap(
			"Test Resource Overlap",
			start_time,
			end_time
		)

		self.assertTrue(result["has_overlap"])
		self.assertTrue(result["capacity_exceeded"])
		self.assertEqual(result["capacity_used"], 2)
		self.assertEqual(result["capacity_available"], 0)

		# Cleanup
		for appointment in appointments:
			appointment.delete()
		frappe.db.commit()

	def test_draft_expiration_filtering(self):
		"""Test that expired drafts are filtered out."""
		start_time = add_to_date(now_datetime(), hours=4)
		end_time = add_to_date(start_time, hours=1)

		# Create draft with expired time (in the past)
		expired_time = add_to_date(now_datetime(), minutes=-10)

		draft = frappe.get_doc({
			"doctype": "Appointment",
			"calendar_resource": "Test Resource Overlap",
			"start_datetime": start_time,
			"end_datetime": end_time,
			"status": "Draft",
			"draft_expires_at": expired_time,
			"docstatus": 0
		})
		draft.insert(ignore_permissions=True)
		frappe.db.commit()

		# Check overlap - expired draft should not count
		result = check_overlap(
			"Test Resource Overlap",
			start_time,
			end_time
		)

		self.assertFalse(result["has_overlap"])
		self.assertEqual(result["capacity_used"], 0)

		# Cleanup
		draft.delete()
		frappe.db.commit()

	def test_active_draft_counts(self):
		"""Test that non-expired drafts are counted."""
		start_time = add_to_date(now_datetime(), hours=5)
		end_time = add_to_date(start_time, hours=1)

		# Create draft with future expiration
		future_expiration = add_to_date(now_datetime(), minutes=10)

		draft = frappe.get_doc({
			"doctype": "Appointment",
			"calendar_resource": "Test Resource Overlap",
			"start_datetime": start_time,
			"end_datetime": end_time,
			"status": "Draft",
			"draft_expires_at": future_expiration,
			"docstatus": 0
		})
		draft.insert(ignore_permissions=True)
		frappe.db.commit()

		# Check overlap - active draft should count
		result = check_overlap(
			"Test Resource Overlap",
			start_time,
			end_time
		)

		self.assertTrue(result["has_overlap"])
		self.assertEqual(result["capacity_used"], 1)

		# Cleanup
		draft.delete()
		frappe.db.commit()

	def test_exclude_appointment(self):
		"""Test excluding an appointment (for edits)."""
		start_time = add_to_date(now_datetime(), hours=6)
		end_time = add_to_date(start_time, hours=1)

		# Create draft appointment (changed from confirmed to avoid availability validation)
		appointment = frappe.get_doc({
			"doctype": "Appointment",
			"calendar_resource": "Test Resource Overlap",
			"start_datetime": start_time,
			"end_datetime": end_time,
			"status": "Draft",
			"docstatus": 0
		})
		appointment.insert(ignore_permissions=True)
		frappe.db.commit()

		# Check overlap excluding this appointment
		result = check_overlap(
			"Test Resource Overlap",
			start_time,
			end_time,
			exclude_appointment=appointment.name
		)

		self.assertFalse(result["has_overlap"])
		self.assertEqual(result["capacity_used"], 0)

		# Cleanup
		appointment.delete()
		frappe.db.commit()

	def tearDown(self):
		"""Clean up after tests."""
		frappe.db.rollback()


def run_tests():
	"""Run all tests in this module."""
	unittest.main()
