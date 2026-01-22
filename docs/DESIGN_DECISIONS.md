# Decisiones de Diseño - Meet Scheduling

**Fecha**: 2026-01-21
**Estado**: Confirmadas

---

## Decisión 1: Validación de Overlaps ✅ CONFIRMADA

### Pregunta
¿Cuándo se deben validar los overlaps (solapamientos)?

### Opciones
- **Opción A**: Solo validar fuerte al hacer Submit (permitir overlaps en Draft)
- **Opción B**: Validar desde Draft para mostrar alertas tempranas

### Decisión Confirmada
✅ **Opción B**: Validar desde Draft para mostrar alertas antes de confirmar

### Implementación
```python
# En appointment.py - validate()
def validate(self):
    # ... otras validaciones
    self.check_overlaps_early_warning()

def check_overlaps_early_warning(self):
    """Mostrar advertencia si hay overlaps, incluso en Draft."""
    from meet_scheduling.scheduling.overlap import check_overlap

    result = check_overlap(
        self.calendar_resource,
        self.start_datetime,
        self.end_datetime,
        exclude_appointment=self.name
    )

    if result["capacity_exceeded"]:
        # En Draft: advertencia
        # En Submit: error (bloquea)
        if self.docstatus == 0:  # Draft
            frappe.msgprint(
                f"⚠️ ADVERTENCIA: Capacidad excedida en este horario. "
                f"Hay {result['capacity_used']} cita(s), capacidad máxima: {result['capacity_available']}",
                indicator="orange",
                alert=True
            )
        else:  # Submit
            frappe.throw(
                f"No se puede confirmar: Capacidad excedida. "
                f"Hay {result['capacity_used']} cita(s) en este horario."
            )
```

### Beneficios
- ✅ Usuario ve alertas tempranas
- ✅ Mejor UX (no esperar hasta Submit)
- ✅ Permite crear "Draft" para consultar, luego ajustar horario

---

## Decisión 2: Estados que Bloquean Horarios ✅ CONFIRMADA

### Pregunta Clarificada
Cuando se hace la validación de overlaps, ¿qué appointments se deben considerar como "bloqueadores"?

### Decisión Confirmada
✅ **Draft y Confirmed bloquean horarios, PERO Drafts tienen expiración temporal**

### Comportamiento
**Regla principal**: Draft y Confirmed bloquean horarios (capacity)

**Regla de expiración**:
- Si un Draft NO se confirma en X tiempo, expira automáticamente
- Drafts expirados NO bloquean horarios
- El horario queda disponible de nuevo

### Configuración de Expiración

**Campo nuevo en Calendar Resource**:
```json
{
    "fieldname": "draft_expiration_minutes",
    "fieldtype": "Int",
    "label": "Draft Expiration (Minutes)",
    "description": "Tiempo en minutos antes de que un Draft expire y libere el horario",
    "default": "15"
}
```

**Valores sugeridos**:
- 15 minutos (para alta demanda)
- 30 minutos (estándar)
- 60 minutos (para procesos más lentos)

### Implementación

#### 1. Campo adicional en Appointment
```json
{
    "fieldname": "draft_expires_at",
    "fieldtype": "Datetime",
    "label": "Draft Expires At",
    "description": "Momento en que este Draft expira (solo para Drafts)",
    "read_only": 1,
    "hidden": 1
}
```

#### 2. Cálculo de expiración en validate()
```python
# En appointment.py - validate()
def validate(self):
    # ... otras validaciones
    self.set_draft_expiration()

def set_draft_expiration(self):
    """Establece la fecha de expiración para Drafts."""
    if self.docstatus == 0 and self.status == "Draft":  # Solo para Drafts nuevos
        if not self.draft_expires_at:  # Solo si no tiene ya
            resource = frappe.get_doc("Calendar Resource", self.calendar_resource)
            expiration_minutes = resource.draft_expiration_minutes or 15  # Default 15 min

            self.draft_expires_at = frappe.utils.add_to_date(
                frappe.utils.now(),
                minutes=expiration_minutes
            )
```

