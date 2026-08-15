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
