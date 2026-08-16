# Barberus

Barberus es una plataforma multi-tenant que actúa como **intermediaria entre múltiples
negocios independientes** (barberías, salones de uñas y otros verticales de servicios de
belleza/cuidado personal con cita o turno) **y sus clientes**. No es dueña de "sedes" de
una sola marca: cada negocio que se registra es su propio tenant, con su propia agenda,
catálogo de servicios, profesionales, clientes y fila de espera en vivo, aislado del resto
de negocios de la plataforma.

North star del producto: reducir los no-shows y el tiempo de espera en fila.

## Estado actual del proyecto

**Existen el esquema de base de datos aplicado a un proyecto Supabase real, el scaffolding
del backend y el scaffolding del frontend (con el contexto `identidad` end-to-end,
incluido registro/login).** Lo que sí existe y está completo:

- `supabase/migrations/`: 11 migraciones SQL (`001` a `011`) que definen 21 tablas —
  14 de dominio (`negocios`, `profesionales`, servicios, clientes, reservas, fila,
  membresías, y `resumen_fila_publico`, el agregado público de fila entre negocios de la
  migración `011`) y 7 de identidad/auth extendida (perfil de usuario, identidades
  vinculadas, sesiones, MFA-ready, tokens de un solo uso, auditoría) — con Row Level
  Security multi-tenant. Ver el detalle en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
- `scripts/migrations/APPLIED.md`: registro de cada migración, su estado y las decisiones
  de diseño detrás de cada una.
- `api/`: scaffolding de la API FastAPI (arquitectura hexagonal + DDD) con los contextos
  `identidad` y `fila` implementados. `identidad`, end-to-end: resolución de JWT/rol/tenant
  (validado vía JWKS contra Supabase Auth, no HS256 legacy) y los endpoints
  `POST /identidad/registro` / `POST /identidad/iniciar-sesion` como proxy a Supabase Auth
  (GoTrue). `fila`, con su primer endpoint real: `GET /fila/publica`, sin autenticación,
  comparador público de fila entre negocios para un mapa. El resto de contextos (`agenda`,
  `membresias`, `reportes`) sigue como esqueleto de carpetas, pendiente de lógica en PRs
  futuros. Ver [`api/README.md`](api/README.md).
- `frontend/`: scaffolding de Next.js (App Router + TypeScript + Tailwind), misma
  arquitectura hexagonal + DDD por contextos que `api/`, con el contexto `identidad`
  implementado: rutas propias `/iniciar-sesion` y `/registro` (no tabs de un mismo
  formulario) y una landing con parallax como elemento de diseño. `agenda`/`fila`/
  `cliente`/`membresia` sin construir todavía. Ver [`frontend/README.md`](frontend/README.md).

Las 11 migraciones **ya se aplicaron a un proyecto Supabase real** (vinculado vía
`supabase link`, con `supabase db push`/`db reset --linked`) — no es solo un esquema
diseñado contra un Postgres local efímero. Las credenciales de ese proyecto (URL, keys,
SMTP) viven en `.env`/`api/.env`, gitignored, nunca en este README ni en el repo.

## Stack

El stack está definido en la configuración de los agentes de este repo
(`.claude/agents/`). Estado real a la fecha:

| Capa | Tecnología | Estado |
|---|---|---|
| Base de datos | Supabase / PostgreSQL, con Row Level Security | Implementado y aplicado a un proyecto Supabase real (esquema completo, 11 migraciones) |
| Backend | FastAPI (Python), arquitectura hexagonal + DDD por contextos delimitados | Scaffolding + contextos `identidad` y `fila` implementados (JWT vía JWKS, registro/login proxy a Supabase Auth, `GET /fila/publica` sin autenticación — ver `api/README.md`); `agenda`/`membresias`/`reportes` sin lógica todavía |
| Frontend | Next.js (App Router) + TypeScript + Tailwind, arquitectura hexagonal + DDD por contextos | Scaffolding + contexto `identidad` (rutas `/iniciar-sesion` y `/registro`, landing con parallax) implementados (ver `frontend/README.md`); `agenda`/`fila`/`cliente`/`membresia` sin construir todavía |
| Tiempo real (fila en vivo) | Supabase Realtime | No implementado |

## Estructura de carpetas

