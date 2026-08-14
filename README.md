# Barberus

Barberus es un SaaS multi-tenant para cadenas de barberías (pensado para 20 sedes de un
mismo grupo). Cada barbería administra su propia agenda, catálogo de servicios, barberos,
clientes y fila de espera en vivo, aislada del resto de sedes.

North star del producto: reducir los no-shows y el tiempo de espera en fila.

## Estado actual del proyecto

**Solo existe el esquema de base de datos.** No hay backend ni frontend implementados
todavía — nada de este repo es desplegable como aplicación en este momento. Lo que sí
existe y está completo:

- `supabase/migrations/`: 10 migraciones SQL (`001` a `010`) que definen 20 tablas —
  13 de dominio (barberías, barberos, servicios, clientes, reservas, fila, membresías) y
  7 de identidad/auth extendida (perfil de usuario, identidades vinculadas, sesiones,
  MFA-ready, tokens de un solo uso, auditoría) — con Row Level Security multi-tenant. Ver el
  detalle en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
- `scripts/migrations/APPLIED.md`: registro de cada migración, su estado y las decisiones
  de diseño detrás de cada una.

Las migraciones están **diseñadas pero no aplicadas a ningún entorno Supabase todavía**
(ver la columna "Estado" en `scripts/migrations/APPLIED.md`); sí fueron validadas
corriéndolas desde cero contra un Postgres real.

## Stack

El stack está definido en la configuración de los agentes de este repo
(`.claude/agents/`), pero a la fecha **solo la capa de base de datos tiene código real**.
El resto es el stack objetivo, todavía sin implementar:

| Capa | Tecnología | Estado |
|---|---|---|
| Base de datos | Supabase / PostgreSQL, con Row Level Security | Implementado (esquema completo, no aplicado a un entorno aún) |
| Backend | FastAPI (Python) | No implementado |
| Frontend | Next.js (App Router) + TypeScript + Tailwind | No implementado |
| Tiempo real (fila en vivo) | Supabase Realtime | No implementado |

## Estructura de carpetas

```
barberus/
├── supabase/
│   └── migrations/          # esquema SQL, 001_..._010_..., orden = orden numérico
├── scripts/
│   └── migrations/
│       └── APPLIED.md       # registro y notas de diseño de cada migración
├── docs/
│   └── ARCHITECTURE.md      # modelo multi-tenant, tablas, decisiones de diseño
└── .claude/agents/          # configuración de los agentes que trabajan este repo
```

No existen todavía carpetas `api/`, `backend/` ni `frontend/` — se documentarán aquí en
cuanto exista código en ellas.

## Cómo aplicar las migraciones localmente

Las migraciones referencian `auth.users` (la tabla de autenticación de Supabase) desde
varias tablas (`roles_usuario`, `barberos`, `clientes`, etc.), así que **no se pueden
aplicar contra un Postgres vanilla** — necesitan un proyecto Supabase real (local o
remoto), que es quien provee el esquema `auth`.

Este repo todavía no incluye `supabase/config.toml` (el proyecto Supabase local no está
inicializado en el repo), así que el primer paso es inicializarlo:

```bash
# 1. Instalar la Supabase CLI si no la tienes:
#    https://supabase.com/docs/guides/cli

# 2. Inicializar el proyecto Supabase local (crea supabase/config.toml)
supabase init

# 3. Levantar Postgres + Auth local vía Docker
supabase start

# 4. Aplicar las migraciones pendientes
supabase migration up
```

Para aplicar contra un proyecto Supabase remoto ya vinculado (`supabase link`):

```bash
supabase db push
```

Ambos comandos están documentados en `scripts/migrations/APPLIED.md` ("Cómo aplicar").
No hay variables de entorno ni datos semilla (seeds) documentados en el repo todavía — se
agregarán aquí cuando existan.
