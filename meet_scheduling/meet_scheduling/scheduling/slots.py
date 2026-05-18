"""
Slot Generation Service

Generates discrete time slots for UI display, considering:
- Effective availability
- Existing appointments
- Capacity remaining
"""

import frappe
from datetime import timedelta, date
from frappe.utils import now_datetime, get_datetime
from typing import List, Dict, Union, Any
from .availability import get_effective_availability


def generate_available_slots(
	calendar_resource: str,
	start_date: Union[date, str],
	end_date: Union[date, str]
) -> List[Dict[str, Any]]:
	"""
	Genera slots discretos disponibles para UI.

	Args:
		calendar_resource: nombre del Calendar Resource
		start_date: fecha inicial
		end_date: fecha final

	Returns:
		list[dict]: [
			{
				"start": "2026-01-15 09:00:00",
				"end": "2026-01-15 09:30:00",
				"capacity_remaining": 1,
				"is_available": True
			},
			...
		]

	Performance:
		Pre-carga todos los appointments del rango en UNA sola query y verifica
		overlaps en memoria. Anteriormente hacía una query por slot (N+1).
	"""
	# 1. Obtener Calendar Resource (única query inicial)
	resource = frappe.get_doc("Calendar Resource", calendar_resource)
	slot_duration_minutes = resource.slot_duration_minutes or 30
	capacity = resource.capacity or 1

	# 2. Obtener availability efectiva para el rango
	availability_intervals = get_effective_availability(
		calendar_resource, start_date, end_date
	)

	# 3. Pre-cargar TODOS los appointments del rango (1 sola query)
	active_appointments = _get_active_appointments_in_range(
		calendar_resource, start_date, end_date
	)

	slots = []

	# 4. Para cada intervalo disponible, generar slots discretos
	for date_intervals in availability_intervals.values():
		for interval in date_intervals:
			interval_start = interval["start"]
			interval_end = interval["end"]

			current_slot_start = interval_start

			while current_slot_start < interval_end:
				current_slot_end = current_slot_start + timedelta(minutes=slot_duration_minutes)

				if current_slot_end > interval_end:
					break

				# Verificar overlaps en memoria (sin queries adicionales)
				overlap_count = _count_overlaps_in_memory(
					active_appointments, current_slot_start, current_slot_end
				)

				capacity_remaining = max(0, capacity - overlap_count)
				is_available = capacity_remaining > 0

				slots.append({
					"start": current_slot_start.strftime("%Y-%m-%d %H:%M:%S"),
					"end": current_slot_end.strftime("%Y-%m-%d %H:%M:%S"),
					"capacity_remaining": capacity_remaining,
					"is_available": is_available
				})

				current_slot_start = current_slot_end

	return slots


def _get_active_appointments_in_range(
	calendar_resource: str,
	start_date: Union[date, str],
	end_date: Union[date, str]
) -> List[Dict[str, Any]]:
	"""
	Pre-carga todos los appointments activos del rango con una sola query.

	Activos = Draft no expirados + Confirmed.
	"""
	if isinstance(start_date, str):
		start_date = get_datetime(start_date).date()
	if isinstance(end_date, str):
		end_date = get_datetime(end_date).date()

	# Rango ampliado: incluye un margen para citas que cruzan medianoche
	range_start = f"{start_date} 00:00:00"
	range_end = f"{end_date} 23:59:59"

	appointments = frappe.get_all(
		"Appointment",
		filters={
			"calendar_resource": calendar_resource,
			"status": ["in", ["Draft", "Confirmed"]],
			"start_datetime": ["<=", range_end],
			"end_datetime": [">=", range_start],
		},
		fields=["name", "status", "draft_expires_at", "start_datetime", "end_datetime"],
	)

	# Filtrar Drafts expirados
	current_time = now_datetime()
	active = []

	for appt in appointments:
		if appt.status == "Draft" and appt.draft_expires_at:
			expires_at = get_datetime(appt.draft_expires_at)
			if expires_at < current_time:
				continue

		active.append({
			"name": appt.name,
			"start_datetime": get_datetime(appt.start_datetime),
			"end_datetime": get_datetime(appt.end_datetime),
		})

	return active


def _count_overlaps_in_memory(
	appointments: List[Dict[str, Any]],
	slot_start,
	slot_end,
) -> int:
	"""
	Cuenta overlaps en memoria contra una lista pre-cargada.
	Overlap: appt.start < slot_end AND appt.end > slot_start.
	"""
	count = 0
	for appt in appointments:
		if appt["start_datetime"] < slot_end and appt["end_datetime"] > slot_start:
			count += 1
	return count
