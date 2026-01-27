# CLAUDE.md - Meet Scheduling App

## Descripción General

**Meet Scheduling** es una aplicación de Frappe Framework diseñada para gestionar calendarios, disponibilidad, agendamiento de citas y generación automática de enlaces de videollamadas (Google Meet / Microsoft Teams).

**Autor**: Sebastian Ortiz Valencia (sebastianortiz989@gmail.com)
**Licencia**: MIT
**Framework**: Frappe Framework (Python + JavaScript)
**Versión Python**: >= 3.10

### Propósito

La aplicación permite:
1. Configurar disponibilidad por calendario usando plantillas semanales + excepciones
2. Crear agendamientos (Appointments) con validación robusta de disponibilidad, solapes y capacidad
3. Generar automáticamente enlaces de videollamada (Google Meet / Microsoft Teams) o permitir enlaces manuales según configuración

---

## Arquitectura de DocTypes

La aplicación está compuesta por 7 DocTypes principales:

### 1. Calendar Resource
**Propósito**: Representa el recurso que se agenda (persona, sala, equipo o servicio).

**Campos principales**:
- `resource_name` (Data, unique): Nombre visible del calendario
- `resource_type` (Select): Person, Room, Equipment, Service
- `reference_doctype` (Link): DocType externo vinculado (ej: Employee)
- `reference_name` (Dynamic Link): Registro específico vinculado
- `timezone` (Data): Zona horaria del calendario (ej: "America/Bogota")
- `slot_duration_minutes` (Int): Duración mínima de cita (default: 60)
- `capacity` (Int): Citas simultáneas permitidas (default: 1)
- `availability_plan` (Link → Availability Plan): Horario semanal asignado
- `video_call_profile` (Link → Video Call Profile): Configuración de videollamada por defecto
- `is_active` (Check): Indica si se puede agendar

**Naming**: By fieldname (`resource_name`)

**Responsabilidades**:
- Define zona horaria, duración de slot y capacidad
- Vincula un plan de disponibilidad
- Vincula un perfil de videollamada por defecto

---

### 2. Availability Plan
**Propósito**: Plantilla semanal reutilizable de disponibilidad.

**Campos principales**:
- `plan_name` (Data, unique): Nombre del horario
- `is_active` (Check): Si el plan está activo
- `valid_from` (Date): Inicio de vigencia
- `valid_to` (Date): Fin de vigencia
- `notes` (Small Text): Notas internas

**Child Table**: `Availability Slot` (define franjas por día de semana)

**Naming**: By fieldname (`plan_name`)

**Responsabilidades**:
- Define franjas horarias por día de semana
- Puede asignarse a múltiples Calendar Resources
- NO guarda slots concretos por fecha (se calculan al vuelo)

---

### 3. Availability Slot (Child DocType)
**Propósito**: Define una franja horaria en un día de la semana.

**Campos esperados**:
- `day_of_week` (Select): Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
- `start_time` (Time): Hora de inicio (ej: 08:00)
- `end_time` (Time): Hora de fin (ej: 12:00)

**Nota**: Pueden existir múltiples slots por día (ej: lunes 08:00-12:00 y 14:00-18:00)

---

### 4. Calendar Exception
**Propósito**: Override de disponibilidad por fecha específica (cierres, bloqueos, aperturas extra).

**Campos principales**:
- `calendar_resource` (Link → Calendar Resource): Calendario afectado
- `exception_type` (Select): Closed, Blocked, Extra Availability
- `date` (Date): Fecha específica
- `start_time` (Time): Hora de inicio (opcional, para excepciones parciales)
- `end_time` (Time): Hora de fin (opcional)
- `reason` (Text): Motivo de la excepción

**Tipos de excepción**:
- **Closed**: Cierra todo el día o un rango específico
- **Blocked**: Bloquea un rango horario
- **Extra Availability**: Agrega disponibilidad adicional fuera del plan normal

---

### 5. Appointment
**Propósito**: El agendamiento real (transaccional).

**Naming**: Expression format `APT-{YYYY}-{#####}`

**Campos principales**:

#### Datos Base
- `calendar_resource` (Link → Calendar Resource): Agenda donde se reserva
- `start_datetime` (Datetime): Hora de inicio
- `end_datetime` (Datetime): Hora de fin
- `status` (Select): Draft, Confirmed, Cancelled, No-show, Completed
- `party_type` (Link → DocType): Tipo de entidad (ej: Customer)
- `party` (Dynamic Link): Cliente específico
- `service` (Data): Servicio agendado
- `notes` (Text): Observaciones adicionales
- `source` (Select): Web, Admin, API

