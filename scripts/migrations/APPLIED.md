

# Migraciones aplicadas

Registro de migraciones del esquema de Barberus (Supabase/PostgreSQL). Los archivos SQL
viven en `supabase/migrations/` con numeración secuencial de 3 dígitos (`NNN_descripcion.sql`,
orden de ejecución = orden numérico), en vez de timestamp, para evitar ambigüedad de zona
horaria en el nombre del archivo.

Coordinar con `git-flow` el commit de cada migración (scope `(tenant)` si toca RLS).

Convención de idioma: nombres de tabla/columna/estado del dominio del negocio están en
español, incluidos los valores del enum de rol (`administrador_plataforma`, `dueno_sede`,
`profesional`, `cliente` — catálogo definido en `auth-users.md`). Nomenclatura `negocios`/
`profesionales` (no `barberías`/`barberos`): la plataforma es intermediaria entre negocios
independientes de distintos verticales (barbería, salón de uñas, etc.), no dueña de sucursales
propias — ver `002_negocios.sql`. `id`, `created_at`,
`updated_at`, `tenant_id`, los tipos de Postgres y la función `set_updated_at()` (trigger
genérico sin lógica de negocio) se mantienen en inglés por ser mecánica técnica genérica.
Todas las funciones helper de RLS (`es_administrador_plataforma`, `es_miembro_del_tenant`,
`es_personal_del_tenant`, `es_dueno_del_tenant`, `es_cliente_del_tenant`,
`es_dueno_del_cliente`, `es_dueno_de_reserva`, y desde `010_identidad_extendida.sql`
`es_personal_de_algun_tenant_del_usuario`/`es_dueno_de_algun_tenant_del_usuario`/
`es_propio_o_dueno_del_tenant_opcional`/`es_dueno_del_factor`) van en
español porque cada una encapsula una decisión de negocio que nombra roles/entidades del
dominio explícitamente — ver nota al pie de `001_extensiones_y_helpers.sql` para el detalle
de ese criterio. Identificadores en español se escriben sin tildes ni "ñ" (`dueno_sede`, no
`dueño_sede`).

