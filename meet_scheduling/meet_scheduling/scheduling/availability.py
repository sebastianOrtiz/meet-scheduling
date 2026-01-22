"""
Availability Service

Provides functions to calculate effective availability for Calendar Resources,
considering:
- Availability Plans (weekly templates)
- Calendar Exceptions (closures, blocks, extra availability)
- Timezones
"""

import frappe
from frappe.utils import get_datetime, getdate, get_time, now_datetime
from datetime import datetime, time, timedelta, date
from typing import List, Dict, Union, Optional, Any
import pytz


def _to_time(time_value: Union[time, timedelta, str]) -> time:
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
		return (datetime.min + time_value).time()
	elif isinstance(time_value, str):
		return get_time(time_value)
	else:
		raise ValueError(f"Cannot convert {type(time_value)} to time")


def get_availability_slots_for_day(
	calendar_resource: Union[str, Any],
	target_date: Union[date, str]
) -> List[Dict[str, datetime]]:
	"""
	Obtiene slots de disponibilidad para un día específico.

	Args:
		calendar_resource: nombre del Calendar Resource o doc
		target_date: fecha (date object o string YYYY-MM-DD)

	Returns:
		list[dict]: [
			{"start": datetime, "end": datetime},
			...
		]

	Algoritmo:
		1. Obtener availability_plan del calendar_resource
		2. Obtener weekday del date (Monday, Tuesday, etc.)
		3. Obtener Availability Slots para ese weekday
		4. Convertir time slots a datetime con timezone del calendar_resource
		5. Aplicar excepciones (Closed, Blocked, Extra Availability)
		6. Merge intervalos adyacentes/overlapping
		7. Retornar lista ordenada
	"""
	# Si es string, convertir a nombre
	if isinstance(calendar_resource, str):
		resource_name = calendar_resource
		resource = frappe.get_doc("Calendar Resource", calendar_resource)
	else:
		resource_name = calendar_resource.name
		resource = calendar_resource

	# Convertir date si es string
	if isinstance(target_date, str):
		target_date = getdate(target_date)

	# Verificar que esté activo
	if not resource.is_active:
		return []

	# Obtener availability plan
	if not resource.availability_plan:
		frappe.log_error(
			f"Calendar Resource {resource_name} no tiene Availability Plan asignado",
			"Get Availability Slots"
		)
		return []

	plan = frappe.get_doc("Availability Plan", resource.availability_plan)

	if not plan.is_active:
		return []

	# Verificar vigencia del plan
	if plan.valid_from and target_date < getdate(plan.valid_from):
		return []
	if plan.valid_to and target_date > getdate(plan.valid_to):
		return []

	# Obtener día de la semana (Monday, Tuesday, etc.)
	weekday_name = target_date.strftime("%A")

	# Obtener timezone del resource
	tz_name = resource.timezone or "UTC"
	if tz_name == "system timezone":
		tz_name = frappe.utils.get_system_timezone()

	try:
		tz = pytz.timezone(tz_name)
	except Exception:
		tz = pytz.UTC
		frappe.log_error(
			f"Invalid timezone '{tz_name}' for {resource_name}, usando UTC",
			"Get Availability Slots"
		)

	# Obtener slots del plan para este día
	base_intervals = []

	# Buscar en child table 'availability_slots'
	if hasattr(plan, 'availability_slots'):
		slots = plan.availability_slots
	elif hasattr(plan, 'slots'):
		# Backward compatibility por si alguien usó 'slots'
		slots = plan.slots
	else:
		# Fallback: buscar directamente en la tabla hija
		slots = frappe.get_all(
			"Availability Slot",
			filters={"parent": plan.name, "parenttype": "Availability Plan"},
			fields=["weekday", "start_time", "end_time"]
		)

	for slot in slots:
		# Verificar si es el día correcto
		slot_day = slot.get("weekday") if isinstance(slot, dict) else slot.weekday

		if slot_day == weekday_name:
			start_time = slot.get("start_time") if isinstance(slot, dict) else slot.start_time
			end_time = slot.get("end_time") if isinstance(slot, dict) else slot.end_time

			# Convertir a time object (puede venir como timedelta o string)
			start_time = _to_time(start_time)
			end_time = _to_time(end_time)

			# Convertir time a datetime con la fecha target y timezone
			start_dt = datetime.combine(target_date, start_time)
			end_dt = datetime.combine(target_date, end_time)

			# Localizar a timezone
			start_dt = tz.localize(start_dt) if start_dt.tzinfo is None else start_dt
			end_dt = tz.localize(end_dt) if end_dt.tzinfo is None else end_dt

			base_intervals.append({"start": start_dt, "end": end_dt})

	# Si no hay slots para este día, retornar vacío
	if not base_intervals:
		return []

	# Aplicar excepciones
	final_intervals = _apply_exceptions(base_intervals, resource_name, target_date, tz)

	# Merge intervalos adyacentes/overlapping
	final_intervals = _merge_intervals(final_intervals)

	# Ordenar por start time
	final_intervals.sort(key=lambda x: x["start"])

	return final_intervals


