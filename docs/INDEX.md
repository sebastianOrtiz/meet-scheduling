# 📚 Documentación - Meet Scheduling

Índice completo de toda la documentación de la aplicación Meet Scheduling.

---

## 🚀 Inicio Rápido

### Para Desarrolladores Nuevos

1. **[../START_HERE.md](../START_HERE.md)** ⭐ **EMPIEZA AQUÍ**
   - Guía de inicio rápido
   - Primeros pasos para implementación
   - Checklist de preparación

2. **[../CLAUDE.md](../CLAUDE.md)** - Referencia Principal
   - Arquitectura completa de la aplicación
   - Descripción de todos los DocTypes
   - Patrones de diseño y mejores prácticas

---

## 📖 Documentación Técnica

### Especificaciones y Diseño

**[DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)** - Decisiones de Diseño Confirmadas
- ✅ Todas las decisiones de diseño con implementación
- Código de ejemplo completo
- Casos de uso documentados
- **LEE ESTO ANTES DE CODEAR**

**[README.md](README.md)** - Documentación Técnica Detallada
- Objetivo del módulo
- Entidades y responsabilidades
- Flujos principales (user journeys)
- Reglas de negocio
- Algoritmos detallados
- Arquitectura de implementación

---

## 🗺️ Plan de Implementación

**[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - Plan Paso a Paso
- Plan completo dividido en 8 fases
- Código de ejemplo para cada tarea
- Checklists de validación
- Tests requeridos
- Cronograma estimado
- **USA ESTO DURANTE LA IMPLEMENTACIÓN**

---

## 👥 Documentación de Usuario

**[USER_GUIDE.ms](USER_GUIDE.ms)** - Guía de Usuario Final
- Manual para administradores
- Manual para staff/schedulers
- Casos de uso comunes
- Solución de problemas
- Preguntas frecuentes (FAQ)

---

## 📂 Estructura de Documentación

```
meet_scheduling/
├── START_HERE.md                    ← 🚀 Punto de entrada
├── CLAUDE.md                        ← 📖 Referencia principal
├── README.md                        ← ℹ️ Info general del proyecto
│
└── docs/
    ├── INDEX.md (este archivo)      ← 📚 Índice de documentación
    ├── DESIGN_DECISIONS.md          ← ✅ Decisiones confirmadas
    ├── IMPLEMENTATION_PLAN.md       ← 🗺️ Plan detallado
    ├── README.md                    ← 🔧 Doc técnica detallada
    └── USER_GUIDE.ms                ← 👥 Guía de usuario
```

---

## 🎯 Flujo de Lectura Recomendado

### Para Implementar la Aplicación

1. **[../START_HERE.md](../START_HERE.md)** - Lee primero
2. **[DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)** - Entiende las decisiones
3. **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - Sigue el plan
4. **[README.md](README.md)** - Consulta algoritmos específicos
5. **[../CLAUDE.md](../CLAUDE.md)** - Referencia general

### Para Entender el Sistema

1. **[../CLAUDE.md](../CLAUDE.md)** - Visión general
2. **[README.md](README.md)** - Detalles técnicos
3. **[USER_GUIDE.ms](USER_GUIDE.ms)** - Casos de uso
4. **[DESIGN_DECISIONS.md](DESIGN_DECISIONS.md)** - Decisiones de diseño

### Para Usuarios Finales

1. **[USER_GUIDE.ms](USER_GUIDE.ms)** - Guía completa
2. **[../README.md](../README.md)** - Instalación y configuración

---

## 📝 Resumen de Contenidos

### DESIGN_DECISIONS.md
- ✅ **Decisión 1**: Validación de Overlaps (Draft vs Submit)
- ✅ **Decisión 2**: Estados que Bloquean Horarios (con expiración de Drafts)
- ✅ **Decisión 3**: Cambio de Hora con Meeting Creado
- ✅ **Decisión 4**: Validación de Slot Duration
- Campos adicionales requeridos
- Implementación completa con código

### IMPLEMENTATION_PLAN.md
- **Fase 0**: Preparación del entorno (1 hora)
- **Fase 1**: Servicios de Scheduling (1-2 días)
- **Fase 2**: Servicios de Videollamadas (1 día)
- **Fase 3**: Lógica de DocTypes (2-3 días)
- **Fase 4**: API Endpoints (1 día)
- **Fase 5**: Tests Comprehensivos (1-2 días)
- **Fase 6**: Permisos y Roles (4 horas)
- **Fase 7**: OAuth y APIs Reales (2-3 días)
- **Fase 8**: Frontend y UX (1-2 días)

### README.md (Técnico)
1. Objetivo del módulo
2. Entidades y responsabilidades
3. Flujos principales
4. Reglas de negocio
5. Arquitectura de implementación
6. Hooks y eventos Frappe
7. Algoritmos (disponibilidad, overlaps)
8. Videollamadas (patrón Adapter)
9. Permisos y roles
10. API endpoints
11. Estados y obligatoriedad
12. Casos borde
13. Plan de pruebas

### USER_GUIDE.ms
1. Conceptos básicos
2. Configuración inicial (admin)
3. Uso diario (crear citas)
4. Cambios y cancelaciones
5. Preguntas frecuentes
6. Solución de problemas
7. Buenas prácticas

---

## 🔍 Búsqueda Rápida

¿Buscas información sobre...?

| Tema | Documento |
|------|-----------|
| ¿Por dónde empezar? | [../START_HERE.md](../START_HERE.md) |
| Arquitectura general | [../CLAUDE.md](../CLAUDE.md) |
| Decisiones de diseño | [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) |
| Cómo implementar | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) |
| Algoritmos específicos | [README.md](README.md) |
| Casos de uso | [USER_GUIDE.ms](USER_GUIDE.ms) |
| DocTypes y campos | [../CLAUDE.md](../CLAUDE.md) |
| Validaciones | [README.md](README.md) + [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) |
| Videollamadas | [README.md](README.md) sección 9 |
| Tests | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) Fase 5 |
| Permisos | [README.md](README.md) sección 10 |
| API endpoints | [README.md](README.md) sección 11 |