| Migración | Estado | Descripción | Rollback |
|---|---|---|---|
| `001_extensiones_y_helpers.sql` | Aplicada (Supabase real) | Extensiones (`pgcrypto`, `btree_gist`), enum `rol_app` (`administrador_plataforma`, `dueno_sede`, `profesional`, `cliente`), tabla `roles_usuario`, funciones helper de RLS parametrizadas por tenant (`es_administrador_plataforma`, `es_miembro_del_tenant`, `es_personal_del_tenant`, `es_dueno_del_tenant`, `es_cliente_del_tenant`), función genérica `set_updated_at()`. | `drop function set_updated_at, es_cliente_del_tenant, es_dueno_del_tenant, es_personal_del_tenant, es_miembro_del_tenant, es_administrador_plataforma; drop table roles_usuario; drop type rol_app;` (requiere haber revertido antes las migraciones que dependen de `roles_usuario`). |
| `002_negocios.sql` | Aplicada (Supabase real) | Tabla `negocios` (tenant raíz) + RLS + cierre de FK diferida `roles_usuario.tenant_id`. | `alter table roles_usuario drop constraint roles_usuario_tenant_id_fkey; drop table negocios cascade;` |
| `003_profesionales.sql` | Aplicada (Supabase real) | Tabla `profesionales` (1:1 con negocios vía `tenant_id`, sin tabla de rotación) + RLS. | `drop table profesionales cascade;` |
| `004_servicios.sql` | Aplicada (Supabase real) | Catálogo `servicios` con `duracion_minutos` (sin precio/billing, fuera de alcance) + RLS. | `drop table servicios cascade;` |
| `005_clientes.sql` | Aplicada (Supabase real) | `clientes` (aislado por sede, sin identidad global cruzada; un mismo `usuario_id` PUEDE tener perfil en varios tenants) + `notas_cliente` (notas internas del profesional, no visibles al cliente) + función helper `es_dueno_del_cliente` + RLS. | `drop function es_dueno_del_cliente; drop table notas_cliente cascade; drop table clientes cascade;` |
| `006_reservas.sql` | Aplicada (Supabase real) | `reservas` + `reserva_servicios` (duración dinámica por combinación de servicios), exclusion constraint `gist` para no-doble-booking de profesional, trigger de recálculo de `fin_programado`, trigger de máquina de estados de la reserva, función helper `es_dueno_de_reserva` + RLS. | `drop function es_dueno_de_reserva, recalcular_fin_reserva, fijar_snapshot_duracion_reserva_servicio, validar_transicion_estado_reserva; drop table reserva_servicios cascade; drop table reservas cascade;` |
| `007_turnos_fila.sql` | Aplicada (Supabase real) | `turnos_fila` + `contadores_fila_diarios` (fila en vivo), unique index parcial (1 turno `en_servicio` por profesional), trigger de número de turno atómico, trigger de máquina de estados de la fila + RLS. | `drop table turnos_fila cascade; drop table contadores_fila_diarios cascade; drop function asignar_numero_turno_fila, validar_transicion_estado_turno;` |
| `008_membresias.sql` | Aplicada (Supabase real) | `niveles_membresia` + `membresias_cliente` + `historial_nivel_membresia_cliente` (tracking de nivel/beneficios, SIN billing/cobro), trigger de recálculo de nivel al completar reserva + RLS. | `drop table historial_nivel_membresia_cliente cascade; drop table membresias_cliente cascade; drop table niveles_membresia cascade; drop function recalcular_membresia_cliente;` |
| `009_identidad_autenticacion.sql` | Aplicada (Supabase real) | Cierra la deuda dejada en `001`: políticas `roles_usuario_insert`/`roles_usuario_delete` (autoasignación de `cliente`, alta de `profesional` por `dueno_sede`, alta de `dueno_sede`/`administrador_plataforma` solo por `administrador_plataforma`; sin política de `UPDATE` a propósito). Agrega trigger `exigir_reautenticacion_clientes` (bloquea cambiar `correo`/`telefono` propio con un JWT de más de 10 minutos). | `drop trigger trg_clientes_exigir_reautenticacion on clientes; drop function exigir_reautenticacion_clientes; drop index idx_clientes_usuario_id_cualquier_tenant; drop policy roles_usuario_delete on roles_usuario; drop policy roles_usuario_insert on roles_usuario;` |
| `010_identidad_extendida.sql` | Aplicada (Supabase real) | Replica en español, adaptado al negocio y sin SSO/SAML, la riqueza de `auth.*` de Supabase: `perfiles_usuario` (1:1 con `auth.users`, sincronizado por trigger, con whitelist REAL de columnas por diferencia de fila completa — `eliminado_at`/`bloqueado_hasta` exclusivos de `administrador_plataforma`, `bloqueado_hasta` es global a todos los negocios de la plataforma, el bloqueo por sede usa `clientes.activo`/`profesionales.activo` existentes), `identidades_usuario`, `sesiones` (con `nivel_autenticacion` tipo aal, `INSERT` valida pertenencia real al `tenant_id` declarado), `factores_autenticacion` + `retos_autenticacion` (MFA-ready, sin lógica de verificación), `tokens_autenticacion` (patrón genérico de token de un solo uso, sin política RLS — solo `service_role`), `auditoria_autenticacion`. Funciones nuevas: `es_personal_de_algun_tenant_del_usuario`, `es_dueno_de_algun_tenant_del_usuario`, `es_propio_o_dueno_del_tenant_opcional`, `es_dueno_del_factor`, `crear_perfil_usuario`, `sincronizar_perfil_usuario` (marca `barberus.contexto='sync_interno'` para no chocar con el trigger de columnas), `restringir_columnas_perfil_usuario`. Ver "Hallazgos al probar 009/010", "Corrección por revisión de guardianes" y "Segunda re-verificación" abajo. | `drop trigger trg_perfiles_usuario_restringir_columnas on perfiles_usuario; drop trigger trg_sincronizar_perfil_usuario on auth.users; drop trigger trg_crear_perfil_usuario on auth.users; drop function restringir_columnas_perfil_usuario, sincronizar_perfil_usuario, crear_perfil_usuario; drop table auditoria_autenticacion, tokens_autenticacion, retos_autenticacion, factores_autenticacion cascade; drop function es_dueno_del_factor; drop table sesiones, identidades_usuario cascade; drop table perfiles_usuario cascade; drop function es_propio_o_dueno_del_tenant_opcional, es_dueno_de_algun_tenant_del_usuario, es_personal_de_algun_tenant_del_usuario;` |
| `011_fila_publica_agregada.sql` | Diseñada y validada contra Postgres real (ver nota abajo), no aplicada aún a Supabase | Primer caso de lectura pública **cross-tenant** del esquema: tabla derivada `resumen_fila_publico` (una fila por negocio, solo `nombre_sede`/`slug_sede`/`activo`/`latitud`/`longitud`/`personas_en_fila`/`tiempo_espera_estimado_minutos`, CERO datos de `clientes`/`profesionales` individuales) mantenida por trigger desde `turnos_fila` y `negocios` (`sincronizar_resumen_fila_publico`, `sincronizar_resumen_fila_publico_desde_negocio`, ambas `SECURITY DEFINER`). `tiempo_espera_estimado_minutos` usa duración promedio real de servicio de las últimas 24h (`calcular_tiempo_espera_estimado_minutos`) y es `NULL` explícito si no hay historial reciente — nunca un valor inventado. También agrega `latitud numeric(9,6)`/`longitud numeric(9,6)` a `negocios` (requisito nuevo: mostrar los negocios en un mapa Leaflet/react-leaflet con marcadores tipo semáforo según ocupación) — nullable, con `check` de rango físico y de consistencia mutua (`negocios_latitud_longitud_consistentes`: no puede haber una sin la otra); se descartó PostGIS por sobre-ingeniería para el caso de uso (puntos simples en Leaflet, no queries geoespaciales). Las coordenadas se desnormalizan también en `resumen_fila_publico` (mismo trigger que ya sincroniza `nombre_sede`/`slug_sede`/`activo`) porque esa tabla es la ÚNICA superficie de lectura pública del esquema — así el frontend del mapa hace un solo query público en vez de necesitar una segunda lectura pública sobre `negocios` (que no la tiene, solo lectura por tenant). Policy `resumen_fila_publico_select_publico` (`for select to anon, authenticated using (activo)`) es la única lectura pública sin JWT de todo el esquema; ninguna policy de escritura para `es_personal_del_tenant`/`es_dueno_del_tenant` (anti-abuso: negocios competidores no pueden inflar/deflactar su propio número), solo `administrador_plataforma` tiene `for all` de corrección manual. | `drop trigger trg_negocios_sincronizar_resumen_publico on negocios; drop trigger trg_turnos_fila_sincronizar_resumen_publico on turnos_fila; drop function sincronizar_resumen_fila_publico_desde_negocio, sincronizar_resumen_fila_publico, calcular_tiempo_espera_estimado_minutos; drop table resumen_fila_publico cascade; alter table negocios drop constraint negocios_latitud_longitud_consistentes, drop constraint negocios_longitud_rango, drop constraint negocios_latitud_rango; alter table negocios drop column longitud, drop column latitud;` |

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
     también ve 'cliente': servicios, profesionales, niveles_membresia, el propio negocio).
   - `es_personal_del_tenant(p_tenant_id)` — `dueno_sede`/`profesional` de ese tenant.
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

