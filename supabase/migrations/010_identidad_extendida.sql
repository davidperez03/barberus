-- Migración: identidad extendida (perfil, identidades, sesiones, MFA-ready, tokens, auditoría)
-- Autor: auth-users
--
-- Decisión de producto (pedida explícitamente): replicar, en español y adaptado al negocio,
-- la riqueza del esquema auth.* que ya mantiene Supabase internamente -- "completo, listo
-- para crecer": estructura MFA-ready e identidades vinculadas aunque la LÓGICA no se
-- implemente todavía. Explícitamente FUERA de alcance: SSO/SAML empresarial
-- (sso_providers/sso_domains/saml_*) -- no aplica a una plataforma de negocios independientes
-- con clientes y dueños individuales, no una empresa cliente con su propio Identity Provider.
--
-- Equivalencia con auth.* de Supabase (todas nuevas, ninguna reemplaza a auth.*, que sigue
-- siendo la fuente de verdad de si un JWT es válido -- estas tablas son METADATA de
-- aplicación: auditoría, UX de "tus dispositivos", y estructura lista para MFA):
--   auth.users            -> NO se duplica (la gestiona Supabase Auth). Lo que sí se agrega
--                            es perfiles_usuario: 1:1 con auth.users, con lo que el negocio
--                            necesita ver/usar de ese usuario sin volver a auth.users desde
--                            cada policy (PostgREST no puede leer auth.users directo).
--   auth.identities        -> identidades_usuario
--   auth.sessions          -> sesiones (+ nivel_autenticacion como equivalente simplificado
--                            de aal, en vez de una tabla aparte de amr_claims -- ver nota ahí)
--   auth.refresh_tokens    -> NO se replica: Supabase Auth lo gestiona por completo
--                            internamente (rotación, revocación); no hay valor en
--                            duplicarlo, y hacerlo sería justo el antipatrón de "reinventar
--                            hashing/sesiones a mano" que auth-users.md prohíbe.
--   auth.mfa_factors       -> factores_autenticacion
--   auth.mfa_challenges    -> retos_autenticacion
--   auth.mfa_amr_claims    -> NO se replica como tabla aparte; ver nivel_autenticacion en
--                            sesiones.
--   auth.one_time_tokens   -> tokens_autenticacion (patrón genérico por tipo, no una tabla
--                            ad-hoc por caso de uso -- ver nota en esa sección: HOY
--                            password-reset/confirmación de email siguen usando el
--                            mecanismo nativo de Supabase Auth, documentado en
--                            009_identidad_autenticacion.sql; esta tabla es para flujos que
--                            GoTrue no cubre de fábrica, no un reemplazo del flujo nativo).
--   auth.audit_log_entries -> auditoria_autenticacion
--   sso_providers/sso_domains/saml_providers/saml_relay_states -> NO se construyen (fuera
--                            de alcance, ver arriba).
--
-- Todas las tablas nuevas cuelgan de usuario_id (auth.users), no de clientes/profesionales
-- (que son entidades DE NEGOCIO por sede, no de identidad): un dueno_sede o un
-- administrador_plataforma no tienen fila en clientes/profesionales, pero sí necesitan perfil de
-- auth, sesiones y auditoría igual que un cliente o un profesional. tenant_id aparece SOLO donde
-- el negocio pidió explícitamente poder filtrar por sede (sesiones, auditoria_autenticacion)
-- y es NULLABLE: representa el contexto de sede activo cuando es resoluble (login de un
-- profesional/dueno_sede de una sede concreta), no siempre aplica (cliente sin sede aún,
-- administrador_plataforma).

-- ============================================================================
-- 0. Helpers nuevos: "¿el usuario autenticado es staff/dueño de ALGUNA sede donde
--    p_usuario_id tiene un rol?". Necesarios porque perfiles_usuario NO tiene tenant_id
--    propio (es transversal) -- hay que resolverlo vía roles_usuario del usuario objetivo.
--
--    IMPORTANTE (hallazgo real al probar esta migración contra Postgres): un EXISTS inline
--    contra roles_usuario DENTRO de una policy de OTRA tabla NO sirve para esto -- esa
--    subquery corre con los privilegios del rol que hace el request y por lo tanto queda
--    sujeta a roles_usuario_select_propio (usuario_id = auth.uid()), que solo deja ver las
--    PROPIAS filas. Un dueno_sede consultando las filas de roles_usuario de otro usuario
--    (su profesional) vía esa subquery ve CERO filas siempre, así que el EXISTS da falso incluso
--    cuando SÍ debería poder -- no es una fuga, es un falso negativo que rompe la función
--    (confirmado con un UPDATE 0 en pruebas manuales). La solución, igual que el resto del
--    esquema: una función SECURITY DEFINER que bypasea RLS a propósito, ya que internamente
--    solo expone un booleano (nunca las filas crudas de roles_usuario).
create or replace function public.es_personal_de_algun_tenant_del_usuario(p_usuario_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.roles_usuario ru
    where ru.usuario_id = p_usuario_id and public.es_personal_del_tenant(ru.tenant_id)
  );
$$;

