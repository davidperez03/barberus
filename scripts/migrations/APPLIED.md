

# Migraciones aplicadas

Registro de migraciones del esquema de Barberus (Supabase/PostgreSQL). Los archivos SQL
viven en `supabase/migrations/` con numeración secuencial de 3 dígitos (`NNN_descripcion.sql`,
orden de ejecución = orden numérico), en vez de timestamp, para evitar ambigüedad de zona
horaria en el nombre del archivo.

Coordinar con `git-flow` el commit de cada migración (scope `(tenant)` si toca RLS).

Convención de idioma: nombres de tabla/columna/estado del dominio del negocio están en
español, incluidos los valores del enum de rol (`administrador_plataforma`, `dueno_sede`,
`barbero`, `cliente` — catálogo definido en `auth-users.md`). `id`, `created_at`,
`updated_at`, `tenant_id`, los tipos de Postgres y la función `set_updated_at()` (trigger
genérico sin lógica de negocio) se mantienen en inglés por ser mecánica técnica genérica.
Todas las funciones helper de RLS (`es_administrador_plataforma`, `es_miembro_del_tenant`,
`es_personal_del_tenant`, `es_dueno_del_tenant`, `es_cliente_del_tenant`,
`es_dueno_del_cliente`, `es_dueno_de_reserva`) van en español porque cada una encapsula una
decisión de negocio que nombra roles/entidades del dominio explícitamente — ver nota al pie
de `001_extensiones_y_helpers.sql` para el detalle de ese criterio. Identificadores en
español se escriben sin tildes ni "ñ" (`dueno_sede`, no `dueño_sede`).

| Migración | Estado | Descripción | Rollback |
|---|---|---|---|
| `001_extensiones_y_helpers.sql` | Diseñada, no aplicada aún a ningún entorno | Extensiones (`pgcrypto`, `btree_gist`), enum `rol_app` (`administrador_plataforma`, `dueno_sede`, `barbero`, `cliente`), tabla `roles_usuario`, funciones helper de RLS parametrizadas por tenant (`es_administrador_plataforma`, `es_miembro_del_tenant`, `es_personal_del_tenant`, `es_dueno_del_tenant`, `es_cliente_del_tenant`), función genérica `set_updated_at()`. | `drop function set_updated_at, es_cliente_del_tenant, es_dueno_del_tenant, es_personal_del_tenant, es_miembro_del_tenant, es_administrador_plataforma; drop table roles_usuario; drop type rol_app;` (requiere haber revertido antes las migraciones que dependen de `roles_usuario`). |
| `002_barberias.sql` | Diseñada, no aplicada aún | Tabla `barberias` (tenant raíz) + RLS + cierre de FK diferida `roles_usuario.tenant_id`. | `alter table roles_usuario drop constraint roles_usuario_tenant_id_fkey; drop table barberias cascade;` |
| `003_barberos.sql` | Diseñada, no aplicada aún | Tabla `barberos` (1:1 con barberias vía `tenant_id`, sin tabla de rotación) + RLS. | `drop table barberos cascade;` |
| `004_servicios.sql` | Diseñada, no aplicada aún | Catálogo `servicios` con `duracion_minutos` (sin precio/billing, fuera de alcance) + RLS. | `drop table servicios cascade;` |
| `005_clientes.sql` | Diseñada, no aplicada aún | `clientes` (aislado por sede, sin identidad global cruzada; un mismo `usuario_id` PUEDE tener perfil en varios tenants) + `notas_cliente` (notas internas del barbero, no visibles al cliente) + función helper `es_dueno_del_cliente` + RLS. | `drop function es_dueno_del_cliente; drop table notas_cliente cascade; drop table clientes cascade;` |
| `006_reservas.sql` | Diseñada, no aplicada aún | `reservas` + `reserva_servicios` (duración dinámica por combinación de servicios), exclusion constraint `gist` para no-doble-booking de barbero, trigger de recálculo de `fin_programado`, trigger de máquina de estados de la reserva, función helper `es_dueno_de_reserva` + RLS. | `drop function es_dueno_de_reserva, recalcular_fin_reserva, fijar_snapshot_duracion_reserva_servicio, validar_transicion_estado_reserva; drop table reserva_servicios cascade; drop table reservas cascade;` |
| `007_turnos_fila.sql` | Diseñada, no aplicada aún | `turnos_fila` + `contadores_fila_diarios` (fila en vivo), unique index parcial (1 turno `en_servicio` por barbero), trigger de número de turno atómico, trigger de máquina de estados de la fila + RLS. | `drop table turnos_fila cascade; drop table contadores_fila_diarios cascade; drop function asignar_numero_turno_fila, validar_transicion_estado_turno;` |
| `008_membresias.sql` | Diseñada, no aplicada aún | `niveles_membresia` + `membresias_cliente` + `historial_nivel_membresia_cliente` (tracking de nivel/beneficios, SIN billing/cobro), trigger de recálculo de nivel al completar reserva + RLS. | `drop table historial_nivel_membresia_cliente cascade; drop table membresias_cliente cascade; drop table niveles_membresia cascade; drop function recalcular_membresia_cliente;` |