## Hallazgos al probar 009/010 (auth-users, 2026-08-14)

`009`/`010` se corrieron desde cero contra Postgres real (Docker, con un esquema `auth`
mínimo simulando `auth.users` + `auth.uid()`/`auth.role()`/`auth.jwt()` leyendo
`request.jwt.claims`, igual que hace PostgREST) y con 18 escenarios funcionales simulando
requests reales (`SET ROLE authenticated` + `SET request.jwt.claims`), no solo que las
migraciones corrieran limpio. Ese proceso encontró y corrigió un hallazgo real antes de
mergear (no fue detectado por inspección, solo probando contra la base):

- **Bloqueante — un `EXISTS` inline contra `roles_usuario` dentro de una policy de OTRA
  tabla queda sujeto a `roles_usuario_select_propio` (`usuario_id = auth.uid()`), que
  restringe a "solo mis propias filas".** Las policies iniciales de `perfiles_usuario`
  (`select`/`update`) y el trigger `impedir_auto_escalada_perfil_usuario` hacían
  `exists (select 1 from roles_usuario ru where ru.usuario_id = perfiles_usuario.usuario_id
  and es_dueno_del_tenant(ru.tenant_id))` para resolver "¿el que pide es dueno_sede de
  alguna sede donde ESTE OTRO usuario tiene un rol?". Como esa subquery corre con los
  privilegios de quien hace el request (no es `SECURITY DEFINER`), un `dueno_sede`
  consultando las filas de `roles_usuario` de otro usuario veía CERO filas siempre —
  confirmado con un `UPDATE 0` real al probar "Ana bloquea a su profesional Carlos". No es una
  fuga de datos entre tenants (el fallo es hacia el lado restrictivo, no permisivo) pero
  rompe la función por completo. Corregido con dos funciones nuevas `SECURITY DEFINER`
  (`es_personal_de_algun_tenant_del_usuario`, `es_dueno_de_algun_tenant_del_usuario`),
  mismo patrón que el resto del esquema — documentado con detalle en la sección 0 de
  `010_identidad_extendida.sql`.
- **Bloqueante — combinar ese mismo helper dentro del trigger de columnas reabría
  auto-escalada.** Una vez arreglado el punto anterior, `impedir_auto_escalada_perfil_usuario`
  eximía de la restricción a "quien es dueño de algún tenant donde el USUARIO OBJETIVO tiene
  un rol" — pero dentro de ese trigger el objetivo YA es siempre el propio usuario
  (`new.usuario_id = auth.uid()`), así que un `dueno_sede` editando SU PROPIA fila quedaba
  exento por ser dueño de su propio tenant, y podía auto-desbloquearse
  (`bloqueado_hasta`)/autoverificarse sin pasar por nadie más. Corregido: la única excepción
  para editar campos sensibles de la PROPIA fila es `administrador_plataforma`; staff
  editando una fila AJENA nunca pasa por esta rama (ya lo autoriza la policy de `update` al
  llegar a la fila, no este trigger). Confirmado con un escenario adicional (`dueno_sede`
  intentando tocar `eliminado_at` de su propio perfil, rechazado).

Los 18 escenarios que quedaron verdes tras la corrección: autoasignación de `cliente` en
primera reserva + creación de `clientes` en la misma transacción; bloqueo de autoasignarse
`dueno_sede`; bloqueo de asignar `cliente` a otro usuario sin ser staff de esa sede;
`dueno_sede` contrata `profesional` en su propia sede; bloqueo de contratar en una sede ajena;
bloqueo de cambiar `correo`/`telefono` propio con JWT viejo; permiso de cambiarlo con JWT
reciente; autoservicio de `metadata_usuario` en `perfiles_usuario`; bloqueo de autoescribir
`bloqueado_hasta` propio; `dueno_sede` bloqueando a su profesional (el caso que expuso el primer
hallazgo); `tokens_autenticacion` ilegible desde `authenticated` (0 filas, sin política);
`service_role` sí puede escribir `tokens_autenticacion`; autoservicio de
`factores_autenticacion`; invisibilidad de los factores de un cliente para su `dueno_sede`
(no hay caso de negocio para que el staff los vea); bloqueo de `INSERT` directo en
`auditoria_autenticacion` desde `authenticated`; lectura de los propios eventos de auditoría;
aislamiento de `auditoria_autenticacion` entre sedes (`dueno_sede` de A no ve eventos con
`tenant_id` de B); y el caso de auto-escalada del segundo hallazgo.

## Corrección por revisión de guardianes (multi-tenant-guard + dry-guard + lang-guard, 2026-08-14)

Ciclo de revisión formal sobre `009`/`010` antes del PR. 1 hallazgo bloqueante, 1 caso
borde, 2 duplicidades y 3 anglicismos — los 6 corregidos en la misma rama.