#### 3. Validación de overlap considerando expiración
```python
# En overlap.py
def check_overlap(calendar_resource, start_datetime, end_datetime, exclude_appointment=None):
    """
    Detecta overlaps considerando:
    - Confirmed: siempre bloquean
    - Draft: solo bloquean si NO están expirados
    """
    import frappe.utils as utils

    appointments = frappe.db.sql("""
        SELECT name, start_datetime, end_datetime, status, draft_expires_at
        FROM `tabAppointment`
        WHERE calendar_resource = %(resource)s
            AND status IN ('Draft', 'Confirmed')
            AND start_datetime < %(end)s
            AND end_datetime > %(start)s
            AND name != %(exclude)s
    """, {
        "resource": calendar_resource,
        "start": start_datetime,
        "end": end_datetime,
        "exclude": exclude_appointment or ""
    }, as_dict=True)

    # Filtrar Drafts expirados
    now = utils.now()
    active_appointments = []

    for apt in appointments:
        if apt.status == "Confirmed":
            # Confirmed siempre bloquea
            active_appointments.append(apt)
        elif apt.status == "Draft":
            # Draft solo bloquea si NO está expirado
            if apt.draft_expires_at and apt.draft_expires_at > now:
                active_appointments.append(apt)
            # Si está expirado, lo ignoramos (no bloquea)

    # ... resto de la lógica con active_appointments
```

#### 4. Scheduled Task para limpiar Drafts expirados

**En hooks.py**:
```python
scheduler_events = {
    "cron": {
        "*/15 * * * *": [  # Cada 15 minutos
            "meet_scheduling.scheduling.tasks.cleanup_expired_drafts"
        ]
    }
}
```

**Archivo nuevo**: `meet_scheduling/scheduling/tasks.py`
```python
import frappe
from frappe.utils import now

def cleanup_expired_drafts():
    """
    Marca Drafts expirados como Cancelled automáticamente.
    Se ejecuta cada 15 minutos vía cron.
    """
    expired_drafts = frappe.db.sql("""
        SELECT name
        FROM `tabAppointment`
        WHERE status = 'Draft'
            AND docstatus = 0
            AND draft_expires_at IS NOT NULL
            AND draft_expires_at < %(now)s
    """, {"now": now()}, as_dict=True)

    for draft in expired_drafts:
        try:
            doc = frappe.get_doc("Appointment", draft.name)
            doc.add_comment(
                "Comment",
                text="Draft expirado automáticamente por inactividad"
            )
            doc.status = "Cancelled"
            doc.save(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(
                f"Error al expirar Draft {draft.name}: {str(e)}",
                "Cleanup Expired Drafts"
            )

    if expired_drafts:
        frappe.logger().info(f"Se expiraron {len(expired_drafts)} drafts automáticamente")
```

### Notificaciones al Usuario

**En appointment.js** (frontend):
```javascript
frappe.ui.form.on('Appointment', {
    refresh: function(frm) {
        // Mostrar advertencia si el Draft está cerca de expirar
        if (frm.doc.status === 'Draft' && frm.doc.draft_expires_at) {
            let now = frappe.datetime.now_datetime();
            let expires_at = frm.doc.draft_expires_at;

            if (expires_at < frappe.datetime.add_minutes(now, 5)) {
                frm.dashboard.add_comment(
                    '⚠️ Este Draft expirará en menos de 5 minutos. Por favor confirma la cita.',
                    'yellow',
                    true
                );
            }
        }
    }
});
```

### Ventajas de esta Solución
- ✅ Bloquea horarios inmediatamente (evita doble reserva)
- ✅ Libera horarios automáticamente si no se confirman
- ✅ Evita "reservas fantasma" que ocupan horarios indefinidamente
- ✅ Configurable por calendario (diferentes tiempos según necesidad)

### Casos de Uso
**Caso 1**: Usuario normal
1. Crea Draft 09:00-10:00 → Horario bloqueado (tiene 15 min)
2. Completa formulario y hace Submit → Queda Confirmed
3. Horario permanece bloqueado

**Caso 2**: Usuario abandona formulario
1. Crea Draft 09:00-10:00 → Horario bloqueado
2. Se distrae, no hace Submit
3. A los 15 minutos → Draft expira automáticamente
4. Horario queda disponible de nuevo

