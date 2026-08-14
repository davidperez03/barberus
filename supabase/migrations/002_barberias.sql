-- Migración: barberias (tenant raíz)
-- Autor: architect

create table public.barberias (
  id           uuid primary key default gen_random_uuid(),
  nombre       text not null,
  slug         text not null unique,
  zona_horaria text not null default 'America/Bogota',
  telefono     text,
  direccion    text,
  activo       boolean not null default true,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  constraint barberias_slug_formato check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$')
);

comment on table public.barberias is
  'Tenant raíz. Cada fila es una sede/barbería del grupo (20 iniciales).';

create trigger trg_barberias_updated_at
  before update on public.barberias
  for each row execute function public.set_updated_at();

-- Ahora que existe barberias, se cierra la FK diferida de roles_usuario.tenant_id.
alter table public.roles_usuario
  add constraint roles_usuario_tenant_id_fkey
  foreign key (tenant_id) references public.barberias(id) on delete cascade;

create index idx_roles_usuario_tenant_id on public.roles_usuario (tenant_id);

alter table public.barberias enable row level security;

-- administrador_plataforma ve/administra las 20; dueno_sede/barbero/cliente solo ven su propia sede
-- (no la lista completa de barberías del grupo).
create policy barberias_select on public.barberias
  for select
  using (public.es_miembro_del_tenant(id));

create policy barberias_insert on public.barberias
  for insert
  with check (public.es_administrador_plataforma());

create policy barberias_update on public.barberias
  for update
  using (public.es_administrador_plataforma())
  with check (public.es_administrador_plataforma());

create policy barberias_delete on public.barberias
  for delete
  using (public.es_administrador_plataforma());