1. **Bloqueante (multi-tenant-guard) — edición sin restricción de columnas en el perfil de
   OTRO usuario.** La cadena: (a) `roles_usuario_insert` permite que staff de una sede
   registre una fila `cliente` para cualquier `usuario_id` (walk-in) sin más validación que
   "soy staff de esa sede"; (b) `perfiles_usuario_select`/`update` usan
   `es_personal_de_algun_tenant_del_usuario`/`es_dueno_de_algun_tenant_del_usuario` — "¿el
   objetivo tiene ALGÚN rol en ALGÚN tenant donde yo soy staff/dueño?", sin importar en qué
   otros negocios tiene actividad ese mismo usuario; (c) el trigger de columnas de la primera
   versión (`impedir_auto_escalada_perfil_usuario`) solo restringía columnas en AUTOedición
   — al editar la fila de OTRO usuario no había ningún límite de columnas. Resultado: un
   `dueno_sede` con una relación real (aunque sea de un walk-in recién registrado) podía
   editar SIN restricción `bloqueado_hasta`/`eliminado_at`/`correo_verificado`/
   `telefono_verificado`/`metadata_app` del perfil GLOBAL de alguien con actividad en otros
   negocios (independientes entre sí, no sub-sedes del mismo tenant) — un escenario
   orgánico (dueño de 2 sedes, o un usuario cliente en una y profesional en otra), no un ataque
   forzado. No estaba cubierto por los 18 escenarios anteriores: probaban que no se podía
   insertar un rol en un tenant ajeno, pero no qué pasaba DESPUÉS de un insert legítimo
   sobre un usuario con roles en otro tenant.

   **Corregido** reescribiendo el trigger de columnas
   (`impedir_auto_escalada_perfil_usuario` → renombrado `restringir_columnas_perfil_usuario`,
   ámbito ampliado) con dos reglas independientes de si la fila es propia o ajena:
   `eliminado_at` (soft-delete de la cuenta completa) SOLO lo puede tocar
   `administrador_plataforma`, nunca un `dueno_sede` aunque comparta sede con el usuario
   objetivo; y una allow-list explícita para edición de una fila AJENA
   (`bloqueado_hasta`/`correo_verificado`/`telefono_verificado`, nunca `metadata_app` ni
   `metadata_usuario`, que es del usuario objetivo, no de quien lo administra).

   **Decisión de producto, dejada por escrito a propósito** (no es un descuido, se evaluó
   explícitamente en este ciclo): la visibilidad de `SELECT` cross-tenant de
   `correo_verificado`/`telefono_verificado`/`ultimo_login_at` (3 campos de estado, no
   `identidades_usuario`/`factores_autenticacion`, que son estrictamente self+admin) para
   cualquier sede con la que el usuario tenga alguna relación **se acepta**, documentado
   directamente en la policy `perfiles_usuario_select` en `010_identidad_extendida.sql`. Se
   evaluó no acotar el `INSERT` de `roles_usuario(cliente)` por staff (walk-in) para exigir
   confirmación del usuario objetivo — se descartó: la base de datos no puede verificar
   "consentimiento" de forma significativa, es un flujo de app (OTP/magic-link al
   registrar), y el fix de columnas de arriba ya cierra el impacto real (staff nunca llega a
   tocar `metadata_app`/`eliminado_at`, sin importar cómo se creó la relación).

2. **Caso borde (multi-tenant-guard) — `sesiones_insert` no validaba pertenencia real al
   `tenant_id` declarado.** Un usuario podía insertar una sesión PROPIA con el `tenant_id`
   de una sede donde no tenía ningún rol, ensuciando la auditoría que vería el dueño
   legítimo de esa sede. Corregido: `with check ((usuario_id = auth.uid() and (tenant_id is
   null or es_miembro_del_tenant(tenant_id))) or auth.role() = 'service_role')`.

3. **Duplicidad (dry-guard) — 2 extracciones.** (a) El booleano `usuario_id = auth.uid() or
   (tenant_id is not null and es_dueno_del_tenant(tenant_id)) or
   es_administrador_plataforma()`, repetido 4 veces (`sesiones_select`, `sesiones_update`
   USING/WITH CHECK, `auditoria_autenticacion_select`), se extrajo a
   `es_propio_o_dueno_del_tenant_opcional(p_usuario_id, p_tenant_id)`. (b) El join inline a
   `factores_autenticacion` en las 3 policies de `retos_autenticacion` se extrajo a
   `es_dueno_del_factor(p_factor_id)`, mismo patrón que `es_dueno_de_reserva` en
   `006_reservas.sql` (definida junto a la tabla de la que depende, no en la sección 0 de
   helpers). (c) Menor: `idx_clientes_usuario_id` (no-único, en `009`) reciclaba el nombre
   de un índice ÚNICO que `005_clientes.sql` eliminó por ser un hallazgo de seguridad —
   renombrado `idx_clientes_usuario_id_cualquier_tenant` con comentario explicando por qué
   este SÍ es correcto siendo no-único.

4. **Idioma (lang-guard) — 3 anglicismos.** `identidades_usuario.proveedor`: `'email'` →
   `'correo'`. `tokens_autenticacion.tipo`: `confirmacion_email`/`cambio_email` →
   `confirmacion_correo`/`cambio_correo`. `auditoria_autenticacion.evento`: `email_cambiado`
   → `correo_cambiado`; y, aunque no se pidió explícito pero es el mismo criterio,
   `password_cambiado`/`password_recuperado`/`recuperacion_password` →
   `contrasena_cambiada`/`contrasena_recuperada`/`recuperacion_contrasena` (ASCII sin ñ —
   "contraseña" es término de negocio/UX, no técnico universal). `nivel_autenticacion` con
   `aal1`/`aal2`/`aal3` se dejó tal cual — terminología estándar NIST/industria, no un
   anglicismo de dominio.

