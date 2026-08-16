# Arquitectura de Barberus

> Estado de este documento: describe el esquema de base de datos (implementado) y el
> scaffolding del backend en `api/` (implementado para los contextos `identidad` y `fila`
> -- este último solo con el endpoint público `GET /fila/publica`; `agenda`/`membresias`/
> `reportes` siguen como esqueleto sin lógica -- ver `README.md` y `api/README.md`). La
> sección "Flujo de una reserva" describe la capa de base de datos con detalle verificado
> contra el código real, y el resto del flujo (agenda vía API → tiempo real) tal como
> está **planeado** en la configuración de los agentes de este repo — se marcará
> explícitamente como no implementado donde aplique, y se completará con detalle real en
> cuanto exista ese código.

## Qué es Barberus

SaaS multi-tenant que actúa como intermediario entre múltiples negocios independientes
(barberías, salones de uñas y otros verticales de servicios con cita/turno) y sus clientes
— la plataforma no es dueña de esos negocios, cada uno es un tenant propio. Cada negocio
(tenant) es una fila en `negocios`; todo el resto del dominio —profesionales, servicios,
clientes, reservas, fila de espera, membresías— cuelga de un `tenant_id`. North star:
reducir no-shows y tiempo de espera en fila.

## Modelo multi-tenant

### Tenant raíz

`negocios` es el tenant raíz (`supabase/migrations/002_negocios.sql`). Toda tabla de
dominio lleva `tenant_id not null references negocios(id)`.

### Roles: `roles_usuario`

`roles_usuario` (`001_extensiones_y_helpers.sql`) mapea `auth.users` a un rol dentro de un
tenant: `(usuario_id, tenant_id, rol)`, con `rol` del enum `rol_app`:
`administrador_plataforma`, `dueno_sede`, `profesional`, `cliente`.

Un mismo `usuario_id` **puede tener varias filas** en `roles_usuario` (una por tenant) —
por ejemplo, `dueno_sede` en la sede A y `cliente` en la sede B. Esto es una decisión de
negocio explícita, no un caso raro: el único constraint es
`unique (usuario_id, tenant_id)`, nunca `unique (usuario_id)` a secas.
`administrador_plataforma` es la excepción: no lleva `tenant_id` (ve todos los negocios), forzado
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
| `es_administrador_plataforma()` | ¿el usuario autenticado es operador de plataforma (ve todos los negocios)? |
| `es_miembro_del_tenant(p_tenant_id)` | ¿tiene cualquier rol (`dueno_sede`, `profesional` o `cliente`) en ese tenant? |
| `es_personal_del_tenant(p_tenant_id)` | ¿es `dueno_sede` o `profesional` de ese tenant? |
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

Además de RLS, las tablas que referencian `clientes`, `profesionales`, `servicios`,
`reservas` o `niveles_membresia` lo hacen con **FK compuesta `(id, tenant_id)`** (habilitada
por un `unique (id, tenant_id)` en la tabla referenciada). Esto hace que, a nivel de motor
de base de datos, sea imposible que por ejemplo una reserva tenga un `cliente_id` de un
tenant y un `tenant_id` de otro — ni siquiera si un bug futuro se saltara RLS. También es
lo que permite simplificar policies como `es_dueno_del_cliente(cliente_id)` sin repetir el
chequeo de `tenant_id`: si no coincidieran, el INSERT ya habría fallado por la FK antes de
llegar a evaluarse la policy.

### Excepción única: lectura pública cross-tenant (`resumen_fila_publico`)

Todo lo anterior asume "toda lectura está scoped a soy miembro de este tenant". Hay UNA sola
excepción en todo el esquema, introducida en `011_fila_publica_agregada.sql`: un visitante
sin login debe poder comparar cuánta fila hay en varios negocios de la plataforma antes de
decidir a cuál ir, y ubicarlos en un mapa (Leaflet/react-leaflet, ya decidido en frontend).
El mecanismo:

- **Nunca se toca `turnos_fila` ni sus policies.** Se creó una tabla derivada,
  `resumen_fila_publico` (una fila por negocio), con solo `nombre_sede`, `slug_sede`,
  `activo`, `latitud`, `longitud`, `personas_en_fila` y `tiempo_espera_estimado_minutos` —
  cero `cliente_id`/`profesional_id`/datos individuales, ni siquiera con columnas limitadas
  por policy. Una tabla que físicamente no tiene esas columnas es más simple de auditar que
  una policy que promete "solo estas columnas" sobre una tabla que sí las tiene.
