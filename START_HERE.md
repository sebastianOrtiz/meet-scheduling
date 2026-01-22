# 🚀 START HERE - Meet Scheduling Implementation

**Fecha**: 2026-01-21
**Estado**: Listo para comenzar implementación

---

## 📋 Resumen Ejecutivo

Has creado los DocTypes básicos y toda la documentación está completa. Ahora debes implementar la lógica.

### ✅ Lo que ya está hecho:
- DocTypes creados (estructura JSON)
- Documentación técnica completa
- Guía de usuario
- Decisiones de diseño confirmadas
- Plan de implementación detallado

### 🔄 Lo que falta implementar:
- Lógica de validación en DocTypes
- Servicios de scheduling (availability, overlap, slots)
- Adaptadores de videollamadas
- API endpoints
- Tests

---

## 📁 Documentos Importantes

| Documento | Propósito | Cuándo leer |
|-----------|-----------|-------------|
| **[START_HERE.md](START_HERE.md)** (este archivo) | 🚀 Guía de inicio rápido | **PRIMERO - Empezar aquí** |
| [CLAUDE.md](CLAUDE.md) | Referencia completa de la app | Para entender arquitectura general |
| [docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md) | Decisiones de diseño confirmadas | Antes de implementar cualquier lógica |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Plan paso a paso | Durante toda la implementación |
| [docs/README.md](docs/README.md) | Documentación técnica detallada | Para algoritmos y reglas de negocio |
| [docs/USER_GUIDE.ms](docs/USER_GUIDE.ms) | Guía de usuario | Para entender casos de uso |

---

## 🎯 Decisiones de Diseño Confirmadas

### 1️⃣ Validación de Overlaps
- ✅ Validar desde Draft (advertencia)
- ✅ Bloquear en Submit (error)

### 2️⃣ Estados que Bloquean Horarios
- ✅ Draft y Confirmed bloquean
- ✅ Drafts expiran en 15 minutos (configurable)
- ✅ Scheduled task limpia drafts expirados cada 15 min

### 3️⃣ Cambio de Hora con Meeting Creado
- ✅ Meeting automático: Cancelar + crear nuevo
- ✅ Meeting manual: Mantener enlace, solo advertir

### 4️⃣ Validación de Slot Duration
- ✅ Validar con advertencia
- ✅ Permitir override (no bloquear)

---

## 🛠️ Primeros Pasos

### Paso 1: Agregar Campos Adicionales (15 min)

**Calendar Resource**:
1. Ir a Customize Form → Calendar Resource
2. Agregar campo:
   - Fieldname: `draft_expiration_minutes`
   - Type: Int
   - Label: Draft Expiration (Minutes)
   - Default: 15
   - Insert after: capacity
3. Save

**Appointment**:
1. Ir a Customize Form → Appointment
2. Agregar campo:
   - Fieldname: `draft_expires_at`
   - Type: Datetime
   - Label: Draft Expires At
   - Read Only: ✅
   - Hidden: ✅
   - Insert after: status
3. Save

**Migrar**:
```bash
cd /workspace/development/frappe-bench
bench --site [tu-site] migrate
```

---

### Paso 2: Crear Estructura de Módulos (15 min)

```bash
cd /workspace/development/frappe-bench/apps/meet_scheduling/meet_scheduling/meet_scheduling

# Crear directorios
mkdir -p scheduling video_calls api

# Crear archivos vacíos
touch scheduling/__init__.py
touch scheduling/availability.py
touch scheduling/overlap.py
touch scheduling/slots.py
touch scheduling/tasks.py

touch video_calls/__init__.py
touch video_calls/base.py
touch video_calls/factory.py
touch video_calls/google_meet.py
touch video_calls/microsoft_teams.py

touch api/__init__.py
touch api/appointment_api.py
```

---

### Paso 3: Configurar Scheduled Task (5 min)

**Editar**: `meet_scheduling/meet_scheduling/hooks.py`

Descomentar y agregar:
```python
# Scheduled Tasks
# ---------------

scheduler_events = {
    "cron": {
        "*/15 * * * *": [  # Cada 15 minutos
            "meet_scheduling.meet_scheduling.scheduling.tasks.cleanup_expired_drafts"
        ]
    }
}
```

---

### Paso 4: Comenzar Implementación (Seguir docs/IMPLEMENTATION_PLAN.md)

**Orden recomendado**:

#### Fase 1: Servicios de Scheduling (1-2 días)
1. `scheduling/availability.py` (6-8 horas)
2. `scheduling/overlap.py` (4-6 horas)
3. `scheduling/slots.py` (4-6 horas)
4. `scheduling/tasks.py` (2-3 horas)

#### Fase 2: Servicios de Videollamadas (1 día)
1. `video_calls/base.py` (1 hora)
2. `video_calls/factory.py` (1 hora)
3. `video_calls/google_meet.py` (mock) (2 horas)
4. `video_calls/microsoft_teams.py` (mock) (2 horas)

#### Fase 3: Lógica de DocTypes (2-3 días)
1. Availability Plan (2 horas)
2. Calendar Exception (2 horas)
3. Calendar Resource (2 horas)
4. **Appointment** (8-12 horas) - El más complejo:
   - validate()
   - on_submit()
   - on_cancel()
   - on_update_after_submit()

