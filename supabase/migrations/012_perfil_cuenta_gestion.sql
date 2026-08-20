-- Migracion: gestion de cuenta -- perfil basico tipado, consentimiento de terminos y
-- onboarding sobre perfiles_usuario (010_identidad_extendida.sql).
-- Autor: db-schema
--
-- Contexto: antes de construir el modulo de gestion de cuenta se audito que del esquema de
-- identidad ya alcanza vs. que falta genuinamente. Resultado (detalle completo en
-- scripts/migrations/APPLIED.md):
--   1. Nombre/avatar: SE PROMUEVEN de metadata_usuario (jsonb) a columnas propias tipadas
--      (nombre_completo, avatar_url) -- ver razon abajo, junto a la tabla.
--   2. Roles/permisos: rol_app (001_extensiones_y_helpers.sql) + roles_usuario YA alcanzan.
--      Sin caso de uso concreto de permisos granulares dentro de un rol -- NO se agrega una
--      tabla de permisos.
--   3. Consentimiento de terminos y condiciones: NO existia. Se agrega en esta migracion.
--   4. Onboarding inicial: NO existia. Se agrega en esta migracion.
--   5. Cierre de sesion en todos los dispositivos: sesiones YA alcanza (cerrada_at +
--      sesiones_update ya permite que el propio usuario cierre cualquiera de sus sesiones,
--      una o todas en un solo UPDATE ... WHERE usuario_id = auth.uid()). Sin cambio de
--      esquema.
--   6. Verificacion de correo obligatoria en registro: ya resuelto por
--      supabase/config.toml ([auth.email] enable_confirmations = true). Sin cambio de
--      esquema.
--
-- Por que nombre_completo/avatar_url pasan a columna propia (y dejan de vivir en
-- metadata_usuario, donde 010_identidad_extendida.sql los sugeria como ejemplo): a
-- diferencia de clientes.nombre_completo/profesionales.nombre_completo (identidad DE NEGOCIO
-- por sede), un dueno_sede o un administrador_plataforma no tienen fila en clientes ni
-- profesionales -- perfiles_usuario es hoy la UNICA fuente de "como se llama esta cuenta" para
-- esos roles, y se va a leer en practicamente cada pantalla de la app (barra superior,
-- selector de sesion activa, lista de dispositivos). Un valor de tipo claro (text), leido en
-- caliente y sin necesidad de la flexibilidad de un blob libre, encaja en el criterio de
-- database.md de preferir columna tipada sobre jsonb. No se agrega ningun check de formato/
-- longitud -- mismo criterio ya usado en clientes.nombre_completo/profesionales.nombre_completo,
-- que tampoco lo tienen.
--
-- metadata_usuario NO se elimina: sigue siendo el lugar para preferencias verdaderamente
-- libres/opcionales que no ameritan columna propia todavia (p.ej. tema claro/oscuro, idioma
-- preferido) -- no hay caso de uso concreto de esas hoy, asi que no se agregan columnas para
-- ellas tampoco.

-- ============================================================================
-- 1. Columnas nuevas en perfiles_usuario.
-- ============================================================================

alter table public.perfiles_usuario
  add column nombre_completo         text,
  add column avatar_url              text,
  add column terminos_aceptados_at   timestamptz,
  add column terminos_version        text,
  add column onboarding_completado_at timestamptz;

comment on column public.perfiles_usuario.nombre_completo is
  'Nombre para mostrar de la cuenta, transversal a todos los roles (a diferencia de clientes.nombre_completo/profesionales.nombre_completo, que son identidad DE NEGOCIO por sede). Nullable: se completa en el onboarding, no al crear la fila. Editable solo por el propio usuario -- ver restringir_columnas_perfil_usuario.';
comment on column public.perfiles_usuario.avatar_url is
  'URL de la imagen de avatar de la cuenta. Nullable. Editable solo por el propio usuario -- ver restringir_columnas_perfil_usuario. La subida del archivo en si (Supabase Storage) es responsabilidad de frontend/backend, esta columna solo guarda la URL resultante.';
comment on column public.perfiles_usuario.terminos_aceptados_at is
  'Momento en que el usuario acepto la version de terminos_version. Null = nunca acepto (o la version cambio y se le exige aceptar de nuevo -- ver terminos_version). Editable solo por el propio usuario -- ver restringir_columnas_perfil_usuario.';
comment on column public.perfiles_usuario.terminos_version is
  'Identificador de la version de terminos y condiciones aceptada (p.ej. "2026-08-20"), no un booleano -- permite volver a exigir consentimiento cuando la app compare esta version contra la version vigente y no coincidan. Se setea junto con terminos_aceptados_at en el mismo UPDATE.';
comment on column public.perfiles_usuario.onboarding_completado_at is
  'Momento en que el usuario completo el flujo de onboarding inicial. Null = onboarding pendiente -- la app lo consulta en cada carga para decidir si redirige. Editable solo por el propio usuario -- ver restringir_columnas_perfil_usuario.';

-- Indice parcial: la consulta de alto trafico es "acaso ESTE usuario ya completo el
-- onboarding" (lookup directo por PK usuario_id, no necesita indice adicional), pero se
-- agrega este parcial pensando en el caso de uso simetrico de administracion/analitica
-- ("cuantos usuarios con onboarding pendiente hay"), que si barre la tabla completa
-- filtrando por la condicion NULL -- mismo patron que idx_sesiones_usuario_activas en
-- 010_identidad_extendida.sql.
create index idx_perfiles_usuario_onboarding_pendiente on public.perfiles_usuario (usuario_id)
  where onboarding_completado_at is null;

-- ============================================================================
-- 2. Ampliar la whitelist de autoedicion de restringir_columnas_perfil_usuario
--    (009/010 ya la definieron; create or replace la reemplaza completa, no la parchea).
-- ============================================================================

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
    -- Autoedicion: metadata_usuario + los campos de cuenta que introduce esta migracion
    -- (nombre/avatar, aceptacion de terminos, onboarding) -- todos datos que solo tiene
    -- sentido que el propio usuario declare sobre si mismo, igual criterio que
    -- metadata_usuario ya tenia.
    v_columnas_permitidas := array[
      'metadata_usuario', 'nombre_completo', 'avatar_url',
      'terminos_aceptados_at', 'terminos_version', 'onboarding_completado_at',
      'updated_at'
    ];
  else
    -- Edicion de una fila AJENA por staff/dueno_sede: sin cambios respecto a 010 -- solo los
    -- 2 campos de verificacion. nombre/avatar/terminos/onboarding de OTRO usuario siguen
    -- fuera del alcance de un dueno_sede, mismo criterio que ya protegia metadata_usuario.
    v_columnas_permitidas := array['correo_verificado', 'telefono_verificado', 'updated_at'];
  end if;

  if (to_jsonb(new) - v_columnas_permitidas) is distinct from (to_jsonb(old) - v_columnas_permitidas) then
    raise exception 'Columna no permitida en esta edicion de perfiles_usuario'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

comment on function public.restringir_columnas_perfil_usuario() is
  'Whitelist REAL (deny-by-default via diff de to_jsonb, no un denylist de nombres) de columnas por UPDATE de perfiles_usuario: eliminado_at y bloqueado_hasta solo administrador_plataforma; fila propia permite metadata_usuario + nombre_completo/avatar_url/terminos_aceptados_at/terminos_version/onboarding_completado_at (agregados en 012_perfil_cuenta_gestion.sql); fila ajena (staff/dueno_sede) solo correo_verificado/telefono_verificado. Excepcion explicita via barberus.contexto para la sincronizacion interna desde auth.users.';