create or replace function public.es_dueno_de_algun_tenant_del_usuario(p_usuario_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.roles_usuario ru
    where ru.usuario_id = p_usuario_id and public.es_dueno_del_tenant(ru.tenant_id)
  );
$$;

comment on function public.es_personal_de_algun_tenant_del_usuario(uuid) is
  'true si el usuario autenticado es dueno_sede o profesional de algún negocio donde p_usuario_id tiene un rol en roles_usuario. SECURITY DEFINER a propósito -- ver nota de la sección 0 sobre por qué un EXISTS inline sin esto falla en policies de otras tablas.';
comment on function public.es_dueno_de_algun_tenant_del_usuario(uuid) is
  'true si el usuario autenticado es dueno_sede de alguna sede donde p_usuario_id tiene un rol en roles_usuario. SECURITY DEFINER a propósito -- ver nota de la sección 0.';

-- "¿Es el propio p_usuario_id, o es dueno_sede del tenant p_tenant_id (cuando ese tenant es
-- resoluble), o es administrador_plataforma?" -- patrón repetido literal en sesiones_select/
-- sesiones_update/auditoria_autenticacion_select (hallazgo de duplicidad de dry-guard).
-- p_tenant_id puede ser null (sesión/evento sin sede resuelta): en ese caso la rama de
-- dueno_sede simplemente no aplica, igual que antes de extraer esto a función.
create or replace function public.es_propio_o_dueno_del_tenant_opcional(p_usuario_id uuid, p_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select
    p_usuario_id = auth.uid()
    or (p_tenant_id is not null and public.es_dueno_del_tenant(p_tenant_id))
    or public.es_administrador_plataforma();
$$;

comment on function public.es_propio_o_dueno_del_tenant_opcional(uuid, uuid) is
  'true si el usuario autenticado ES p_usuario_id, o es dueno_sede de p_tenant_id (si no es null), o es administrador_plataforma. Extraído de sesiones_select/sesiones_update/auditoria_autenticacion_select -- mismo patrón repetido 4 veces (hallazgo de dry-guard).';

-- Nota: es_dueno_del_factor(p_factor_id) -- equivalente para retos_autenticacion al patrón
-- es_dueno_de_reserva de 006_reservas.sql -- se define más abajo, junto a la tabla
-- factores_autenticacion (de la que depende), no acá, por el mismo motivo que
-- es_dueno_de_reserva se define en 006 y no en 001: necesita que la tabla ya exista.

-- ============================================================================
-- 1. perfiles_usuario: 1:1 con auth.users. Equivalente enriquecido de auth.users que el
--    negocio SÍ puede leer vía PostgREST/RLS (auth.users no es accesible directo desde ahí).
-- ============================================================================

create table public.perfiles_usuario (
  usuario_id         uuid primary key references auth.users(id) on delete cascade,
  correo_verificado  boolean not null default false,
  telefono_verificado boolean not null default false,
  ultimo_login_at    timestamptz,
  bloqueado_hasta    timestamptz, -- equivalente a auth.users.banned_until: bloqueo administrativo (no ban del propio Supabase Auth, sino "esta cuenta no puede operar en Barberus hasta esta fecha")
  eliminado_at       timestamptz, -- soft-delete de la cuenta a nivel de negocio (espejo de auth.users.deleted_at, no lo reemplaza). SOLO administrador_plataforma puede modificarla -- ver trigger restringir_columnas_perfil_usuario; ni el propio usuario ni un dueno_sede, sin importar sede compartida.
  metadata_app       jsonb not null default '{}'::jsonb, -- equivalente a raw_app_meta_data: solo el sistema (backend/service_role) la escribe, nunca el propio usuario
  metadata_usuario    jsonb not null default '{}'::jsonb, -- equivalente a raw_user_meta_data: preferencias propias editables por el usuario (nombre para mostrar, avatar, etc.)
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

comment on table public.perfiles_usuario is
  'Perfil de auth 1:1 con auth.users, legible desde PostgREST/RLS (auth.users no lo es). No duplica clientes/profesionales (eso sigue siendo la entidad de negocio por sede) -- esto es identidad transversal a todos los roles, incluidos dueno_sede/administrador_plataforma que no tienen fila en clientes ni profesionales.';
comment on column public.perfiles_usuario.bloqueado_hasta is
  'Bloqueo administrativo GLOBAL de la cuenta (todos los negocios de la plataforma), no por sede. SOLO administrador_plataforma puede modificarla -- ver trigger restringir_columnas_perfil_usuario. NO es "dueno_sede suspende a un profesional/cliente de SU sede" (eso ya existe con alcance correcto en clientes.activo/profesionales.activo, columnas tenant-scoped por RLS estándar) -- mezclar ambos conceptos en un solo campo transversal permitía que un dueno_sede bloqueara a alguien de OTRO negocio en toda la plataforma con solo una relación roles_usuario trivial (hallazgo bloqueante de multi-tenant-guard, ver scripts/migrations/APPLIED.md). Distinto también de auth.users.banned_until -- ese es un bloqueo a nivel de Supabase Auth que impide incluso emitir un JWT; este es "no puede operar en Barberus" aunque el login en sí siga funcionando. La app debe chequear los tres (banned_until, bloqueado_hasta, activo de la fila tenant-scoped) donde aplique.';
comment on column public.perfiles_usuario.metadata_app is
  'Solo escribible por sistema (service_role) o administrador_plataforma -- ver trigger restringir_columnas_perfil_usuario. Nunca exponer edición directa al propio usuario NI a un dueno_sede/profesional editando el perfil de otro.';
comment on column public.perfiles_usuario.metadata_usuario is
  'Preferencias libres editables por el propio usuario (nombre para mostrar, avatar, etc.) -- única columna que el branch de autoservicio puede cambiar sin restricción.';

create trigger trg_perfiles_usuario_updated_at
  before update on public.perfiles_usuario
  for each row execute function public.set_updated_at();

alter table public.perfiles_usuario enable row level security;

-- Select: el propio usuario ve su perfil; administrador_plataforma ve cualquiera; staff de
-- una sede ve el perfil de cualquier usuario que tenga un rol en ESA sede (para operar
-- bloqueo/verificación de sus profesionales/clientes) -- resuelto contra roles_usuario, nunca
-- contra un tenant_id propio de esta tabla (no existe: el perfil es transversal).
--
-- DECISIÓN DE PRODUCTO, aceptada a propósito (revisada explícitamente en el ciclo de
-- multi-tenant-guard, no es un descuido): como perfiles_usuario NO tiene tenant_id propio,
-- correo_verificado/telefono_verificado/ultimo_login_at de un usuario son visibles para
-- CUALQUIER sede con la que tenga alguna relación en roles_usuario, aunque el evento
-- (el login, la verificación) haya ocurrido en el contexto de OTRA sede -- y los negocios de
-- la plataforma son independientes entre sí (potenciales competidores), no sub-sedes de
-- un mismo tenant. Se acepta porque son solo 3 campos de estado operativo (no
-- identidades_usuario/factores_autenticacion, que sí son estrictamente self+admin, ver sus
-- policies más abajo) y porque el caso de uso real (dueno_sede necesita saber si SU profesional
-- verificó su cuenta) lo requiere. Si en el futuro esto deja de ser aceptable, la fila
-- correcta a agregar es un "último login POR TENANT" en la fila de roles_usuario (o una
-- tabla de eventos ya filtrada por tenant, como sesiones/auditoria_autenticacion, que SÍ
-- llevan tenant_id) en vez de intentar particionar perfiles_usuario por tenant.
create policy perfiles_usuario_select on public.perfiles_usuario
  for select
  using (
    usuario_id = auth.uid()
    or public.es_administrador_plataforma()
    or public.es_personal_de_algun_tenant_del_usuario(usuario_id)
  );

-- Sin política de INSERT: la única fila legítima la crea trg_crear_perfil_usuario (trigger
-- SECURITY DEFINER sobre auth.users, más abajo) al registrarse el usuario. Ningún cliente de
-- la API crea perfiles a mano ni a nombre de otro usuario.

-- Update: el propio usuario puede tocar su fila (el trigger de abajo restringe qué columnas
-- puede cambiar realmente); dueno_sede puede actualizar el perfil de alguien con rol en su
-- sede (p.ej. corregir correo_verificado/telefono_verificado de un walk-in registrado a
-- mano); administrador_plataforma cualquiera. bloqueado_hasta/eliminado_at NO están en el
-- allow-list de "fila ajena" del trigger de abajo -- ver ese trigger y el comentario de la
-- columna bloqueado_hasta para el porqué.
create policy perfiles_usuario_update on public.perfiles_usuario
  for update
  using (
    usuario_id = auth.uid()
    or public.es_administrador_plataforma()
    or public.es_dueno_de_algun_tenant_del_usuario(usuario_id)
  )
  with check (
    usuario_id = auth.uid()
    or public.es_administrador_plataforma()
    or public.es_dueno_de_algun_tenant_del_usuario(usuario_id)
  );

-- Restringe QUÉ COLUMNAS se pueden tocar en un UPDATE de perfiles_usuario, más allá de QUIÉN
-- puede llegar a la fila (eso ya lo decide la policy de arriba).
--
-- WHITELIST REAL (deny-by-default), no un denylist de columnas conocidas -- corrige un
-- segundo hallazgo bloqueante de multi-tenant-guard sobre la primera versión de este
-- trigger: esa versión solo bloqueaba metadata_app/metadata_usuario por nombre, así que
-- ultimo_login_at quedaba editable sin querer, y CUALQUIER columna que se agregue a
-- perfiles_usuario en el futuro nacería desprotegida por omisión en vez de protegida por
-- default. Acá se compara la fila COMPLETA (to_jsonb) quitando solo las columnas
-- explícitamente permitidas para ese caso -- si sobra cualquier diferencia, se rechaza, sin
-- importar qué columna sea ni si existía cuando se escribió este trigger.
--
--   1. eliminado_at (soft-delete de la CUENTA completa) y bloqueado_hasta (bloqueo GLOBAL de
--      la cuenta en todos los negocios de la plataforma) SIEMPRE requieren administrador_plataforma -- ni el propio
--      usuario ni ningún dueno_sede, sin importar que comparta sede con el usuario objetivo.
--      bloqueado_hasta se sumó a esta regla tras un hallazgo bloqueante posterior: quedaba
--      en el allow-list de "fila ajena", y como esa rama se habilita con
--      es_dueno_de_algun_tenant_del_usuario (true con CUALQUIER rol compartido, incluido un
--      'cliente' que el propio staff puede crear unilateralmente vía roles_usuario_insert,
--      ver 009), un dueno_sede de la sede A podía "atarse" como cliente al dueno_sede o
--      profesional de la sede B con solo conocer su usuario_id/correo, y luego bloquearlo de
--      operar en TODA la plataforma -- sabotaje directo entre negocios competidores. El
--      bloqueo POR SEDE que un dueno_sede sí debe poder aplicar (p.ej. un cliente
--      problemático de SU sede) ya existe con el alcance correcto en clientes.activo /
--      profesionales.activo (tenant-scoped, RLS estándar de 003/005) -- no hacía falta una tabla
--      nueva, solo sacar bloqueado_hasta del perfil transversal.
--   2. Fuera de ese caso, administrador_plataforma no tiene restricción de columnas. Todos
--      los demás quedan sujetos a la whitelist según de quién es la fila:
--        - Fila PROPIA (new.usuario_id = auth.uid()): solo metadata_usuario (+ updated_at,
--          mecánico).
--        - Fila AJENA (llegaste aquí porque la policy de update ya te reconoció como
--          dueno_sede de alguna sede donde el usuario objetivo tiene un rol): solo
--          correo_verificado/telefono_verificado (+ updated_at) -- NUNCA metadata_app
--          (sistema), metadata_usuario (preferencias del USUARIO, no de quien lo
--          administra), bloqueado_hasta ni eliminado_at (ver punto 1).
--
-- Excepción explícita para sincronización interna: sincronizar_perfil_usuario (el trigger
-- sobre auth.users que espeja el soft-delete REAL hecho vía Admin API de Supabase, más
-- abajo) corre sin contexto de JWT (auth.uid()/auth.role() son null ahí, no 'service_role'
-- -- es una llamada interna del sistema, no una request de PostgREST), así que sin esta
-- excepción la protección de eliminado_at del punto 1 también bloqueaba esa sincronización
-- legítima y rompía la transacción cada vez que se soft-eliminaba una cuenta por el flujo
-- estándar (regresión encontrada en revisión). La excepción es una variable de sesión
-- (barberus.contexto) que SOLO sincronizar_perfil_usuario setea, nunca expuesta a
-- PostgREST/anon/authenticated -- no relaja la condición por rol, abre una vía explícita y
-- angosta para ese único caller interno.
create or replace function public.restringir_columnas_perfil_usuario()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  v_columnas_permitidas text[];
begin
  if current_setting('barberus.contexto', true) = 'sync_interno' then
    return new;
  end if;

  if auth.role() = 'service_role' then
    return new;
  end if;

  if public.es_administrador_plataforma() then
    return new;
  end if;

  if new.eliminado_at is distinct from old.eliminado_at then
    raise exception 'Solo administrador_plataforma puede modificar eliminado_at'
      using errcode = '42501';
  end if;

  if new.bloqueado_hasta is distinct from old.bloqueado_hasta then
    raise exception 'Solo administrador_plataforma puede modificar bloqueado_hasta (bloqueo global de la cuenta, no por sede -- usa clientes.activo/profesionales.activo para bloqueo por sede)'
      using errcode = '42501';
  end if;

  if new.usuario_id = auth.uid() then
    -- Autoedición: únicamente metadata_usuario. Sin excepción por rol -- ni siquiera un
    -- dueno_sede editando su PROPIA fila queda exento (hallazgo encontrado y corregido
    -- probando esta migración contra Postgres real: eximirlo reabría auto-escalada).
    v_columnas_permitidas := array['metadata_usuario', 'updated_at'];
  else
    -- Edición de una fila AJENA por staff/dueno_sede: solo los 2 campos de verificación.
    v_columnas_permitidas := array['correo_verificado', 'telefono_verificado', 'updated_at'];
  end if;

  if (to_jsonb(new) - v_columnas_permitidas) is distinct from (to_jsonb(old) - v_columnas_permitidas) then
    raise exception 'Columna no permitida en esta edición de perfiles_usuario'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

comment on function public.restringir_columnas_perfil_usuario() is
  'Whitelist REAL (deny-by-default vía diff de to_jsonb, no un denylist de nombres) de columnas por UPDATE de perfiles_usuario: eliminado_at y bloqueado_hasta solo administrador_plataforma (nunca dueno_sede, sin importar sede compartida -- bloqueado_hasta es global a todos los negocios de la plataforma, no por tenant); fila propia solo metadata_usuario; fila ajena (staff/dueno_sede) solo correo_verificado/telefono_verificado. Excepción explícita vía barberus.contexto para la sincronización interna desde auth.users (soft-delete real). Corrige 2 hallazgos bloqueantes de multi-tenant-guard -- ver scripts/migrations/APPLIED.md.';

create trigger trg_perfiles_usuario_restringir_columnas
  before update on public.perfiles_usuario
  for each row execute function public.restringir_columnas_perfil_usuario();

-- Alta automática: cada usuario nuevo de auth.users obtiene su fila de perfiles_usuario sin
-- intervención de la app. SECURITY DEFINER porque quien dispara el trigger es el rol interno
-- de Supabase Auth (supabase_auth_admin), sin privilegios de escritura sobre public.
create or replace function public.crear_perfil_usuario()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.perfiles_usuario (usuario_id, correo_verificado, telefono_verificado, ultimo_login_at)
  values (new.id, (new.email_confirmed_at is not null), (new.phone_confirmed_at is not null), new.last_sign_in_at)
  on conflict (usuario_id) do nothing;

  return new;
end;
$$;

comment on function public.crear_perfil_usuario() is
  'Trigger AFTER INSERT en auth.users: crea la fila perfiles_usuario correspondiente. on conflict do nothing por idempotencia si algo más ya la creó.';

create trigger trg_crear_perfil_usuario
  after insert on auth.users
  for each row execute function public.crear_perfil_usuario();

-- Sincroniza los campos espejo de auth.users cada vez que cambian (confirmación de
-- email/teléfono, cada login, soft-delete). Mismo motivo SECURITY DEFINER que el trigger de
-- creación.
--
-- set_config('barberus.contexto', 'sync_interno', true) marca esta transacción como
-- sincronización interna del sistema ANTES del UPDATE -- restringir_columnas_perfil_usuario
-- (trigger BEFORE UPDATE de perfiles_usuario) la reconoce como excepción explícita, porque
-- esta llamada corre sin contexto de JWT (auth.uid()/auth.role() son null acá, no
-- 'service_role': no es una request de PostgREST, es Supabase Auth escribiendo auth.users
-- directo, p.ej. al soft-eliminar una cuenta vía Admin API). El tercer argumento `true`
-- hace que sea LOCAL a esta transacción (no persiste ni se filtra a otras) -- nunca se
-- expone a PostgREST/anon/authenticated, así que un cliente no puede auto-otorgarse esta
-- excepción.
create or replace function public.sincronizar_perfil_usuario()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  perform set_config('barberus.contexto', 'sync_interno', true);

  update public.perfiles_usuario
     set correo_verificado = (new.email_confirmed_at is not null),
         telefono_verificado = (new.phone_confirmed_at is not null),
         ultimo_login_at = coalesce(new.last_sign_in_at, ultimo_login_at),
         eliminado_at = new.deleted_at
   where usuario_id = new.id;

  return new;
end;
$$;

comment on function public.sincronizar_perfil_usuario() is
  'Trigger AFTER UPDATE en auth.users (email_confirmed_at, phone_confirmed_at, last_sign_in_at, deleted_at): mantiene perfiles_usuario espejado. No es la fuente de verdad -- esa sigue siendo auth.users. Marca barberus.contexto=sync_interno (local a la transacción) para que restringir_columnas_perfil_usuario no bloquee este UPDATE interno del soft-delete real (eliminado_at).';

create trigger trg_sincronizar_perfil_usuario
  after update of email_confirmed_at, phone_confirmed_at, last_sign_in_at, deleted_at on auth.users
  for each row execute function public.sincronizar_perfil_usuario();

-- ============================================================================
-- 2. identidades_usuario: equivalente a auth.identities. Un registro por método de login
--    vinculado a un usuario (hoy correo/telefono; estructura lista para OAuth social a
--    futuro -- login social en sí NO se implementa en esta migración, solo el esquema).
-- ============================================================================

create table public.identidades_usuario (
  id                     uuid primary key default gen_random_uuid(),
  usuario_id             uuid not null references auth.users(id) on delete cascade,
  proveedor              text not null check (proveedor in ('correo', 'telefono', 'google', 'apple')),
  identificador_proveedor text not null, -- el correo, el teléfono, o el subject id que devuelva el proveedor OAuth
  datos_identidad        jsonb not null default '{}'::jsonb, -- payload crudo devuelto por el proveedor (perfil OAuth, etc.)
  ultimo_login_at        timestamptz,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now(),

  -- Una identidad concreta (p.ej. una cuenta de Google específica) solo puede estar
  -- vinculada a UN usuario de Barberus.
  constraint identidades_usuario_proveedor_identificador_unico unique (proveedor, identificador_proveedor),
  -- Un usuario tiene a lo sumo una identidad vinculada por proveedor (mismo criterio que
  -- auth.identities de Supabase).
  constraint identidades_usuario_usuario_proveedor_unico unique (usuario_id, proveedor)
);

comment on table public.identidades_usuario is
  'Métodos de autenticación vinculados a un usuario (correo, teléfono, y a futuro OAuth social: google/apple). Estructura lista para login social; la lógica de vinculación/desvinculación OAuth no está implementada todavía -- las escrituras hoy las hace el backend/service_role, no hay policy de INSERT/UPDATE/DELETE para PostgREST a propósito.';

create index idx_identidades_usuario_usuario_id on public.identidades_usuario (usuario_id);

create trigger trg_identidades_usuario_updated_at
  before update on public.identidades_usuario
  for each row execute function public.set_updated_at();

alter table public.identidades_usuario enable row level security;

-- Solo lectura propia + admin (más sensible que perfiles_usuario -- es el detalle de CÓMO
-- se autentica alguien, no solo si está verificado). Sin política de staff: un dueno_sede no
-- necesita ver qué proveedores usa un cliente para loguearse.
create policy identidades_usuario_select on public.identidades_usuario
  for select
  using (usuario_id = auth.uid() or public.es_administrador_plataforma());

-- ============================================================================
-- 3. sesiones: metadata de aplicación sobre sesiones activas (dispositivo, IP, nivel de
--    autenticación). NO reemplaza auth.sessions/el JWT -- Supabase/PostgREST sigue validando
--    el JWT en cada request independientemente de esta tabla. Sirve para auditoría de
--    dispositivos, "cerrar sesión en todos lados", y para que el backend aplique el timeout
--    diferenciado por rol documentado en 009_identidad_autenticacion.sql (profesional/dueno_sede:
--    corto + inactividad; cliente: normal), comparando ultima_actividad_at/expira_at.
-- ============================================================================

create table public.sesiones (
  id                  uuid primary key default gen_random_uuid(),
  usuario_id          uuid not null references auth.users(id) on delete cascade,
  tenant_id           uuid null references public.negocios(id) on delete cascade, -- contexto de sede activo en esta sesión, cuando es resoluble (login como staff de una sede concreta); null para cliente sin sede aún o administrador_plataforma
  dispositivo         text, -- descripción legible derivada del user-agent (p.ej. "Chrome en Windows"), la resuelve el backend al crear la fila
  user_agent          text,
  ip                  inet,
  nivel_autenticacion text not null default 'aal1' check (nivel_autenticacion in ('aal1', 'aal2', 'aal3')), -- equivalente simplificado al aal de Supabase: aal1 = password/OTP/magic-link solamente, aal2 = + un factor MFA verificado, aal3 reservado. Reemplaza a auth.mfa_amr_claims: no hace falta una tabla de métodos aparte para lo que el negocio necesita hoy (saber el NIVEL alcanzado, no el detalle de cada claim).
  iniciada_at         timestamptz not null default now(),
  ultima_actividad_at timestamptz not null default now(),
  expira_at           timestamptz not null, -- calculado por el backend al crear la fila, según la política de sesión del rol activo (ver 009)
  cerrada_at          timestamptz, -- null = sesión activa; set en logout explícito o al forzar cierre (dispositivo compartido)
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

comment on table public.sesiones is
  'Metadata de aplicación sobre sesiones (dispositivo/IP/nivel de autenticación/expiración por rol). No es la fuente de verdad de si un JWT es válido -- eso lo resuelve Supabase Auth/PostgREST con el JWT firmado; esta tabla es para UX (tus dispositivos, cerrar sesión remota) y para que el backend aplique el timeout diferenciado por rol.';
comment on column public.sesiones.tenant_id is
  'Negocio activo en esta sesión cuando es resoluble (login de profesional/dueno_sede). Nullable: cliente todavía sin negocio, o administrador_plataforma (ve todos).';
comment on column public.sesiones.nivel_autenticacion is
  'Equivalente simplificado al aal (assurance level) de Supabase: aal1 sin MFA, aal2 con un factor MFA verificado en esta sesión. La lógica que lo eleva de aal1 a aal2 no está implementada todavía (depende de factores_autenticacion/retos_autenticacion).';

create index idx_sesiones_usuario_id on public.sesiones (usuario_id);
create index idx_sesiones_tenant_id on public.sesiones (tenant_id);
create index idx_sesiones_usuario_activas on public.sesiones (usuario_id) where cerrada_at is null;

create trigger trg_sesiones_updated_at
  before update on public.sesiones
  for each row execute function public.set_updated_at();

alter table public.sesiones enable row level security;

-- Select: el propio usuario ve sus sesiones; dueno_sede audita sesiones con tenant_id de su
-- sede (dispositivo compartido en el local); administrador_plataforma ve todas.
create policy sesiones_select on public.sesiones
  for select
  using (public.es_propio_o_dueno_del_tenant_opcional(usuario_id, tenant_id));

-- Insert: el backend crea la fila en nombre del propio usuario al iniciar sesión. Además de
-- ser la propia fila, si viene con tenant_id (login como staff de una sede concreta) ese
-- tenant_id debe ser uno donde el usuario REALMENTE tiene un rol (es_miembro_del_tenant) --
-- si no, cualquier usuario podía insertar una sesión propia con el tenant_id de una sede
-- ajena y ensuciar la auditoría que vería el dueño legítimo de esa sede (caso borde
-- encontrado en revisión, no en las pruebas iniciales).
create policy sesiones_insert on public.sesiones
  for insert
  with check (
    (usuario_id = auth.uid() and (tenant_id is null or public.es_miembro_del_tenant(tenant_id)))
    or auth.role() = 'service_role'
  );

-- Update: el propio usuario puede refrescar ultima_actividad_at o autocerrar su sesión;
-- dueno_sede/administrador_plataforma pueden forzar el cierre de una sesión ajena
-- (cerrada_at) -- p.ej. sospecha de dispositivo compartido sin cerrar turno.
create policy sesiones_update on public.sesiones
  for update
  using (public.es_propio_o_dueno_del_tenant_opcional(usuario_id, tenant_id))
  with check (public.es_propio_o_dueno_del_tenant_opcional(usuario_id, tenant_id));

-- ============================================================================
-- 4. factores_autenticacion + retos_autenticacion: equivalentes a auth.mfa_factors y
--    auth.mfa_challenges. Estructura MFA-ready -- la lógica de verificación TOTP/WebAuthn NO
--    se implementa en esta migración, solo el esquema para no bloquear a futuro.
-- ============================================================================

create table public.factores_autenticacion (
  id              uuid primary key default gen_random_uuid(),
  usuario_id      uuid not null references auth.users(id) on delete cascade,
  tipo            text not null check (tipo in ('totp', 'telefono', 'webauthn')),
  estado          text not null default 'no_verificado' check (estado in ('no_verificado', 'verificado')),
  nombre_amistoso text, -- p.ej. "iPhone de Juan", lo elige el usuario al registrar el factor
  secreto         jsonb, -- placeholder del secreto/clave pública del factor (TOTP seed, credencial WebAuthn); DEBE cifrarse en reposo (p.ej. Supabase Vault) antes de implementar la lógica real -- nunca escribir el secreto en claro
  ultimo_uso_at   timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

comment on table public.factores_autenticacion is
  'Equivalente a auth.mfa_factors. Estructura lista para MFA (TOTP/telefono/WebAuthn); la lógica de enrolamiento/verificación no está implementada. secreto debe cifrarse en reposo antes de guardar datos reales -- no usar esta columna en claro en producción.';
comment on column public.factores_autenticacion.secreto is
  'Placeholder para el secreto/clave del factor. Cifrar en reposo (Supabase Vault u otro KMS) antes de implementar la lógica real -- no se escribe nada sensible en claro en esta migración.';

create index idx_factores_autenticacion_usuario_id on public.factores_autenticacion (usuario_id);

create trigger trg_factores_autenticacion_updated_at
  before update on public.factores_autenticacion
  for each row execute function public.set_updated_at();

alter table public.factores_autenticacion enable row level security;

-- Solo el propio usuario (y administrador_plataforma para soporte/recuperación de cuenta) --
-- nunca staff de sede: esto es tan sensible como una contraseña.
create policy factores_autenticacion_select on public.factores_autenticacion
  for select
  using (usuario_id = auth.uid() or public.es_administrador_plataforma());

create policy factores_autenticacion_insert on public.factores_autenticacion
  for insert
  with check (usuario_id = auth.uid());

create policy factores_autenticacion_update on public.factores_autenticacion
  for update
  using (usuario_id = auth.uid())
  with check (usuario_id = auth.uid());

create policy factores_autenticacion_delete on public.factores_autenticacion
  for delete
  using (usuario_id = auth.uid() or public.es_administrador_plataforma());

create table public.retos_autenticacion (
  id             uuid primary key default gen_random_uuid(),
  factor_id      uuid not null references public.factores_autenticacion(id) on delete cascade,
  ip             inet,
  creado_at      timestamptz not null default now(),
  verificado_at  timestamptz, -- null = reto pendiente/vencido; set al validarse el código/credencial
  expira_at      timestamptz not null
);

comment on table public.retos_autenticacion is
  'Equivalente a auth.mfa_challenges: un intento de verificación de un factor concreto (código TOTP enviado, reto WebAuthn emitido). La lógica de emisión/validación no está implementada -- solo el esquema.';

create index idx_retos_autenticacion_factor_id on public.retos_autenticacion (factor_id);

alter table public.retos_autenticacion enable row level security;

-- "¿Es el usuario autenticado el dueño (usuario_id) del factor MFA p_factor_id?" -- mismo
-- patrón que es_dueno_de_reserva (006_reservas.sql): resuelve la relación vía un id
-- intermedio en vez de repetir el join inline en cada policy (hallazgo de duplicidad de
-- dry-guard sobre retos_autenticacion, que repetía este join 3 veces). Se define acá, junto
-- a factores_autenticacion (de la que depende), no en la sección 0 -- mismo motivo que
-- es_dueno_de_reserva se define en 006_reservas.sql y no en 001.
create or replace function public.es_dueno_del_factor(p_factor_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.factores_autenticacion fa
    where fa.id = p_factor_id and fa.usuario_id = auth.uid()
  );
$$;

comment on function public.es_dueno_del_factor(uuid) is
  'true si el usuario autenticado ES el dueño (usuario_id) del factor MFA p_factor_id. Mismo patrón que es_dueno_de_reserva en 006_reservas.sql.';

-- Acceso vía el dueño del factor (es_dueno_del_factor), mismo criterio que arriba: solo el
-- propio usuario y administrador_plataforma.
create policy retos_autenticacion_select on public.retos_autenticacion
  for select
  using (public.es_dueno_del_factor(factor_id) or public.es_administrador_plataforma());

create policy retos_autenticacion_insert on public.retos_autenticacion
  for insert
  with check (public.es_dueno_del_factor(factor_id));

create policy retos_autenticacion_update on public.retos_autenticacion
  for update
  using (public.es_dueno_del_factor(factor_id))
  with check (public.es_dueno_del_factor(factor_id));

-- ============================================================================
-- 5. tokens_autenticacion: patrón genérico de token de un solo uso, equivalente a
--    auth.one_time_tokens, PERO para flujos que Supabase Auth no cubre nativamente. HOY
--    recuperación de contraseña y confirmación de email siguen el mecanismo nativo de
--    GoTrue (ver nota en 009_identidad_autenticacion.sql) -- esta tabla no los reemplaza.
--    Existe para no crear una tabla ad-hoc por cada caso futuro (confirmación de un teléfono
--    de contacto adicional, cambio de email con doble confirmación propia de la app, etc.).
-- ============================================================================

create table public.tokens_autenticacion (
  id         uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references auth.users(id) on delete cascade,
  tipo       text not null check (tipo in ('recuperacion_contrasena', 'confirmacion_correo', 'confirmacion_telefono', 'cambio_correo')),
  token_hash text not null, -- SOLO el hash (p.ej. sha256) del token -- nunca el token en claro, mismo criterio que GoTrue
  datos      jsonb not null default '{}'::jsonb, -- p.ej. el correo NUEVO destino en un cambio_correo
  creado_at  timestamptz not null default now(),
  expira_at  timestamptz not null,
  usado_at   timestamptz, -- null = vigente; se setea al canjear, hace el token de un solo uso

  constraint tokens_autenticacion_hash_unico unique (token_hash)
);

comment on table public.tokens_autenticacion is
  'Patrón genérico de token de un solo uso por tipo, para flujos de confirmación/recuperación que Supabase Auth no cubre de fábrica. NO se usa hoy para recuperacion_contrasena/confirmacion_correo de la cuenta principal -- esos siguen el flujo nativo de GoTrue. Sin políticas RLS de PostgREST a propósito: tabla accesible solo vía service_role (backend), nunca desde el cliente.';

create index idx_tokens_autenticacion_usuario_tipo on public.tokens_autenticacion (usuario_id, tipo);
create index idx_tokens_autenticacion_expira_at on public.tokens_autenticacion (expira_at);

alter table public.tokens_autenticacion enable row level security;
-- Sin ninguna política: RLS habilitado + cero policies = ningún rol de PostgREST
-- (anon/authenticated) puede leer ni escribir esta tabla, ni siquiera su propio token.
-- Solo service_role (bypassa RLS) la usa, siempre desde el backend.

-- ============================================================================
-- 6. auditoria_autenticacion: equivalente a auth.audit_log_entries. Importante para el caso
--    de dispositivo compartido en profesional/dueno_sede (auth-users.md).
-- ============================================================================

create table public.auditoria_autenticacion (
  id         uuid primary key default gen_random_uuid(),
  usuario_id uuid null references auth.users(id) on delete set null, -- null permitido: p.ej. login_fallido con un correo que no corresponde a ninguna cuenta -- y justamente por eso NO se debe inferir/crear un usuario_id ahí (reintroduciría la fuga de enumeración de usuarios)
  tenant_id  uuid null references public.negocios(id) on delete set null, -- contexto de sede si es resoluble, mismo criterio que sesiones.tenant_id
  evento     text not null check (evento in ('login', 'logout', 'login_fallido', 'contrasena_cambiada', 'contrasena_recuperada', 'bloqueo_aplicado', 'bloqueo_removido', 'mfa_activado', 'mfa_desactivado', 'correo_cambiado')),
  ip         inet,
  user_agent text,
  metadata   jsonb not null default '{}'::jsonb,
  creado_at  timestamptz not null default now()
);

comment on table public.auditoria_autenticacion is
  'Equivalente a auth.audit_log_entries. Registra eventos de auth (login/logout/fallidos/cambios de contraseña/bloqueo/MFA) para auditoría -- clave para detectar mal uso de un dispositivo compartido en profesional/dueno_sede. Solo la escribe el backend (service_role); no hay política de INSERT/UPDATE/DELETE para PostgREST a propósito.';
comment on column public.auditoria_autenticacion.usuario_id is
  'Nullable a propósito: un login_fallido contra un correo inexistente no debe inventar ni resolver un usuario_id (evita reintroducir enumeración de usuarios vía la auditoría misma).';

create index idx_auditoria_autenticacion_usuario_id on public.auditoria_autenticacion (usuario_id);
create index idx_auditoria_autenticacion_tenant_id on public.auditoria_autenticacion (tenant_id);
create index idx_auditoria_autenticacion_creado_at on public.auditoria_autenticacion (creado_at desc);

alter table public.auditoria_autenticacion enable row level security;

-- Solo lectura: administrador_plataforma ve todo; dueno_sede ve eventos de su propia sede;
-- cualquier usuario ve sus propios eventos (p.ej. "¿fui yo quien inició sesión ahí?").
-- Ninguna policy de escritura: solo service_role (backend) inserta filas de auditoría.
create policy auditoria_autenticacion_select on public.auditoria_autenticacion
  for select
  using (public.es_propio_o_dueno_del_tenant_opcional(usuario_id, tenant_id));