- **Mantenida por trigger** (`sincronizar_resumen_fila_publico` sobre `turnos_fila`,
  `sincronizar_resumen_fila_publico_desde_negocio` sobre `negocios`, ambas
  `SECURITY DEFINER`), no una vista calculada al vuelo: el tráfico de lectura es público y
  potencialmente alto; las escrituras en `turnos_fila` son al ritmo de check-ins de un
  negocio (bajo volumen). La lectura pública es un lookup por PK.
- **`tiempo_espera_estimado_minutos` usa datos reales o es `NULL`.** Se calcula con la
  duración promedio real de servicio (`hora_completado - hora_inicio`) de las últimas 24h de
  ese negocio; si no hay historial reciente, es `NULL` explícito — nunca un valor inventado.
- **Anti-abuso:** ninguna policy de escritura para `es_personal_del_tenant`/
  `es_dueno_del_tenant` — los negocios de la plataforma son competidores entre sí, y un
  `dueno_sede` no puede tener forma de inflar/deflactar su propio número frente a los demás.
  Solo `administrador_plataforma` tiene un `for all` de corrección manual.
- **La única policy sin `auth.uid()` de todo el esquema:** `resumen_fila_publico_select_publico`
  — `for select to anon, authenticated using (activo)`.
- **Coordenadas para el mapa:** `negocios` gana `latitud numeric(9,6)`/`longitud
  numeric(9,6)` (nullable, con `check` de rango físico y de consistencia mutua — no puede
  existir una sin la otra). Se descartó PostGIS por sobre-ingeniería (el caso de uso es
  ubicar puntos simples en Leaflet, no queries geoespaciales). Como `negocios` no tiene
  lectura pública, las coordenadas se desnormalizan también en `resumen_fila_publico` —así el
  frontend del mapa hace un solo query público en vez de abrir una segunda tabla con lectura
  pública.

Detalle completo de la decisión (incluida la validación contra Postgres real) en
`scripts/migrations/APPLIED.md`, sección `011_fila_publica_agregada.sql`.

## Las tablas

Todas con RLS habilitado. Migración de origen entre paréntesis.

**Identidad y catálogo**
- `roles_usuario` (`001`) — mapa `usuario_id` → `(tenant_id, rol)`. Base de todo el RLS.
- `negocios` (`002`, `latitud`/`longitud` agregadas en `011`) — tenant raíz: nombre, `slug`
  único, zona horaria, contacto, coordenadas opcionales para el mapa público.
- `profesionales` (`003`) — 1:1 con una sede (`tenant_id` normal, sin tabla de rotación —
  decisión de negocio ya cerrada). `usuario_id` nullable (puede no tener login todavía).
- `servicios` (`004`) — catálogo por sede: nombre, `duracion_minutos`. Sin precio/billing
  (fuera de alcance).

**Clientes**
- `clientes` (`005`) — perfil **aislado por sede**: un mismo humano que visita 2 sedes
  tiene 2 filas independientes, sin FK entre ellas. `usuario_id` nullable (walk-ins sin
  cuenta). Único por `(tenant_id, usuario_id)`, nunca por `usuario_id` global.
- `notas_cliente` (`005`) — notas internas del profesional sobre un cliente; nunca visibles
  para el propio cliente (solo policies de `es_personal_del_tenant`).

**Reservas**
- `reservas` (`006`) — agenda: `cliente_id`, `profesional_id`, `estado`
  (`pendiente`→`confirmada`→`en_progreso`→`completada`, o `cancelada`/`no_asistio` según
  máquina de estados en trigger), `inicio_programado`/`fin_programado`. No-doble-booking de
  un profesional garantizado por un `exclude using gist` (constraint de exclusión), no un
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
  `cancelado`/`no_asistio`. Un profesional solo puede tener un turno `en_servicio` a la vez
  (unique index parcial). `numero_turno` se asigna de forma atómica por trigger.
- `contadores_fila_diarios` (`007`) — contador `(tenant_id, fecha_fila) → último número`,
  usado internamente por el trigger de numeración; no se toca directamente desde la app.
