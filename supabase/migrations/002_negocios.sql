-- Migración: negocios (tenant raíz)
-- Autor: architect
--
-- Cada fila es un negocio independiente de la plataforma (barbería, salón de uñas u otro
-- vertical soportado), no una sucursal propia de Barberus.

create table public.negocios (
  id           uuid primary key default gen_random_uuid(),
  nombre       text not null,
  slug         text not null unique,
  zona_horaria text not null default 'America/Bogota',
  telefono     text,
  direccion    text,
  activo       boolean not null default true,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  constraint negocios_slug_formato check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$')
);

comment on table public.negocios is
  'Tenant raíz. Cada fila es un negocio independiente de la plataforma (barbería, salón de uñas u otro vertical soportado), no una sucursal propia de Barberus.';

create trigger trg_negocios_updated_at
  before update on public.negocios
  for each row execute function public.set_updated_at();

-- Ahora que existe negocios, se cierra la FK diferida de roles_usuario.tenant_id.
alter table public.roles_usuario
  add constraint roles_usuario_tenant_id_fkey
  foreign key (tenant_id) references public.negocios(id) on delete cascade;

create index idx_roles_usuario_tenant_id on public.roles_usuario (tenant_id);

alter table public.negocios enable row level security;

-- administrador_plataforma ve/administra todos los negocios; dueno_sede/profesional/cliente
-- solo ven su propio negocio (no la lista completa de negocios de la plataforma).
create policy negocios_select on public.negocios
  for select
  using (public.es_miembro_del_tenant(id));

create policy negocios_insert on public.negocios
  for insert
  with check (public.es_administrador_plataforma());

create policy negocios_update on public.negocios
  for update
  using (public.es_administrador_plataforma())
  with check (public.es_administrador_plataforma());

create policy negocios_delete on public.negocios
  for delete
  using (public.es_administrador_plataforma());
