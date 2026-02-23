"""
Tests for scheduling/availability.py

Tests availability calculation, exception handling, and interval mathematics.
"""

import unittest
import frappe
from frappe.utils import getdate, get_datetime
from datetime import datetime, date, time
import pytz

from meet_scheduling.meet_scheduling.scheduling.availability import (
	get_availability_slots_for_day,
	get_effective_availability,
	_merge_intervals,
	_interval_subtract
)


class TestAvailability(unittest.TestCase):
	"""Tests for availability calculation functions."""

	def setUp(self):
		"""Set up test data before each test."""
		# Create test Calendar Resource
		if not frappe.db.exists("Calendar Resource", "Test Resource"):
			resource = frappe.get_doc({
				"doctype": "Calendar Resource",
				"resource_name": "Test Resource",
					"timezone": "America/Bogota",
				"slot_duration_minutes": 30,
				"capacity": 1,
				"is_active": 1
			})
			resource.insert(ignore_permissions=True)

		# Create test Availability Plan
		if not frappe.db.exists("Availability Plan", "Test Plan"):
			plan = frappe.get_doc({
				"doctype": "Availability Plan",
				"plan_name": "Test Plan",
				"is_active": 1
			})
			plan.insert(ignore_permissions=True)

		frappe.db.commit()

	def test_merge_intervals_no_overlap(self):
		"""Test merging intervals with no overlap."""
		tz = pytz.timezone("America/Bogota")
		intervals = [
			{
				"start": tz.localize(datetime(2026, 1, 20, 9, 0)),
				"end": tz.localize(datetime(2026, 1, 20, 10, 0))
			},
			{
				"start": tz.localize(datetime(2026, 1, 20, 11, 0)),
				"end": tz.localize(datetime(2026, 1, 20, 12, 0))
			}
		]

		result = _merge_intervals(intervals)
		self.assertEqual(len(result), 2)

	def test_merge_intervals_with_overlap(self):
		"""Test merging overlapping intervals."""
		tz = pytz.timezone("America/Bogota")
		intervals = [
			{
				"start": tz.localize(datetime(2026, 1, 20, 9, 0)),
				"end": tz.localize(datetime(2026, 1, 20, 10, 30))
			},
			{
				"start": tz.localize(datetime(2026, 1, 20, 10, 0)),
				"end": tz.localize(datetime(2026, 1, 20, 12, 0))
			}
		]

		result = _merge_intervals(intervals)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["start"], tz.localize(datetime(2026, 1, 20, 9, 0)))
		self.assertEqual(result[0]["end"], tz.localize(datetime(2026, 1, 20, 12, 0)))

	def test_merge_intervals_adjacent(self):
		"""Test merging adjacent intervals."""
		tz = pytz.timezone("America/Bogota")
		intervals = [
			{
				"start": tz.localize(datetime(2026, 1, 20, 9, 0)),
				"end": tz.localize(datetime(2026, 1, 20, 10, 0))
			},
			{
				"start": tz.localize(datetime(2026, 1, 20, 10, 0)),
				"end": tz.localize(datetime(2026, 1, 20, 11, 0))
			}
		]

		result = _merge_intervals(intervals)
		self.assertEqual(len(result), 1)

	def test_interval_subtract_no_overlap(self):
		"""Test subtracting interval with no overlap."""
		tz = pytz.timezone("America/Bogota")
		interval = {
			"start": tz.localize(datetime(2026, 1, 20, 9, 0)),
			"end": tz.localize(datetime(2026, 1, 20, 12, 0))
		}
		block = {
			"start": tz.localize(datetime(2026, 1, 20, 14, 0)),
			"end": tz.localize(datetime(2026, 1, 20, 15, 0))
		}

		result = _interval_subtract(interval, block)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0], interval)

	def test_interval_subtract_covers_all(self):
		"""Test subtracting interval that covers all."""
		tz = pytz.timezone("America/Bogota")
		interval = {
			"start": tz.localize(datetime(2026, 1, 20, 10, 0)),
			"end": tz.localize(datetime(2026, 1, 20, 11, 0))
		}
		block = {
			"start": tz.localize(datetime(2026, 1, 20, 9, 0)),
			"end": tz.localize(datetime(2026, 1, 20, 12, 0))
		}

		result = _interval_subtract(interval, block)
		self.assertEqual(len(result), 0)

	def test_interval_subtract_start(self):
		"""Test subtracting interval that covers start."""
		tz = pytz.timezone("America/Bogota")
		interval = {
			"start": tz.localize(datetime(2026, 1, 20, 9, 0)),
			"end": tz.localize(datetime(2026, 1, 20, 12, 0))
		}
		block = {
			"start": tz.localize(datetime(2026, 1, 20, 8, 0)),
			"end": tz.localize(datetime(2026, 1, 20, 10, 0))
		}

		result = _interval_subtract(interval, block)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["start"], tz.localize(datetime(2026, 1, 20, 10, 0)))
		self.assertEqual(result[0]["end"], tz.localize(datetime(2026, 1, 20, 12, 0)))

	def test_interval_subtract_end(self):
		"""Test subtracting interval that covers end."""
		tz = pytz.timezone("America/Bogota")
		interval = {
			"start": tz.localize(datetime(2026, 1, 20, 9, 0)),
			"end": tz.localize(datetime(2026, 1, 20, 12, 0))
		}
		block = {
			"start": tz.localize(datetime(2026, 1, 20, 11, 0)),
			"end": tz.localize(datetime(2026, 1, 20, 13, 0))
		}

		result = _interval_subtract(interval, block)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["start"], tz.localize(datetime(2026, 1, 20, 9, 0)))
		self.assertEqual(result[0]["end"], tz.localize(datetime(2026, 1, 20, 11, 0)))

	def test_interval_subtract_middle(self):
		"""Test subtracting interval in the middle (splits in two)."""
		tz = pytz.timezone("America/Bogota")
		interval = {
			"start": tz.localize(datetime(2026, 1, 20, 9, 0)),
			"end": tz.localize(datetime(2026, 1, 20, 12, 0))
		}
		block = {
			"start": tz.localize(datetime(2026, 1, 20, 10, 0)),
			"end": tz.localize(datetime(2026, 1, 20, 11, 0))
		}

		result = _interval_subtract(interval, block)
		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["start"], tz.localize(datetime(2026, 1, 20, 9, 0)))
		self.assertEqual(result[0]["end"], tz.localize(datetime(2026, 1, 20, 10, 0)))
		self.assertEqual(result[1]["start"], tz.localize(datetime(2026, 1, 20, 11, 0)))
		self.assertEqual(result[1]["end"], tz.localize(datetime(2026, 1, 20, 12, 0)))

	def tearDown(self):
		"""Clean up after tests."""
		frappe.db.rollback()


def run_tests():
	"""Run all tests in this module."""
	unittest.main()
