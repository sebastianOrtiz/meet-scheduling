"""
Slot Generation Service

Generates discrete time slots for UI display, considering:
- Effective availability
- Existing appointments
- Capacity remaining
"""

import frappe
from datetime import timedelta, date
from typing import List, Dict, Union, Any
from .availability import get_effective_availability
from .overlap import check_overlap


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

	Algoritmo:
		1. Obtener effective_availability para rango
		2. Obtener slot_duration_minutes del calendar_resource
		3. Para cada intervalo disponible:
			a. Generar slots discretos cada slot_duration_minutes
			b. Para cada slot, verificar overlaps y capacity
			c. Marcar capacity_remaining
		4. Retornar lista ordenada
	"""
	# 1. Obtener Calendar Resource y slot_duration_minutes
	resource = frappe.get_doc("Calendar Resource", calendar_resource)
	slot_duration_minutes = resource.slot_duration_minutes or 30
	capacity = resource.capacity or 1

	# 2. Obtener availability efectiva para el rango
	availability_intervals = get_effective_availability(
		calendar_resource, start_date, end_date
	)

	slots = []

	# 3. Para cada intervalo disponible, generar slots discretos
	# availability_intervals es un dict: {"2026-01-15": [intervals], ...}
	for date_intervals in availability_intervals.values():
		for interval in date_intervals:
			interval_start = interval["start"]
			interval_end = interval["end"]

			# Generar slots cada slot_duration_minutes
			current_slot_start = interval_start

			while current_slot_start < interval_end:
				current_slot_end = current_slot_start + timedelta(minutes=slot_duration_minutes)

				# Si el slot se pasa del intervalo, truncar
				if current_slot_end > interval_end:
					break

				# 4. Verificar overlaps y capacity para este slot
				overlap_result = check_overlap(
					calendar_resource,
					current_slot_start,
					current_slot_end,
					exclude_appointment=None
				)

				capacity_remaining = overlap_result["capacity_available"]
				is_available = capacity_remaining > 0

				# Crear slot
				slot = {
					"start": current_slot_start.strftime("%Y-%m-%d %H:%M:%S"),
					"end": current_slot_end.strftime("%Y-%m-%d %H:%M:%S"),
					"capacity_remaining": capacity_remaining,
					"is_available": is_available
				}

				slots.append(slot)

				# Avanzar al siguiente slot
				current_slot_start = current_slot_end

	# 5. Retornar lista ordenada (ya están ordenados por construcción)
	return slots