- `resumen_fila_publico` (`011`) — ÚNICA tabla de lectura pública cross-tenant del esquema
  (sin `auth.uid()`, rol `anon` incluido). Una fila por negocio: `personas_en_fila` +
  `tiempo_espera_estimado_minutos` (agregado, `NULL` si no hay base real) + `latitud`/
  `longitud` (desnormalizadas desde `negocios`, para el mapa público), mantenida por trigger
  desde `turnos_fila`/`negocios`. Ver sección "Excepción única: lectura pública cross-tenant"
  arriba.

**Membresías (solo tracking, sin cobro)**
- `niveles_membresia` (`008`) — catálogo de niveles por sede: `visitas_minimas`,
  `dias_ventana` (nullable; hoy no usado — ver nota abajo), `beneficios` (jsonb).
- `membresias_cliente` (`008`) — una fila viva por cliente: `nivel_actual_id`,
  `visitas_totales`, `estado` (`activa`/`vencida`/`cancelada`), fechas administrativas de
  periodo (`inicio_periodo_actual`/`fin_periodo_actual`, escritas a mano por `dueno_sede`
  al renovar; no hay billing).
- `historial_nivel_membresia_cliente` (`008`) — auditoría de cada cambio de nivel, generada
  por el trigger de recálculo.

**Identidad extendida (ver sección "Identidad y autenticación" arriba para el detalle)**
- `perfiles_usuario` (`010`) — 1:1 con `auth.users`, transversal a los 4 roles.
- `identidades_usuario` (`010`) — métodos de login vinculados por usuario.
- `sesiones` (`010`) — metadata de dispositivo/IP/nivel de autenticación por sesión.
- `factores_autenticacion` (`010`) — factores MFA-ready (`totp`/`telefono`/`webauthn`).
- `retos_autenticacion` (`010`) — intentos de verificación de un factor.
- `tokens_autenticacion` (`010`) — tokens de un solo uso, patrón genérico por `tipo`.
- `auditoria_autenticacion` (`010`) — log de eventos de auth (login/logout/bloqueo/MFA).

Un trigger (`recalcular_membresia_cliente`) sube de nivel al cliente cada vez que una
reserva pasa a `completada`, usando el **conteo histórico total** de visitas como
simplificación de MVP — no la ventana `dias_ventana` que ya está modelada en
`niveles_membresia` mismo. No usar `dias_ventana` como fuente de verdad de "visitas en los
últimos N días" todavía; está reservado para cuando se implemente un recálculo periódico
por ventana.

## Identidad y autenticación

Construido sobre Supabase Auth (`auth.users`, JWT, GoTrue) — el esquema `public` nunca
reinventa hashing/sesiones, solo agrega lo que el negocio necesita y Supabase Auth no
expone directo a PostgREST/RLS.

### `roles_usuario` escribible (`009_identidad_autenticacion.sql`)

`001` dejó `roles_usuario` con solo `SELECT` propio. `009` agrega quién puede crear/borrar
una fila de rol, y para quién:

- **Cliente se autoasigna `cliente`** al hacer su primera reserva en una sede (el backend
  hace `INSERT roles_usuario` seguido de `INSERT clientes` en la misma transacción — en ese
  orden, porque `clientes_insert` exige `es_cliente_del_tenant(tenant_id)`, que lee
  `roles_usuario`).
- **Staff de la sede** (`dueno_sede` o `profesional`) puede registrar la cuenta `cliente` de un
  walk-in.
- **Solo `dueno_sede`** da de alta un `profesional` en su propia sede.
- **Solo `administrador_plataforma`** da de alta un `dueno_sede` o a otro
  `administrador_plataforma` — cierra el vector de escalamiento de privilegios más obvio de
  esta tabla.
- **Sin política de `UPDATE`** a propósito: un cambio de rol es `DELETE` + `INSERT`, cada
  paso pasando otra vez por las reglas de arriba — no hay atajo de un paso para escalar
  privilegios.

`009` también agrega el trigger `exigir_reautenticacion_clientes`: un cliente no puede
cambiar su propio `correo`/`telefono` (`clientes`) si el JWT actual (`iat`) tiene más de 10
minutos — fuerza reautenticación reciente en vez de un `PATCH` silencioso sobre un dato
sensible. No aplica a staff ni a `service_role`.

### Identidad extendida estilo `auth.*` (`010_identidad_extendida.sql`)

