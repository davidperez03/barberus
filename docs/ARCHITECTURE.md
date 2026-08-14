# Arquitectura de Barberus

> Estado de este documento: describe el esquema de base de datos, que es lo único
> implementado hoy (ver `README.md`). La sección "Flujo de una reserva" describe la capa
> de base de datos con detalle verificado contra el código real, y el resto del flujo
> (frontend → API → tiempo real) tal como está **planeado** en la configuración de los
> agentes de este repo — se marcará explícitamente como no implementado donde aplique, y
> se completará con detalle real en cuanto exista ese código.

## Qué es Barberus

SaaS multi-tenant para una cadena de barberías (20 sedes de un mismo grupo). Cada sede
(tenant) es una fila en `barberias`; todo el resto del dominio —barberos, servicios,
clientes, reservas, fila de espera, membresías— cuelga de un `tenant_id`. North star:
reducir no-shows y tiempo de espera en fila.

## Modelo multi-tenant

### Tenant raíz

`barberias` es el tenant raíz (`supabase/migrations/002_barberias.sql`). Toda tabla de
dominio lleva `tenant_id not null references barberias(id)`.

### Roles: `roles_usuario`

`roles_usuario` (`001_extensiones_y_helpers.sql`) mapea `auth.users` a un rol dentro de un
tenant: `(usuario_id, tenant_id, rol)`, con `rol` del enum `rol_app`:
`administrador_plataforma`, `dueno_sede`, `barbero`, `cliente`.

Un mismo `usuario_id` **puede tener varias filas** en `roles_usuario` (una por tenant) —
por ejemplo, `dueno_sede` en la sede A y `cliente` en la sede B. Esto es una decisión de
negocio explícita, no un caso raro: el único constraint es
`unique (usuario_id, tenant_id)`, nunca `unique (usuario_id)` a secas.
`administrador_plataforma` es la excepción: no lleva `tenant_id` (ve las 20 sedes), forzado
por el constraint `roles_usuario_tenant_requerido_salvo_administrador_plataforma`.

### Cómo se resuelve el aislamiento: funciones helper parametrizadas, no un "tenant actual" global

La regla de RLS de Barberus **no** usa `current_setting('app.current_tenant')` ni ninguna
otra forma de "tenant actual" de sesión. En su lugar, cada política RLS llama a una función
`SECURITY DEFINER` pasándole explícitamente el `tenant_id` (o `cliente_id`/`reserva_id`) de
la fila que esa política está evaluando. Las funciones, definidas en
`001_extensiones_y_helpers.sql` (las tres primeras), `005_clientes.sql` y
`006_reservas.sql`:

| Función | Pregunta que responde |
|---|---|
| `es_administrador_plataforma()` | ¿el usuario autenticado es operador de plataforma (ve las 20 sedes)? |
| `es_miembro_del_tenant(p_tenant_id)` | ¿tiene cualquier rol (`dueno_sede`, `barbero` o `cliente`) en ese tenant? |
| `es_personal_del_tenant(p_tenant_id)` | ¿es `dueno_sede` o `barbero` de ese tenant? |
| `es_dueno_del_tenant(p_tenant_id)` | ¿es `dueno_sede` de ese tenant? |
| `es_cliente_del_tenant(p_tenant_id)` | ¿tiene una fila en `roles_usuario` con `rol='cliente'` en ese tenant? |
| `es_dueno_del_cliente(p_cliente_id)` | ¿es el cliente `p_cliente_id` (usuario propio + rol `cliente` vigente)? |
| `es_dueno_de_reserva(p_reserva_id)` | ¿es el dueño (cliente) de la reserva `p_reserva_id`? (compone `es_dueno_del_cliente`) |

Todas resuelven internamente contra `auth.uid()` (que Supabase/PostgREST ya resuelve desde
el JWT en cada request) — nunca contra un valor de sesión que la app tenga que fijar a
mano.

**Por qué no `current_setting`/un tenant global implícito:** un `SET app.current_tenant`
por conexión es frágil con el connection pooler de Supabase/PostgREST (no hay garantía de
qué conexión física atiende cada request). Más importante: una primera versión de este
esquema sí tuvo un patrón equivalente —dos funciones `current_tenant_id()`/
`current_user_role()` que resolvían "el tenant/rol actual" con
`... where usuario_id = auth.uid() limit 1` sin `order by`— y una revisión de seguridad
encontró que era **indeterminado** en cuanto un usuario tiene más de una fila en
`roles_usuario` (el caso legítimo de `dueno_sede` en A + `cliente` en B). Con eso, un
`UPDATE` sobre `clientes` podía reasignar el `tenant_id` de la propia fila del cliente a
cualquier tenant, sin haber sido nunca registrado ahí. Se corrigió eliminando esas dos
funciones y reemplazando el patrón por las funciones parametrizadas de la tabla de arriba,
que reciben el `tenant_id`/`cliente_id`/`reserva_id` de la fila evaluada como parámetro
explícito. El detalle completo de este hallazgo y su corrección está en
`scripts/migrations/APPLIED.md`, sección "Corrección post-auditoría".