def get_effective_availability(
	calendar_resource: str,
	start_date: Union[date, str],
	end_date: Union[date, str]
) -> Dict[str, List[Dict[str, datetime]]]:
	"""
	Obtiene disponibilidad efectiva para un rango de fechas.

	Args:
		calendar_resource: nombre del Calendar Resource
		start_date: fecha inicial
		end_date: fecha final

	Returns:
		dict: {
			"2026-01-15": [{"start": datetime, "end": datetime}, ...],
			"2026-01-16": [...],
			...
		}
	"""
	# Convertir a date objects
	if isinstance(start_date, str):
		start_date = getdate(start_date)
	if isinstance(end_date, str):
		end_date = getdate(end_date)

	result = {}
	current_date = start_date

	while current_date <= end_date:
		slots = get_availability_slots_for_day(calendar_resource, current_date)
		if slots:
			result[current_date.strftime("%Y-%m-%d")] = slots
		current_date += timedelta(days=1)

	return result


def _apply_exceptions(
	intervals: List[Dict[str, datetime]],
	calendar_resource: str,
	target_date: date,
	tz: pytz.tzinfo.BaseTzInfo
) -> List[Dict[str, datetime]]:
	"""
	Aplica excepciones (Closed/Blocked/Extra) a intervalos base.

	Args:
		intervals: lista de intervalos base del plan
		calendar_resource: nombre del resource
		target_date: fecha objetivo
		tz: timezone object

	Returns:
		list: intervalos después de aplicar excepciones
	"""
	# Obtener excepciones para esta fecha y resource
	exceptions = frappe.get_all(
		"Calendar Exception",
		filters={
			"calendar_resource": calendar_resource,
			"date": target_date
		},
		fields=["name", "exception_type", "start_time", "end_time", "reason"]
	)

	if not exceptions:
		return intervals

	# Procesar cada excepción
	for exc in exceptions:
		exception_type = exc.get("exception_type")

		if exception_type == "Closed":
			# Closed: elimina disponibilidad
			if exc.get("start_time") and exc.get("end_time"):
				# Closed parcial (solo un rango)
				closed_start_time = _to_time(exc.get("start_time"))
				closed_end_time = _to_time(exc.get("end_time"))
				closed_start = datetime.combine(target_date, closed_start_time)
				closed_end = datetime.combine(target_date, closed_end_time)
				closed_start = tz.localize(closed_start) if closed_start.tzinfo is None else closed_start
				closed_end = tz.localize(closed_end) if closed_end.tzinfo is None else closed_end

				# Restar este rango de todos los intervalos
				new_intervals = []
				for interval in intervals:
					result = _interval_subtract(interval, {"start": closed_start, "end": closed_end})
					new_intervals.extend(result)
				intervals = new_intervals
			else:
				# Closed todo el día
				intervals = []

		elif exception_type == "Blocked":
			# Blocked: similar a closed parcial
			if exc.get("start_time") and exc.get("end_time"):
				blocked_start_time = _to_time(exc.get("start_time"))
				blocked_end_time = _to_time(exc.get("end_time"))
				blocked_start = datetime.combine(target_date, blocked_start_time)
				blocked_end = datetime.combine(target_date, blocked_end_time)
				blocked_start = tz.localize(blocked_start) if blocked_start.tzinfo is None else blocked_start
				blocked_end = tz.localize(blocked_end) if blocked_end.tzinfo is None else blocked_end

				new_intervals = []
				for interval in intervals:
					result = _interval_subtract(interval, {"start": blocked_start, "end": blocked_end})
					new_intervals.extend(result)
				intervals = new_intervals

		elif exception_type == "Extra Availability":
			# Extra: agrega disponibilidad adicional
			if exc.get("start_time") and exc.get("end_time"):
				extra_start_time = _to_time(exc.get("start_time"))
				extra_end_time = _to_time(exc.get("end_time"))
				extra_start = datetime.combine(target_date, extra_start_time)
				extra_end = datetime.combine(target_date, extra_end_time)
				extra_start = tz.localize(extra_start) if extra_start.tzinfo is None else extra_start
				extra_end = tz.localize(extra_end) if extra_end.tzinfo is None else extra_end

				intervals.append({"start": extra_start, "end": extra_end})

	return intervals