**Caso 3**: Dos usuarios simultáneos
1. Usuario A crea Draft 09:00-10:00 → Bloqueado
2. Usuario B intenta crear Draft 09:00-10:00 → ❌ Rechazado (capacity)
3. Draft de Usuario A expira
4. Usuario B puede crear Draft ahora → ✅ Bloqueado para B

---

## Decisión 3: Cambio de Hora con Meeting Creado ✅ CONFIRMADA

### Pregunta Clarificada
¿Qué hacer cuando se cambia la hora de un Appointment que ya tiene un meeting creado?

### Decisión Confirmada
✅ **Depende del modo de enlace:**
- **Si es AUTOMÁTICO** (Google Meet/Teams vía API): Cancelar viejo + crear nuevo
- **Si es MANUAL** (enlace pegado manualmente): Mantener el enlace (no tocar)

### Comportamiento

#### Caso 1: Meeting Automático (Google Meet/Teams API)
**Escenario**:
1. Appointment con `meeting_status = "created"` (creado vía API)
2. Usuario cambia hora: 09:00-10:00 → 14:00-15:00
3. **Acción**: Cancelar meeting viejo + crear nuevo

**Motivo**: El meeting tiene hora específica en Google/Teams, hay que recrearlo.

**Implementación**:
```python
# En appointment.py
def on_update_after_submit(self):
    """Se ejecuta cuando se modifica un appointment ya submitted."""
    # Detectar si cambió la hora
    if self.has_value_changed("start_datetime") or self.has_value_changed("end_datetime"):
        if self.meeting_status == "created":  # Meeting automático
            self._recreate_meeting()

def _recreate_meeting(self):
    """Cancela meeting viejo y crea uno nuevo."""
    frappe.msgprint(
        "⚠️ Al cambiar la hora se generará un nuevo enlace de videollamada",
        alert=True,
        indicator="orange"
    )

    # 1. Cancelar meeting viejo
    try:
        from meet_scheduling.video_calls.factory import get_adapter
        profile = frappe.get_doc("Video Call Profile", self.video_call_profile)
        adapter = get_adapter(profile.provider)
        adapter.delete_meeting(profile, self)
    except Exception as e:
        frappe.log_error(
            f"Error al cancelar meeting viejo: {str(e)}",
            "Recreate Meeting"
        )

    # 2. Crear meeting nuevo
    old_url = self.meeting_url
    self.meeting_id = None
    self.meeting_status = "not_created"
    self.provider_payload = None

    try:
        self._create_meeting_via_adapter()

        # 3. Notificar al usuario
        frappe.msgprint(
            f"✅ Nuevo enlace generado: {self.meeting_url}<br>"
            f"<small>Enlace anterior: {old_url} (ya no funciona)</small>",
            alert=True,
            indicator="blue"
        )
    except Exception as e:
        frappe.throw(f"Error al crear nuevo meeting: {str(e)}")
```

---

#### Caso 2: Meeting Manual (enlace pegado)
**Escenario**:
1. Appointment con `manual_meeting_url` (enlace pegado por usuario)
2. Usuario cambia hora: 09:00-10:00 → 14:00-15:00
3. **Acción**: NO tocar el enlace, mantener `manual_meeting_url`

**Motivo**:
- El enlace manual puede ser permanente (ej: Zoom personal room)
- Usuario es responsable de su enlace
- No tenemos control sobre ese enlace

**Implementación**:
```python
def on_update_after_submit(self):
    """Se ejecuta cuando se modifica un appointment ya submitted."""
    if self.has_value_changed("start_datetime") or self.has_value_changed("end_datetime"):
        if self.meeting_status == "created":
            # Meeting automático → recrear
            self._recreate_meeting()
        elif self.manual_meeting_url:
            # Meeting manual → solo advertir
            frappe.msgprint(
                "ℹ️ La hora cambió. El enlace de videollamada se mantiene igual. "
                "Si necesitas cambiarlo, edita el campo 'Manual Meeting URL'.",
                alert=True,
                indicator="blue"
            )
```

