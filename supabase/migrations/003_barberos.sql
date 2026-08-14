-- Migración: barberos
-- Autor: architect
--
-- Decisión de diseño: barbero -> una sola barbería (1:1), ya cerrada por negocio.
-- Se modela como columna tenant_id normal (no hace falta tabla N:N de rotación).

create table public.barberos (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.barberias(id) on delete cascade,
  usuario_id    uuid null references auth.users(id) on delete set null,
  nombre_completo text not null,
  telefono      text,
  activo        boolean not null default true,
  fecha_contratacion date not null default current_date,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  -- Habilita FK compuesta (barbero_id, tenant_id) desde reservas: así la base de datos
  -- rechaza, además de RLS, que una reserva asigne un barbero de OTRO tenant.
  constraint barberos_id_tenant_unico unique (id, tenant_id)
);

comment on table public.barberos is
  'Barberos de una sede. Relación 1:1 con barberias vía tenant_id (sin rotación entre sedes).';
comment on column public.barberos.usuario_id is
  'Cuenta de auth.users asociada (login del barbero), nullable mientras no tenga acceso al sistema.';

create index idx_barberos_tenant_id on public.barberos (tenant_id);
create unique index idx_barberos_usuario_id on public.barberos (usuario_id) where usuario_id is not null;
-- Un usuario auth solo puede ser barbero de UNA sede (consistente con roles_usuario único por
-- usuario_id+tenant y con la regla de negocio 1:1).
create index idx_barberos_tenant_activo on public.barberos (tenant_id, activo);

create trigger trg_barberos_updated_at
  before update on public.barberos
  for each row execute function public.set_updated_at();

alter table public.barberos enable row level security;

-- Visible a cualquier miembro del tenant (incluido 'cliente': necesita ver la lista de
-- barberos para elegir barbero_preferido_id).
create policy barberos_select on public.barberos
  for select
  using (public.es_miembro_del_tenant(tenant_id));

create policy barberos_insert on public.barberos
  for insert
  with check (public.es_dueno_del_tenant(tenant_id));

create policy barberos_update on public.barberos
  for update
  using (public.es_dueno_del_tenant(tenant_id))
  with check (public.es_dueno_del_tenant(tenant_id));

create policy barberos_delete on public.barberos
  for delete
  using (public.es_dueno_del_tenant(tenant_id));