#### Enlace de Llamada
- `video_call_profile` (Link → Video Call Profile): Perfil aplicado
- `call_link_mode` (Select): inherit, manual, auto
- `manual_meeting_url` (Small Text): Enlace pegado manualmente
- `manual_meeting_notes` (Small Text): Nota sobre el enlace manual

#### Resultado Final
- `meeting_url` (Small Text): **Enlace final que usan los participantes**
- `video_provider` (Select): google_meet, microsoft_teams
- `meeting_id` (Data): ID externo para editar/cancelar
- `meeting_status` (Select): not_created, created, failed
- `meeting_error` (Small Text): Mensaje de error si falló
- `provider_payload` (JSON): Respuesta cruda del proveedor
- `meeting_created_at` (Datetime): Momento de creación del enlace

**Responsabilidades**:
- Validar tiempos (start < end)
- Validar disponibilidad (plan + excepciones)
- Validar solapes vs otras citas (según capacidad)
- Resolver y persistir video_call_profile snapshot
- Generar o copiar meeting_url
- Gestionar estados del meeting

---

### 6. Video Call Profile
**Propósito**: Perfil reutilizable para definir cómo se crea (o se pega) el enlace de videollamada.

**Naming**: By fieldname (`profile_name`)

**Campos principales**:
- `profile_name` (Data, unique): Nombre del perfil
- `is_active` (Check): Si el perfil puede usarse
- `provider` (Select): google_meet, microsoft_teams
- `link_mode` (Select): auto_generate, manual_only, auto_or_manual
- `require_manual_if_auto_fails` (Check): Permitir fallback manual
- `provider_account` (Link → Provider Account): Cuenta para generación automática
- `generation_mode` (Select): api_create_meeting, static_template
- `meeting_title_template` (Data): Plantilla Jinja para título
- `meeting_description_template` (Text): Plantilla Jinja para descripción
- `manual_url_instructions` (Text): Instrucciones cuando es manual
- `default_duration_minutes` (Int): Duración por defecto
- `create_on` (Select): on_submit (recomendado), manual
- `timezone_mode` (Select): calendar_timezone, user_timezone, custom
- `extra_options_json` (JSON): Opciones adicionales del proveedor
- `fallback_profile` (Link → Video Call Profile): Perfil alternativo

**Modos de enlace**:
- **auto_generate**: Genera enlace automático vía API
- **manual_only**: El usuario pega el enlace
- **auto_or_manual**: Intenta automático, si falla permite manual

**Cuándo crear**:
- **on_submit**: Recomendado, crea el meeting al confirmar la cita
- **manual**: Solo cuando el usuario presiona un botón

---

### 7. Provider Account
**Propósito**: Credenciales para crear meetings por API (Google Meet / Microsoft Teams).

**Campos principales**:
- `account_name` (Data): Nombre identificador
- `provider` (Select): google_meet, microsoft_teams
- `owner_user` (Link → User): Usuario que autoriza la conexión
- `auth_mode` (Select): oauth_user, service_account
- `status` (Select): Connected, Expired, Revoked, Pending
- `access_token` (Password): Token de acceso (encriptado)
- `refresh_token` (Password): Token de refresco (encriptado)
- `token_expires_at` (Datetime): Expiración del token
- `scopes` (Small Text): Permisos OAuth

**Responsabilidades**:
- Almacenar credenciales de forma segura
- Gestionar estado de conexión
- Facilitar refresh token
- (Futuro) Soportar service accounts

**Seguridad**: CRÍTICO - Debe estar muy restringido con permisos, tokens encriptados

---

## Flujos de Trabajo Principales

### Flujo 1: Configurar Disponibilidad

**Actor**: Administrador

1. Crear **Availability Plan** con nombre (ej: "Horario Consultorio 2026")
2. Agregar **Availability Slots** (ej: Monday 08:00-12:00, Monday 14:00-18:00)
3. Crear **Calendar Resource** y asignar el plan
4. (Opcional) Crear **Calendar Exceptions** para fechas específicas

**Resultado**: El sistema puede calcular slots disponibles para un rango de fechas

---

### Flujo 2: Crear Appointment con Validación