Validado: las 10 migraciones se corrieron de nuevo desde cero contra Postgres real tras
estas correcciones, con los 18 escenarios anteriores (todos siguen en verde) más un
escenario nuevo específico para el hallazgo bloqueante: un usuario (Carlos) con rol real en
2 tenants (`profesional` en A, `cliente` en B) — su `dueno_sede` de A puede verlo y tocar
`bloqueado_hasta` (columna permitida), pero NO `eliminado_at`/`metadata_app`/
`metadata_usuario` (bloqueado, incluida la comprobación de que `administrador_plataforma`
SÍ puede `eliminado_at`); más los escenarios del caso borde de `sesiones_insert`, la
paridad de comportamiento de los dos helpers extraídos, y que los nuevos valores de enum en
español se aceptan.

## Segunda re-verificación de multi-tenant-guard (línea por línea, 2026-08-14): el fix anterior no cerraba del todo

`multi-tenant-guard` re-auditó el fix del punto 1 de la sección anterior sin confiar en el
reporte y encontró 3 problemas reales sobre `restringir_columnas_perfil_usuario`/
`sincronizar_perfil_usuario` (`010_identidad_extendida.sql`) — 2 bloqueantes, 1 regresión
funcional. Los 3 corregidos en la misma rama, antes de una tercera pasada de guardianes.

1. **Bloqueante — el "allow-list" de fila ajena era en realidad un denylist con hueco.** La
   versión anterior solo bloqueaba `metadata_app`/`metadata_usuario` por nombre en la rama de
   edición ajena — no comparaba contra las 3 columnas realmente permitidas. Consecuencia:
   `ultimo_login_at` quedaba editable sin restricción, y cualquier columna nueva que se
   agregara a `perfiles_usuario` en el futuro nacería desprotegida por omisión en vez de
   protegida por default. **Corregido** invirtiendo la lógica a una whitelist real por
   diferencia de fila completa: `(to_jsonb(new) - columnas_permitidas) is distinct from
   (to_jsonb(old) - columnas_permitidas)` — cualquier columna que no esté en la lista
   explícita de permitidas para ese caso (propia: `metadata_usuario`; ajena:
   `correo_verificado`/`telefono_verificado`; ambas + `updated_at` mecánico) queda protegida
   por default, exista hoy o se agregue mañana. Se aplicó tanto a la rama propia como a la
   ajena (la propia tenía el mismo problema de fondo, aunque no fue el hallazgo reportado
   explícitamente — se corrigió igual por consistencia, para no dejar la mitad del mismo bug
   sin cerrar).

2. **Bloqueante nuevo — `bloqueado_hasta` habilitaba sabotaje cross-tenant real entre
   negocios competidores.** Cadena completa: `roles_usuario_insert` (`009`) deja que
   cualquier staff de un tenant inserte `roles_usuario(usuario_id = <cualquier uuid
   existente>, tenant_id = mi_tenant, rol = 'cliente')` sin exigir `usuario_id = auth.uid()`
   ni consentimiento del usuario objetivo. Con eso, `es_dueno_de_algun_tenant_del_usuario`
   (true con CUALQUIER rol compartido, incluido ese `'cliente'` trivial recién creado)
   habilitaba la rama de "fila ajena" del trigger de columnas — y `bloqueado_hasta`, que
   bloquea la cuenta GLOBALMENTE (todos los negocios de la plataforma, no por tenant), estaba
   en el allow-list de esa rama. Resultado: un `dueno_sede` de la sede A podía "atar" como
   cliente suyo al `dueno_sede`/`profesional` de la sede B con solo conocer su
   `usuario_id`/correo, y bloquearlo de operar en TODA la plataforma — sabotaje directo entre
   competidores, no cubierto por la decisión de producto ya aceptada (esa solo hablaba de 3
   campos de LECTURA, no de escritura con efecto global). No estaba cubierto por ningún
   escenario anterior: todos probaban relaciones DENTRO del propio tenant o el caso de un
   usuario multi-tenant (Carlos), pero ninguno simulaba a un `dueno_sede`/`profesional` de
   OTRA sede siendo "atado" como cliente trivial.

   **Decisión de diseño evaluada y tomada** (una de las dos direcciones que propuso el
   guardián, sin prescribir el mecanismo): `bloqueado_hasta` se sumó a la regla que ya tenía
   `eliminado_at` — **SIEMPRE** `administrador_plataforma`, nunca un `dueno_sede` aunque
   comparta sede con el usuario objetivo. El bloqueo POR SEDE que un `dueno_sede` sí debe
   poder aplicar sobre un cliente/profesional problemático de SU sede **ya existía con el
   alcance correcto**: `clientes.activo`/`profesionales.activo` (columnas tenant-scoped,
   `003_profesionales.sql`/`005_clientes.sql`, RLS estándar por `tenant_id` de la fila) — no
   hizo falta una tabla ni columna nueva, solo sacar `bloqueado_hasta` del perfil transversal.
   Se evaluó también la segunda dirección (restringir `roles_usuario_insert` para que staff no
   pueda atar como `cliente` walk-in a un `usuario_id` que ya tiene rol
   `dueno_sede`/`administrador_plataforma`/`profesional` en cualquier tenant) — **se
   descartó** por ahora: con `bloqueado_hasta`/`eliminado_at` ya exclusivos de
   `administrador_plataforma`, el residual de dejar `roles_usuario_insert` sin ese filtro es
   que un `dueno_sede` con una relación trivial puede seguir viendo (decisión ya aceptada) y
   escribir `correo_verificado`/`telefono_verificado` (2 columnas de estado, no
   destructivas, no bloquean operar) de alguien de otra sede — riesgo residual aceptado
   explícitamente, documentado en el comentario de la columna `bloqueado_hasta` en
   `010_identidad_extendida.sql`, revisable si un guardián futuro lo considera insuficiente.