## Cómo aplicar

```bash
supabase db push          # aplica migraciones pendientes a Supabase remoto
# o, en local con Supabase CLI:
supabase migration up
```

El agente `database` es quien ejecuta esto en staging/producción, no `architect`. Antes de
correr en producción: backup manual explícito (regla dura de `database.md`).

## Corrección post-auditoría (multi-tenant-guard + dry-guard, 2026-08-14)

Los revisores encontraron 2 hallazgos bloqueantes con la misma causa raíz, uno de caso
borde, y duplicidad alta de patrones RLS. Los 8 archivos de migración se reescribieron
(mismos nombres, mismo orden) para corregirlo — no quedó ninguna versión previa en el repo.

1. **Bloqueante — `clientes_select`/`clientes_update` con rama `usuario_id = auth.uid()`
   sin validar tenant.** Corregido: la rama de autoservicio del cliente ahora es
   `usuario_id = auth.uid() and es_cliente_del_tenant(tenant_id)`, que valida contra
   `roles_usuario` (fuente de verdad) en vez de confiar en el valor crudo de la columna.
   Sin esto, un `UPDATE` podía reasignar `tenant_id` de la propia fila a cualquier tenant,
   sin haber sido nunca registrado ahí como cliente.
2. **Bloqueante — índice único global `idx_clientes_usuario_id` contradecía "cliente
   aislado por sede".** Eliminado. Queda solo `idx_clientes_tenant_usuario_unico
   (tenant_id, usuario_id)`, único por tenant, no global — permite que un mismo
   `usuario_id` tenga perfil de cliente en varias sedes, que es la decisión de negocio.
   Este cambio es lo que hacía explotable el punto 1 si no se corregían juntos (por eso se
   atendieron en el mismo commit).
3. **Caso borde — `current_tenant_id()`/`current_user_role()` indeterministas.**
   `... where usuario_id = auth.uid() limit 1` sin `order by` es ambiguo en cuanto un
   usuario tiene roles en más de un tenant (p.ej. `dueno_sede` en A y `cliente` en B, que el
   punto 2 ahora permite explícitamente). Ambas funciones se **eliminaron** — no quedó
   ningún uso legítimo tras el refactor del punto 4 (ver abajo), y dejarlas como utilidad de
   app solo habría trasladado el mismo bug a otra capa. El mismo patrón ambiguo también
   afectaba los triggers `validar_transicion_estado_reserva`/`validar_transicion_estado_turno`
   (usaban `current_user_role() = 'cliente'` para decidir si restringir la transición a solo
   cancelar) — se corrigieron para usar `es_personal_del_tenant(new.tenant_id)`, parametrizado
   por el tenant de la fila que se está actualizando.
4. **Duplicidad alta — patrón de autorización copiado 46 veces.** Se reemplazaron los dos
   patrones (`es_administrador_plataforma() or (tenant_id = current_tenant_id() and
   es_personal_sede())`, 29 veces; y la variante con `current_user_role() = 'dueno_sede'`,
   17 veces) por funciones parametrizadas por el `tenant_id`/`cliente_id`/`reserva_id` de la
   fila que evalúa cada policy, nunca por un "tenant actual" global:
   - `es_miembro_del_tenant(p_tenant_id)` — cualquier rol en ese tenant (para catálogos que
     también ve 'cliente': servicios, barberos, niveles_membresia, la propia barbería).
   - `es_personal_del_tenant(p_tenant_id)` — `dueno_sede`/`barbero` de ese tenant.
   - `es_dueno_del_tenant(p_tenant_id)` — `dueno_sede` de ese tenant (o admin).
   - `es_cliente_del_tenant(p_tenant_id)` — rol `cliente` vigente en ese tenant (nueva,
     necesaria para cerrar los puntos 1/2).
   - `es_dueno_del_cliente(p_cliente_id)` (definida en `005_clientes.sql`, depende de la
     tabla `clientes`) y `es_dueno_de_reserva(p_reserva_id)` (definida en `006_reservas.sql`,
     depende de `reservas` y compone `es_dueno_del_cliente`) — "¿el usuario autenticado es
     el dueño de esta fila específica?", usadas en `reservas`, `turnos_fila`,
     `membresias_cliente` y `historial_nivel_membresia_cliente`. Se usan dos funciones en
     vez de una sola genérica (como sugería la propuesta inicial) porque las formas de join
     son distintas: `turnos_fila`/`membresias_cliente` tienen `cliente_id` directo,
     mientras que `reserva_servicios` solo tiene `reserva_id` y necesita pasar por la
     reserva para llegar al cliente.
   - `current_tenant_id()`/`current_user_role()`: eliminadas (ver punto 3). Todas las
     funciones nuevas SÍ incluyen `es_administrador_plataforma()` internamente (salvo
     `es_dueno_del_cliente`/`es_dueno_de_reserva`, que se combinan con
     `es_personal_del_tenant()` a nivel de policy, que ya cubre admin), así que la mayoría
     de las policies quedaron en una sola línea por rama en vez de dos.
5. **Menor — nomenclatura `cancelada` (reservas) vs `cancelado` (turnos_fila).** Es
   concordancia de género intencional con el sustantivo de cada tabla ("una reserva
   cancelada" / "un turno cancelado"), mismo criterio en `completada`/`completado`. No se
   unificó porque cambiar el género rompería la lectura natural en español; queda
   documentado en el propio `007_turnos_fila.sql`. No se extrajo el guard "cliente solo
   cancela" a una función compartida entre los dos triggers de transición de estado: además
   del guard, ambas funciones difieren en el grafo de transiciones completo (estados y
   literales distintos), así que una función compartida solo ahorraría ~2 líneas a cambio de
   una indirección extra — no se justificó el trade-off.

Validado: las 8 migraciones se corrieron desde cero contra Postgres real (Docker) tras el
refactor, más los 7 escenarios funcionales previos y uno nuevo (mismo `usuario_id` con
perfil de `cliente` en dos tenants distintos: ve solo sus 2 filas propias, puede editar la
suya, y un intento de mover `tenant_id` de su propio perfil a un tenant sin registro en
`roles_usuario` es rechazado por RLS).

## Notas de diseño que no caben en el nombre del archivo

- Mecanismo de tenant en RLS: `auth.uid()` + tabla `roles_usuario`, NO
  `current_setting('app.current_tenant')`. Se eligió así porque Supabase resuelve
  `auth.uid()` automáticamente desde el JWT en cada request vía PostgREST/pooler; exigir un
  `SET app.current_tenant` por conexión es frágil con connection pooling.
- FKs compuestas `(id, tenant_id)` en `clientes`, `barberos`, `servicios`, `reservas`,
  `niveles_membresia` para que las tablas que referencian esas entidades (reservas,
  reserva_servicios, turnos_fila, membresias_cliente) NUNCA puedan apuntar a una fila de
  otro tenant, ni siquiera si un bug se saltara RLS. Es defensa en profundidad, no
  reemplaza RLS.
- No-doble-booking de barbero: `EXCLUDE USING gist (...) DEFERRABLE INITIALLY DEFERRED`,
  no un trigger — es atómico bajo concurrencia real. El `DEFERRABLE` es necesario porque
  `fin_programado` se calcula recién cuando se insertan los `reserva_servicios` en la misma
  transacción.
- Membresía: el trigger de recálculo de nivel usa conteo de visitas HISTÓRICO total como
  simplificación de MVP, no la ventana `dias_ventana` que ya está modelada en
  `niveles_membresia`. Documentado en el propio archivo de migración.
- Idioma: nombres de tabla/columna/estado del dominio del negocio en español (`barberias`,
  `barberos`, `servicios`, `clientes`, `notas_cliente`, `reservas`, `reserva_servicios`,
  `turnos_fila`, `contadores_fila_diarios`, `niveles_membresia`, `membresias_cliente`,
  `historial_nivel_membresia_cliente`, y los valores de estado como `pendiente`,
  `confirmada`, `en_progreso`, `completada`, `cancelada`, `no_asistio`, `esperando`,
  `llamado`, `en_servicio`, `completado`, `activa`, `vencida`, y el enum de rol
  `administrador_plataforma`/`dueno_sede`/`barbero`/`cliente` — catálogo canónico de
  `auth-users.md`, actualizado el 2026-08-14 de `platform_admin`/`tenant_owner` a estos
  nombres en español; este esquema se realineó en el mismo día). Se mantienen en inglés:
  `id`, `created_at`, `updated_at`, `tenant_id` (convención literal ya fijada en las reglas
  de `architect.md`, `multi-tenant-guard.md` y `database.md` — renombrarla rompería sus
  checklists) y el trigger genérico `set_updated_at` (mecánica técnica pura). TODAS las
  funciones helper de RLS quedaron en español
  (`es_administrador_plataforma`/`es_miembro_del_tenant`/`es_personal_del_tenant`/
  `es_dueno_del_tenant`/`es_cliente_del_tenant`/`es_dueno_del_cliente`/
  `es_dueno_de_reserva`) porque, a diferencia de un accessor genérico, cada una encapsula
  una decisión de negocio que nombra roles/entidades del dominio explícitamente — ver la
  sección "Corrección post-auditoría" arriba para el detalle de por qué
  `current_tenant_id()`/`current_user_role()` (que sí eran accessors genéricos) se
  eliminaron en vez de mantenerse. El criterio completo queda documentado en el encabezado
  de `001_extensiones_y_helpers.sql`. Los sufijos de política RLS
  (`_select`/`_insert`/`_update`/`_delete`/`_all`) también se dejan como palabras clave SQL,
  no se traducen.
- Fuera de alcance explícito en este esquema: pagos/facturación, guías visuales de
  resultado (referencias de cortes), notificaciones WhatsApp/SMS.
