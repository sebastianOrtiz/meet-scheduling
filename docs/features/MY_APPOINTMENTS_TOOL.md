# Feature: Tool del portal `my_appointments`

Tool del Service Portal que permite a un `User contact` autenticado ver y cancelar sus propias citas. Es complementaria a `meet_scheduling` (que agenda).

---

## Registro como Tool Type

Definido en `meet_scheduling/fixtures/tool_type.json:12-21`:

```json
{
  "doctype": "Tool Type",
  "name": "my_appointments",
  "tool_name": "my_appointments",
  "tool_label": "Mis Citas",
  "app_name": "meet_scheduling",
  "icon": "ClipboardList",
  "description": "Visualiza y gestiona tus citas agendadas",
  "is_active": 1
}
```

---

## Configuración por instancia

A diferencia de la tool `meet_scheduling`, esta tool **no requiere custom fields adicionales**. No hay que configurar un `Calendar Resource`: el endpoint `get_my_appointments` retorna TODAS las citas del `User contact` autenticado, sin importar el recurso.

---

## Componente Angular

- **Ubicación**: `common_configurations/front_apps/service-portal/src/app/features/tools/my-appointments/`
- **Archivos**:
  - `my-appointments-tool.component.ts` (161 líneas).
  - `my-appointments-tool.component.html`
  - `my-appointments-tool.component.scss`

### Estado

```ts
protected loading = signal<boolean>(false);
protected error = signal<string | null>(null);
protected successMessage = signal<string | null>(null);
protected userAppointments = signal<Appointment[]>([]);
```

### `ngOnInit` (`component.ts:41-44`)

```ts
ngOnInit(): void {
  if (this.isAnonymousUser()) return;
  this.loadUserAppointments();
}
```

### Carga de citas (`component.ts:49-76`)

```ts
this.meetSchedulingService.getMyAppointments().subscribe({
  next: (appointments) => {
    const sorted = appointments.sort((a, b) =>
      new Date(b.start_datetime).getTime() - new Date(a.start_datetime).getTime()
    );
    this.userAppointments.set(sorted);
    this.loading.set(false);
  },
  error: (err) => { /* ... */ }
});
```

Usa `getMyAppointments`, que hace la llamada al endpoint `meet_scheduling.api.appointments.get_my_appointments` con el header `X-User-Contact-Token`.

### Cancelación (`component.ts:81-105`)

```ts
cancelAppointment(appointment: Appointment): void {
  if (!confirm('¿Estás seguro de cancelar esta cita?')) return;

  this.meetSchedulingService.cancelMyAppointment(appointment.name).subscribe({
    next: (result) => {
      this.successMessage.set(result.message || 'Cita cancelada exitosamente');
      this.loadUserAppointments();
    },
    error: (err) => { /* ... */ }
  });
}
```

Llama al endpoint `meet_scheduling.api.appointments.cancel_my_appointment`, que:
- Si la cita es Draft (`docstatus=0`) → la elimina.
- Si es Confirmed (`docstatus=1`) → la cancela.
- Si ya está Cancelled → retorna mensaje informativo.

### Helpers de formato

- `formatTime` y `formatDate` formatean en `es-ES` con `toLocaleTimeString`/`toLocaleDateString`.
- `getStatusClass(status)` mapea el status a clases CSS:
  - `Confirmed` → `status-confirmed`
  - `Completed` → `status-completed`
  - `Cancelled` → `status-cancelled`
  - `No-show` → `status-noshow`
  - default → `status-draft`

---

## Estado anónimo

Si el usuario no está autenticado (`isAnonymousUser()` true), el componente muestra un bloque pidiendo registrarse. El botón redirige a `[portalName]/register`.

---

## Diferencias con la pestaña "appointments" de `meet_scheduling`

El componente `meet-scheduling-tool` también tiene una pestaña `activeTab='appointments'` que muestra las citas del usuario. Esto duplica funcionalidad. Posible refactor: dejar solo la tool `my_appointments` para esta vista.

---

## Estado actual

- Funcional: lista las citas del `User contact` autenticado ordenadas por fecha descendente y permite cancelarlas.
- Sin filtros UI: no hay UI para filtrar por status, rango de fechas, etc. El backend sí lo soporta (`get_my_appointments` acepta `status`, `from_date`, `to_date`).
- Sin paginación: el backend devuelve hasta 100 citas (`limit=100` en `endpoints.py`).
- No muestra `meeting_url` clickeable destacado: hay que mejorar UX para "Unirse a la videollamada".