3. **Regresión funcional — el fix del punto 1 de la ronda anterior rompía el soft-delete
   real de cuentas.** `trg_sincronizar_perfil_usuario` (dispara sobre `auth.users` cuando
   Supabase Auth hace soft-delete real vía Admin API) corre sin contexto de JWT
   (`auth.uid()`/`auth.role()` son `null` ahí, no `'service_role'` — es una llamada interna
   del sistema, no una request de PostgREST), así que la protección incondicional de
   `eliminado_at` para no-admin también bloqueaba esta sincronización legítima y rompía la
   transacción cada vez que se soft-eliminaba una cuenta por el flujo estándar. **Corregido**
   sin relajar la condición por rol: `sincronizar_perfil_usuario` (ya `SECURITY DEFINER`)
   ahora hace `perform set_config('barberus.contexto', 'sync_interno', true)` (local a la
   transacción, nunca expuesto a PostgREST/`anon`/`authenticated`) antes del `UPDATE`, y
   `restringir_columnas_perfil_usuario` reconoce esa variable de sesión como primera
   excepción explícita.

Validado: las 10 migraciones se corrieron de nuevo desde cero contra Postgres real tras estas
3 correcciones. Los 30 escenarios anteriores (18 + 12) siguen en verde, más 7 escenarios
nuevos específicos: la cadena de ataque completa con una víctima realista (Beatriz,
`dueno_sede` de la sede B, atada como `cliente` trivial de la sede A por Ana) — se crea la
relación trivial (`roles_usuario_insert` sigue permitiéndolo, es el residual aceptado), Ana
puede verla (decisión aceptada) pero NO bloquearla globalmente ni tocar `ultimo_login_at`
(el hueco del denylist), SÍ puede seguir tocando `telefono_verificado` (residual aceptado),
`administrador_plataforma` sí puede `bloqueado_hasta`; y el soft-delete real simulado con un
`UPDATE auth.users SET deleted_at = now()` sin contexto de JWT ya no rompe la transacción.

## Notas de diseño que no caben en el nombre del archivo

- Mecanismo de tenant en RLS: `auth.uid()` + tabla `roles_usuario`, NO
  `current_setting('app.current_tenant')`. Se eligió así porque Supabase resuelve
  `auth.uid()` automáticamente desde el JWT en cada request vía PostgREST/pooler; exigir un
  `SET app.current_tenant` por conexión es frágil con connection pooling.
- FKs compuestas `(id, tenant_id)` en `clientes`, `profesionales`, `servicios`, `reservas`,
  `niveles_membresia` para que las tablas que referencian esas entidades (reservas,
  reserva_servicios, turnos_fila, membresias_cliente) NUNCA puedan apuntar a una fila de
  otro tenant, ni siquiera si un bug se saltara RLS. Es defensa en profundidad, no
  reemplaza RLS.
- No-doble-booking de profesional: `EXCLUDE USING gist (...) DEFERRABLE INITIALLY DEFERRED`,
  no un trigger — es atómico bajo concurrencia real. El `DEFERRABLE` es necesario porque
  `fin_programado` se calcula recién cuando se insertan los `reserva_servicios` en la misma
  transacción.
- Membresía: el trigger de recálculo de nivel usa conteo de visitas HISTÓRICO total como
  simplificación de MVP, no la ventana `dias_ventana` que ya está modelada en
  `niveles_membresia`. Documentado en el propio archivo de migración.
- Idioma: nombres de tabla/columna/estado del dominio del negocio en español (`negocios`,
  `profesionales`, `servicios`, `clientes`, `notas_cliente`, `reservas`, `reserva_servicios`,
  `turnos_fila`, `contadores_fila_diarios`, `niveles_membresia`, `membresias_cliente`,
  `historial_nivel_membresia_cliente`, y los valores de estado como `pendiente`,
  `confirmada`, `en_progreso`, `completada`, `cancelada`, `no_asistio`, `esperando`,
  `llamado`, `en_servicio`, `completado`, `activa`, `vencida`, y el enum de rol
  `administrador_plataforma`/`dueno_sede`/`profesional`/`cliente` — catálogo canónico de
  `auth-users.md`, actualizado el 2026-08-14 de `platform_admin`/`tenant_owner` a estos
  nombres en español; este esquema se realineó el mismo día). `negocios`/`profesionales`
  (no `barberías`/`barberos`) porque la plataforma es intermediaria entre negocios
  independientes de distintos verticales (barbería, salón de uñas, etc.), no dueña de
  sucursales propias. Se mantienen en inglés:
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

## `011_fila_publica_agregada.sql` — comparador público de fila entre negocios + mapa (2026-08-16)

Requisito de negocio: un visitante sin login debe poder comparar cuánta fila hay en varios
negocios de la plataforma antes de decidir a cuál ir, y ubicarlos en un mapa (Leaflet/
react-leaflet, ya decidido en frontend). Primer caso genuino de lectura pública cross-tenant
de todo el esquema — hasta ahora toda lectura estaba scoped a "soy miembro de este tenant".
Diseño y justificación:

1. **Tabla derivada, no una policy pública sobre `turnos_fila`.** Se creó
   `resumen_fila_publico` con solo columnas de negocio (`nombre_sede`, `slug_sede`, `activo`,
   `latitud`, `longitud`, `personas_en_fila`, `tiempo_espera_estimado_minutos`) — ningún
   `cliente_id`, `profesional_id`, `numero_turno` ni hora individual. Se descartó relajar
   `turnos_fila_select` para `anon` con columnas limitadas por policy: una tabla físicamente
   sin esas columnas es más simple de auditar que una policy que promete "solo estas
   columnas" sobre una tabla que sí las tiene.
2. **Mantenida por trigger, no una vista calculada al vuelo.** El tráfico de lectura es
   público (potencialmente alto y sin control), las escrituras en `turnos_fila` son al ritmo
   humano de check-ins de un negocio (bajo volumen). Trigger `AFTER INSERT/UPDATE/DELETE` en
   `turnos_fila` (`sincronizar_resumen_fila_publico`) recalcula la fila de resumen del tenant
   afectado con un `COUNT`/`AVG` completo (no contadores incrementales — inmune a drift,
   volumen por negocio demasiado bajo para que importe el costo). Un segundo trigger en
   `negocios` (`sincronizar_resumen_fila_publico_desde_negocio`) mantiene `nombre_sede`/
   `slug_sede`/`activo`/`latitud`/`longitud` sincronizados y crea la fila al alta de un
   negocio nuevo. Ambos `SECURITY DEFINER`: quien dispara el cambio real (staff o el propio
   cliente vía `es_dueno_del_cliente`, o `administrador_plataforma` editando `negocios`) no
   tiene ni debe tener permiso de escritura directa sobre `resumen_fila_publico`.
3. **`personas_en_fila` cuenta por `estado` (`esperando`+`llamado`+`en_servicio`), sin
   filtrar por `fecha_fila = current_date`.** Filtrar por el día introduce un caso real: si
   nadie hace check-in justo después de medianoche, el comparador queda "congelado" con el
   conteo de ayer hasta el primer write del nuevo día. Contar por estado a secas es más
   correcto semánticamente ("¿hay fila ahora mismo?") y evita ese caso sin necesitar un job
   programado de reset. Limitación conocida y documentada en el propio archivo de migración:
   no hay horario de atención modelado, así que un turno `esperando` sin cerrar por el staff
   seguiría contando fuera de horario — problema de higiene operativa, no de este mecanismo;
   un reset programado (`pg_cron`) queda fuera de alcance para una migración futura si el
   negocio lo pide.
4. **`tiempo_espera_estimado_minutos`: solo con base real, `NULL` si no la hay.**
   `turnos_fila` ya guarda `hora_inicio`/`hora_completado`, así que la duración promedio real
   de atención de un negocio en las últimas 24h es un dato genuino. La estimación es
   `duracion_promedio_reciente * personas_esperando / profesionales_atendiendo_ahora`
   (`calcular_tiempo_espera_estimado_minutos`, `SECURITY DEFINER`, `STABLE`). Si el negocio no
   tiene ningún turno completado en las últimas 24h, la función retorna `NULL` explícito — se
   evitó a propósito una constante mágica tipo "20 minutos por defecto" sin base en datos
   reales.
5. **Anti-abuso: negocios competidores no pueden tocar su propio resumen.** Deliberadamente
   NO hay policy de escritura para `es_personal_del_tenant` ni `es_dueno_del_tenant` sobre
   `resumen_fila_publico` — si un `dueno_sede` pudiera escribir directo su propia fila,
   podría inflar/deflactar su número para verse mejor que los demás negocios en el
   comparador público, un incentivo real dado que compiten por el mismo cliente. Única
   escritura posible fuera de los triggers: `administrador_plataforma`, vía policy `for all`
   de corrección manual.
6. **Policy pública real:** `resumen_fila_publico_select_publico` — `for select to anon,
   authenticated using (activo)`. Es la ÚNICA policy de todo el esquema sin ningún chequeo de
   `auth.uid()`/`es_miembro_del_tenant`, y a propósito: es el único recurso diseñado para ser
   público. Solo negocios `activo = true` aparecen — un negocio desactivado no debe listarse
   en el comparador ni en el mapa.
7. **Coordenadas para el mapa (`latitud`/`longitud` en `negocios`), decisión nueva no
   contemplada en el diseño original.** `negocios` solo tenía `direccion` como texto libre,
   sin geolocalización estructurada. Se agregaron `latitud numeric(9,6)`/`longitud
   numeric(9,6)`, nullable (un negocio puede no estar geolocalizado todavía), con dos
   `check`: rango físico válido (`latitud between -90 and 90`, `longitud between -180 and
   180`) y consistencia mutua (`negocios_latitud_longitud_consistentes`: `(latitud is null) =
   (longitud is null)` — no puede existir una coordenada a medias). Se descartó PostGIS por
   sobre-ingeniería: el caso de uso es ubicar puntos simples en Leaflet/react-leaflet, no
   hacer queries geoespaciales (radio de búsqueda, polígonos de cobertura, etc.) — si ese
   caso de uso aparece a futuro, es una migración aparte que sí justificaría la extensión.
   Como `negocios` no tiene lectura pública (solo `es_miembro_del_tenant`, scoped a tenant) y
   `resumen_fila_publico` es la única superficie de lectura pública del esquema, se
   desnormalizaron `latitud`/`longitud` también ahí (mismo trigger que ya sincronizaba
   `nombre_sede`/`slug_sede`/`activo`) en vez de abrir una policy pública nueva sobre
   `negocios` — abrir una segunda tabla con lectura pública habría contradicho el punto 1 de
   esta misma lista (una sola superficie pública, auditable). El frontend del mapa hace un
   solo query público.