Decisión de producto: replicar, en español y adaptado al negocio, la riqueza del esquema
`auth.*` que Supabase mantiene internamente — estructura lista para crecer (MFA,
identidades vinculadas) aunque esa lógica todavía no esté implementada. **Explícitamente
fuera de alcance: SSO/SAML empresarial** (no aplica a una plataforma de negocios
independientes con clientes y dueños individuales).

| Tabla nueva | Equivalente en `auth.*` de Supabase | Qué es |
|---|---|---|
| `perfiles_usuario` | `auth.users` (enriquecido) | 1:1 con `auth.users`, legible desde RLS (a diferencia de `auth.users`). `correo_verificado`/`telefono_verificado`/`ultimo_login_at` se sincronizan por trigger; `bloqueado_hasta` (bloqueo GLOBAL, todos los negocios) y `eliminado_at` (soft-delete de la cuenta) son exclusivos de `administrador_plataforma` — el bloqueo POR SEDE que un `dueno_sede` sí puede aplicar usa `clientes.activo`/`profesionales.activo`, ya existentes; `metadata_app` solo sistema; `metadata_usuario` el propio usuario. Transversal a los 4 roles — incluye `dueno_sede`/`administrador_plataforma`, que no tienen fila en `clientes` ni `profesionales`. |
| `identidades_usuario` | `auth.identities` | Un registro por método de login vinculado (hoy `correo`/`telefono`; estructura lista para `google`/`apple` a futuro — sin lógica OAuth todavía). |
| `sesiones` | `auth.sessions` | Metadata de aplicación (dispositivo, IP, `nivel_autenticacion` tipo `aal1`/`aal2`/`aal3`, `expira_at`). No reemplaza el JWT — Supabase/PostgREST lo sigue validando en cada request; esta tabla es para UX ("tus dispositivos"/cerrar sesión remota) y para que el backend aplique el timeout diferenciado por rol (ver abajo). |
| `factores_autenticacion` + `retos_autenticacion` | `auth.mfa_factors` + `auth.mfa_challenges` | MFA-ready (`totp`/`telefono`/`webauthn`); sin lógica de verificación todavía. `secreto` es un placeholder que debe cifrarse en reposo antes de usarse con datos reales. |
| `tokens_autenticacion` | `auth.one_time_tokens` | Patrón genérico de token de un solo uso por `tipo`. **No reemplaza** recuperación de contraseña/confirmación de correo de la cuenta (eso sigue el flujo nativo de GoTrue) — es para flujos que Supabase Auth no cubre de fábrica. Sin políticas RLS: solo `service_role` (backend) la toca. |
| `auditoria_autenticacion` | `auth.audit_log_entries` | Eventos de auth (`login`/`logout`/`login_fallido`/cambios de contraseña/bloqueo/MFA) — clave para detectar mal uso de un dispositivo compartido en `profesional`/`dueno_sede`. Solo lectura vía RLS; solo `service_role` escribe. |

`auth.refresh_tokens` y `auth.mfa_amr_claims` **no** se replican: el primero porque Supabase
Auth ya lo gestiona por completo (replicarlo sería el antipatrón de reinventar
hashing/sesiones a mano); el segundo se simplificó a la columna `nivel_autenticacion` de
`sesiones` en vez de una tabla aparte, porque el negocio solo necesita saber el nivel
alcanzado, no el detalle de cada claim.

`sesiones`/`auditoria_autenticacion` llevan `tenant_id` **nullable** (a diferencia de las
tablas de dominio, donde es obligatorio): representa el contexto de sede activo cuando es
resoluble (login de `profesional`/`dueno_sede` de una sede concreta), y es `null` para un
`cliente` sin sede aún o para `administrador_plataforma`. Sus policies de `SELECT` dejan que
un `dueno_sede` audite solo eventos/sesiones con el `tenant_id` de su propia sede
(`es_propio_o_dueno_del_tenant_opcional`, ver abajo). `sesiones_insert` además valida que,
si la fila trae `tenant_id`, el usuario REALMENTE tenga un rol ahí (`es_miembro_del_tenant`)
— si no, cualquiera podía insertar una sesión propia con el `tenant_id` de una sede ajena y
ensuciar la auditoría que vería el dueño legítimo (caso borde de multi-tenant-guard).

