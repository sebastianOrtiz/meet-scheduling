# Tests - Meet Scheduling App

Este directorio contiene tests unitarios e de integración para la aplicación Meet Scheduling.

## Estructura de Tests

```
tests/
├── __init__.py
├── README.md                    # Este archivo
├── test_availability.py         # Tests para scheduling/availability.py
├── test_overlap.py              # Tests para scheduling/overlap.py
├── test_slots.py                # Tests para scheduling/slots.py
├── test_tasks.py                # Tests para scheduling/tasks.py
└── test_appointment_api.py      # Tests para api/appointment_api.py

doctype/appointment/
└── test_appointment.py          # Tests para DocType Appointment
```

## Ejecutar Tests

### Ejecutar Todos los Tests de la App

```bash
cd frappe-bench
bench --site development.localhost run-tests --app meet_scheduling
```

### Ejecutar Tests de un Módulo Específico

```bash
# Tests de availability
bench --site development.localhost run-tests --module meet_scheduling.meet_scheduling.tests.test_availability

# Tests de overlap
bench --site development.localhost run-tests --module meet_scheduling.meet_scheduling.tests.test_overlap

# Tests de slots
bench --site development.localhost run-tests --module meet_scheduling.meet_scheduling.tests.test_slots

# Tests de tasks
bench --site development.localhost run-tests --module meet_scheduling.meet_scheduling.tests.test_tasks

# Tests de API
bench --site development.localhost run-tests --module meet_scheduling.meet_scheduling.tests.test_appointment_api

# Tests del DocType
bench --site development.localhost run-tests --doctype Appointment
```

### Ejecutar un Test Específico

```bash
# Ejemplo: Ejecutar solo test_merge_intervals_with_overlap
bench --site development.localhost run-tests --module meet_scheduling.meet_scheduling.tests.test_availability --test TestAvailability.test_merge_intervals_with_overlap
```

### Ejecutar con Verbosidad

```bash
bench --site development.localhost run-tests --app meet_scheduling --verbose
```

### Ejecutar con Coverage

```bash
bench --site development.localhost run-tests --app meet_scheduling --coverage
```

## Cobertura de Tests

### test_availability.py

Tests para `scheduling/availability.py`:
- ✅ Merge de intervalos sin overlap
- ✅ Merge de intervalos con overlap
- ✅ Merge de intervalos adyacentes
- ✅ Sustracción de intervalos (5 casos)
- ⏳ get_availability_slots_for_day (requiere configuración completa)
- ⏳ get_effective_availability (requiere configuración completa)

### test_overlap.py

Tests para `scheduling/overlap.py`:
- ✅ Sin overlaps
- ✅ Con overlap de appointment confirmado
- ✅ Capacity excedida
- ✅ Filtrado de drafts expirados
- ✅ Drafts activos cuentan
- ✅ Exclusión de appointments para ediciones

### test_slots.py

Tests para `scheduling/slots.py`:
- ✅ Retorna lista
- ✅ Estructura de slots correcta
- ✅ Duración de slots (básico)

### test_tasks.py

Tests para `scheduling/tasks.py`:
- ✅ Retorna count de drafts cancelados
- ✅ Cancela drafts expirados
- ✅ No cancela drafts activos
- ✅ No afecta appointments confirmados

### test_appointment.py

Tests para `doctype/appointment/appointment.py`:
- ✅ Validación de consistencia de fechas
- ✅ Cálculo automático de draft_expires_at
- ✅ Status Confirmed en submit
- ✅ Requiere calendar_resource

### test_appointment_api.py

Tests para `api/appointment_api.py`:
- ✅ get_available_slots retorna lista
- ✅ get_available_slots falla con resource inválido
- ✅ validate_appointment retorna estructura correcta
- ✅ validate_appointment detecta fechas inválidas
- ✅ validate_appointment detecta end < start
- ✅ generate_meeting retorna estructura correcta

## Configuración Requerida para Tests

Algunos tests requieren configuración adicional:

1. **Availability Plan**: Crear un plan de disponibilidad con slots definidos
2. **Video Call Profile**: Para tests de generación de meetings
3. **Provider Account**: Para tests de video calls

## Ejecutar Tests en CI/CD

Los tests se pueden ejecutar en CI/CD usando:

```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Frappe
        run: |
          # Setup Frappe environment
      - name: Run Tests
        run: |
          cd frappe-bench
          bench --site test_site run-tests --app meet_scheduling --coverage
```

## Notas

- Todos los tests usan `frappe.db.rollback()` en tearDown para evitar contaminar la base de datos
- Los tests crean datos de prueba con nombres únicos (ej: "Test Resource API")
- Se recomienda ejecutar tests en un site de prueba, no en producción

## Agregar Nuevos Tests

Para agregar nuevos tests:

1. Crear archivo `test_<module>.py` en esta carpeta
2. Heredar de `unittest.TestCase` o `FrappeTestCase`
3. Implementar `setUp()` y `tearDown()`
4. Escribir métodos de test con prefix `test_`
5. Documentar cada test con docstring

Ejemplo:

```python
import unittest
import frappe

class TestNewFeature(unittest.TestCase):
    def setUp(self):
        """Setup test data."""
        pass

    def test_something(self):
        """Test that something works."""
        # Test code here
        self.assertTrue(True)

    def tearDown(self):
        """Cleanup."""
        frappe.db.rollback()
```
