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

## Las 20 tablas

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
- **Staff de la sede** (`dueno_sede` o `barbero`) puede registrar la cuenta `cliente` de un
  walk-in.
- **Solo `dueno_sede`** da de alta un `barbero` en su propia sede.
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
fuera de alcance: SSO/SAML empresarial** (no aplica a un negocio de barberías con clientes y
dueños individuales).

| Tabla nueva | Equivalente en `auth.*` de Supabase | Qué es |
|---|---|---|
| `perfiles_usuario` | `auth.users` (enriquecido) | 1:1 con `auth.users`, legible desde RLS (a diferencia de `auth.users`). `correo_verificado`/`telefono_verificado`/`ultimo_login_at` se sincronizan por trigger; `bloqueado_hasta` (bloqueo GLOBAL, las 20 sedes) y `eliminado_at` (soft-delete de la cuenta) son exclusivos de `administrador_plataforma` — el bloqueo POR SEDE que un `dueno_sede` sí puede aplicar usa `clientes.activo`/`barberos.activo`, ya existentes; `metadata_app` solo sistema; `metadata_usuario` el propio usuario. Transversal a los 4 roles — incluye `dueno_sede`/`administrador_plataforma`, que no tienen fila en `clientes` ni `barberos`. |
| `identidades_usuario` | `auth.identities` | Un registro por método de login vinculado (hoy `correo`/`telefono`; estructura lista para `google`/`apple` a futuro — sin lógica OAuth todavía). |
| `sesiones` | `auth.sessions` | Metadata de aplicación (dispositivo, IP, `nivel_autenticacion` tipo `aal1`/`aal2`/`aal3`, `expira_at`). No reemplaza el JWT — Supabase/PostgREST lo sigue validando en cada request; esta tabla es para UX ("tus dispositivos"/cerrar sesión remota) y para que el backend aplique el timeout diferenciado por rol (ver abajo). |
| `factores_autenticacion` + `retos_autenticacion` | `auth.mfa_factors` + `auth.mfa_challenges` | MFA-ready (`totp`/`telefono`/`webauthn`); sin lógica de verificación todavía. `secreto` es un placeholder que debe cifrarse en reposo antes de usarse con datos reales. |
| `tokens_autenticacion` | `auth.one_time_tokens` | Patrón genérico de token de un solo uso por `tipo`. **No reemplaza** recuperación de contraseña/confirmación de correo de la cuenta (eso sigue el flujo nativo de GoTrue) — es para flujos que Supabase Auth no cubre de fábrica. Sin políticas RLS: solo `service_role` (backend) la toca. |
| `auditoria_autenticacion` | `auth.audit_log_entries` | Eventos de auth (`login`/`logout`/`login_fallido`/cambios de contraseña/bloqueo/MFA) — clave para detectar mal uso de un dispositivo compartido en `barbero`/`dueno_sede`. Solo lectura vía RLS; solo `service_role` escribe. |

`auth.refresh_tokens` y `auth.mfa_amr_claims` **no** se replican: el primero porque Supabase
Auth ya lo gestiona por completo (replicarlo sería el antipatrón de reinventar
hashing/sesiones a mano); el segundo se simplificó a la columna `nivel_autenticacion` de
`sesiones` en vez de una tabla aparte, porque el negocio solo necesita saber el nivel
alcanzado, no el detalle de cada claim.

`sesiones`/`auditoria_autenticacion` llevan `tenant_id` **nullable** (a diferencia de las
tablas de dominio, donde es obligatorio): representa el contexto de sede activo cuando es
resoluble (login de `barbero`/`dueno_sede` de una sede concreta), y es `null` para un
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
   así las filas de `roles_usuario` de su barbero ve **cero filas siempre**, así que el
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
   de la sede A podía "atar" como cliente suyo al `dueno_sede`/`barbero` de la sede B (solo
   con su `usuario_id`/correo) y luego usar `bloqueado_hasta` — que bloquea la cuenta en las
   20 sedes, no por tenant — para sacarlo de operar en TODA la plataforma. Corregido
   sumando `bloqueado_hasta` a la regla de `eliminado_at`: **siempre**
   `administrador_plataforma`. El bloqueo POR SEDE que un `dueno_sede` sí debe poder hacer
   ya existía con el alcance correcto: `clientes.activo`/`barberos.activo`
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
`activo` de `clientes`/`barberos`, no en el perfil transversal.

**Riesgo residual aceptado explícitamente** (no cerrado, documentado a propósito): un
`dueno_sede` con una relación trivial (`cliente` creado unilateralmente por staff, sin
`usuario_id = auth.uid()`) todavía puede VER (decisión de producto ya aceptada abajo) y
escribir `correo_verificado`/`telefono_verificado` de alguien de otra sede — 2 columnas de
estado, no destructivas, que no bloquean operar. Se evaluó cerrar esto restringiendo
`roles_usuario_insert` para que staff no pueda atar como `cliente` walk-in a un `usuario_id`
que ya tiene rol `dueno_sede`/`administrador_plataforma`/`barbero` en cualquier tenant — se
descartó por ahora porque el impacto real ya quedó acotado con los puntos 4 y 5; queda
como candidato a revisar si un guardián futuro lo considera insuficiente.

**Decisión de producto aceptada explícitamente** (documentada también en la policy
`perfiles_usuario_select`): como `perfiles_usuario` no tiene `tenant_id` propio, el `SELECT`
de `correo_verificado`/`telefono_verificado`/`ultimo_login_at` de un usuario **es visible
para cualquier sede con la que tenga alguna relación** en `roles_usuario`, aunque el evento
haya ocurrido en el contexto de otra sede — y las 20 barberías son negocios independientes
entre sí (potenciales competidores), no sub-sedes de un mismo tenant. Se acepta porque son
solo 3 campos de estado operativo (no `identidades_usuario`/`factores_autenticacion`, que sí
son estrictamente self+admin) y porque el caso de uso real (un `dueno_sede` necesita saber
si su barbero verificó su cuenta) lo requiere.

### Política de sesión/inactividad por rol — decisión de diseño, no tabla

`barbero`/`dueno_sede` (dispositivo compartido en el local) necesitan expiración más corta y
logout por inactividad; `cliente`, sesión normal. GoTrue configura el JWT/refresh token a
nivel de **proyecto**, no por rol, así que la diferenciación real es de app: un timer de
inactividad en frontend-nextjs que cierra sesión tras ~15 min sin interacción SOLO cuando el
rol activo es `barbero`/`dueno_sede` (leyendo `roles_usuario`, igual que cualquier otra
decisión de autorización), apoyado en `sesiones.expira_at`/`ultima_actividad_at`. No se
modeló como una escritura a la base en cada request: sería una escritura por request a la
escala de las 20 sedes.

### Recuperación de contraseña y enumeración de usuarios — Supabase Auth nativo

`resetPasswordForEmail` + `verifyOtp(type='recovery')` de Supabase Auth: el token vive en el
esquema `auth` (`flow_state`), expira corto y es de un solo uso por diseño de GoTrue — no se
reimplementa a mano. `signInWithPassword` devuelve el mismo error genérico exista o no la
cuenta, y `resetPasswordForEmail` siempre responde "ok": no agregar un endpoint propio de
"¿existe este correo?" que reintroduzca la fuga de enumeración de usuarios.

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
- `supabase/migrations/001_extensiones_y_helpers.sql` a `010_identidad_extendida.sql` —
  código fuente de todo lo descrito en este documento.
