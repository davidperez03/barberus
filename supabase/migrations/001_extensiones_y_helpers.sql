-- Migración: extensiones y helpers de multi-tenant
-- Autor: architect
--
-- Prepara la base para RLS multi-tenant en los negocios de la plataforma:
--   - extensiones necesarias (uuid, exclusion constraints por rango)
--   - tabla roles_usuario: mapea auth.users -> (tenant_id, rol). Un mismo usuario_id PUEDE
--     tener varias filas (una por tenant): p.ej. dueno_sede en la sede A y cliente en la
--     sede B. Es una decisión de negocio válida, no un caso raro — ver 005_clientes.sql.
--   - funciones helper SECURITY DEFINER usadas en TODAS las políticas RLS, siempre
--     parametrizadas por el tenant_id de la FILA que se está evaluando (nunca por un
--     "tenant actual" global e implícito — ver nota de auditoría más abajo)
--   - función genérica de trigger para mantener updated_at
--
-- Decisión de diseño: en vez de current_setting('app.current_tenant') (requiere que
-- la app haga SET en cada conexión, frágil con el connection pooler de Supabase/PostgREST),
-- se usa el patrón idiomático de Supabase: auth.uid() + tabla de roles. Cada request
-- autenticado ya trae auth.uid() resuelto por el JWT sin trabajo adicional del backend.
--
-- Nota de auditoría (multi-tenant-guard + dry-guard, corregida en esta versión): la primera
-- versión de este archivo tenía current_tenant_id()/current_user_role(), dos funciones que
-- resolvían "el tenant/rol actual" con `... where usuario_id = auth.uid() limit 1` SIN
-- order by. Eso es indeterminado en cuanto un usuario tiene más de una fila en
-- roles_usuario (que es exactamente el caso legítimo de dueno_sede-en-A + cliente-en-B). Se
-- ELIMINARON esas dos funciones — no quedó ningún caso de uso legítimo tras el refactor de
-- las policies (ver abajo) y dejarlas como "utilidad genérica para la app" solo trasladaría
-- el mismo bug a otra capa. En su lugar, toda policy recibe el tenant_id de la fila que
-- evalúa y lo pasa explícito a estas funciones — no hay "tenant actual" implícito en el
-- esquema.
--
-- Nota de idioma: nombres de dominio del negocio van en español (tablas, columnas,
-- estados, y también los valores del enum de rol: administrador_plataforma, dueno_sede,
-- profesional, cliente — catálogo canónico definido en auth-users.md). `tenant_id`, `id`,
-- `created_at`, `updated_at`, y los sufijos de política (_select/_insert/_update/_delete)
-- se dejan en inglés a propósito: son mecánica técnica genérica del multi-tenant/RLS,
-- reutilizada igual en TODAS las tablas sin importar el idioma del dominio, y `tenant_id`
-- en particular ya está fijado como convención literal en las reglas de otros agentes
-- (architect.md, multi-tenant-guard.md, database.md) — renombrarlo rompería sus checklists.
--
-- Criterio para las funciones helper de RLS: si la función encapsula lógica de negocio que
-- nombra roles/conceptos específicos del dominio, va en español; si es un accessor genérico
-- que no decide nada de negocio, se queda en inglés como mecánica técnica.
--   - es_administrador_plataforma(), es_miembro_del_tenant(), es_personal_del_tenant(),
--     es_dueno_del_tenant(), es_cliente_del_tenant() (las 3 últimas definidas aquí abajo) y,
--     más adelante, es_dueno_del_cliente() (005_clientes.sql) y es_dueno_de_reserva()
--     (006_reservas.sql — definidas ahí y no aquí porque dependen de tablas que todavía no
--     existen en esta migración): TODAS van en español — cada una encapsula una decisión de
--     negocio ("¿este usuario pertenece a este negocio?", "¿es staff de este negocio?",
--     "¿es su dueño?", "¿es este cliente específico?") y se leen como una pregunta de
--     negocio en cada policy. TODAS reciben el id de la fila que evalúan como parámetro
--     explícito — ninguna asume un "tenant/cliente actual" implícito.
--   - set_updated_at(): se queda en inglés — mecánica técnica pura, no decide nada de
--     negocio.
--
-- Los identificadores en español se escriben sin tildes ni "ñ" (dueno_sede, no dueño_sede)
-- para evitar problemas de identificadores entre comillas y de locale en Postgres.

create extension if not exists pgcrypto;   -- gen_random_uuid()
create extension if not exists btree_gist; -- exclusion constraints con uuid + tstzrange

-- Roles del sistema (ver .claude/agents/auth-users.md). administrador_plataforma no tiene tenant_id
-- (ve todos los negocios); el resto SIEMPRE está atado a un único negocio, pero un mismo
-- usuario_id puede tener varias filas (una por tenant).
do $$
begin
  if not exists (select 1 from pg_type where typname = 'rol_app') then
    create type public.rol_app as enum ('administrador_plataforma', 'dueno_sede', 'profesional', 'cliente');
  end if;
end $$;