---

## 💡 Tips para Navegar la Documentación

### Durante Desarrollo
- Mantén abierto **IMPLEMENTATION_PLAN.md** como guía principal
- Consulta **DESIGN_DECISIONS.md** cuando tengas dudas sobre "por qué"
- Usa **README.md** (técnico) para algoritmos y pseudocódigo
- Referencia **CLAUDE.md** para recordar campos y estructuras

### Durante Revisión
- **DESIGN_DECISIONS.md** para validar que cumple con decisiones
- **IMPLEMENTATION_PLAN.md** para verificar que todos los pasos están completos

### Para Nuevos Miembros del Equipo
1. Leer **START_HERE.md**
2. Leer **CLAUDE.md** secciones 1-3
3. Leer **DESIGN_DECISIONS.md** completo
4. Empezar con **IMPLEMENTATION_PLAN.md**

---

## 📅 Estado de la Documentación

| Documento | Estado | Última Actualización |
|-----------|--------|---------------------|
| START_HERE.md | ✅ Completo | 2026-01-21 |
| CLAUDE.md | ✅ Completo | 2026-01-21 |
| DESIGN_DECISIONS.md | ✅ Completo | 2026-01-21 |
| IMPLEMENTATION_PLAN.md | ✅ Completo | 2026-01-21 |
| README.md (técnico) | ✅ Completo | 2026-01-21 |
| USER_GUIDE.ms | ✅ Completo | 2026-01-21 |

---

## 🆘 ¿Necesitas Ayuda?

Si no encuentras lo que buscas en la documentación:

1. **Revisa el índice arriba** - tabla de búsqueda rápida
2. **Busca en los archivos** - usa Ctrl+F / Cmd+F
3. **Consulta START_HERE.md** - tiene tips y comandos útiles
4. **Revisa los ejemplos de código** en IMPLEMENTATION_PLAN.md

---

## 📧 Contacto

**Desarrollador**: Sebastian Ortiz Valencia
**Email**: sebastianortiz989@gmail.com

---

**Última actualización**: 2026-01-21