Como regla general las políticas siguen este patrón (staff ve todo su tenant, cliente ve
solo lo propio):

```sql
create policy reservas_select on public.reservas
  for select
  using (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_del_cliente(cliente_id)
  );
```

### Defensa en profundidad: FKs compuestas

Además de RLS, las tablas que referencian `clientes`, `barberos`, `servicios`,
`reservas` o `niveles_membresia` lo hacen con **FK compuesta `(id, tenant_id)`** (habilitada
por un `unique (id, tenant_id)` en la tabla referenciada). Esto hace que, a nivel de motor
de base de datos, sea imposible que por ejemplo una reserva tenga un `cliente_id` de un
tenant y un `tenant_id` de otro — ni siquiera si un bug futuro se saltara RLS. También es
lo que permite simplificar policies como `es_dueno_del_cliente(cliente_id)` sin repetir el
chequeo de `tenant_id`: si no coincidieran, el INSERT ya habría fallado por la FK antes de
llegar a evaluarse la policy.

## Las 13 tablas

Todas con RLS habilitado. Migración de origen entre paréntesis.

**Identidad y catálogo**
- `roles_usuario` (`001`) — mapa `usuario_id` → `(tenant_id, rol)`. Base de todo el RLS.
- `barberias` (`002`) — tenant raíz: nombre, `slug` único, zona horaria, contacto.
- `barberos` (`003`) — 1:1 con una sede (`tenant_id` normal, sin tabla de rotación —
  decisión de negocio ya cerrada). `usuario_id` nullable (puede no tener login todavía).
- `servicios` (`004`) — catálogo por sede: nombre, `duracion_minutos`. Sin precio/billing
  (fuera de alcance).

**Clientes**
- `clientes` (`005`) — perfil **aislado por sede**: un mismo humano que visita 2 sedes
  tiene 2 filas independientes, sin FK entre ellas. `usuario_id` nullable (walk-ins sin
  cuenta). Único por `(tenant_id, usuario_id)`, nunca por `usuario_id` global.
- `notas_cliente` (`005`) — notas internas del barbero sobre un cliente; nunca visibles
  para el propio cliente (solo policies de `es_personal_del_tenant`).

**Reservas**
- `reservas` (`006`) — agenda: `cliente_id`, `barbero_id`, `estado`
  (`pendiente`→`confirmada`→`en_progreso`→`completada`, o `cancelada`/`no_asistio` según
  máquina de estados en trigger), `inicio_programado`/`fin_programado`. No-doble-booking de
  un barbero garantizado por un `exclude using gist` (constraint de exclusión), no un
  trigger — atómico bajo concurrencia real, `deferrable initially deferred` porque
  `fin_programado` se recalcula al insertar los servicios de la reserva en la misma
  transacción.
- `reserva_servicios` (`006`) — combinación de servicios de una reserva; guarda
  `duracion_minutos_snapshot` (copia de `servicios.duracion_minutos` al momento de
  agendar, para que cambios futuros del catálogo no alteren reservas ya creadas). Un
  trigger recalcula `reservas.fin_programado` = `inicio_programado` + suma de duraciones
  cada vez que cambia la combinación.

**Fila en vivo**
- `turnos_fila` (`007`) — check-in físico en sede, con o sin reserva previa
  (`reserva_id` nullable). `estado`: `esperando`→`llamado`→`en_servicio`→`completado`, o
  `cancelado`/`no_asistio`. Un barbero solo puede tener un turno `en_servicio` a la vez
  (unique index parcial). `numero_turno` se asigna de forma atómica por trigger.
- `contadores_fila_diarios` (`007`) — contador `(tenant_id, fecha_fila) → último número`,
  usado internamente por el trigger de numeración; no se toca directamente desde la app.

**Membresías (solo tracking, sin cobro)**
- `niveles_membresia` (`008`) — catálogo de niveles por sede: `visitas_minimas`,
  `dias_ventana` (nullable; hoy no usado — ver nota abajo), `beneficios` (jsonb).
- `membresias_cliente` (`008`) — una fila viva por cliente: `nivel_actual_id`,
  `visitas_totales`, `estado` (`activa`/`vencida`/`cancelada`), fechas administrativas de
  periodo (`inicio_periodo_actual`/`fin_periodo_actual`, escritas a mano por `dueno_sede`
  al renovar; no hay billing).
- `historial_nivel_membresia_cliente` (`008`) — auditoría de cada cambio de nivel, generada
  por el trigger de recálculo.

Un trigger (`recalcular_membresia_cliente`) sube de nivel al cliente cada vez que una
reserva pasa a `completada`, usando el **conteo histórico total** de visitas como
simplificación de MVP — no la ventana `dias_ventana` que ya está modelada en
`niveles_membresia` mismo. No usar `dias_ventana` como fuente de verdad de "visitas en los
últimos N días" todavía; está reservado para cuando se implemente un recálculo periódico
por ventana.

## Flujo de una reserva