**Actor**: Usuario/Staff

1. Seleccionar `calendar_resource`
2. Definir `start_datetime` y `end_datetime`
3. Completar datos del party y servicio
4. Guardar en **Draft**
5. Al confirmar (**Submit**):
   - Sistema valida disponibilidad efectiva
   - Sistema valida solapes según capacidad
   - Sistema resuelve videollamada (auto o manual)
   - Sistema completa `meeting_url`

**Resultado**: Cita confirmada y horario bloqueado

---

### Flujo 3: Videollamada - Manual vs Automática

#### Modo Manual
- `call_link_mode` = manual O perfil con `link_mode` = manual_only
- Usuario pega `manual_meeting_url`
- Sistema copia a `meeting_url` como enlace final

#### Modo Auto
- `call_link_mode` = auto O perfil con `link_mode` = auto_generate
- En `on_submit` (recomendado):
  - Se crea meeting vía adapter (factory pattern)
  - Se llena `meeting_url`, `meeting_id`, `provider_payload`, `meeting_status`

#### Modo Auto con Fallback Manual
- Perfil con `link_mode` = auto_or_manual + `require_manual_if_auto_fails` = 1
- Si falla creación:
  - Se marca `meeting_status` = failed
  - Se permite pegar `manual_meeting_url`

---

## Reglas de Negocio

### Reglas de Disponibilidad

Para que un Appointment sea válido, el rango `[start_datetime, end_datetime)` debe:

1. **Caer completamente** dentro de una franja disponible del día (Availability Slots del weekday correspondiente)
2. **No estar bloqueado** por excepciones Closed o Blocked en esa fecha/rango
3. **Puede ser habilitado extra** si existe Extra Availability que lo cubra

**Notas**:
- Si hay múltiples slots ese día, debe caber en uno de ellos
- Manejar timezone consistentemente (almacenar y comparar en timezone del Calendar Resource)

---

### Reglas de Solapamiento (Overlap)

**Definir "citas activas"**: Aquellas con `status` in (Draft, Confirmed) o solo Confirmed según política

**Condición de overlap**:
```
Existe overlap si: other.start_datetime < end_datetime AND other.end_datetime > start_datetime
```

**Filtrar por**:
- `calendar_resource` = X
- `status` in (...)
- `name` != current_doc.name

**Capacidad**:
- Si `capacity` = 1: No se permite overlap
- Si `capacity` > 1: Se permite overlap hasta N citas simultáneas

**Recomendación**:
- Bloquear solapes para Confirmed
- Para Draft, permitir solapes y validar fuerte al confirmar

---

### Reglas de Duración/Slots

Si `slot_duration_minutes` existe:
- `start_datetime` y `end_datetime` deben respetar esa granularidad
- Ejemplo: si slot_duration = 30, permitir solo múltiplos de 30min

---

## Arquitectura de Implementación

### Estructura de Código Sugerida

```
meet_scheduling/
├── meet_scheduling/
│   ├── doctype/
│   │   ├── appointment/
│   │   │   ├── appointment.py          # Lógica del DocType
│   │   │   ├── appointment.json        # Definición
│   │   │   └── appointment.js          # Frontend
│   │   ├── calendar_resource/
│   │   ├── calendar_exception/
│   │   ├── video_call_profile/
│   │   ├── provider_account/
│   │   ├── availability_plan/
│   │   └── availability_slot/
│   │
│   ├── scheduling/                      # Servicios de agendamiento
│   │   ├── availability.py              # Calcular disponibilidad efectiva
│   │   ├── overlap.py                   # Detectar colisiones
│   │   └── slots.py                     # Generar slots para UI
│   │
│   ├── video_calls/                     # Servicios de videollamada
│   │   ├── base.py                      # Interfaz base (adapter)
│   │   ├── google_meet.py               # Implementación Google Meet
│   │   ├── microsoft_teams.py           # Implementación MS Teams
│   │   └── factory.py                   # Factory pattern
│   │
│   ├── hooks.py                         # Hooks de Frappe
│   ├── modules.txt
│   └── patches.txt
```

---

### Separación de Lógica (Services)

**IMPORTANTE**: Separar lógica de negocio de los DocTypes

#### `scheduling/availability.py`
- Función: `get_effective_availability(calendar_resource, date_range)`
- Combina plan + excepciones
- Retorna intervalos disponibles

