# Barberus API

Backend de Barberus en FastAPI, sobre **arquitectura hexagonal (puertos y adaptadores) +
Domain-Driven Design**, organizado en contextos delimitados. Ver la justificación completa
en [`.claude/agents/backend-fastapi.md`](../.claude/agents/backend-fastapi.md) y el resumen
en la sección "Backend (API)" de [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## Gestión de dependencias: `uv`

Se eligió [`uv`](https://docs.astral.sh/uv/) (Poetry y `pip-tools` eran las alternativas
consideradas) por instalación reproducible vía `uv.lock`, `uv run` sin activar
manualmente el entorno virtual, y por ser sensiblemente más rápido resolviendo/instalando
-- relevante porque cada contexto futuro (`agenda`, `fila`, `membresias`, `reportes`)
sumará sus propias dependencias sin que el ciclo de instalación se vuelva un cuello de
botella. El proyecto se declaró como aplicación, no como librería distribuible
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
│   ├── agenda/              # esqueleto de carpetas, sin código — PR futuro
│   ├── fila/                # esqueleto de carpetas, sin código — PR futuro
│   ├── membresias/          # esqueleto de carpetas, sin código — PR futuro
│   └── reportes/            # esqueleto de carpetas, sin código — PR futuro
├── nucleo/                  # shared kernel: configuración, excepciones base, tipos compartidos
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

## Tests

`uv run pytest -q` desde `api/`. Los tests de `dominio/`/`aplicacion/` no requieren red
ni Supabase real (puertos con implementaciones fake) -- es la garantía que promete la
arquitectura hexagonal. Tests de integración contra un Supabase real (local o de CI)
quedan fuera de alcance de este PR.
