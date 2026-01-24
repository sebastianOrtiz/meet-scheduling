# Copyright (c) 2026, Sebastian Ortiz Valencia and contributors
# For license information, please see license.txt

"""
Availability Plan DocType

Plantilla semanal reutilizable de disponibilidad.
Define franjas horarias por día de semana.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, get_time
from datetime import time, timedelta
from typing import List, Dict, Any


class AvailabilityPlan(Document):
	"""
	Availability Plan with validation for slots.

	Validations:
	- plan_name required
	- valid_from < valid_to (if both present)
	- Each slot: start_time < end_time
	- No overlapping slots on same weekday
	- At least one slot required
	"""

	def validate(self) -> None:
		"""
		Validación antes de guardar.
		"""
		self._validate_plan_name()
		self._validate_validity_dates()
		self._validate_slots_exist()
		self._validate_slots_times()
		self._validate_no_overlapping_slots()

	def _validate_plan_name(self) -> None:
		"""Valida que plan_name esté presente."""
		if not self.plan_name:
			frappe.throw(_("Plan Name es requerido"))

	def _validate_validity_dates(self) -> None:
		"""Valida que valid_from < valid_to si ambos están presentes."""
		if self.valid_from and self.valid_to:
			from_date = getdate(self.valid_from)
			to_date = getdate(self.valid_to)

			if from_date > to_date:
				frappe.throw(_("Valid From debe ser menor o igual que Valid To"))

	def _validate_slots_exist(self) -> None:
		"""Valida que exista al menos un slot."""
		if not self.availability_slots or len(self.availability_slots) == 0:
			frappe.throw(_("Debe agregar al menos un Availability Slot"))

	def _validate_slots_times(self) -> None:
		"""
		Valida que cada slot tenga start_time < end_time.
		También valida que los tiempos estén presentes.
		"""
		for idx, slot in enumerate(self.availability_slots, 1):
			# Validar que weekday esté presente
			if not slot.weekday:
				frappe.throw(_(f"Fila {idx}: Weekday es requerido"))

			# Validar que start_time esté presente
			if not slot.start_time:
				frappe.throw(_(f"Fila {idx}: Start Time es requerido"))

			# Validar que end_time esté presente
			if not slot.end_time:
				frappe.throw(_(f"Fila {idx}: End Time es requerido"))

			# Convertir a time objects para comparar
			start = self._to_time(slot.start_time)
			end = self._to_time(slot.end_time)

			if start >= end:
				frappe.throw(
					_(f"Fila {idx} ({slot.weekday}): Start Time ({start.strftime('%H:%M')}) debe ser menor que End Time ({end.strftime('%H:%M')})")
				)

			# Validar capacity si está presente (debe ser > 0)
			if slot.capacity is not None and slot.capacity <= 0:
				frappe.throw(_(f"Fila {idx} ({slot.weekday}): Capacity debe ser mayor que 0"))

	def _validate_no_overlapping_slots(self) -> None:
		"""
		Valida que no haya slots solapados en el mismo día.

		Dos slots se solapan si:
		- Son del mismo weekday
		- slot1.start < slot2.end AND slot1.end > slot2.start
		"""
		# Agrupar slots por weekday
		slots_by_day: Dict[str, List[Dict[str, Any]]] = {}

		for idx, slot in enumerate(self.availability_slots, 1):
			weekday = slot.weekday
			if weekday not in slots_by_day:
				slots_by_day[weekday] = []

			start = self._to_time(slot.start_time)
			end = self._to_time(slot.end_time)

			slots_by_day[weekday].append({
				"idx": idx,
				"start": start,
				"end": end,
				"slot": slot
			})

		# Verificar overlaps en cada día
		for weekday, slots in slots_by_day.items():
			if len(slots) < 2:
				continue

			# Ordenar por start_time
			slots.sort(key=lambda x: x["start"])

			# Comparar cada par consecutivo
			for i in range(len(slots) - 1):
				current = slots[i]
				next_slot = slots[i + 1]

				# Overlap: current.end > next.start
				if current["end"] > next_slot["start"]:
					frappe.throw(
						_(f"{weekday}: Slots solapados - Fila {current['idx']} ({current['start'].strftime('%H:%M')}-{current['end'].strftime('%H:%M')}) "
						  f"se solapa con Fila {next_slot['idx']} ({next_slot['start'].strftime('%H:%M')}-{next_slot['end'].strftime('%H:%M')})")
					)

	def _to_time(self, time_value) -> time:
		"""
		Convierte diferentes formatos de tiempo a datetime.time.

		Args:
			time_value: puede ser time, timedelta (desde medianoche), o string

		Returns:
			datetime.time object
		"""
		if isinstance(time_value, time):
			return time_value
		elif isinstance(time_value, timedelta):
			# timedelta representa tiempo desde medianoche
			from datetime import datetime
			return (datetime.min + time_value).time()
		elif isinstance(time_value, str):
			return get_time(time_value)
		else:
			# Intentar convertir con get_time de frappe
			return get_time(time_value)