#### `scheduling/overlap.py`
- Función: `check_overlap(calendar_resource, start, end, current_appointment_name=None)`
- Detecta colisiones considerando capacidad
- Retorna lista de appointments en conflicto

#### `scheduling/slots.py`
- Función: `generate_available_slots(calendar_resource, from_date, to_date)`
- Genera slots discretos para UI
- Considera disponibilidad efectiva y appointments existentes

#### `video_calls/base.py`
```python
class VideoCallAdapter:
    def create_meeting(self, profile, appointment):
        """Retorna: {meeting_url, meeting_id, payload}"""
        raise NotImplementedError

    def update_meeting(self, profile, appointment):
        """Opcional"""
        pass

    def delete_meeting(self, profile, appointment):
        """Opcional"""
        pass
```

#### `video_calls/factory.py`
```python
def get_adapter(provider):
    if provider == "google_meet":
        return GoogleMeetAdapter()
    elif provider == "microsoft_teams":
        return TeamsAdapter()
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

---

### Convenciones de Código Python

**IMPORTANTE**: Seguir estas convenciones en toda la implementación

#### Type Hints Obligatorios

Todas las funciones deben incluir type hints para parámetros y valores de retorno:

```python
from typing import List, Dict, Union, Optional, Any
from datetime import datetime, date

# ✅ CORRECTO
def check_overlap(
    calendar_resource: str,
    start_datetime: datetime,
    end_datetime: datetime,
    exclude_appointment: Optional[str] = None
) -> Dict[str, Any]:
    """Detecta overlaps con appointments existentes."""
    pass

# ✅ CORRECTO
def get_availability_slots_for_day(
    calendar_resource: Union[str, Any],
    target_date: Union[date, str]
) -> List[Dict[str, datetime]]:
    """Obtiene slots de disponibilidad para un día."""
    pass

# ❌ INCORRECTO (sin type hints)
def check_overlap(calendar_resource, start_datetime, end_datetime, exclude_appointment=None):
    pass
```

**Tipos comunes a usar**:
- `str`, `int`, `bool`, `float` para tipos básicos
- `datetime`, `date`, `time` de módulo datetime
- `List[T]` para listas tipadas
- `Dict[K, V]` para diccionarios tipados
- `Optional[T]` para valores que pueden ser None
- `Union[T1, T2]` para múltiples tipos posibles
- `Any` cuando el tipo es dinámico (usar con moderación)

**Beneficios**:
- Mejor documentación del código
- Detección de errores con herramientas como `mypy`
- Mejor autocompletado en IDEs
- Mayor mantenibilidad

---

## Hooks y Eventos Frappe

### Appointment (DocType)

#### `validate`
- Validar consistencia básica:
  - `start_datetime` < `end_datetime`
  - Timezone normalizada
  - Slot granularity (si aplica)
- Resolver `video_call_profile` snapshot si está vacío:
  - Si `Appointment.video_call_profile` vacío → tomar de `Calendar Resource`
- Resolver modo efectivo:
  - `call_link_mode` (inherit/manual/auto) + `profile.link_mode`

#### `on_submit` (recomendado)
- **Validación fuerte final**:
  - Disponibilidad efectiva (usar servicio `availability.py`)
  - Overlaps según capacidad y status (usar servicio `overlap.py`)
- **Crear videollamada** si corresponde:
  - Si modo efectivo incluye auto Y `create_on` = on_submit
  - Usar factory para obtener adapter
  - Llamar `adapter.create_meeting(profile, appointment)`
  - Llenar `meeting_url`, `meeting_id`, `meeting_status`, `provider_payload`
- **Si modo efectivo es manual**:
  - Exigir `manual_meeting_url` para Submit
  - Copiar `manual_meeting_url` → `meeting_url`

#### `on_cancel`
- Si meeting fue creado por API:
  - Opcional: `adapter.delete_meeting(...)` o marcar cancelado sin borrar
- Marcar `status` = Cancelled

---

### Calendar Exception / Availability Plan

Normalmente solo CRUD, sin lógica pesada.

**Validaciones opcionales**:
- `start_time` < `end_time` en excepciones parciales
- No solapes absurdos dentro del mismo plan

---

## Algoritmo de Disponibilidad Efectiva

### Entrada
- `calendar_resource`
- `date` o rango de fechas

### Pasos (por cada día)

1. **Obtener slots del plan** por weekday
2. **Convertir slots a intervalos** `[start_datetime, end_datetime)` del día
3. **Obtener excepciones** del calendario para esa fecha:
   - **Closed** → elimina intervalos (o recorta si parcial)
   - **Blocked** → elimina/recorta intervalos
   - **Extra Availability** → agrega intervalos
4. **Normalizar y merge** intervalos (unificar overlaps/adyacentes)
5. **Resultado**: Lista final de intervalos disponibles

### Resultado
- Intervalos disponibles del día
- De ahí generar slots discretos según `slot_duration_minutes`

---

## API Endpoints Recomendados (Whitelisted)

### 1. `get_available_slots`
```python
@frappe.whitelist()
def get_available_slots(calendar_resource, from_date, to_date):
    """
    Retorna: [
        {
            "start": "2026-01-15 09:00:00",
            "end": "2026-01-15 09:30:00",
            "capacity_remaining": 1
        },
        ...
    ]
    """