**Hallazgos reales corregidos probando esta migración contra Postgres** (no detectados por
inspección, ver el detalle completo con los escenarios de prueba en
`scripts/migrations/APPLIED.md`, secciones "Hallazgos al probar 009/010" y "Corrección por
revisión de guardianes"):

1. Un `EXISTS` inline contra `roles_usuario` dentro de la policy de OTRA tabla queda sujeto a
   `roles_usuario_select_propio` (`usuario_id = auth.uid()`) — un `dueno_sede` consultando
   así las filas de `roles_usuario` de su profesional ve **cero filas siempre**, así que el
   `EXISTS` da falso incluso cuando debería poder. Se agregaron funciones `SECURITY DEFINER`
   para esto (mismo patrón que el resto del esquema):
   `es_personal_de_algun_tenant_del_usuario(p_usuario_id)`,
   `es_dueno_de_algun_tenant_del_usuario(p_usuario_id)`,
   `es_propio_o_dueno_del_tenant_opcional(p_usuario_id, p_tenant_id)` (dedup de
   `sesiones`/`auditoria_autenticacion`) y `es_dueno_del_factor(p_factor_id)` (dedup de
   `retos_autenticacion`, mismo patrón que `es_dueno_de_reserva` en `006_reservas.sql`).
2. Reutilizar `es_dueno_de_algun_tenant_del_usuario` como excepción dentro del trigger de
   columnas reabría auto-escalada (un `dueno_sede` editando su PROPIA fila quedaba exento
   por ser dueño de su propio tenant).
3. **Bloqueante (encontrado en revisión formal de multi-tenant-guard):** aun corregido el
   punto 2, editar la fila de OTRO usuario (`dueno_sede`/staff con una relación real vía
   `roles_usuario`) no tenía NINGÚN límite de columnas — un `dueno_sede` podía escribir
   `eliminado_at`/`metadata_app` del perfil GLOBAL de alguien con actividad en otras 19
   sedes independientes. Corregido con el trigger `restringir_columnas_perfil_usuario`
   (reemplaza al anterior `impedir_auto_escalada_perfil_usuario`, ámbito ampliado).
4. **Bloqueante — el fix del punto 3 era un denylist con hueco, no una whitelist real**
   (encontrado en una segunda re-verificación línea por línea de multi-tenant-guard, sin
   confiar en el reporte anterior): solo bloqueaba `metadata_app`/`metadata_usuario` por
   nombre, así que `ultimo_login_at` quedaba editable, y cualquier columna futura nacería
   desprotegida por default. Corregido invirtiendo a una whitelist real por diferencia de
   fila completa: `(to_jsonb(new) - columnas_permitidas) is distinct from (to_jsonb(old) -
   columnas_permitidas)` — protegido por default salvo lo explícitamente permitido.
5. **Bloqueante nuevo — `bloqueado_hasta` habilitaba sabotaje cross-tenant real entre
   negocios competidores.** `roles_usuario_insert` (`009`) deja que cualquier staff de un
   tenant registre `roles_usuario(usuario_id = <cualquier uuid existente>, tenant_id = mi
   tenant, rol = 'cliente')` sin exigir `usuario_id = auth.uid()`. Con eso, un `dueno_sede`
   de la sede A podía "atar" como cliente suyo al `dueno_sede`/`profesional` de la sede B (solo
   con su `usuario_id`/correo) y luego usar `bloqueado_hasta` — que bloquea la cuenta en las
   todos los negocios, no por tenant — para sacarlo de operar en TODA la plataforma. Corregido
   sumando `bloqueado_hasta` a la regla de `eliminado_at`: **siempre**
   `administrador_plataforma`. El bloqueo POR SEDE que un `dueno_sede` sí debe poder hacer
   ya existía con el alcance correcto: `clientes.activo`/`profesionales.activo`
   (`003`/`005`, tenant-scoped) — no hizo falta tabla ni columna nueva.
6. **Regresión funcional del fix del punto 3** — la protección incondicional de
   `eliminado_at` también bloqueaba a `trg_sincronizar_perfil_usuario` (corre sin contexto de
   JWT al reflejar un soft-delete real hecho vía Admin API de Supabase, así que
   `auth.role()` no es `'service_role'` ahí, es `null`), rompiendo esa sincronización
   legítima. Corregido con una variable de sesión local a la transacción
   (`barberus.contexto = 'sync_interno'`, seteada solo por esa función `SECURITY DEFINER`,
   nunca expuesta a PostgREST) en vez de relajar la condición por rol.

En síntesis: la policy decide QUIÉN llega a una fila; el trigger decide QUÉ COLUMNAS puede
tocar una vez que llegó, con whitelist real (deny-by-default) en vez de una lista de
prohibiciones conocidas — mezclar esas preguntas, y proteger por nombre en vez de por
default, fue la causa raíz de los puntos 2, 3, 4 y 5. `bloqueado_hasta` terminó con el mismo
tratamiento que `eliminado_at` (siempre `administrador_plataforma`) precisamente porque su
efecto es global, no de sede — el bloqueo con alcance de tenant vive en las columnas
`activo` de `clientes`/`profesionales`, no en el perfil transversal.

**Riesgo residual aceptado explícitamente** (no cerrado, documentado a propósito): un
`dueno_sede` con una relación trivial (`cliente` creado unilateralmente por staff, sin
`usuario_id = auth.uid()`) todavía puede VER (decisión de producto ya aceptada abajo) y
escribir `correo_verificado`/`telefono_verificado` de alguien de otra sede — 2 columnas de
estado, no destructivas, que no bloquean operar. Se evaluó cerrar esto restringiendo
`roles_usuario_insert` para que staff no pueda atar como `cliente` walk-in a un `usuario_id`
que ya tiene rol `dueno_sede`/`administrador_plataforma`/`profesional` en cualquier tenant — se
descartó por ahora porque el impacto real ya quedó acotado con los puntos 4 y 5; queda
como candidato a revisar si un guardián futuro lo considera insuficiente.

**Decisión de producto aceptada explícitamente** (documentada también en la policy
`perfiles_usuario_select`): como `perfiles_usuario` no tiene `tenant_id` propio, el `SELECT`
de `correo_verificado`/`telefono_verificado`/`ultimo_login_at` de un usuario **es visible
para cualquier sede con la que tenga alguna relación** en `roles_usuario`, aunque el evento
haya ocurrido en el contexto de otra sede — y los negocios de la plataforma son
independientes entre sí (potenciales competidores), no sub-sedes de un mismo tenant. Se acepta porque son
solo 3 campos de estado operativo (no `identidades_usuario`/`factores_autenticacion`, que sí
son estrictamente self+admin) y porque el caso de uso real (un `dueno_sede` necesita saber
si su profesional verificó su cuenta) lo requiere.

### Política de sesión/inactividad por rol — decisión de diseño, no tabla

`profesional`/`dueno_sede` (dispositivo compartido en el local) necesitan expiración más corta y
logout por inactividad; `cliente`, sesión normal. GoTrue configura el JWT/refresh token a
nivel de **proyecto**, no por rol, así que la diferenciación real es de app: un timer de
inactividad en frontend-nextjs que cierra sesión tras ~15 min sin interacción SOLO cuando el
rol activo es `profesional`/`dueno_sede` (leyendo `roles_usuario`, igual que cualquier otra
decisión de autorización), apoyado en `sesiones.expira_at`/`ultima_actividad_at`. No se
modeló como una escritura a la base en cada request: sería una escritura por request a la
escala de todos los negocios de la plataforma.

### Recuperación de contraseña y enumeración de usuarios — Supabase Auth nativo

`resetPasswordForEmail` + `verifyOtp(type='recovery')` de Supabase Auth: el token vive en el
esquema `auth` (`flow_state`), expira corto y es de un solo uso por diseño de GoTrue — no se
reimplementa a mano. `signInWithPassword` devuelve el mismo error genérico exista o no la
cuenta, y `resetPasswordForEmail` siempre responde "ok": no agregar un endpoint propio de
"¿existe este correo?" que reintroduzca la fuga de enumeración de usuarios.

## Backend (API): arquitectura hexagonal + DDD

Capa nueva respecto a lo anterior de este documento (que describe el esquema de base de
datos y su RLS). Esta sección describe la capa de encima: cómo `api/` (FastAPI) organiza
la lógica de negocio y resuelve identidad/tenant por request. Detalle completo de la
convención de capas y contextos en
[`.claude/agents/backend-fastapi.md`](../.claude/agents/backend-fastapi.md); cómo correr
el proyecto en [`api/README.md`](../api/README.md). No se repite acá el detalle de
`roles_usuario`/`sesiones`/RLS ya cubierto arriba en "Identidad y autenticación" — esta
sección es sobre la capa de aplicación que consume ese esquema, no sobre el esquema en sí.

**Por qué dos capas de autorización, no una.** RLS (arriba) es la garantía de que,
incluso si un bug del backend se saltara toda validación, Postgres seguiría negando el
acceso cross-tenant a nivel de fila. La resolución de identidad en `api/` es la
*primera* capa, la que decide qué `tenant_id` aplica a una request y con qué rol,
**antes** de que cualquier query llegue a Postgres -- necesaria igual, porque RLS por sí
sola no puede decidir "¿cuál de los varios tenants de este usuario aplica a esta
request en particular?": esa es una decisión de la request (qué sede seleccionó el
usuario en el frontend), no del dato.