**Validado localmente contra Postgres real** (Docker `postgres:16-alpine`, con un stub
mínimo de `auth.users` — incluidas las columnas reales que usa `010`
(`email_confirmed_at`/`phone_confirmed_at`/`last_sign_in_at`/`deleted_at`) — y de
`auth.uid()`/`auth.role()`/`auth.jwt()` y de los roles `anon`/`authenticated`/`service_role`,
ya que este entorno no tiene Supabase CLI/Docker Compose disponible): las 11 migraciones
(`001` a `011`) corren limpias en orden desde cero. Casos probados:

- Constraint `negocios_latitud_longitud_consistentes`: insertar solo `longitud` sin
  `latitud` falla (`check_violation`). Constraint `negocios_latitud_rango`: `latitud = 200`
  falla.
- Alta de un negocio nuevo crea automáticamente su fila en `resumen_fila_publico` con
  `latitud`/`longitud` desnormalizadas (o `NULL`/`NULL` si el negocio no las tiene).
- Un turno pasa por `esperando → llamado → en_servicio → completado` y
  `resumen_fila_publico.personas_en_fila` se actualiza en cada paso (1 → 0 al completarse);
  con historial de un servicio completado, `tiempo_espera_estimado_minutos` deja de ser
  `NULL` para el siguiente cliente en espera.
- Con el rol `anon` real (sin bypass de RLS, con los mismos `GRANT` de tabla que Supabase
  otorga por defecto a `anon`/`authenticated` — la protección real es RLS, no el `GRANT`):
  el `SELECT` de `resumen_fila_publico` devuelve solo los negocios `activo = true` (incluidas
  sus coordenadas), **excluye** el negocio inactivo creado en el setup; ve **0 filas** de
  `turnos_fila` (bloqueo total confirmado); un `UPDATE` directo sobre `resumen_fila_publico`
  afecta **0 filas** (RLS lo bloquea, no hay policy de escritura para ese rol); un `INSERT`
  falla explícito con `insufficient_privilege` (RLS deniega la fila).
- Desactivar dinámicamente un negocio ya existente (`UPDATE negocios SET activo = false`,
  no solo al crearlo) lo hace desaparecer de inmediato del `SELECT` de `anon` sobre
  `resumen_fila_publico` — confirma que el trigger de sincronización reacciona a cambios de
  `negocios`, no solo al alta.

No se pudo probar contra Supabase local real (CLI no disponible en este entorno) — pendiente
de que `database` confirme el mismo resultado ahí antes de aplicar a staging/producción.

## Corrección por revisión de guardianes sobre `011` (multi-tenant-guard + dry-guard, 2026-08-16)

2 hallazgos, ambos corregidos en el mismo archivo `011_fila_publica_agregada.sql`.

1. **Bloqueante (multi-tenant-guard) — `calcular_tiempo_espera_estimado_minutos(uuid)` era
   `SECURITY DEFINER` sin ningún `REVOKE EXECUTE`.** Al ser `SECURITY DEFINER` y no tener
   restricción de rol, quedaba invocable directo por RPC (`select
   calcular_tiempo_espera_estimado_minutos('<tenant_id>')`) desde `anon`/`authenticated` para
   CUALQUIER `tenant_id`, sin pasar por la policy `resumen_fila_publico_select_publico`
   (`using (activo)`) — un negocio inactivo/oculto del comparador público seguía respondiendo
   su tiempo de espera si alguien conocía o adivinaba su `tenant_id`. Rompía la Decisión 1
   del propio archivo ("una sola tabla auditable, `resumen_fila_publico`, como única
   superficie de lectura pública"). Corregido con
   `revoke execute on function calcular_tiempo_espera_estimado_minutos(uuid) from public,
   anon, authenticated;` justo después de la definición. El trigger interno
   (`sincronizar_resumen_fila_publico`) que la invoca no se ve afectado: corre con
   privilegios de owner por su propio `SECURITY DEFINER`, independiente del `REVOKE` a roles
   de request.
2. **Duplicidad menor (dry-guard) — el predicado `estado in ('esperando', 'llamado',
   'en_servicio')` scoped por `tenant_id` estaba literal y repetido** en
   `sincronizar_resumen_fila_publico()` y en el `INSERT ... SELECT` de backfill, en vez de
   seguir el mismo patrón ya usado para `tiempo_espera_estimado_minutos` (extraída a su
   propia función y reusada en ambos lugares). Corregido extrayendo
   `contar_personas_en_fila_activa(p_tenant_id uuid) returns integer`, reusada en el trigger
   y en el backfill; mismo `revoke execute` que la función anterior por el mismo motivo de
   seguridad (aunque esta no filtra por `activo`, tampoco se justifica dejarla como RPC
   pública).

**Verificado de nuevo contra Postgres real desde cero** (mismo stub de Docker descrito
arriba): las 11 migraciones corren limpias en orden. Con el rol `anon` (y también
`authenticated`) real, `select calcular_tiempo_espera_estimado_minutos('<uuid>')` y `select
contar_personas_en_fila_activa('<uuid>')` fallan ambos con `permission denied for function`
— ya no son invocables directo. La lectura pública normal de `resumen_fila_publico` (el único
camino legítimo) sigue funcionando igual para `anon`. El trigger de sincronización sigue
actualizando `resumen_fila_publico` con normalidad tras insertar turnos y al cambiar su
estado (`personas_en_fila` 1 → 0 al cancelar el turno en espera), confirmando que el `REVOKE`
a nivel de rol de request no afecta la ejecución interna `SECURITY DEFINER` del trigger.