```

### 2. `validate_appointment`
```python
@frappe.whitelist()
def validate_appointment(calendar_resource, start_datetime, end_datetime, appointment_name=None):
    """
    Retorna: {
        "valid": true/false,
        "errors": [...],
        "warnings": [...]
    }
    Útil para UI antes de guardar
    """
```

### 3. `generate_meeting`
```python
@frappe.whitelist()
def generate_meeting(appointment_name):
    """
    Solo si create_on=manual o reintentos tras falla
    Retorna: {meeting_url, meeting_id, status}
    """
```

---

## Estados y Obligatoriedad de Campos

### Draft
- Permitir crear sin `meeting_url`
- No generar meeting todavía
- No validar fuertemente (solo consistencia básica)

### Confirmed/Submitted
- **Debe estar validado**:
  - Disponibilidad efectiva
  - No solapes (según capacidad)
- **Videollamada**:
  - Si manual → `manual_meeting_url` requerido
  - Si auto → `meeting_status` = created O permitir fallback manual

### Cancelled
- Liberar horario
- Opcional: cancelar meeting en proveedor

---

## Casos Borde a Definir

1. **Excepción Closed todo el día** vs slots del plan → disponibilidad = 0
2. **Excepción Blocked parcial** recorta slot (08:00-12:00 con bloqueo 10:00-11:00 => 08:00-10:00 y 11:00-12:00)
3. **Extra Availability** puede crear franjas fuera del plan
4. **Timezone**: Citas cruzando medianoche (ideal: no permitir o manejar con cuidado)
5. **Cambio de hora** en cita ya creada con meeting:
   - Opción simple: cancelar meeting viejo + crear nuevo
6. **Capacidad**: 2 citas simultáneas, tercera debe fallar
7. **Draft overlap**: Decidir si bloquear o no en Draft (recomendado: permitir, validar en Submit)

---

## Plan de Pruebas (Mínimo)

### Unit Tests (lógica pura)
- `availability.py`: plan + excepciones (closed/blocked/extra)
- `overlap.py`: capacity=1 y capacity>1
- `slots.py`: respeta `slot_duration_minutes`

### Integration Tests (DocType)
- Crear Appointment válido → submit → meeting auto (mock adapter)
- Falla provider → fallback manual permitido
- Cancelación → meeting delete (mock) o status update
- Validación de disponibilidad con excepciones
- Validación de overlaps con capacidad

---

## Permisos y Roles (Mínimo Viable)

### Roles Sugeridos

#### Scheduling Admin
- **Permisos**: CRUD completo en:
  - Calendar Resource
  - Availability Plan
  - Calendar Exception
  - Video Call Profile
  - Provider Account
- **Restricción**: Tokens/Provider Account muy restringido

#### Scheduler / Staff
- **Permisos**: CRUD en Appointment
- **Restricción**: NO acceso a tokens/Provider Account

#### Read-only / Viewer
- **Permisos**: Ver agendas y citas
- **Restricción**: No modificar

---

## Definition of Done

El módulo está listo cuando:

- ✅ Se puede consultar disponibilidad y crear citas sin solapes
- ✅ Excepciones funcionan y se reflejan en slots disponibles
- ✅ Video call funciona en los tres escenarios:
  - auto_generate
  - manual_only
  - auto_or_manual con fallback
- ✅ Logs/errores claros: `meeting_error` útil para soporte
- ✅ Tokens protegidos y permisos aplicados
- ✅ Tests unitarios y de integración pasando

---

## Referencias a Documentación

### Documentación Técnica Completa
- **Ubicación**: [docs/README.md](docs/README.md)
- **Contenido**: Especificación técnica detallada con arquitectura, reglas de negocio, y algoritmos

### Guía de Usuario
- **Ubicación**: [docs/USER_GUIDE.ms](docs/USER_GUIDE.ms)
- **Contenido**: Manual de usuario para administradores y staff, con ejemplos prácticos

### Decisiones de Diseño
- **Ubicación**: [docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md)
- **Contenido**: Todas las decisiones de diseño confirmadas con implementación detallada

### Plan de Implementación
- **Ubicación**: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)
- **Contenido**: Plan paso a paso con código de ejemplo para cada fase

### Guía de Inicio Rápido
- **Ubicación**: [START_HERE.md](START_HERE.md)
- **Contenido**: Primeros pasos para comenzar la implementación

### README Principal
- **Ubicación**: [README.md](README.md)
- **Contenido**: Instalación, contribución, y resumen básico

---

## Estado Actual de Desarrollo

**Fecha de documentación**: 2026-01-21

### Implementado
- ✅ Estructura de DocTypes definida (JSON)
- ✅ Campos y relaciones configurados
- ✅ Documentación técnica completa
- ✅ Guía de usuario

### Pendiente de Implementación
- ⏳ Lógica de validación en DocTypes (validate, on_submit, on_cancel)
- ⏳ Servicios de scheduling (availability.py, overlap.py, slots.py)
- ⏳ Adaptadores de videollamada (google_meet.py, microsoft_teams.py)
- ⏳ API endpoints whitelisted
- ⏳ Tests unitarios y de integración
- ⏳ Frontend JavaScript personalizado
- ⏳ OAuth flows para Provider Account

**Nota**: Los archivos Python de DocTypes actualmente solo contienen clases vacías (pass). La lógica debe implementarse según las especificaciones de este documento y la documentación técnica.

---

## Instrucciones para Claude / Desarrolladores

### Al trabajar en esta aplicación

1. **SIEMPRE** leer este documento primero para entender la arquitectura
2. **NUNCA** implementar lógica de negocio directamente en DocTypes sin usar servicios
3. **SIEMPRE** validar disponibilidad y overlaps antes de confirmar appointments
4. **SIEMPRE** usar el patrón Adapter para videollamadas (no hardcodear proveedores)
5. **SIEMPRE** manejar timezones consistentemente (usar el timezone del Calendar Resource)
6. **SIEMPRE** proteger tokens y credenciales (Password fields, permisos restrictivos)

### Decisiones Clave a Confirmar con Usuario

Cuando implementes código, confirma con el usuario:

1. **¿Validar overlaps en Draft o solo al Confirmar?**
   - Recomendado: Permitir overlaps en Draft, validar fuerte en Submit

2. **¿Submit vs Confirmed?**
   - Si no usas Submit, implementar workflow para Confirmed

3. **¿Actualizar meeting si cambia hora o recrear?**
   - Recomendado: Cancelar viejo + crear nuevo (más simple)

4. **¿Qué status bloquean horarios? (Draft, Confirmed, ambos)**
   - Recomendado: Solo Confirmed

### Ejemplos de Código

Consultar la documentación técnica ([docs/README.md](docs/README.md)) para ejemplos detallados de:
- Cálculo de disponibilidad efectiva
- Detección de overlaps
- Creación de videollamadas
- Validaciones en DocTypes

---

## Herramientas de Desarrollo

### Pre-commit Hooks
- **ruff**: Linter y formatter Python
- **eslint**: Linter JavaScript
- **prettier**: Formatter JavaScript
- **pyupgrade**: Modernización de sintaxis Python

### Instalación
```bash
cd apps/meet_scheduling
pre-commit install
```

### Ejecutar manualmente
```bash
pre-commit run --all-files
```

---

## Instalación

### Usando bench

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app meet_scheduling
```