#### Fase 4: API Endpoints (1 día)
1. get_available_slots() (2 horas)
2. validate_appointment() (2 horas)
3. generate_meeting() (2 horas)

#### Fase 5: Tests (1-2 días)
1. Unit tests de scheduling
2. Integration tests de Appointment
3. API tests

---

## 📊 Tiempo Estimado por Fase

| Fase | Duración | Prioridad |
|------|----------|-----------|
| Fase 0 (preparación) | 1 hora | 🔴 Crítica |
| Fase 1 (scheduling) | 1-2 días | 🔴 Crítica |
| Fase 2 (video calls) | 1 día | 🔴 Crítica |
| Fase 3 (doctypes) | 2-3 días | 🔴 Crítica |
| Fase 4 (API) | 1 día | 🔴 Crítica |
| Fase 5 (tests) | 1-2 días | 🔴 Crítica |
| **Total MVP** | **6-10 días** | |
| Fase 6 (permisos) | 4 horas | 🟡 Media |
| Fase 7 (OAuth real) | 2-3 días | 🟢 Baja (usar mocks) |
| Fase 8 (frontend) | 1-2 días | 🟢 Baja (UI estándar) |

---

## 🧪 Testing Strategy

### Durante Desarrollo
```bash
# Ejecutar tests después de cada módulo
bench --site [site] run-tests --app meet_scheduling --module meet_scheduling.scheduling.tests.test_availability

# Ejecutar todos los tests
bench --site [site] run-tests --app meet_scheduling
```

### Manual Testing
1. Crear datos de prueba:
   - Availability Plan con slots
   - Calendar Resource
   - Calendar Exceptions
2. Crear Appointments y verificar validaciones
3. Probar expiración de Drafts (reducir a 1 min para testing)

---

## 🆘 Comandos Útiles

```bash
# Migrar después de cambios
bench --site [site] migrate

# Limpiar caché
bench --site [site] clear-cache

# Ver logs
tail -f logs/[site].log

# Ejecutar scheduled task manualmente (para testing)
bench --site [site] console
>>> from meet_scheduling.meet_scheduling.scheduling.tasks import cleanup_expired_drafts
>>> cleanup_expired_drafts()

# Pre-commit hooks
cd apps/meet_scheduling
pre-commit run --all-files
```

---

## 📝 Checklist de Inicio

Antes de comenzar a codear:

- [ ] Leer [docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md) completo
- [ ] Leer [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) Fase 0-3
- [ ] Agregar campos a Calendar Resource
- [ ] Agregar campos a Appointment
- [ ] Migrar base de datos
- [ ] Crear estructura de directorios
- [ ] Configurar scheduler_events en hooks.py
- [ ] Hacer commit de cambios: `git commit -m "feat: prepare for implementation"`

---

## 🎯 Definition of Done (MVP)

El MVP está completo cuando:

### Funcionalidad
- [ ] Se pueden crear Calendar Resources con Availability Plans
- [ ] Se pueden crear Appointments con validación de disponibilidad
- [ ] Se validan overlaps según capacity
- [ ] Drafts expiran automáticamente después de 15 minutos
- [ ] Se pueden generar meetings (mock) en modo automático
- [ ] Se pueden pegar meetings manuales
- [ ] Se puede cancelar Appointments
- [ ] Cambio de hora recrea meeting automático

### Calidad
- [ ] Todos los tests unitarios pasan
- [ ] Todos los tests de integración pasan
- [ ] No hay errores en logs durante testing
- [ ] Código con docstrings completos
- [ ] Pre-commit hooks pasan

### Documentación
- [ ] README actualizado
- [ ] Casos de uso documentados
- [ ] API endpoints documentados

---

## 💡 Tips Importantes

### Durante Implementación

1. **Commit frecuentemente**: Después de cada función implementada
2. **Tests primero**: Escribir tests ayuda a pensar en edge cases
3. **Debug con console**: `bench --site [site] console` es tu amigo
4. **Logs everywhere**: Usar `frappe.logger().info()` para debugging
5. **Permisos**: Usar `ignore_permissions=True` en scheduled tasks

### Errores Comunes

1. **Import circular**: Usar imports dentro de funciones si hay conflicto
2. **Timezone**: Siempre usar timezone del Calendar Resource
3. **Commit en loops**: Usar `frappe.db.commit()` cuidadosamente en loops
4. **SQL injection**: Usar parámetros, nunca concatenar strings
5. **N+1 queries**: Usar `frappe.db.sql()` con joins para bulk operations

---

## 🤝 Siguiente Paso

1. **Confirmar** que leíste y entendiste las decisiones de diseño
2. **Ejecutar** Paso 1 (agregar campos)
3. **Ejecutar** Paso 2 (crear estructura)
4. **Ejecutar** Paso 3 (configurar scheduled task)
5. **Abrir** [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) y empezar con Fase 1, Tarea 1.1

---

## 📞 Contacto

**Desarrollador**: Sebastian Ortiz Valencia
**Email**: sebastianortiz989@gmail.com

---

**¡Éxito con la implementación! 🚀**
