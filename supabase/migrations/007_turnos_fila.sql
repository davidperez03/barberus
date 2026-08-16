-- Migración: turnos_fila (fila en vivo / check-in)
-- Autor: architect
--
-- Modela el check-in físico en sede, independiente de si hubo reserva previa (walk-in)
-- o no. North star del negocio: reducir tiempo de espera en fila, por eso esta tabla
-- lleva timestamps de cada transición para poder medir tiempo de espera real.
--
-- Decisiones no triviales:
-- 1. numero_turno se genera de forma atómica por (tenant_id, fecha) vía tabla contador
--    con `for update` (evita colisión de número de turno bajo check-ins concurrentes).
-- 2. Un profesional solo puede tener UN turno 'en_servicio' a la vez: unique index parcial,
--    no un simple trigger (misma razón que el exclude constraint de reservas: atomicidad
--    real bajo concurrencia).
-- 3. Transición de estados validada en trigger: esperando -> llamado -> en_servicio ->
--    completado, con salidas a cancelado/no_asistio solo desde esperando/llamado.
-- 4. cliente_id/profesional_id/reserva_id llevan FK compuesta (id, tenant_id): la misma
--    garantía de "no mezclar tenants" que en reservas, por eso las policies de autoservicio
--    del cliente pueden usar es_dueno_del_cliente(cliente_id) sin repetir el chequeo de
--    tenant_id (ver nota equivalente en 006_reservas.sql).

create table public.contadores_fila_diarios (
  tenant_id           uuid not null references public.negocios(id) on delete cascade,
  fecha_fila          date not null,
  ultimo_numero_turno integer not null default 0,
  primary key (tenant_id, fecha_fila)
);

comment on table public.contadores_fila_diarios is
  'Contador atómico de numero_turno por sede y día, usado por trg_turnos_fila_asignar_numero.';

create table public.turnos_fila (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references public.negocios(id) on delete cascade,
  reserva_id    uuid null,
  cliente_id    uuid not null,
  profesional_id    uuid null,
  estado        text not null default 'esperando'
                   check (estado in ('esperando','llamado','en_servicio','completado','cancelado','no_asistio')),
  fecha_fila       date not null default current_date,
  numero_turno     integer, -- asignado por trigger, no lo fija el cliente
  hora_ingreso     timestamptz not null default now(),
  hora_llamado     timestamptz,
  hora_inicio      timestamptz,
  hora_completado  timestamptz,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),

  constraint turnos_fila_reserva_tenant_fkey foreign key (reserva_id, tenant_id)
    references public.reservas(id, tenant_id) on delete set null,
  constraint turnos_fila_cliente_tenant_fkey foreign key (cliente_id, tenant_id)
    references public.clientes(id, tenant_id) on delete restrict,
  constraint turnos_fila_profesional_tenant_fkey foreign key (profesional_id, tenant_id)
    references public.profesionales(id, tenant_id) on delete restrict,
  constraint turnos_fila_numero_turno_unico unique (tenant_id, fecha_fila, numero_turno)
);

comment on table public.turnos_fila is
  'Fila en vivo de una sede: check-in físico, con o sin reserva previa (reserva_id nullable).';

create index idx_turnos_fila_tenant_fecha_estado on public.turnos_fila (tenant_id, fecha_fila, estado);
create index idx_turnos_fila_profesional on public.turnos_fila (profesional_id) where profesional_id is not null;

-- Un profesional atiende UN turno a la vez.
create unique index idx_turnos_fila_un_en_servicio_por_profesional
  on public.turnos_fila (profesional_id)
  where estado = 'en_servicio';

create trigger trg_turnos_fila_updated_at
  before update on public.turnos_fila
  for each row execute function public.set_updated_at();

-- Asignación atómica de numero_turno por (tenant_id, fecha_fila).
create or replace function public.asignar_numero_turno_fila()
returns trigger
language plpgsql
as $$
declare
  v_siguiente integer;
begin
  insert into public.contadores_fila_diarios (tenant_id, fecha_fila, ultimo_numero_turno)
  values (new.tenant_id, new.fecha_fila, 1)
  on conflict (tenant_id, fecha_fila)
  do update set ultimo_numero_turno = public.contadores_fila_diarios.ultimo_numero_turno + 1
  returning ultimo_numero_turno into v_siguiente;

  new.numero_turno := v_siguiente;
  return new;