### Después de instalar

1. Migrar base de datos: `bench --site [site-name] migrate`
2. Crear Provider Accounts y conectar OAuth
3. Crear Video Call Profiles
4. Crear Availability Plans con sus Slots
5. Crear Calendar Resources
6. ¡Empezar a agendar!

---

## Contacto y Soporte

**Desarrollador**: Sebastian Ortiz Valencia
**Email**: sebastianortiz989@gmail.com
**Licencia**: MIT

---

**Última actualización**: 2026-01-27

---

## Arquitectura de la API Modular

### Principios de Diseño

La API sigue los mismos principios que `common_configurations`:

1. **SOLID**: Single Responsibility, Open/Closed, Dependency Inversion
2. **KISS**: Estructura simple, sin sobre-ingeniería
3. **DRY**: Utilidades compartidas importadas de `common_configurations`

### Estructura de Carpetas

```
api/
├── __init__.py              # Re-exports para acceso conveniente
├── appointments/            # Dominio: Citas
│   ├── __init__.py          # Re-exporta desde endpoints
│   └── endpoints.py         # Todos los endpoints de appointments
└── shared/                  # Utilidades (importa de common_configurations)
    ├── __init__.py          # Re-exporta utilidades compartidas
    └── validators.py        # Validadores específicos de citas
```

