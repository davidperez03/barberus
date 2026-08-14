-- Migración: niveles_membresia + membresias_cliente (club: solo tracking, sin billing)
-- Autor: architect
--
-- Decisión de negocio ya cerrada: la membresía NO cobra. Este esquema solo trackea
-- nivel/beneficios según frecuencia de visitas y fechas; la renovación/cobro es manual
-- y ocurre fuera del sistema. Por eso NO hay columnas de precio/ciclo de facturación:
-- fin_periodo_actual es una fecha administrativa que el dueno_sede escribe a mano
-- (p.ej. "vence el 2026-12-31"), no algo que el sistema cobre ni renueve solo.
--
-- Simplificación documentada: el recálculo automático de nivel (trigger sobre reservas
-- completadas) usa el conteo de visitas TOTAL histórico, no una ventana deslizante de
-- `dias_ventana`. `dias_ventana` queda modelado en niveles_membresia para cuando se
-- implemente el recálculo con ventana (job periódico), pero el trigger de esta migración
-- es intencionalmente simple para el MVP. No lo uses como fuente de verdad de "visitas
-- en los últimos N días" todavía.

create table public.niveles_membresia (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.barberias(id) on delete cascade,
  nombre          text not null,
  visitas_minimas integer not null,
  dias_ventana    integer, -- null = histórico total (comportamiento actual del trigger)
  beneficios      jsonb not null default '{}'::jsonb,
  orden           integer not null default 0,
  activo          boolean not null default true,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),

  constraint niveles_membresia_visitas_minimas_no_negativas check (visitas_minimas >= 0),
  constraint niveles_membresia_tenant_nombre_unico unique (tenant_id, nombre),
  -- Habilita FK compuesta (nivel_id, tenant_id) desde membresias_cliente.
  constraint niveles_membresia_id_tenant_unico unique (id, tenant_id)
);

comment on table public.niveles_membresia is
  'Catálogo de niveles del club por sede (configurable por dueno_sede). Sin precio: la membresía no cobra.';

create index idx_niveles_membresia_tenant_activo on public.niveles_membresia (tenant_id, activo);

create trigger trg_niveles_membresia_updated_at
  before update on public.niveles_membresia
  for each row execute function public.set_updated_at();

create table public.membresias_cliente (
  id                    uuid primary key default gen_random_uuid(),
  tenant_id             uuid not null references public.barberias(id) on delete cascade,
  cliente_id            uuid not null,
  nivel_actual_id       uuid null,
  estado                text not null default 'activa' check (estado in ('activa', 'vencida', 'cancelada')),
  visitas_totales       integer not null default 0,
  fecha_ingreso         timestamptz not null default now(),
  ultima_visita         timestamptz,
  ultimo_recalculo      timestamptz,
  -- Administrativo/manual, sin billing: lo escribe el dueno_sede al renovar "a mano".
  inicio_periodo_actual date,
  fin_periodo_actual    date,
  notas                 text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),

  constraint membresias_cliente_cliente_tenant_fkey foreign key (cliente_id, tenant_id)
    references public.clientes(id, tenant_id) on delete cascade,
  constraint membresias_cliente_nivel_tenant_fkey foreign key (nivel_actual_id, tenant_id)
    references public.niveles_membresia(id, tenant_id) on delete set null,
  -- Un cliente tiene UNA membresía viva por sede (no historial de membresías pasadas;
  -- si se necesita histórico de niveles, ver historial_nivel_membresia_cliente más abajo).
  constraint membresias_cliente_cliente_unico unique (cliente_id)
);

comment on table public.membresias_cliente is
  'Tracking de membresía club por cliente: nivel calculado, contador de visitas, fechas administrativas. Sin cobro.';

create index idx_membresias_cliente_tenant_estado on public.membresias_cliente (tenant_id, estado);

create trigger trg_membresias_cliente_updated_at
  before update on public.membresias_cliente
  for each row execute function public.set_updated_at();

-- Histórico de cambios de nivel, útil para auditar por qué un cliente subió/bajó de nivel.
create table public.historial_nivel_membresia_cliente (
  id                        uuid primary key default gen_random_uuid(),
  tenant_id                 uuid not null references public.barberias(id) on delete cascade,
  cliente_id                uuid not null,
  nivel_anterior_id         uuid null,
  nivel_nuevo_id            uuid null,
  visitas_al_cambio         integer not null,
  fecha_cambio              timestamptz not null default now(),

  constraint historial_nivel_membresia_cliente_cliente_tenant_fkey foreign key (cliente_id, tenant_id)
    references public.clientes(id, tenant_id) on delete cascade
);

comment on table public.historial_nivel_membresia_cliente is
  'Auditoría de cambios de nivel de membresía, generada por el trigger de recálculo.';