end;
$$;

create trigger trg_turnos_fila_asignar_numero
  before insert on public.turnos_fila
  for each row execute function public.asignar_numero_turno_fila();

-- Máquina de estados de la fila + timestamps automáticos de cada transición.
--
-- Corrección de auditoría (mismo criterio que validar_transicion_estado_reserva en
-- 006_reservas.sql): se reemplazó `current_user_role() = 'cliente'` (función global
-- eliminada, ambigua para un usuario con roles en más de un tenant) por
-- es_personal_del_tenant(new.tenant_id), parametrizado por el tenant de ESTE turno.
--
-- Nota de nomenclatura (dry-guard, prioridad baja): el estado terminal de cancelación es
-- 'cancelada' en reservas pero 'cancelado' en turnos_fila. Es concordancia de género
-- intencional, no inconsistencia — "una reserva cancelada" / "un turno cancelado". Mismo
-- criterio en 'completada' (reserva, fem.) vs 'completado' (turno, masc.). Documentado
-- también en APPLIED.md.
create or replace function public.validar_transicion_estado_turno()
returns trigger
language plpgsql
as $$
begin
  if new.estado = old.estado then
    return new;
  end if;

  if not (
    (old.estado = 'esperando' and new.estado in ('llamado', 'cancelado', 'no_asistio'))
    or (old.estado = 'llamado'   and new.estado in ('en_servicio', 'cancelado', 'no_asistio'))
    or (old.estado = 'en_servicio' and new.estado in ('completado', 'cancelado'))
  ) then
    raise exception 'Transición de estado inválida en turno_fila %: % -> %', old.id, old.estado, new.estado;
  end if;

  if new.estado = 'llamado' and new.profesional_id is null then
    raise exception 'No se puede llamar un turno sin profesional asignado (turno_fila %)', old.id;
  end if;

  -- Igual que en reservas: el cliente solo puede cancelar su propio turno, nunca
  -- llamarse, pasarse a atención o marcarse completado a sí mismo.
  if not public.es_personal_del_tenant(new.tenant_id) then
    if new.estado <> 'cancelado' then
      raise exception 'Un cliente solo puede cancelar su propio turno, no puede fijar el estado %', new.estado;
    end if;
  end if;

  if new.estado = 'llamado' then
    new.hora_llamado := coalesce(new.hora_llamado, now());
  elsif new.estado = 'en_servicio' then
    new.hora_inicio := coalesce(new.hora_inicio, now());
  elsif new.estado = 'completado' then
    new.hora_completado := coalesce(new.hora_completado, now());
  end if;

  return new;
end;
$$;

create trigger trg_turnos_fila_transicion_estado
  before update of estado on public.turnos_fila
  for each row execute function public.validar_transicion_estado_turno();

alter table public.contadores_fila_diarios enable row level security;
alter table public.turnos_fila enable row level security;

-- El contador es un detalle interno de implementación: solo staff/administrador_plataforma lo tocan
-- (indirectamente, vía el trigger que corre con los privilegios del actor que inserta en
-- turnos_fila).
create policy contadores_fila_diarios_all on public.contadores_fila_diarios
  for all
  using (public.es_personal_del_tenant(tenant_id))
  with check (public.es_personal_del_tenant(tenant_id));

create policy turnos_fila_select on public.turnos_fila
  for select
  using (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_del_cliente(cliente_id)
  );

create policy turnos_fila_insert on public.turnos_fila
  for insert
  with check (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_del_cliente(cliente_id)
  );

-- Actualizar estado de la fila (llamar, pasar a atención, completar) es operación de staff.
-- El cliente puede cancelar su propio turno (mismo criterio que reservas).
create policy turnos_fila_update on public.turnos_fila
  for update
  using (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_del_cliente(cliente_id)
  )
  with check (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_del_cliente(cliente_id)
  );

create policy turnos_fila_delete on public.turnos_fila
  for delete
  using (public.es_dueno_del_tenant(tenant_id));
