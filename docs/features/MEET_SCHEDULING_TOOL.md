# Feature: Tool del portal `meet_scheduling`

El Service Portal de `common_configurations` soporta "tools" pluggables. `meet_scheduling` registra dos: `meet_scheduling` (agendar) y `my_appointments` (ver/cancelar). Este documento describe la primera.

---

## Registro como Tool Type

Definido en `meet_scheduling/fixtures/tool_type.json:2-11`:

```json
{
  "doctype": "Tool Type",
  "name": "meet_scheduling",
  "tool_name": "meet_scheduling",
  "tool_label": "Agendamiento de Citas",
  "app_name": "meet_scheduling",
  "icon": "Calendar",
  "description": "Permite agendar citas según disponibilidad de Calendar Resources",
  "is_active": 1
}
```

El admin del portal puede agregar esta tool a un `Service Portal` desde el Desk: `Service Portal → Tools → Add Row → Tool Type = meet_scheduling`.

---

## Configuración por instancia: custom field `calendar_resource`

Cada vez que el admin agrega una tool `meet_scheduling` a un portal, debe escoger **qué Calendar Resource** se va a agendar. Esto se hace con el custom field `calendar_resource` en el child DocType `Service Portal Tool`.

Definido en `meet_scheduling/fixtures/custom_field.json`:

```json
{
  "doctype": "Custom Field",
  "name": "Service Portal Tool-calendar_resource",
  "dt": "Service Portal Tool",
  "fieldname": "calendar_resource",
  "fieldtype": "Link",
  "options": "Calendar Resource",
  "label": "Calendar Resource",
  "insert_after": "tool_type",
  "depends_on": "eval:doc.tool_type=='meet_scheduling'",
  "mandatory_depends_on": "eval:doc.tool_type=='meet_scheduling'",
  "description": "Recurso de calendario para obtener disponibilidad"
}
```

Es:
- **Visible solo** cuando `tool_type == 'meet_scheduling'`.
- **Obligatorio** cuando `tool_type == 'meet_scheduling'`.

---

## Flujo end-to-end de uso

1. El admin del portal crea/edita un `Service Portal`, agrega una fila a `tools` con `tool_type = meet_scheduling` y selecciona `calendar_resource = "Dr. Juan Pérez"`.
2. El ciudadano público entra al portal en `https://<sitio>/service-portal/<portal_name>`.
3. Si no está autenticado, ve un estado bloqueado pidiendo registrarse. Tras registrar `User contact`, recibe un token (header `X-User-Contact-Token`).
4. El ciudadano selecciona la tool "Agendamiento de Citas". El componente Angular lee la config del portal, encuentra la tool con `tool_type='meet_scheduling'` y extrae su `calendar_resource`.
5. El componente llama `meet_scheduling.api.appointments.get_available_slots` para el mes corriente. Pinta un calendario con días que tienen disponibilidad.
6. El ciudadano elige una fecha → ve slots disponibles del día (filtrados por `is_available`).
7. Selecciona un slot → opcionalmente escribe `appointment_context` (con soporte voice-input).
8. Confirma → el componente llama `meet_scheduling.api.appointments.create_and_confirm_appointment` con el token. El backend valida, crea Draft, hace submit, devuelve el Appointment confirmado.
9. Si el `Calendar Resource.send_email_notification = 1`, se encola la notificación por email (`enqueue_after_commit=True`).
10. Si el `Calendar Resource.create_case_log = 1` (lex_app), se crea un `Case Log` en `on_submit`.
11. Si el `Calendar Resource.create_logbook_entry = 1` (logbook), se crea un `Logbook Entry`.

---

## Componente Angular

- **Ubicación**: `common_configurations/front_apps/service-portal/src/app/features/tools/meet-scheduling/`
- **Archivos**:
  - `meet-scheduling-tool.component.ts` (573 líneas).
  - `meet-scheduling-tool.component.html`
  - `meet-scheduling-tool.component.scss`

### Inyecciones

```ts
private meetSchedulingService = inject(MeetSchedulingService);
private stateService = inject(StateService);
private router = inject(Router);
```

### Estado principal (signals)

```ts
protected calendarResource = signal<string>('');
protected showCalendarView = signal<boolean>(true);
protected loading = signal<boolean>(false);
protected loadingSlots = signal<boolean>(false);
protected error = signal<string | null>(null);
protected successMessage = signal<string | null>(null);
protected activeTab = signal<'book' | 'appointments'>('book');
protected showPreConfirmModal = signal<boolean>(false);
protected showConfirmModal = signal<boolean>(false);
protected confirmedAppointment = signal<Appointment | null>(null);
protected appointmentContext = signal<string>('');
protected selectedDate = signal<string>('');
protected availableSlots = signal<AvailableSlot[]>([]);
protected selectedSlot = signal<AvailableSlot | null>(null);
protected currentMonth = signal<Date>(new Date());
protected calendarDays = signal<CalendarDay[]>([]);
protected availabilityMap = signal<Map<string, AvailableSlot[]>>(new Map());
```

### `ngOnInit`

`meet-scheduling-tool.component.ts:85-104`:

```ts
ngOnInit(): void {
  if (this.isAnonymousUser()) return;

  const portal = this.selectedPortal();
  const tool = portal?.tools.find(t => t.tool_type === 'meet_scheduling');

  if (tool && tool.calendar_resource) {
    this.calendarResource.set(tool.calendar_resource);
    this.showCalendarView.set(tool.show_calendar_view ?? true);

    this.loadCalendarMonth(this.currentMonth());
    this.loadUserAppointments();
  } else {
    this.error.set('Configuración de calendario no encontrada');
  }
}
```

### Carga del mes

`loadCalendarMonth` (`component.ts:109-151`):
- Calcula primer y último día del mes.
- Llama `getAvailableSlots(resource, fromDate, toDate)`.
- Agrupa los slots por `dateStr` (campo `start` partido por espacio).
- Pinta el calendario con indicador `hasAvailability` por día.

### Confirmación

Tras seleccionar slot y opcionalmente capturar `appointmentContext`:

```ts
this.meetSchedulingService.createAndConfirmAppointment({
  calendar_resource: this.calendarResource(),
  user_contact: this.userContact()!.name,
  start_datetime: this.selectedSlot()!.start,
  end_datetime: this.selectedSlot()!.end,
  appointment_context: this.appointmentContext(),
});
```

El service envía el header `X-User-Contact-Token` automáticamente (via interceptor).

---

## Estado anónimo

Si el usuario no se ha registrado, `isAnonymousUser()` retorna true y el componente muestra un estado bloqueado pidiendo registrarse. Esto es porque `create_and_confirm_appointment` exige token autenticado.

---

## Estado actual y deuda técnica

- **Implementado y funcional**: agendar citas, ver disponibilidad mensual, capturar `appointment_context` (incluso por voz vía `VoiceInputComponent`).
- **Adapter mock**: cuando la cita tiene videollamada `auto_generate`, el `meeting_url` resultante es `https://meet.google.com/mock-APT-...`. En producción aún no se crean meetings reales.
- **El componente carga también `my_appointments`** vía la pestaña `activeTab = 'appointments'`, duplicando lógica con la tool `my_appointments`. Posible deuda: refactor para usar solo la tool `my_appointments`.
- **No hay manejo explícito de rate limit**: si el usuario excede 5 creaciones/min/IP, el backend retorna error pero el frontend no muestra mensaje específico.