**Base de datos (implementado, verificado):**

1. `INSERT` en `reservas` con `cliente_id`, `barbero_id`, `inicio_programado` y un
   `fin_programado` tentativo (el `check` `fin_programado > inicio_programado` no es
   diferible; hace falta un valor válido inicial, p.ej. `inicio + 1 minuto`).
2. `INSERT` en `reserva_servicios` por cada servicio elegido, en la misma transacción. Un
   trigger fija `duracion_minutos_snapshot` desde `servicios.duracion_minutos` si no viene
   explícito, y otro recalcula `reservas.fin_programado` sumando esas duraciones.
3. Al hacer `COMMIT`, el exclusion constraint `reservas_sin_doble_reserva` valida (recién
   ahí, por ser `deferred`) que el barbero no tenga otra reserva activa con rango
   solapado; si lo hay, la transacción falla completa.
4. Cambios de `estado` pasan por el trigger `validar_transicion_estado_reserva`: valida la
   transición contra la máquina de estados y, si quien actualiza no es staff del tenant de
   esa reserva (`es_personal_del_tenant`), solo permite `cancelada` (un cliente nunca puede
   marcarse a sí mismo `completada` o `no_asistio`).
5. Cuando una reserva pasa a `completada`, un trigger recalcula la membresía del cliente
   (`recalcular_membresia_cliente`): incrementa `visitas_totales` y evalúa si sube de
   nivel.

**Frontend → API → tiempo real (planeado, no implementado):** según la configuración de
los agentes de este repo, la reserva se crearía desde un formulario Next.js
(`react-hook-form` + `zod`), un endpoint FastAPI validaría y ejecutaría la transacción de
arriba, y la fila en vivo (`turnos_fila`) se sincronizaría entre barbero y cliente vía
Supabase Realtime. Ninguna de estas tres capas tiene código todavía — no hay `api/` ni
`frontend/` en el repo — así que este párrafo describe el plan, no el comportamiento
actual.

## Decisiones de negocio ya cerradas

- **Cliente aislado por sede, sin identidad global.** Un mismo `usuario_id` puede tener
  perfil de cliente en varias sedes, pero son filas independientes en `clientes` sin FK
  entre ellas; `correo`/`telefono` no son únicos globalmente, solo (implícitamente) dentro
  del tenant. Ver `005_clientes.sql`.
- **Membresía solo tracking, sin cobro.** `niveles_membresia`/`membresias_cliente` no
  tienen columnas de precio ni ciclo de facturación; la renovación es manual y ocurre fuera
  del sistema (`fin_periodo_actual` es una fecha que el `dueno_sede` escribe a mano). Pagos
  quedan fuera de alcance por ahora. Ver `008_membresias.sql`.
- **Barbero pertenece a una sola sede.** Modelado como columna `tenant_id` normal en
  `barberos` (no una tabla N:N de rotación entre sedes) — decisión de negocio ya cerrada,
  no una limitación técnica temporal. Ver `003_barberos.sql`.
- **Fuera de alcance explícito en este esquema:** pagos/facturación, guías visuales de
  resultado (referencias de cortes), notificaciones WhatsApp/SMS.

## Convención de idioma

Todo nombre de tabla, columna, tipo, enum o valor de estado que representa un concepto del
negocio va en **español, sin tildes ni "ñ"** (`dueno_sede`, no `dueño_sede` — evita
problemas de identificadores entre comillas y de locale en Postgres). Esto incluye los
valores de estado (`pendiente`, `confirmada`, `esperando`, `en_servicio`, etc.) y las
funciones helper de RLS listadas arriba, porque cada una encapsula una decisión de negocio
que nombra roles/entidades del dominio explícitamente.

Se mantiene en inglés solo la mecánica técnica genérica y universal, reutilizada igual sin
importar el idioma del dominio: `id`, `created_at`, `updated_at`, `tenant_id` (convención
ya fijada también en las reglas de otros agentes de este repo), los tipos de dato de
Postgres, el trigger genérico `set_updated_at()`, y los sufijos de política RLS
(`_select`/`_insert`/`_update`/`_delete`/`_all`).

Un caso de nomenclatura que parece inconsistente pero es intencional: el estado terminal de
cancelación es `cancelada` en `reservas` pero `cancelado` en `turnos_fila` (y
`completada`/`completado` igual) — es concordancia de género con el sustantivo de cada
tabla ("una reserva cancelada" / "un turno cancelado"), no un error.

Nombres de archivo de migración usan numeración secuencial de 3 dígitos
(`001_descripcion.sql`, orden de ejecución = orden numérico) en vez de timestamp, para
evitar ambigüedad de zona horaria en el nombre del archivo.

## Referencias

- `scripts/migrations/APPLIED.md` — registro de cada migración aplicada/diseñada, estado y
  rollback, más el detalle completo del hallazgo de seguridad corregido en el esquema
  multi-tenant.
- `supabase/migrations/001_extensiones_y_helpers.sql` a `008_membresias.sql` — código
  fuente de todo lo descrito en este documento.