create index idx_historial_nivel_membresia_cliente_cliente on public.historial_nivel_membresia_cliente (tenant_id, cliente_id, fecha_cambio desc);

-- Recalcula membresía cuando una reserva pasa a 'completada': incrementa visitas y
-- reevalúa el nivel más alto que el cliente ya alcanza (por conteo histórico, ver nota
-- de simplificación arriba).
create or replace function public.recalcular_membresia_cliente()
returns trigger
language plpgsql
as $$
declare
  v_membresia      public.membresias_cliente%rowtype;
  v_nuevo_nivel_id uuid;
  v_nuevas_visitas integer;
begin
  if old.estado is not distinct from new.estado or new.estado <> 'completada' then
    return new;
  end if;

  insert into public.membresias_cliente (tenant_id, cliente_id, visitas_totales, ultima_visita, ultimo_recalculo)
  values (new.tenant_id, new.cliente_id, 0, new.fin_programado, now())
  on conflict (cliente_id) do nothing;

  select * into v_membresia
  from public.membresias_cliente
  where cliente_id = new.cliente_id
  for update;

  v_nuevas_visitas := v_membresia.visitas_totales + 1;

  select id into v_nuevo_nivel_id
  from public.niveles_membresia
  where tenant_id = new.tenant_id
    and activo
    and visitas_minimas <= v_nuevas_visitas
  order by visitas_minimas desc, orden desc
  limit 1;

  if v_nuevo_nivel_id is distinct from v_membresia.nivel_actual_id then
    insert into public.historial_nivel_membresia_cliente
      (tenant_id, cliente_id, nivel_anterior_id, nivel_nuevo_id, visitas_al_cambio)
    values
      (new.tenant_id, new.cliente_id, v_membresia.nivel_actual_id, v_nuevo_nivel_id, v_nuevas_visitas);
  end if;

  update public.membresias_cliente
  set visitas_totales = v_nuevas_visitas,
      ultima_visita = new.fin_programado,
      ultimo_recalculo = now(),
      nivel_actual_id = v_nuevo_nivel_id
  where cliente_id = new.cliente_id;

  return new;
end;
$$;

create trigger trg_reservas_recalcular_membresia
  after update of estado on public.reservas
  for each row execute function public.recalcular_membresia_cliente();

alter table public.niveles_membresia enable row level security;
alter table public.membresias_cliente enable row level security;
alter table public.historial_nivel_membresia_cliente enable row level security;

-- Visible a cualquier miembro del tenant (incluido 'cliente': son los beneficios que puede alcanzar).
create policy niveles_membresia_select on public.niveles_membresia
  for select
  using (public.es_miembro_del_tenant(tenant_id));

create policy niveles_membresia_insert on public.niveles_membresia
  for insert
  with check (public.es_dueno_del_tenant(tenant_id));

create policy niveles_membresia_update on public.niveles_membresia
  for update
  using (public.es_dueno_del_tenant(tenant_id))
  with check (public.es_dueno_del_tenant(tenant_id));

create policy niveles_membresia_delete on public.niveles_membresia
  for delete
  using (public.es_dueno_del_tenant(tenant_id));

create policy membresias_cliente_select on public.membresias_cliente
  for select
  using (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_del_cliente(cliente_id)
  );

-- Insert/update de membresias_cliente es responsabilidad del trigger (recalcular_membresia_cliente,
-- corre con los privilegios del actor que actualiza reservas.estado) y del staff para ajustes
-- administrativos (p.ej. registrar la fecha de renovación manual). El cliente nunca escribe
-- directo aquí.
create policy membresias_cliente_insert on public.membresias_cliente
  for insert
  with check (public.es_personal_del_tenant(tenant_id));

create policy membresias_cliente_update on public.membresias_cliente
  for update
  using (public.es_personal_del_tenant(tenant_id))
  with check (public.es_personal_del_tenant(tenant_id));

create policy membresias_cliente_delete on public.membresias_cliente
  for delete
  using (public.es_dueno_del_tenant(tenant_id));

create policy historial_nivel_membresia_cliente_select on public.historial_nivel_membresia_cliente
  for select
  using (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_del_cliente(cliente_id)
  );

-- El historial solo lo escribe el trigger (SECURITY INVOKER, corre con el rol de quien
-- actualiza reservas.estado, típicamente staff) — sin policy de insert explícita para
-- 'cliente' porque un cliente nunca marca su propia reserva como 'completada'
-- (validar_transicion_estado_reserva ya se lo impide).
create policy historial_nivel_membresia_cliente_insert on public.historial_nivel_membresia_cliente
  for insert
  with check (public.es_personal_del_tenant(tenant_id));
