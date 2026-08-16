-- Migración: servicios (catálogo de servicios)
-- Autor: architect
--
-- Fuera de alcance explícito: precios/facturación. Solo se modela lo necesario para
-- agendar (duración). Cuando el proyecto defina billing, se extiende esta tabla o se
-- agrega una tabla de tarifas aparte — no se anticipa aquí.

create table public.servicios (
  id                uuid primary key default gen_random_uuid(),
  tenant_id         uuid not null references public.negocios(id) on delete cascade,
  nombre            text not null,
  descripcion       text,
  duracion_minutos  integer not null,
  activo            boolean not null default true,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  constraint servicios_duracion_positiva check (duracion_minutos > 0),
  constraint servicios_tenant_nombre_unico unique (tenant_id, nombre),
  -- Habilita FK compuesta (servicio_id, tenant_id) desde reserva_servicios.
  constraint servicios_id_tenant_unico unique (id, tenant_id)
);

comment on table public.servicios is
  'Catálogo de servicios por sede (corte, barba, etc.) con duración base en minutos.';

create index idx_servicios_tenant_activo on public.servicios (tenant_id, activo);

create trigger trg_servicios_updated_at
  before update on public.servicios
  for each row execute function public.set_updated_at();

alter table public.servicios enable row level security;

-- Visible a cualquier miembro del tenant (incluido 'cliente': es el catálogo que ve al reservar).
create policy servicios_select on public.servicios
  for select
  using (public.es_miembro_del_tenant(tenant_id));

create policy servicios_insert on public.servicios
  for insert
  with check (public.es_dueno_del_tenant(tenant_id));

create policy servicios_update on public.servicios
  for update
  using (public.es_dueno_del_tenant(tenant_id))
  with check (public.es_dueno_del_tenant(tenant_id));

create policy servicios_delete on public.servicios
  for delete
  using (public.es_dueno_del_tenant(tenant_id));