### Detección del Tipo de Meeting

**¿Cómo saber si es automático o manual?**

```python
def is_automatic_meeting(self):
    """Verifica si el meeting fue creado automáticamente."""
    return self.meeting_status == "created" and self.meeting_id

def is_manual_meeting(self):
    """Verifica si el meeting es manual."""
    return bool(self.manual_meeting_url) and not self.is_automatic_meeting()
```

### Matriz de Decisiones

| Estado | Cambio de Hora | Acción |
|--------|----------------|--------|
| `meeting_status = "created"` + `meeting_id` existe | ✅ Sí | Cancelar viejo + crear nuevo |
| `manual_meeting_url` existe + sin `meeting_id` | ✅ Sí | Mantener enlace, solo advertir |
| `meeting_status = "not_created"` | ✅ Sí | No hacer nada |
| `meeting_status = "failed"` | ✅ Sí | No hacer nada |

### Validaciones Adicionales

**Antes de recrear meeting automático**:
```python
def _recreate_meeting(self):
    # Validar que el perfil siga activo
    if not self.video_call_profile:
        frappe.throw("No se puede recrear meeting: Video Call Profile no definido")

    profile = frappe.get_doc("Video Call Profile", self.video_call_profile)
    if not profile.is_active:
        frappe.throw("No se puede recrear meeting: Video Call Profile inactivo")

    # Validar que la cuenta siga conectada
    if profile.provider_account:
        account = frappe.get_doc("Provider Account", profile.provider_account)
        if account.status != "Connected":
            frappe.throw(
                f"No se puede recrear meeting: Provider Account no está conectado ({account.status})"
            )

    # Continuar con recreación...
```

### Notificaciones al Usuario

**Email opcional** (si está configurado):
```python
def _recreate_meeting(self):
    # ... código de recreación ...

    # Enviar email al party si cambió el enlace
    if self.party and old_url != self.meeting_url:
        self._send_meeting_change_notification(old_url, self.meeting_url)

def _send_meeting_change_notification(self, old_url, new_url):
    """Envía notificación de cambio de enlace."""
    # TODO: Implementar envío de email
    pass
```

### Casos Especiales

#### ¿Qué pasa si el meeting automático falla al recrearse?

```python
def _recreate_meeting(self):
    # ... cancelar viejo ...

    try:
        self._create_meeting_via_adapter()
    except Exception as e:
        # Si falla, permitir pegar manual
        self.meeting_status = "failed"
        self.meeting_error = str(e)

        frappe.msgprint(
            f"❌ Error al crear nuevo meeting: {str(e)}<br><br>"
            f"Puedes pegar un enlace manual en el campo 'Manual Meeting URL'",
            alert=True,
            indicator="red"
        )

        # NO lanzar error, permitir guardar con meeting_status=failed
```

### Ventajas de esta Solución
- ✅ Simple para meetings automáticos (recrear)
- ✅ No toca meetings manuales (usuario tiene control)
- ✅ Maneja errores gracefully
- ✅ Notifica claramente al usuario qué pasó

---

## Decisión 4: Validación de Slot Duration ✅ CONFIRMADA

### Pregunta
¿Se debe validar que la duración de los appointments respete la granularidad de `slot_duration_minutes`?

### Ejemplo
Si `Calendar Resource.slot_duration_minutes = 30`, entonces:
- ✅ Appointment de 09:00-09:30 (30 min) → OK
- ✅ Appointment de 09:00-10:00 (60 min) → OK (múltiplo de 30)
- ❌ Appointment de 09:00-09:45 (45 min) → FAIL (no es múltiplo de 30)

### Decisión Confirmada
✅ **Sí, validar granularidad PERO debe poder modificarse**

### Implementación