def _merge_intervals(intervals: List[Dict[str, datetime]]) -> List[Dict[str, datetime]]:
	"""
	Une intervalos adyacentes o overlapping.

	Args:
		intervals: lista de intervalos {"start": datetime, "end": datetime}

	Returns:
		list: intervalos merged
	"""
	if not intervals:
		return []

	# Ordenar por start time
	intervals.sort(key=lambda x: x["start"])

	merged = [intervals[0]]

	for current in intervals[1:]:
		last_merged = merged[-1]

		# Si current se solapa o es adyacente a last_merged, merge
		if current["start"] <= last_merged["end"]:
			# Extend el end si es mayor
			if current["end"] > last_merged["end"]:
				last_merged["end"] = current["end"]
		else:
			# No hay overlap, agregar como nuevo intervalo
			merged.append(current)

	return merged


def _interval_subtract(
	interval: Dict[str, datetime],
	block: Dict[str, datetime]
) -> List[Dict[str, datetime]]:
	"""
	Resta un bloqueo de un intervalo.

	Args:
		interval: {"start": datetime, "end": datetime} - intervalo original
		block: {"start": datetime, "end": datetime} - bloqueo a restar

	Returns:
		list: lista de intervalos resultantes (puede ser 0, 1 o 2 intervalos)
	"""
	# Casos:
	# 1. Block no se solapa con interval -> retornar interval original
	# 2. Block cubre completamente interval -> retornar []
	# 3. Block cubre parte inicial -> retornar [parte final]
	# 4. Block cubre parte final -> retornar [parte inicial]
	# 5. Block está en medio -> retornar [parte inicial, parte final]

	# Verificar si hay overlap
	if block["end"] <= interval["start"] or block["start"] >= interval["end"]:
		# No hay overlap
		return [interval]

	# Verificar si block cubre completamente interval
	if block["start"] <= interval["start"] and block["end"] >= interval["end"]:
		# Block cubre todo
		return []

	# Block cubre parte inicial
	if block["start"] <= interval["start"] and block["end"] < interval["end"]:
		return [{"start": block["end"], "end": interval["end"]}]

	# Block cubre parte final
	if block["start"] > interval["start"] and block["end"] >= interval["end"]:
		return [{"start": interval["start"], "end": block["start"]}]

	# Block está en medio (split en dos)
	if block["start"] > interval["start"] and block["end"] < interval["end"]:
		return [
			{"start": interval["start"], "end": block["start"]},
			{"start": block["end"], "end": interval["end"]}
		]

	# Fallback (no debería llegar aquí)
	return [interval]
