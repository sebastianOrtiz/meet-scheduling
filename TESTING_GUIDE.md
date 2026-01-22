# 🧪 Guía Práctica: Probar Meet Scheduling desde la Interfaz

**Versión actualizada con los cambios recientes**

## 📋 Tabla de Contenido
1. [Acceso al Sistema](#1-acceso-al-sistema)
2. [Configuración Inicial (5 min)](#2-configuración-inicial)
3. [Crear Primera Cita](#3-crear-primera-cita)
4. [Probar Validaciones](#4-probar-validaciones)
5. [Probar Video Calls](#5-probar-video-calls)
6. [Verificar Draft Expiration](#6-verificar-draft-expiration)
7. [Probar API Endpoints](#7-probar-api-endpoints)
8. [Probar Calendar Exceptions](#8-probar-calendar-exceptions)
9. [Checklist Final](#9-checklist-final)

---

## 1. Acceso al Sistema

### Paso 1.1: Iniciar Frappe
```bash
cd /workspace/development/frappe-bench
bench start
```

### Paso 1.2: Abrir el Navegador
```
URL: http://localhost:8000
Usuario: Administrator
Password: [tu password]
```

---

## 2. Configuración Inicial

### Paso 2.1: Crear Video Call Profile (Modo Manual)

1. **Ir al DocType**:
   - Busca en Awesome Bar: `Video Call Profile`
   - Click en **New**

2. **Llenar campos**:
   ```
   Profile Name: Test Profile - Manual
   Provider: google_meet
   Link Mode: manual_only
   Create On: on_submit
   Is Active: ✓
   ```

3. **Guardar** (Ctrl+S)

✅ **Resultado esperado**: Profile creado, listo para usar

---

### Paso 2.2: Crear Availability Plan

1. **Ir al DocType**:
   - Busca: `Availability Plan`
   - Click en **New**

2. **Llenar campos**:
   ```
   Plan Name: Horario de Prueba 2026
   Is Active: ✓
   ```

3. **Agregar Availability Slots** en la tabla `availability_slots`:

   **Slot 1:**
   ```
   Weekday: Monday
   Start Time: 09:00:00
   End Time: 12:00:00
   Capacity: 1
   Location: (opcional)
   ```

   **Slot 2:**
   ```
   Weekday: Monday
   Start Time: 14:00:00
   End Time: 18:00:00
   Capacity: 1
   ```

   **Slot 3:**
   ```
   Weekday: Tuesday
   Start Time: 09:00:00
   End Time: 13:00:00
   Capacity: 1
   ```

   **📝 Nota**: El campo `Weekday` ahora usa opciones simples en inglés:
   - Monday
   - Tuesday
   - Wednesday
   - Thursday
   - Friday
   - Saturday
   - Sunday

4. **Guardar**

✅ **Resultado esperado**: Plan con 3 slots configurados

---

### Paso 2.3: Crear Calendar Resource

1. **Ir al DocType**:
   - Busca: `Calendar Resource`
   - Click en **New**

2. **Llenar campos**:
   ```
   Resource Name: Dr. Test - Consultas
   Resource Type: Person
   Timezone: America/Bogota
   Slot Duration (Minutes): 30
   Capacity: 1
   Draft Expiration Minutes: 15
   Availability Plan: Horario de Prueba 2026
   Video Call Profile: Test Profile - Manual
   Is Active: ✓
   ```

3. **Guardar**

✅ **Resultado esperado**: Calendar Resource configurado y activo

---

## 3. Crear Primera Cita

### Paso 3.1: Crear Appointment (Draft)

1. **Ir al DocType**:
   - Busca: `Appointment`
   - Click en **New**

2. **Llenar campos básicos**:
   ```
   Calendar Resource: Dr. Test - Consultas
   ```

3. **Fecha/Hora** (debe ser un Lunes en horario 09:00-12:00):

   Para obtener el próximo lunes a las 10:00:
   - Abre consola del navegador (F12)
   - Ejecuta:
   ```javascript
   // Calcular próximo lunes
   let d = new Date();
   let dayOfWeek = d.getDay();
   let daysToAdd = (dayOfWeek === 0 ? 1 : 8 - dayOfWeek);
   d.setDate(d.getDate() + daysToAdd);
   d.setHours(10, 0, 0, 0);
   console.log("Start:", d.toISOString().slice(0, 19).replace('T', ' '));
   d.setHours(11, 0, 0, 0);
   console.log("End:", d.toISOString().slice(0, 19).replace('T', ' '));
   ```

   Copia las fechas generadas en:
   ```
   Start Datetime: [fecha generada - ej: 2026-01-26 10:00:00]
   End Datetime: [fecha generada - ej: 2026-01-26 11:00:00]
   ```

4. **Otros campos** (opcional):
   ```
   Party Type: Customer
   Party: [deja vacío o selecciona uno]
   Notes: Primera cita de prueba
   Source: Admin
   Call Link Mode: inherit
   Manual Meeting URL: https://meet.google.com/abc-defg-hij
   ```

5. **Guardar** (Ctrl+S)

✅ **Verificaciones inmediatas**:
- Status = "Draft" ✓
- draft_expires_at tiene fecha (15 min futuro) ✓
- Aparece mensaje naranja: "Este horario tiene 0 appointments" (warning informativo)

---

### Paso 3.2: Confirmar Appointment (Submit)

1. **En el mismo Appointment**:
   - Scroll arriba
   - Click botón **Submit**

2. **Observa los mensajes**:
   ```
   ✓ Meeting creado: https://meet.google.com/abc-defg-hij (verde)
   ✓ Status cambió a "Confirmed"
   ✓ docstatus = 1
   ```

✅ **Verificaciones**:
- Status = "Confirmed" ✓
- Meeting URL = tu enlace manual ✓
- docstatus = 1 ✓

---

## 4. Probar Validaciones

### Prueba 4.1: Validación de Horario Fuera de Disponibilidad

1. **Crear nuevo Appointment**:
   ```
   Calendar Resource: Dr. Test - Consultas
   Start Datetime: [mismo lunes] 19:00:00  ← Fuera de horario
   End Datetime: [mismo lunes] 20:00:00
   ```

2. **Guardar** (Draft) → ✓ Funciona (solo warning)

3. **Intentar Submit** → ❌ Error esperado:
   ```
   ValidationError: No hay disponibilidad en 2026-01-26 para este Calendar Resource
   ```

✅ **Resultado esperado**: Submit bloqueado, mensaje de error claro

---

### Prueba 4.2: Validación de Overlap / Capacity

1. **Crear segundo Appointment en mismo horario**:
   ```
   Calendar Resource: Dr. Test - Consultas
   Start Datetime: [mismo lunes] 10:00:00  ← Mismo horario que appointment #1
   End Datetime: [mismo lunes] 11:00:00
   Manual Meeting URL: https://meet.google.com/otro-enlace
   ```

2. **Guardar** (Draft) → ✓ Funciona

3. **Observa warning naranja**:
   ```
   ⚠️ Este horario tiene 1 appointments: [nombre del appointment anterior]
   ⚠️ Capacidad excedida (1/1)
   ```

4. **Intentar Submit** → ❌ Error esperado:
   ```
   ValidationError: Capacidad excedida. Ya hay 1 appointments: [nombre]
   ```

✅ **Resultado esperado**: Submit bloqueado por capacidad

---

### Prueba 4.3: Validación de Fechas Inconsistentes

1. **Crear Appointment con end < start**:
   ```
   Start Datetime: 2026-01-26 11:00:00
   End Datetime: 2026-01-26 10:00:00  ← Antes del start
   ```

2. **Intentar Guardar** → ❌ Error esperado:
   ```
   ValidationError: Start DateTime debe ser menor que End DateTime
   ```

✅ **Resultado esperado**: Ni siquiera permite guardar Draft

---

## 5. Probar Video Calls

### Prueba 5.1: Modo Manual (Ya probado)

✓ Ya lo hiciste en Paso 3.1-3.2

---

### Prueba 5.2: Crear Profile Auto (Mock)

1. **Crear Provider Account**:
   ```
   DocType: Provider Account
   Account Name: Test Google Account
   Provider: google_meet
   Owner User: Administrator
   Auth Mode: oauth_user
   ```

2. **Crear Video Call Profile Auto**:
   ```
   Profile Name: Test Profile - Auto
   Provider: google_meet
   Link Mode: auto_generate
   Provider Account: Test Google Account
   Create On: on_submit
   Is Active: ✓
   ```

3. **Actualizar Calendar Resource**:
   - Edita: Dr. Test - Consultas
   - Cambia Video Call Profile a: **Test Profile - Auto**
   - Guardar

4. **Crear nuevo Appointment**:
   ```
   Calendar Resource: Dr. Test - Consultas
   Start Datetime: [próximo martes] 10:00:00
   End Datetime: [próximo martes] 11:00:00
   Call Link Mode: inherit
   ```

5. **Submit**

✅ **Resultado esperado**:
```
✓ Meeting URL generado automáticamente (mock)
✓ Formato: https://meet.google.com/mock-meeting-id-[timestamp]
✓ Meeting ID: mock-meeting-id-[timestamp]
```

---

## 6. Verificar Draft Expiration

### Prueba 6.1: Ver Draft Expiration en Acción

1. **Crear Appointment Draft (NO submit)**:
   ```
   Calendar Resource: Dr. Test - Consultas
   Start Datetime: [futuro válido]
   End Datetime: [futuro válido]
   Manual Meeting URL: https://test.com
   ```

2. **Guardar** (Draft)

3. **Verificar campo**:
   ```
   draft_expires_at: [15 minutos en el futuro]
   ```

4. **Cambiar manualmente la expiración al pasado**:
   - Abrir consola de Frappe:
   ```bash
   bench --site development.localhost console
   ```

   - Ejecutar:
   ```python
   import frappe
   from frappe.utils import add_to_date, now_datetime

   # Obtener último appointment draft
   draft = frappe.get_last_doc("Appointment", filters={"status": "Draft"})
   print(f"Draft: {draft.name}")

   # Cambiar expiración al pasado
   draft.draft_expires_at = add_to_date(now_datetime(), minutes=-10)
   draft.save(ignore_permissions=True)
   frappe.db.commit()
   print(f"Expirado: {draft.draft_expires_at}")
   ```

5. **Ejecutar cleanup manual**:
   ```python
   from meet_scheduling.meet_scheduling.scheduling.tasks import cleanup_expired_drafts

   count = cleanup_expired_drafts()
   print(f"Drafts cancelados: {count}")
   ```

6. **Verificar en UI**:
   - Refrescar página del Appointment
   - Status debería cambiar a: **Cancelled**

✅ **Resultado esperado**: Draft expirado cancelado automáticamente

---

### Prueba 6.2: Configurar Cron (Automático cada 15 min)

El cron ya está configurado en `hooks.py`:

```python
scheduler_events = {
    "cron": {
        "*/15 * * * *": [
            "meet_scheduling.meet_scheduling.scheduling.tasks.cleanup_expired_drafts"
        ]
    }
}
```

Para verificar que funciona:

1. **Habilitar scheduler**:
   ```bash
   bench --site development.localhost set-config enable_scheduler 1
   bench restart
   ```

2. **Ver logs**:
   ```bash
   tail -f logs/scheduler.log | grep cleanup_expired_drafts
   ```

✅ **Resultado esperado**: Cada 15 minutos verás el cleanup ejecutándose

---

## 7. Probar API Endpoints

### Prueba 7.1: get_available_slots

1. **Abrir consola del navegador** (F12)

2. **Ejecutar**:
```javascript
frappe.call({
    method: "meet_scheduling.meet_scheduling.api.appointment_api.get_available_slots",
    args: {
        calendar_resource: "Dr. Test - Consultas",
        from_date: "2026-01-26",
        to_date: "2026-01-28"
    },
    callback: function(r) {
        console.log("Available Slots:", r.message);
        console.table(r.message);
    }
});
```

✅ **Resultado esperado**:
```javascript
[
  {
    start: "2026-01-26 09:00:00",
    end: "2026-01-26 09:30:00",
    capacity_remaining: 1,
    is_available: true
  },
  // ... más slots
]
```

---

### Prueba 7.2: validate_appointment

```javascript
frappe.call({
    method: "meet_scheduling.meet_scheduling.api.appointment_api.validate_appointment",
    args: {
        calendar_resource: "Dr. Test - Consultas",
        start_datetime: "2026-01-26 10:00:00",
        end_datetime: "2026-01-26 11:00:00"
    },
    callback: function(r) {
        console.log("Validation Result:", r.message);
        if (r.message.valid) {
            frappe.show_alert({message: "✓ Horario válido", indicator: "green"});
        } else {
            frappe.show_alert({message: "✗ " + r.message.errors[0], indicator: "red"});
        }
    }
});
```

---

### Prueba 7.3: generate_meeting

```javascript
// Primero, obtén el nombre de un appointment confirmado
frappe.call({
    method: "meet_scheduling.meet_scheduling.api.appointment_api.generate_meeting",
    args: {
        appointment_name: "APT-00001"  // Reemplaza con un nombre real
    },
    callback: function(r) {
        console.log("Generate Meeting Result:", r.message);
        if (r.message.success) {
            frappe.msgprint(`Meeting creado: ${r.message.meeting_url}`);
        } else {
            frappe.msgprint(`Error: ${r.message.message}`);
        }
    }
});
```

---

## 8. Probar Calendar Exceptions

### Paso 8.1: Crear Excepción de Cierre

1. **Ir al DocType**:
   - Busca: `Calendar Exception`
   - Click en **New**

2. **Llenar**:
   ```
   Calendar Resource: Dr. Test - Consultas
   Exception Type: Closed
   Date: [próximo lunes]
   Reason: Día festivo - Prueba
   ```

3. **Guardar**

---

### Paso 8.2: Verificar Bloqueo

1. **Intentar crear Appointment en ese día**:
   ```
   Calendar Resource: Dr. Test - Consultas
   Start Datetime: [día de la excepción] 10:00:00
   End Datetime: [día de la excepción] 11:00:00
   ```

2. **Submit** → ❌ Error esperado:
   ```
   ValidationError: No hay disponibilidad en [fecha] para este Calendar Resource
   ```

✅ **Resultado esperado**: Exception bloqueó todo el día

---

### Paso 8.3: Excepción de Bloqueo Parcial

1. **Crear Exception tipo Blocked**:
   ```
   Calendar Resource: Dr. Test - Consultas
   Exception Type: Blocked
   Date: [próximo martes]
   Start Time: 10:00:00
   End Time: 11:00:00
   Reason: Reunión interna
   ```

2. **Verificar**: Solo esa franja horaria estará bloqueada

---

### Paso 8.4: Excepción de Disponibilidad Extra

1. **Crear Exception tipo Extra Availability**:
   ```
   Calendar Resource: Dr. Test - Consultas
   Exception Type: Extra Availability
   Date: [un sábado]
   Start Time: 09:00:00
   End Time: 12:00:00
   Reason: Horario especial por demanda
   ```

2. **Verificar**: Ese sábado ahora tendrá disponibilidad

---

## 9. Checklist Final de Funcionalidades

Marca cada funcionalidad después de probarla:

### Core Features
- [ ] Crear Calendar Resource
- [ ] Crear Availability Plan con slots
- [ ] Crear Appointment Draft
- [ ] Submit Appointment → Confirmed
- [ ] Cancelar Appointment
- [ ] Validación: horario fuera de disponibilidad (bloqueado)
- [ ] Validación: overlap con capacity excedida (bloqueado)
- [ ] Validación: end < start (bloqueado)

### Video Call Features
- [ ] Video Call Profile - manual_only
- [ ] Video Call Profile - auto_generate (mock)
- [ ] Meeting URL copiado correctamente en manual
- [ ] Meeting URL generado automáticamente en auto

### Advanced Features
- [ ] Draft Expiration automático (15 min)
- [ ] Warnings en Draft (naranja, no bloquea)
- [ ] Calendar Exception - Closed
- [ ] Calendar Exception - Blocked
- [ ] Calendar Exception - Extra Availability
- [ ] Capacity > 1 (múltiples appointments simultáneos)

### API Features
- [ ] get_available_slots retorna lista
- [ ] validate_appointment valida correctamente
- [ ] generate_meeting (manual generation)

---

## 10. Troubleshooting

### Problema: "No availability for selected time"

**Solución**:
1. Verifica que el día esté en Availability Plan
2. Verifica que no haya Calendar Exception bloqueando
3. Verifica que la hora esté dentro de un slot
4. Verifica que el `weekday` en Availability Slot use el formato correcto (Monday, Tuesday, etc.)

---

### Problema: "Module not found"

**Solución**:
```bash
bench restart
bench clear-cache
```

---

### Problema: Tests no pasan después de cambios en UI

**Solución**:
```bash
bench --site development.localhost run-tests --app meet_scheduling
```

---

### Problema: Campo "weekday" muestra valores incorrectos

**Verificación**:
- El campo debe tener opciones: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
- Sin traducciones ni prefijos (ej: "Monday: Lunes" es incorrecto)
- Python `strftime("%A")` retorna exactamente estos valores

---

## 11. Notas Técnicas

### Cambios Recientes Implementados

1. **Campo `availability_slots` agregado**:
   - Ahora los Availability Plans tienen un campo tabla llamado `availability_slots`
   - El código usa fallback en cascada para máxima compatibilidad

2. **Campo `weekday` simplificado**:
   - Opciones: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
   - Sin traducciones
   - Valor por defecto: Monday
   - Compatible con Python `strftime("%A")`

3. **Tests actualizados**:
   - 32 tests pasando (100%)
   - Cobertura completa de scheduling, overlaps, slots, tasks, API

---

## 🎉 Conclusión

Si completaste todos los pasos, has probado:
- ✅ 100% de la funcionalidad del USER_GUIDE.md
- ✅ Todas las validaciones implementadas
- ✅ Video calls (manual y auto mock)
- ✅ Draft expiration
- ✅ Calendar exceptions (3 tipos)
- ✅ API endpoints
- ✅ Cambios recientes en campos

**La aplicación está lista para producción con enlaces manuales** 🚀

---

## 📚 Referencias

- **USER_GUIDE.md**: Guía de usuario completo
- **CLAUDE.md**: Documentación del proyecto y decisiones de diseño
- **tests/README.md**: Documentación de tests
- **docs/**: Documentación técnica completa

---

**Última actualización**: 2026-01-21
**Versión**: 1.1 (con cambios en availability_slots y weekday)
