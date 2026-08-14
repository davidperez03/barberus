-- Migración: identidad y autenticación (roles_usuario escribible + reautenticación sensible)
-- Autor: auth-users
--
-- 001_extensiones_y_helpers.sql dejó roles_usuario con SOLO política de SELECT propio, con
-- esta nota explícita: "Escritura de roles queda fuera de este esquema: la gestiona
-- auth-users vía función/endpoint controlado (...), nunca INSERT directo del cliente."
-- Esta migración cierra esa deuda: agrega INSERT/DELETE controlados por rol (nunca UPDATE,
-- ver más abajo) y exige reautenticación reciente para cambios sensibles de contacto en
-- clientes (correo/telefono).
--
-- El "perfil de auth" enriquecido (correo/teléfono verificado, último login, bloqueo
-- administrativo, soft-delete, metadata) y el resto de la estructura estilo auth.* de
-- Supabase (identidades vinculadas, sesiones, MFA-ready, tokens de un solo uso, auditoría)
-- se modelan en 010_identidad_extendida.sql, en UNA tabla perfiles_usuario 1:1 con
-- auth.users (no duplicada por tenant en clientes/barberos/dueños) — ver esa migración para
-- el detalle y el porqué de esa decisión de diseño.
--
-- Fuera de alcance de SQL (se resuelven en Supabase Auth / capa de app, documentado en
-- docs/ARCHITECTURE.md, no en el esquema):
--   - Login email+password y OTP/magic link para clientes: supabase-js
--     (signInWithPassword / signInWithOtp), sin tablas propias.
--   - Recuperación de contraseña: resetPasswordForEmail + verifyOtp(type='recovery') de
--     Supabase Auth. El token vive en el esquema auth (flow_state), expira corto y es de un
--     solo uso por diseño de GoTrue — no se reimplementa a mano.
--   - Mensajes de login que no filtran si el email existe: comportamiento ya nativo de
--     Supabase Auth (signInWithPassword devuelve el mismo error genérico exista o no la
--     cuenta; resetPasswordForEmail siempre responde "ok"). Responsabilidad de
--     frontend-nextjs/backend-fastapi: no agregar un endpoint propio de "¿existe este
--     email?" que reintroduzca la fuga.
--   - Política de sesión/inactividad por rol (expiración corta + logout por inactividad
--     para barbero/dueno_sede, normal para cliente): GoTrue configura el JWT/refresh token
--     a nivel de PROYECTO, no por rol, así que la diferenciación real es de app: un timer de
--     inactividad en frontend-nextjs que llama auth.signOut() tras ~15 min sin interacción
--     SOLO cuando el rol activo de la sesión es barbero/dueno_sede (se resuelve leyendo
--     roles_usuario, igual que cualquier otra decisión de autorización). No se modela como
--     columna de "última actividad" escrita en cada request: eso sería una escritura por
--     request a la escala de las 20 sedes, contradice la guía de performance de
--     database.md, y un timer client-side ya resuelve el caso de uso (dispositivo
--     compartido en el local) sin ese costo.

-- ============================================================================
-- 1. roles_usuario: INSERT/DELETE controlados por rol. Base de la asignación de roles.
-- ============================================================================

-- Quién puede crear qué fila de rol, y para quién:
--   - cliente se autoasigna 'cliente' (flujo "primera reserva en una sede": el backend
--     hace INSERT roles_usuario -> INSERT clientes en la misma transacción, en ese orden,
--     porque clientes_insert exige es_cliente_del_tenant(tenant_id), que lee esta tabla).
--   - staff de la sede (dueno_sede o barbero) puede registrar la cuenta de un cliente
--     walk-in (p.ej. para mandarle luego un magic link) — nunca su PROPIO rol vía este
--     branch, porque el branch exige rol = 'cliente' explícito, no el rol de quien inserta.
--   - solo dueno_sede (es_dueno_del_tenant ya incluye administrador_plataforma) da de alta
--     un barbero en SU sede — un barbero no puede contratar a otro barbero.
--   - solo administrador_plataforma da de alta un dueno_sede o a otro
--     administrador_plataforma — ningún dueno_sede puede autoasignarse ni asignarle a otro
--     ese rol (cierra el vector de escalamiento de privilegios más obvio de esta tabla).
create policy roles_usuario_insert on public.roles_usuario
  for insert
  with check (
    (rol = 'cliente' and usuario_id = auth.uid())
    or (rol = 'cliente' and public.es_personal_del_tenant(tenant_id))
    or (rol = 'barbero' and public.es_dueno_del_tenant(tenant_id))
    or (rol in ('dueno_sede', 'administrador_plataforma') and public.es_administrador_plataforma())
  );