create table if not exists public.roles_usuario (
  id          uuid primary key default gen_random_uuid(),
  usuario_id  uuid not null references auth.users(id) on delete cascade,
  tenant_id   uuid null, -- FK real se agrega en 002_negocios.sql una vez existe negocios
  rol         public.rol_app not null,
  created_at  timestamptz not null default now(),
  constraint roles_usuario_tenant_requerido_salvo_administrador_plataforma
    check (
      (rol = 'administrador_plataforma' and tenant_id is null)
      or (rol <> 'administrador_plataforma' and tenant_id is not null)
    ),
  constraint roles_usuario_usuario_tenant_unico unique (usuario_id, tenant_id)
);

comment on table public.roles_usuario is
  'Mapea un usuario de auth.users a su rol dentro de un negocio (tenant). Un mismo usuario_id puede tener varias filas (una por tenant). Base de todas las políticas RLS.';

alter table public.roles_usuario enable row level security;

-- Cualquier usuario autenticado puede leer su(s) propia(s) fila(s) de rol (necesario para
-- que el frontend sepa qué tenants/roles tiene). Nadie puede leer roles de otros usuarios
-- salvo administrador_plataforma. Escritura de roles queda fuera de este esquema: la
-- gestiona auth-users vía función/endpoint controlado (alta de profesional, alta de dueno_sede,
-- etc.), nunca INSERT directo del cliente.
create policy roles_usuario_select_propio on public.roles_usuario
  for select
  using (usuario_id = auth.uid());

create or replace function public.es_administrador_plataforma()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.roles_usuario
    where usuario_id = auth.uid() and rol = 'administrador_plataforma'
  );
$$;

-- ¿El usuario autenticado pertenece a este negocio, en CUALQUIER rol (dueno_sede, profesional
-- o cliente)? Para recursos visibles a todo miembro de la sede (p.ej. catálogo de
-- servicios/profesionales/niveles de membresía, que un cliente también necesita ver).
create or replace function public.es_miembro_del_tenant(p_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.es_administrador_plataforma() or exists (
    select 1 from public.roles_usuario ru
    where ru.usuario_id = auth.uid() and ru.tenant_id = p_tenant_id
  );
$$;

-- ¿El usuario autenticado es staff operativo (dueno_sede o profesional) de ESTE negocio
-- específico? Reemplaza el viejo patrón `tenant_id = current_tenant_id() and
-- es_personal_sede()` — ahora la comparación de tenant vive DENTRO de la función,
-- parametrizada por la fila que evalúa cada policy, no por un "tenant actual" global.
create or replace function public.es_personal_del_tenant(p_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.es_administrador_plataforma() or exists (
    select 1 from public.roles_usuario ru
    where ru.usuario_id = auth.uid()
      and ru.tenant_id = p_tenant_id
      and ru.rol in ('dueno_sede', 'profesional')
  );
$$;

-- ¿El usuario autenticado es dueno_sede de ESTE negocio específico? Reemplaza el viejo
-- patrón `tenant_id = current_tenant_id() and current_user_role() = 'dueno_sede'`.
create or replace function public.es_dueno_del_tenant(p_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.es_administrador_plataforma() or exists (
    select 1 from public.roles_usuario ru
    where ru.usuario_id = auth.uid()
      and ru.tenant_id = p_tenant_id
      and ru.rol = 'dueno_sede'
  );
$$;

-- ¿El usuario autenticado tiene una fila roles_usuario con rol='cliente' en ESTE negocio
-- específico? Es la contraparte de es_personal_del_tenant/es_dueno_del_tenant, pero para
-- el rol 'cliente'. Se usa para el auto-registro/auto-servicio de clientes: valida contra
-- roles_usuario (fuente de verdad, escrita solo por auth-users), NUNCA confiando en el
-- propio valor de una columna usuario_id/tenant_id de la fila de negocio que el cliente
-- está insertando/editando — así se cierra el hallazgo de multi-tenant-guard de "rama
-- usuario_id = auth.uid() sin comparar tenant_id".
create or replace function public.es_cliente_del_tenant(p_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.roles_usuario ru
    where ru.usuario_id = auth.uid()
      and ru.tenant_id = p_tenant_id
      and ru.rol = 'cliente'
  );
$$;

comment on function public.es_administrador_plataforma() is
  'true si el usuario autenticado es operador de plataforma (ve todos los negocios).';
comment on function public.es_miembro_del_tenant(uuid) is
  'true si el usuario autenticado tiene CUALQUIER rol (dueno_sede, profesional o cliente) en el tenant dado.';
comment on function public.es_personal_del_tenant(uuid) is
  'true si el usuario autenticado es dueno_sede o profesional del tenant dado (staff operativo de esa sede específica).';
comment on function public.es_dueno_del_tenant(uuid) is
  'true si el usuario autenticado es dueno_sede del tenant dado.';
comment on function public.es_cliente_del_tenant(uuid) is
  'true si el usuario autenticado tiene una fila roles_usuario con rol=cliente en el tenant dado (NO consulta la tabla clientes).';

-- Trigger genérico para mantener updated_at en cualquier tabla que lo tenga.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;