```python
# En appointment.py - validate()
def validate_slot_granularity(self):
    """
    Valida que la duración respete slot_duration_minutes.
    Permite override manual si el usuario lo confirma.
    """
    if not self.calendar_resource:
        return

    resource = frappe.get_doc("Calendar Resource", self.calendar_resource)

    # Si no hay slot_duration configurado, no validar
    if not resource.slot_duration_minutes:
        return

    # Calcular duración
    duration_minutes = (
        get_datetime(self.end_datetime) - get_datetime(self.start_datetime)
    ).total_seconds() / 60

    # Validar que sea múltiplo
    if duration_minutes % resource.slot_duration_minutes != 0:
        # Mostrar advertencia pero permitir guardar
        frappe.msgprint(
            f"⚠️ ADVERTENCIA: La duración ({duration_minutes} min) no es múltiplo de "
            f"la granularidad configurada ({resource.slot_duration_minutes} min). "
            f"Se recomienda ajustar el horario.",
            indicator="orange",
            alert=True
        )

        # Si es Draft, solo advertencia
        # Si es Submit, podríamos bloquear o permitir según configuración
        if self.docstatus == 1:  # Submit
            # Opción 1: Permitir pero advertir
            pass

            # Opción 2: Bloquear (comentado, activar si se prefiere)
            # frappe.throw(
            #     f"La duración debe ser múltiplo de {resource.slot_duration_minutes} minutos"
            # )
```

### Configuración Adicional (Opcional)
Agregar campo en Calendar Resource:

```json
{
    "fieldname": "enforce_slot_duration",
    "fieldtype": "Check",
    "label": "Enforce Slot Duration",
    "description": "Si está activo, bloquea appointments que no respeten slot_duration_minutes",
    "default": "0"
}
```

```python
def validate_slot_granularity(self):
    # ... código anterior ...

    if duration_minutes % resource.slot_duration_minutes != 0:
        if resource.enforce_slot_duration:
            # BLOQUEAR
            frappe.throw(
                f"La duración debe ser múltiplo de {resource.slot_duration_minutes} minutos"
            )
        else:
            # ADVERTIR (comportamiento actual)
            frappe.msgprint(..., indicator="orange")
```

### Decisión Final
- ✅ Validar granularidad por defecto (advertencia)
- ✅ Permitir guardar/confirmar de todas formas
- ✅ (Opcional) Agregar campo `enforce_slot_duration` para bloquear si se desea

---

## Resumen de Decisiones

| # | Decisión | Status | Valor Confirmado |
|---|----------|--------|------------------|
| 1 | Validación de Overlaps | ✅ CONFIRMADA | Validar desde Draft (advertencia), bloquear en Submit |
| 2 | Estados que Bloquean | ✅ CONFIRMADA | Draft y Confirmed bloquean, pero Drafts expiran (15 min default) |
| 3 | Cambio de Hora con Meeting | ✅ CONFIRMADA | Automático: recrear; Manual: mantener enlace |
| 4 | Validación de Slot Duration | ✅ CONFIRMADA | Validar (advertencia) pero permitir override |

---

## Campos Adicionales Requeridos

Basado en las decisiones confirmadas, se requieren estos campos adicionales en los DocTypes:

### 1. Calendar Resource
```json
{
    "fieldname": "draft_expiration_minutes",
    "fieldtype": "Int",
    "label": "Draft Expiration (Minutes)",
    "description": "Tiempo en minutos antes de que un Draft expire y libere el horario",
    "default": "15"
}
```

### 2. Appointment
```json
{
    "fieldname": "draft_expires_at",
    "fieldtype": "Datetime",
    "label": "Draft Expires At",
    "description": "Momento en que este Draft expira (solo para Drafts)",
    "read_only": 1,
    "hidden": 1
}
```

### 3. Appointment (opcional)
```json
{
    "fieldname": "enforce_slot_duration",
    "fieldtype": "Check",
    "label": "Enforce Slot Duration",
    "description": "Si está activo, bloquea appointments que no respeten slot_duration_minutes",
    "default": "0"
}
```

---

## Próximos Pasos

1. ✅ **TODAS LAS DECISIONES CONFIRMADAS**
2. 🔄 **ACTUALIZAR** IMPLEMENTATION_PLAN.md con las decisiones confirmadas
3. 🔄 **AGREGAR** campos adicionales a los DocTypes
4. 🔄 **COMENZAR** implementación con Fase 0

---

**Última actualización**: 2026-01-21