**Contextos delimitados** (`api/contextos/`): cada área de negocio (`identidad`,
`agenda`, `fila`, `membresias`, `reportes`) es un módulo con sus propias 4 capas
(`dominio/aplicacion/infraestructura/interfaces`), dependencias apuntando siempre hacia
adentro. Un contexto nunca importa el `dominio`/`infraestructura` interno de otro -- pide
lo que necesita a través de la superficie pública del contexto dueño (p.ej.
`contextos.identidad.aplicacion.contexto_publico`). Hoy `identidad` y `fila` tienen
lógica; `agenda`/`membresias`/`reportes` siguen como carpetas esqueleto que fijan la
convención para los PR que los implementen.

**Factory compartido de clientes Supabase (`nucleo/cliente_supabase.py`).** La
instanciación de `Client` (`create_client` + `@lru_cache` para un único cliente por
proceso) es idéntica en cualquier contexto -- lo único que cambia es qué key usar, y esa
decisión (con su razonamiento de seguridad) vive en el `infraestructura/
cliente_supabase.py` propio de cada contexto, que reexporta las funciones de `nucleo/`:
`obtener_cliente_supabase_secreto()` (bypasea RLS, usa `SUPABASE_SECRET_KEY` -- solo
cuando el propio backend ya resolvió la autorización antes de la query, p.ej.
`identidad` consultando `roles_usuario`/`sesiones`) y `obtener_cliente_supabase_publico()`
(respeta RLS, usa `SUPABASE_PUBLISHABLE_KEY` -- mismo privilegio que un cliente anónimo,
usado por `identidad` para signup/login contra GoTrue y por `fila` para leer
`resumen_fila_publico`). `nucleo/` nunca decide cuál de las dos usar; ese criterio es
responsabilidad de cada contexto.