```
barberus/
├── supabase/
│   └── migrations/          # esquema SQL, 001_..._011_..., orden = orden numérico
├── scripts/
│   └── migrations/
│       └── APPLIED.md       # registro y notas de diseño de cada migración
├── api/                      # backend FastAPI — arquitectura hexagonal + DDD
│   ├── contextos/
│   │   ├── identidad/        # perfiles, roles, sesiones (implementado) — ver api/README.md
│   │   ├── fila/               # GET /fila/publica, sin auth (implementado) — ver api/README.md
│   │   ├── agenda/            # esqueleto de carpetas, sin código — PR futuro
│   │   ├── membresias/         # esqueleto de carpetas, sin código — PR futuro
│   │   └── reportes/           # esqueleto de carpetas, sin código — PR futuro
│   ├── nucleo/                # shared kernel: configuración, excepciones base, tipos,
│   │                           # factory de clientes Supabase (secreto/público)
│   ├── main.py                # composición: monta el router de cada contexto
│   └── tests/
├── frontend/                  # frontend Next.js — arquitectura hexagonal + DDD por contextos
│   ├── src/
│   │   ├── contextos/
│   │   │   └── identidad/     # login/registro/contexto — ver frontend/README.md
│   │   │       ├── dominio/         # tipos + validación (zod) puros, sin React/fetch
│   │   │       ├── aplicacion/      # hooks de caso de uso (use-registro, use-iniciar-sesion...)
│   │   │       ├── infraestructura/ # cliente HTTP hacia api/, almacén de sesión (cookie)
│   │   │       └── ui/               # pantalla-registro, pantalla-iniciar-sesion, panel-sesion
│   │   ├── compartido/         # design tokens, animación (incl. parallax), UI genérica
│   │   └── app/                 # App Router: landing + rutas /iniciar-sesion y /registro,
│   │                             # solo compone ui/ de los contextos
│   └── README.md
├── docs/
│   └── ARCHITECTURE.md      # modelo multi-tenant, tablas, decisiones de diseño
└── .claude/agents/          # configuración de los agentes que trabajan este repo
```

Cada contexto bajo `api/contextos/` y bajo `frontend/src/contextos/` sigue la misma
convención de 4 capas (`dominio/aplicacion/infraestructura/interfaces` en el backend;
`dominio/aplicacion/infraestructura/ui` en el frontend), descrita en
[`.claude/agents/backend-fastapi.md`](.claude/agents/backend-fastapi.md) /
[`.claude/agents/frontend-nextjs.md`](.claude/agents/frontend-nextjs.md) y detallada en
[`api/README.md`](api/README.md) / [`frontend/README.md`](frontend/README.md).

## Cómo aplicar las migraciones localmente

Las migraciones referencian `auth.users` (la tabla de autenticación de Supabase) desde
varias tablas (`roles_usuario`, `profesionales`, `clientes`, etc.), así que **no se pueden
aplicar contra un Postgres vanilla** — necesitan un proyecto Supabase real (local o
remoto), que es quien provee el esquema `auth`.

Este repo **ya incluye `supabase/config.toml`** (proyecto Supabase inicializado, con la
configuración de SMTP de producción vía variables de entorno — nunca credenciales en
claro), y ya está vinculado a un proyecto Supabase remoto real con las 11 migraciones
aplicadas. Para levantar un entorno local (Docker) contra ese mismo esquema:

```bash
# 1. Instalar la Supabase CLI si no la tienes:
#    https://supabase.com/docs/guides/cli

# 2. Levantar Postgres + Auth local vía Docker (usa supabase/config.toml ya existente)
supabase start

# 3. Aplicar las migraciones al Postgres local
supabase migration up
```

Para aplicar contra el proyecto Supabase remoto ya vinculado (`supabase link`, requiere
las credenciales del proyecto real, que no viven en este repo):

```bash
supabase db push
```

Ambos comandos están documentados en `scripts/migrations/APPLIED.md` ("Cómo aplicar").
No hay datos semilla (seeds) documentados en el repo todavía — se agregarán aquí cuando
existan. Las variables de entorno del backend (URL/keys de Supabase) están en
[`api/.env.example`](api/.env.example), documentadas en [`api/README.md`](api/README.md).