### Importación de Utilidades Compartidas

**IMPORTANTE**: Las utilidades de seguridad y validación se importan de `common_configurations`:

```python
# En meet_scheduling/api/shared/__init__.py
from common_configurations.api.shared import (
    check_rate_limit,
    get_client_ip,
    check_honeypot,
    get_current_user_contact,
    require_user_contact,
    validate_user_contact_ownership,
    sanitize_string,
    AUTH_HEADER,
)

# Validadores específicos de appointments
from .validators import (
    validate_date_string,
    validate_datetime_string,
    validate_docname,
)
```

### Uso de la API

```javascript
// Obtener citas del usuario autenticado
frappe.call({
    method: "meet_scheduling.api.appointments.get_my_appointments",
    headers: { "X-User-Contact-Token": "token-here" }
});

// Obtener slots disponibles (público)
frappe.call({
    method: "meet_scheduling.api.appointments.get_available_slots",
    args: {
        calendar_resource: "CR-00001",
        from_date: "2026-01-20",
        to_date: "2026-01-27"
    }
});
```

### Endpoints Disponibles

#### Públicos (allow_guest=True, sin token)
- `get_active_calendar_resources`: Lista recursos de calendario activos
- `get_available_slots`: Obtiene slots disponibles para un rango de fechas
- `validate_appointment`: Valida un appointment antes de crearlo

#### Autenticados (requieren token)
- `create_and_confirm_appointment`: Crea y confirma una cita
- `get_my_appointments`: Lista citas del usuario autenticado
- `get_appointment_detail`: Detalle de una cita específica
- `cancel_my_appointment`: Cancela una cita del usuario

#### Administrativos (requieren permisos Frappe)
- `cancel_or_delete_appointment`: Cancela o elimina cualquier cita
- `generate_meeting`: Genera meeting para una cita

### Autenticación por Token

Los endpoints autenticados validan el token de User Contact:

```python
@frappe.whitelist(allow_guest=True, methods=['GET'])
def get_my_appointments():
    # Importar de shared (que importa de common_configurations)
    from meet_scheduling.api.shared import (
        check_rate_limit,
        get_current_user_contact
    )

    check_rate_limit("get_my_appointments", limit=30, seconds=60)

    user_contact = get_current_user_contact()
    if not user_contact:
        frappe.throw("Authentication required", frappe.AuthenticationError)

    # ... lógica
```

### Validadores Específicos

En `api/shared/validators.py`:

```python
def validate_date_string(date_str: str, field_name: str = "date") -> str:
    """Valida formato YYYY-MM-DD"""
    pass

def validate_datetime_string(datetime_str: str, field_name: str = "datetime") -> str:
    """Valida formato YYYY-MM-DD HH:MM:SS"""
    pass

def validate_docname(name: str, field_name: str = "name") -> str:
    """Valida nombre de documento Frappe"""
    pass
```

---

## Dependencias

### De common_configurations

Esta app depende de `common_configurations` para:

1. **Autenticación por token**: `get_current_user_contact()`, `require_user_contact()`
2. **Rate limiting**: `check_rate_limit()`, `get_client_ip()`
3. **Seguridad**: `check_honeypot()`, `validate_user_contact_ownership()`
4. **Validación**: `sanitize_string()`, validadores genéricos

### Instalación

```bash
# common_configurations debe estar instalado primero
bench get-app common_configurations
bench install-app common_configurations

# Luego meet_scheduling
bench get-app meet_scheduling
bench install-app meet_scheduling
```