**Contexto `fila`: comparador público de fila entre negocios.** `GET /fila/publica`
(`api/contextos/fila/interfaces/router.py`) -- sin JWT, sin `tenant_id`, es a propósito
el único endpoint cross-tenant de toda la API, espejo del único caso de lectura pública
del esquema descrito arriba en "Excepción única: lectura pública cross-tenant
(`resumen_fila_publico`)". Devuelve la lista de negocios activos con
`tenant_id, nombre_sede, slug_sede, personas_en_fila, tiempo_espera_estimado_minutos,
latitud, longitud`, leyendo `resumen_fila_publico` con el cliente Supabase público (RLS
hace el filtro `activo = true`, el adaptador no lo repite). No hay lógica de negocio en
el caso de uso (`ListarNegociosConFilaPublica`) más allá de invocar el repositorio -- todo
el cálculo (tiempo estimado, qué negocios están activos) ya vive en la base vía triggers
(ver esa misma sección arriba).

**Resolución de tenant cuando un usuario tiene roles en varios (`identidad`).** Como
`roles_usuario` permite varias filas por `usuario_id` (ver arriba, "Roles:
`roles_usuario`"), el caso de uso `ResolverContextoIdentidad`
(`api/contextos/identidad/aplicacion/resolver_contexto_identidad.py`) nunca elige un
tenant por su cuenta cuando hay más de uno: exige que el llamador lo especifique
explícito (header `X-Tenant-Id`), y si no lo hace, falla con `TenantAmbiguo` en vez de
adivinar -- réplica intencional, a nivel de aplicación, de la lección del hallazgo de
`current_tenant_id()`/`limit 1` sin `order by` corregido en el esquema (ver arriba, "Cómo
se resuelve el aislamiento"). Con una sola asignación no hace falta el header (no hay
ambigüedad posible). `administrador_plataforma` es la excepción: puede operar sobre
cualquier `tenant_id` solicitado, incluida ausencia de uno (contexto de plataforma).

**Timeout de sesión diferenciado por rol.** El mismo caso de uso aplica la política ya
documentada arriba ("Política de sesión/inactividad por rol"): timeout corto (15 min)
para `profesional`/`dueno_sede` (dispositivo compartido en el local), normal (8 h) para
`cliente`/`administrador_plataforma`, comparando contra `sesiones.expira_at` -- lógica de
dominio pura en `contextos/identidad/dominio/servicios.py`, sin escritura a la base en
cada request (se lee `sesiones`, no se actualiza en cada llamada).

**Endpoint de verificación:** `GET /identidad/contexto` devuelve el usuario/rol/tenant/
sesión resueltos a partir del JWT de la request -- pensado para que QA y el futuro
frontend verifiquen esta capa contra un Supabase real.

## Flujo de una reserva

**Base de datos (implementado, verificado):**

1. `INSERT` en `reservas` con `cliente_id`, `profesional_id`, `inicio_programado` y un
   `fin_programado` tentativo (el `check` `fin_programado > inicio_programado` no es
   diferible; hace falta un valor válido inicial, p.ej. `inicio + 1 minuto`).
2. `INSERT` en `reserva_servicios` por cada servicio elegido, en la misma transacción. Un
   trigger fija `duracion_minutos_snapshot` desde `servicios.duracion_minutos` si no viene
   explícito, y otro recalcula `reservas.fin_programado` sumando esas duraciones.
3. Al hacer `COMMIT`, el exclusion constraint `reservas_sin_doble_reserva` valida (recién
   ahí, por ser `deferred`) que el profesional no tenga otra reserva activa con rango
   solapado; si lo hay, la transacción falla completa.
4. Cambios de `estado` pasan por el trigger `validar_transicion_estado_reserva`: valida la
   transición contra la máquina de estados y, si quien actualiza no es staff del tenant de
   esa reserva (`es_personal_del_tenant`), solo permite `cancelada` (un cliente nunca puede
   marcarse a sí mismo `completada` o `no_asistio`).
5. Cuando una reserva pasa a `completada`, un trigger recalcula la membresía del cliente
   (`recalcular_membresia_cliente`): incrementa `visitas_totales` y evalúa si sube de
   nivel.

**Frontend → API → tiempo real (planeado, parcialmente implementado):** según la
configuración de los agentes de este repo, la reserva se crearía desde un formulario
Next.js (`react-hook-form` + `zod`), un endpoint FastAPI del contexto `agenda` validaría
y ejecutaría la transacción de arriba, y la fila en vivo (`turnos_fila`) se
sincronizaría entre profesional y cliente vía Supabase Realtime. Hoy existe el scaffolding de
`api/` y el contexto `identidad` (resolución de JWT/rol/tenant, ver sección "Backend
(API)" más abajo), pero el contexto `agenda` en sí es solo esqueleto de carpetas, sin
endpoints ni lógica — no hay `frontend/` en el repo tampoco. Este párrafo sigue
describiendo mayormente el plan, no el comportamiento actual del flujo de reserva.

## Decisiones de negocio ya cerradas

- **Cliente aislado por sede, sin identidad global.** Un mismo `usuario_id` puede tener
  perfil de cliente en varias sedes, pero son filas independientes en `clientes` sin FK
  entre ellas; `correo`/`telefono` no son únicos globalmente, solo (implícitamente) dentro
  del tenant. Ver `005_clientes.sql`.
- **Membresía solo tracking, sin cobro.** `niveles_membresia`/`membresias_cliente` no
  tienen columnas de precio ni ciclo de facturación; la renovación es manual y ocurre fuera
  del sistema (`fin_periodo_actual` es una fecha que el `dueno_sede` escribe a mano). Pagos
  quedan fuera de alcance por ahora. Ver `008_membresias.sql`.
- **Profesional pertenece a una sola sede.** Modelado como columna `tenant_id` normal en
  `profesionales` (no una tabla N:N de rotación entre sedes) — decisión de negocio ya cerrada,
  no una limitación técnica temporal. Ver `003_profesionales.sql`.
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
- `supabase/migrations/001_extensiones_y_helpers.sql` a `011_fila_publica_agregada.sql` —
  código fuente de todo lo descrito en este documento.
- [`.claude/agents/backend-fastapi.md`](../.claude/agents/backend-fastapi.md) — convención
  completa de arquitectura hexagonal + DDD y contextos delimitados del backend.
- [`api/README.md`](../api/README.md) — cómo correr/testear la API, estructura real de
  `api/contextos/`.