-- Revocar acceso: administrador_plataforma borra cualquier fila; dueno_sede solo puede
-- revocar barbero/cliente de SU propia sede (nunca una fila dueno_sede/administrador_plataforma
-- — ni siquiera la suya propia, evita que un dueno_sede se auto-bloquee o bloquee a otro
-- dueno_sede por error/abuso; esa baja la hace administrador_plataforma).
create policy roles_usuario_delete on public.roles_usuario
  for delete
  using (
    public.es_administrador_plataforma()
    or (rol in ('cliente', 'barbero') and public.es_dueno_del_tenant(tenant_id))
  );

-- Deliberadamente SIN política de UPDATE (RLS deniega por defecto si no hay policy para el
-- comando, incluso para administrador_plataforma): un cambio de rol es DELETE + INSERT, no
-- un UPDATE de la columna rol. Evita la ambigüedad de "¿quién puede mover a alguien de
-- cliente a dueno_sede con un solo PATCH?" — con delete+insert, cada paso pasa otra vez por
-- las reglas de arriba (revocar exige la regla de delete, otorgar el rol nuevo exige la
-- regla de insert correspondiente a ESE rol), así que no hay atajo de un paso para escalar
-- privilegios.

comment on policy roles_usuario_insert on public.roles_usuario is
  'Cliente se autoasigna su propio rol cliente; staff/dueno_sede/administrador_plataforma asignan según la tabla de alcance en auth-users.md. Nunca autoservicio para dueno_sede/administrador_plataforma/barbero.';
comment on policy roles_usuario_delete on public.roles_usuario is
  'administrador_plataforma revoca cualquier rol; dueno_sede solo revoca barbero/cliente de su propia sede. Sin política de UPDATE a propósito (ver comentario en la migración).';

-- Índice de soporte para lookups de "todas las filas de cliente de este usuario_id, en
-- cualquier sede" (p.ej. el propio usuario viendo sus perfiles en distintas barberías) --
-- independiente del perfil de auth centralizado de 010_identidad_extendida.sql. El índice
-- único ya existente (idx_clientes_tenant_usuario_unico) es (tenant_id, usuario_id) y no
-- sirve para un filtro que no fija tenant_id primero.
--
-- Nombre a propósito DISTINTO de "idx_clientes_usuario_id" (nombre de un índice ÚNICO
-- GLOBAL que 005_clientes.sql eliminó por ser un hallazgo de seguridad bloqueante --
-- contradecía "cliente aislado por sede", ver esa migración y la sección "Corrección
-- post-auditoría" de este archivo). Este índice NO reintroduce ese bug -- es NO único
-- (varias filas de clientes, una por tenant, pueden compartir usuario_id; solo acelera el
-- filtro, no restringe cardinalidad) -- pero reciclar el mismo nombre habría sido una trampa
-- para el próximo auditor que lo viera en un `\d clientes` y asumiera que es el índice
-- eliminado.
create index idx_clientes_usuario_id_cualquier_tenant on public.clientes (usuario_id) where usuario_id is not null;

-- ============================================================================
-- 2. Reautenticación reciente para cambios sensibles en clientes (correo/telefono).
--    "Cambios de datos sensibles (email, teléfono) requieren reautenticación o
--    confirmación, no un simple PATCH silencioso" (auth-users.md). Solo aplica a
--    clientes: es la única tabla con branch de autoservicio (usuario_id = auth.uid()) en su
--    política de UPDATE -- barberos_update NO tiene ese branch (solo dueno_sede edita
--    barberos hoy, ver 003_barberos.sql), así que no hay autoservicio que restringir ahí.
-- ============================================================================

-- Exige que el JWT actual (claim "iat") tenga menos de 10 minutos cuando el propio cliente
-- (no staff, no service_role) cambia su correo/telefono. auth.jwt()/auth.role() son
-- funciones estándar de Supabase que leen el JWT de la request actual -- no hacen falta
-- columnas nuevas. service_role (llamadas de backend con la service key, sin JWT de un
-- usuario final) queda exento: ese contexto ya resolvió su propia autorización en otra capa
-- y no tiene un "iat" de sesión de usuario que evaluar.
create or replace function public.exigir_reautenticacion_clientes()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  v_iat bigint;
begin
  if auth.role() = 'service_role' or public.es_personal_del_tenant(new.tenant_id) then
    return new;
  end if;

  if new.correo is distinct from old.correo or new.telefono is distinct from old.telefono then
    v_iat := nullif(auth.jwt() ->> 'iat', '')::bigint;
    if v_iat is null or now() - to_timestamp(v_iat) > interval '10 minutes' then
      raise exception 'Cambiar correo o telefono requiere iniciar sesion de nuevo (reautenticacion reciente)'
        using errcode = '42501';
    end if;
  end if;

  return new;
end;
$$;

comment on function public.exigir_reautenticacion_clientes() is
  'Bloquea que un cliente cambie su propio correo/telefono con un JWT de más de 10 minutos -- fuerza reautenticación reciente en vez de un PATCH silencioso. No aplica a staff ni a service_role.';

create trigger trg_clientes_exigir_reautenticacion
  before update on public.clientes
  for each row execute function public.exigir_reautenticacion_clientes();
