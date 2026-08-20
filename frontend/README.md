# Barberus Frontend

Next.js (App Router) + TypeScript + Tailwind, sobre la misma arquitectura hexagonal +
DDD por contextos delimitados que usa `api/` (ver
[`.claude/agents/frontend-nextjs.md`](../.claude/agents/frontend-nextjs.md)).

## Gestión de paquetes: `pnpm`

Se eligió `pnpm` (npm era la alternativa por defecto) por consistencia con el criterio ya
usado en `api/` (`uv`, con lockfile reproducible y resolución estricta): `pnpm` usa un
store de contenido direccionado + symlinks que evita instalar duplicados por cada
paquete futuro (`agenda`, `fila`, etc. sumarán sus propias dependencias con el tiempo,
igual que se justificó `uv` en el backend), y su `node_modules` no-flat detecta
dependencias fantasma (importar algo que no está declarado en `package.json` porque otro
paquete lo trajo transitivamente) que `npm`/`yarn` clásicos dejan pasar en silencio.
`pnpm-lock.yaml` es el lockfile versionado.

```bash
# Instalar pnpm si no lo tienes: https://pnpm.io/installation

cd frontend
pnpm install
cp .env.local.example .env.local     # completar si el backend no corre en localhost:8000
pnpm dev                              # http://localhost:3000
pnpm lint
pnpm build
```

Requiere el backend (`api/`) corriendo (`uv run uvicorn main:app --reload`, puerto 8000
por defecto) y con `CORS_ORIGENES=http://localhost:3000` en `api/.env` -- sin eso, el
navegador bloquea las llamadas del contexto `identidad` por CORS.

## Estructura

```
src/
├── contextos/
│   └── identidad/            # login/registro, resolución de rol+tenant -- ver abajo
│       ├── dominio/          # tipos + validación (zod) puros, sin React/fetch
│       ├── aplicacion/       # hooks de caso de uso (use-registro, use-iniciar-sesion...)
│       ├── infraestructura/  # cliente HTTP hacia api/, almacén de sesión (cookie)
│       └── ui/                # formulario de acceso, panel de sesión
├── compartido/
│   ├── tokens/                # paleta de marca (fuente de verdad, ver globals.css)
│   ├── animacion/             # variantes de framer-motion reutilizables
│   ├── ui/                    # Boton, Campo, tablero-fila-en-vivo (mock de landing)...
│   └── proveedores/           # QueryClientProvider
└── app/                        # landing (cascarón: solo compone ui/ de los contextos)
```

`agenda`, `fila`, `cliente`, `membresia` no existen todavía como contextos de frontend --
se agregan cuando el backend tenga la lógica correspondiente (hoy son esqueleto en `api/`).

## Tipos generados desde el OpenAPI del backend

`src/compartido/tipos-api/openapi.d.ts` se genera con
[`openapi-typescript`](https://www.npmjs.com/package/openapi-typescript) a partir del
schema OpenAPI que FastAPI ya expone solo (`api/main.py`, sin tocar nada del backend para
esto). Es la fuente de verdad de la FORMA del JSON que viaja por HTTP (nombres de campo en
snake_case, opcionalidad, nesting) -- evita mantener a mano tipos "crudos" de respuesta que
se desincronizan en silencio cuando cambia un esquema Pydantic (ver
`contextos/identidad/infraestructura/repositorio-identidad-http.ts`, que usa
`SchemaDatosSesionAuthRespuesta`/`SchemaContextoIdentidadRespuesta` en vez de interfaces
escritas a mano).

```bash
cd frontend
pnpm generar-tipos-api
```

Ese comando:

1. Corre `api/scripts/exportar_openapi.py` vía `uv run --directory ../api` -- importa la
   app FastAPI real y vuelca `app.openapi()` a un JSON (no necesita `uvicorn` corriendo,
   solo `api/.env` completo porque `main.py` valida configuración al importarse).
2. Corre `openapi-typescript` sobre ese JSON y escribe
   `src/compartido/tipos-api/openapi.d.ts`.
3. Borra el JSON intermedio (`frontend/openapi.json`, gitignorado -- no es la fuente de
   verdad versionada).

**`openapi.d.ts` SÍ se versiona** (a diferencia del JSON intermedio): así el frontend
compila sin depender de que el backend esté corriendo. Regenerarlo a mano cuando cambie
algún esquema Pydantic de `api/contextos/*/interfaces/esquemas.py` -- no hay hook
automático todavía (candidato a CI/pre-commit futuro).

Solo genera TIPOS estáticos, no un cliente HTTP: `openapi-typescript` no trae dependencias
de runtime. `RolIdentidad` (`contextos/identidad/dominio/tipos.ts`) sigue escrito a mano
porque el backend expone `rol` como `str` plano (no enum) en el schema -- ver el
comentario en ese archivo.

## Contexto `identidad`

Implementa los 3 endpoints reales de `api/contextos/identidad/interfaces/router.py`:

- `POST /identidad/registro` -- la UI muestra el MISMO mensaje genérico sea el correo
  nuevo o ya existente (anti-enumeración, igual criterio que el backend). Ver
  `dominio/tipos.ts::ResultadoRegistro`.
- `POST /identidad/iniciar-sesion` -- 401 se muestra como mensaje genérico, sin
  distinguir el motivo.
- `GET /identidad/contexto` -- el caso `403 SinRolAsignado` (usuario recién registrado,
  todavía sin rol -- el rol `cliente` se autoasigna en la primera reserva, que no existe
  aún) se trata como estado esperado del producto, no como error fatal. Ver
  `ui/panel-sesion.tsx`.

### Dónde vive el token

`infraestructura/almacen-sesion-cookie.ts` guarda el `access_token` en una cookie **no
httpOnly** escrita desde JS (no `localStorage`). Motivo: el backend hoy es un proxy de
Supabase Auth que devuelve el token en el body JSON, no vía `Set-Cookie`, así que quien
decide dónde persistirlo es el frontend. Una cookie viaja en cada request y la puede leer
un middleware/Server Component de Next más adelante (rutas protegidas por SSR) sin tocar
esta capa de nuevo -- solo agregar un lector server-side de la misma cookie. Si el backend
empieza a emitir `Set-Cookie` `httpOnly` (más resistente a XSS), este archivo es el único
que cambia. Documentado como decisión intencional, no definitiva, en el propio archivo.

## Diseño

Paleta, tipografía (`Bricolage Grotesque` display + `Inter` body + `JetBrains Mono` para
datos/horarios) y el elemento firma (`compartido/ui/tablero-fila-en-vivo.tsx`, una
recreación tipo tablero de salidas de la fila en vivo de una sede) están documentados como
comentarios en `compartido/tokens/colores.ts` y en el propio componente. Deliberadamente
NO usa la paleta "crema + serif + terracota" ni "negro + verde ácido" típicas de un
resultado genérico de IA para este brief.
