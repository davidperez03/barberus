# Barberus API

Backend de Barberus en FastAPI, sobre **arquitectura hexagonal (puertos y adaptadores) +
Domain-Driven Design**, organizado en contextos delimitados. Ver la justificación completa
en [`.claude/agents/backend-fastapi.md`](../.claude/agents/backend-fastapi.md) y el resumen
en la sección "Backend (API)" de [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## Gestión de dependencias: `uv`

Se eligió [`uv`](https://docs.astral.sh/uv/) (Poetry y `pip-tools` eran las alternativas
consideradas) por instalación reproducible vía `uv.lock`, `uv run` sin activar
manualmente el entorno virtual, y por ser sensiblemente más rápido resolviendo/instalando
-- relevante porque cada contexto futuro (`agenda`, `membresias`, `reportes`) sumará sus
propias dependencias sin que el ciclo de instalación se vuelva un cuello de botella. El proyecto se declaró como aplicación, no como librería distribuible
(`[tool.uv] package = false` en `pyproject.toml`): no hay `src/` layout ni
`[build-system]`, `contextos/`/`nucleo/`/`main.py` viven directo bajo `api/`.

```bash
# Instalar uv si no lo tienes: https://docs.astral.sh/uv/getting-started/installation/

cd api
uv sync                     # crea .venv e instala dependencias + grupo dev, según uv.lock
cp .env.example .env        # completar con los datos de tu proyecto Supabase
uv run uvicorn main:app --reload
uv run pytest -q            # tests
uv run ruff check .         # lint
```

## Estructura

```
api/
├── contextos/
│   ├── identidad/          # perfiles, roles, sesiones — sobre supabase/migrations/009-010
│   │   ├── dominio/        # entidades, objetos de valor, servicios de dominio, puertos
│   │   ├── aplicacion/     # casos de uso (orquestan el dominio vía sus puertos)
│   │   ├── infraestructura/# adaptadores concretos contra Supabase (supabase-py, PyJWT)
│   │   └── interfaces/     # router FastAPI, esquemas Pydantic, Depends
│   ├── fila/                # comparador público de fila — sobre supabase/migrations/011
│   │   ├── dominio/        # objetos de valor (ResumenFilaNegocio), puertos
│   │   ├── aplicacion/     # caso de uso (ListarNegociosConFilaPublica)
│   │   ├── infraestructura/# adaptador contra `resumen_fila_publico` (supabase-py)
│   │   └── interfaces/     # router FastAPI, esquemas Pydantic, Depends
│   ├── agenda/              # esqueleto de carpetas, sin código — PR futuro
│   ├── membresias/          # esqueleto de carpetas, sin código — PR futuro
│   └── reportes/            # esqueleto de carpetas, sin código — PR futuro
├── nucleo/                  # shared kernel: configuración, excepciones base, tipos
│                             # compartidos, factory de clientes Supabase (cliente_supabase.py)
├── main.py                  # composición: monta el router de cada contexto
├── tests/                   # organizados en espejo de contextos/
├── pyproject.toml / uv.lock
└── .env.example
```

Cada contexto tiene sus propias 4 capas y las dependencias solo apuntan hacia adentro
(`interfaces` → `aplicacion` → `dominio`; `infraestructura` implementa puertos de
`dominio`). Un contexto nunca importa el `dominio`/`infraestructura` interno de otro --
si necesita algo de `identidad`, lo pide vía
`contextos.identidad.aplicacion.contexto_publico`.

## Contexto `identidad`

Resuelve, a partir del JWT de Supabase Auth de la request, el `ContextoIdentidad`
(usuario, rol activo, tenant aplicable, sesión) del que depende cualquier endpoint de
dominio futuro. Detalle de las decisiones de diseño (resolución de tenant cuando el
usuario tiene roles en varios, timeout de sesión diferenciado por rol) en los docstrings
de `contextos/identidad/dominio/servicios.py` y
`contextos/identidad/aplicacion/resolver_contexto_identidad.py`.

Endpoint de verificación end-to-end: `GET /identidad/contexto` (requiere
`Authorization: Bearer <jwt>`; opcionalmente `X-Tenant-Id` si el usuario tiene roles en
más de un tenant, y `X-Sesion-Id` para incluir el estado de la sesión).

### Registro e inicio de sesión

El login/registro NO se deja en manos del frontend llamando a `supabase-js` directo: el
backend hace de proxy de Supabase Auth (GoTrue) para que ambos flujos se puedan probar
desde `/docs` y para que toda la dependencia de Supabase Auth quede encerrada en un
adaptador de `infraestructura/` (`AutenticadorSupabase`) -- mismo patrón que
`ValidadorJwtSupabase`. Este adaptador usa un cliente `supabase-py` separado,
inicializado con la clave PÚBLICA (`SUPABASE_PUBLISHABLE_KEY`), nunca con la
`SUPABASE_SECRET_KEY` que usa el resto de `identidad` (signup/login no requieren
privilegios elevados).

- `POST /identidad/registro` -- body `{"correo": str, "contrasena": str}` (mínimo 8
  caracteres). Crea la cuenta en Supabase Auth. **No asigna ningún rol**: `cliente` se
  autoasigna recién en la primera reserva (ver `docs/ARCHITECTURE.md`). Responde `201`
  con `{access_token, refresh_token, usuario_id, expira_at}` si hay sesión inmediata;
  `202` con un mensaje genérico si no la hay -- deliberadamente el MISMO `202`, sin
  distinción posible, tanto si el correo era nuevo (confirmación pendiente) como si ya
  tenía cuenta: no existe un `409` para este endpoint, sería una fuga de enumeración de
  cuentas (ver "Recuperación de contraseña y enumeración de usuarios" en
  `docs/ARCHITECTURE.md`).
- `POST /identidad/iniciar-sesion` -- mismo body. Responde `200` con los mismos campos;
  `401` con un mensaje genérico si el correo/contraseña no coinciden o si la cuenta
  existe pero no ha confirmado su correo (mismo criterio anti-enumeración).

Los tokens devueltos son los mismos que emitiría Supabase Auth directo: se usan igual
como `Authorization: Bearer <access_token>` contra `GET /identidad/contexto` y el resto
de endpoints.

## Contexto `fila`

Primer y único endpoint del contexto: `GET /fila/publica`. **Sin `Authorization`, sin
`X-Tenant-Id`** -- es a propósito el único endpoint cross-tenant de toda la API, espejo
de la única tabla de lectura pública del esquema (`resumen_fila_publico`, migración
`supabase/migrations/011_fila_publica_agregada.sql`, ver la sección "Excepción única:
lectura pública cross-tenant" de `docs/ARCHITECTURE.md`).

Responde `200` con una lista de negocios activos, uno por ítem:

```json
[
  {
    "tenant_id": "5f3b...",
    "nombre_sede": "Barbería Central",
    "slug_sede": "barberia-central",
    "personas_en_fila": 4,
    "tiempo_espera_estimado_minutos": 25,
    "latitud": 4.710989,
    "longitud": -74.072092
  }
]
```

`tiempo_espera_estimado_minutos`, `latitud` y `longitud` pueden venir `null` (negocio sin
historial reciente de atención o sin geolocalizar) -- el backend nunca inventa un valor,
los propaga tal cual; decidir cómo mostrar ese `null` es responsabilidad del frontend.
El caso de uso (`ListarNegociosConFilaPublica`) no aplica ninguna lógica de negocio propia:
delega el filtro `activo = true` y el cálculo de las cifras enteramente a Postgres (RLS +
triggers), y solo mapea la respuesta.

## Factory de clientes Supabase (`nucleo/cliente_supabase.py`)

Compartido por todos los contextos: `obtener_cliente_supabase_secreto()` (bypasea RLS,
`SUPABASE_SECRET_KEY`) y `obtener_cliente_supabase_publico()` (respeta RLS,
`SUPABASE_PUBLISHABLE_KEY`), ambos cacheados con `@lru_cache` para un único cliente por
proceso. `nucleo/` solo resuelve la instanciación genérica -- decidir CUÁL de las dos
key usar es responsabilidad de cada contexto, documentada en su propio
`infraestructura/cliente_supabase.py` (p. ej. `identidad` usa la secreta para
`roles_usuario`/`sesiones` y la pública solo para signup/login vía GoTrue; `fila` usa
solo la pública, porque `resumen_fila_publico` es la única tabla con policy de lectura
genuinamente abierta).

## Tests

`uv run pytest -q` desde `api/`. Los tests de `dominio/`/`aplicacion/` no requieren red
ni Supabase real (puertos con implementaciones fake) -- es la garantía que promete la
arquitectura hexagonal. Tests de integración contra un Supabase real (local o de CI)
quedan fuera de alcance de este PR.
