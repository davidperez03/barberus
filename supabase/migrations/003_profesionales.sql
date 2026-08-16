-- Migración: profesionales
-- Autor: architect
--
-- Decisión de diseño: profesional -> un solo negocio (1:1), ya cerrada por negocio.
-- Se modela como columna tenant_id normal (no hace falta tabla N:N de rotación).

create table public.profesionales (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.negocios(id) on delete cascade,
  usuario_id    uuid null references auth.users(id) on delete set null,
  nombre_completo text not null,
  telefono      text,
  activo        boolean not null default true,
  fecha_contratacion date not null default current_date,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  -- Habilita FK compuesta (profesional_id, tenant_id) desde reservas: así la base de datos
  -- rechaza, además de RLS, que una reserva asigne un profesional de OTRO tenant.
  constraint profesionales_id_tenant_unico unique (id, tenant_id)
);

comment on table public.profesionales is
  'Profesionales de un negocio (barberos, manicuristas u otro rol operativo según el vertical). Relación 1:1 con negocios vía tenant_id (sin rotación entre sedes).';
comment on column public.profesionales.usuario_id is
  'Cuenta de auth.users asociada (login del profesional), nullable mientras no tenga acceso al sistema.';

create index idx_profesionales_tenant_id on public.profesionales (tenant_id);
create unique index idx_profesionales_usuario_id on public.profesionales (usuario_id) where usuario_id is not null;
-- Un usuario auth solo puede ser profesional de UN negocio (consistente con roles_usuario único por
-- usuario_id+tenant y con la regla de negocio 1:1).
create index idx_profesionales_tenant_activo on public.profesionales (tenant_id, activo);

create trigger trg_profesionales_updated_at
  before update on public.profesionales
  for each row execute function public.set_updated_at();

alter table public.profesionales enable row level security;

-- Visible a cualquier miembro del tenant (incluido 'cliente': necesita ver la lista de
-- profesionales para elegir profesional_preferido_id).
create policy profesionales_select on public.profesionales
  for select
  using (public.es_miembro_del_tenant(tenant_id));

create policy profesionales_insert on public.profesionales
  for insert
  with check (public.es_dueno_del_tenant(tenant_id));

create policy profesionales_update on public.profesionales
  for update
  using (public.es_dueno_del_tenant(tenant_id))
  with check (public.es_dueno_del_tenant(tenant_id));

create policy profesionales_delete on public.profesionales
  for delete
  using (public.es_dueno_del_tenant(tenant_id));
