-- Migración: reservas + reserva_servicios (reserva/agenda con combinación de servicios)
-- Autor: architect
--
-- Decisiones de diseño no triviales:
--
-- 1. La duración de una reserva es dinámica: se calcula sumando los servicios combinados
--    (reserva_servicios), no es un campo editable a mano. Un trigger recalcula
--    reservas.fin_programado cada vez que cambia la combinación de servicios.
--
-- 2. No-doble-booking de un barbero se garantiza con un EXCLUDE CONSTRAINT (gist), no solo
--    con un trigger: es atómico a nivel de motor, corre incluso bajo concurrencia real
--    (dos requests intentando agendar el mismo slot al mismo tiempo), cosa que un trigger
--    con SELECT+INSERT no garantiza sin locks explícitos. Es DEFERRABLE INITIALLY DEFERRED
--    porque una reserva nace con fin_programado "provisional" hasta que se insertan sus
--    reserva_servicios en la misma transacción y el trigger recalcula el rango real; el
--    chequeo de solapamiento se pospone al COMMIT de esa transacción.
--
-- 3. cliente_id/barbero_id llevan FK COMPUESTA (id, tenant_id) contra clientes/barberos:
--    refuerza a nivel de esquema (no solo RLS) que una reserva no puede mezclar entidades
--    de dos tenants distintos. Esto también es lo que hace SEGURO simplificar las policies
--    de autoservicio del cliente a solo `es_dueno_del_cliente(cliente_id)` sin repetir el
--    chequeo de tenant_id: si cliente_id y tenant_id no correspondieran al mismo tenant, el
--    INSERT/UPDATE ya habría fallado por la FK compuesta antes de llegar a evaluarse RLS.
--
-- 4. reservas_fin_despues_inicio es un CHECK constraint normal (Postgres no permite CHECK
--    deferrable). Por eso, al crear una reserva, quien la inserta debe mandar un
--    fin_programado tentativo válido (> inicio_programado; p.ej. inicio + duración conocida,
--    o inicio + 1 minuto si aún no se insertaron los reserva_servicios) — el trigger
--    recalcular_fin_reserva lo corrige al valor real en cuanto se agregan los servicios,
--    dentro de la misma transacción, antes de que el exclusion constraint (ese sí deferred)
--    se evalúe en el COMMIT.

create table public.reservas (
  id                uuid primary key default gen_random_uuid(),
  tenant_id         uuid not null references public.barberias(id) on delete cascade,
  cliente_id        uuid not null,
  barbero_id        uuid not null,
  estado            text not null default 'pendiente'
                       check (estado in ('pendiente','confirmada','en_progreso','completada','cancelada','no_asistio')),
  origen            text not null default 'en_linea'
                       check (origen in ('en_linea','presencial','telefonica')),
  inicio_programado timestamptz not null,
  fin_programado    timestamptz not null,
  motivo_cancelacion text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),

  constraint reservas_fin_despues_inicio check (fin_programado > inicio_programado),
  constraint reservas_cliente_tenant_fkey foreign key (cliente_id, tenant_id)
    references public.clientes(id, tenant_id) on delete restrict,
  constraint reservas_barbero_tenant_fkey foreign key (barbero_id, tenant_id)
    references public.barberos(id, tenant_id) on delete restrict,
  -- Habilita FK compuesta (reserva_id, tenant_id) desde turnos_fila.
  constraint reservas_id_tenant_unico unique (id, tenant_id),

  -- No-doble-booking: mismo barbero no puede tener 2 reservas activas con rango solapado.
  -- Reservas canceladas/no-asistió no cuentan (liberan el slot).
  constraint reservas_sin_doble_reserva exclude using gist (
    barbero_id with =,
    tstzrange(inicio_programado, fin_programado, '[)') with &&
  ) where (estado not in ('cancelada', 'no_asistio')) deferrable initially deferred
);

comment on table public.reservas is
  'Reserva/agenda. fin_programado se recalcula automáticamente a partir de reserva_servicios (ver trigger recalcular_fin_reserva).';

create index idx_reservas_tenant_inicio on public.reservas (tenant_id, inicio_programado);
create index idx_reservas_tenant_estado on public.reservas (tenant_id, estado);
create index idx_reservas_barbero_inicio on public.reservas (barbero_id, inicio_programado);
create index idx_reservas_cliente on public.reservas (cliente_id);

create trigger trg_reservas_updated_at
  before update on public.reservas
  for each row execute function public.set_updated_at();

-- Máquina de estados de la reserva. Aplica a TODO actor (staff o cliente); combinado con
-- RLS esto da defensa en profundidad: RLS decide QUIÉN puede tocar la fila, este trigger
-- decide QUÉ transición de estado es válida y, si el actor NO es staff de ESTE tenant
-- específico (new.tenant_id), la restringe a cancelar su propia reserva (no puede
-- marcarse a sí mismo 'completada' o 'no_asistio').
--
-- Corrección de auditoría: la versión anterior usaba `current_user_role() = 'cliente'`
-- (función global, ya eliminada) para decidir si aplicaba la restricción. Eso era
-- incorrecto para un usuario con roles en más de un tenant (p.ej. dueno_sede en A y
-- cliente en B): al actualizar una reserva en B, current_user_role() podía devolver
-- 'dueno_sede' (el rol de OTRO tenant) y saltarse la restricción indebidamente. Ahora se
-- evalúa es_personal_del_tenant(new.tenant_id) — parametrizado por el tenant de ESTA
-- reserva, no por un rol global ambiguo.
create or replace function public.validar_transicion_estado_reserva()
returns trigger
language plpgsql
as $$
begin
  if new.estado = old.estado then
    return new;
  end if;

  if not (
    (old.estado = 'pendiente'    and new.estado in ('confirmada', 'cancelada'))
    or (old.estado = 'confirmada'   and new.estado in ('en_progreso', 'cancelada', 'no_asistio'))
    or (old.estado = 'en_progreso'  and new.estado in ('completada', 'cancelada'))
  ) then
    raise exception 'Transición de estado inválida en reserva %: % -> %', old.id, old.estado, new.estado;
  end if;

  if not public.es_personal_del_tenant(new.tenant_id) then
    if new.estado <> 'cancelada' then
      raise exception 'Un cliente solo puede cancelar su propia reserva, no puede fijar el estado %', new.estado;
    end if;
  end if;

  return new;
end;
$$;

create trigger trg_reservas_transicion_estado
  before update of estado on public.reservas
  for each row execute function public.validar_transicion_estado_reserva();

-- ¿El usuario autenticado es el dueño (cliente) de la reserva p_reserva_id? Se define aquí
-- (no en 001) porque depende de reservas, que recién existe en esta migración. Compone
-- es_dueno_del_cliente (005_clientes.sql) en vez de repetir el join a clientes/roles_usuario.
create or replace function public.es_dueno_de_reserva(p_reserva_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.reservas r
    where r.id = p_reserva_id
      and public.es_dueno_del_cliente(r.cliente_id)
  );
$$;

comment on function public.es_dueno_de_reserva(uuid) is
  'true si el usuario autenticado es el cliente dueño de la reserva p_reserva_id.';

-- Combinación de servicios de una reserva (N servicios por reserva -> duración dinámica).
create table public.reserva_servicios (
  id                          uuid primary key default gen_random_uuid(),
  tenant_id                   uuid not null references public.barberias(id) on delete cascade,
  reserva_id                  uuid not null references public.reservas(id) on delete cascade,
  servicio_id                 uuid not null,
  -- snapshot de la duración del servicio al momento de agendar: si el catálogo cambia
  -- después, no debe alterar retroactivamente reservas ya creadas.
  duracion_minutos_snapshot   integer not null,
  posicion                    integer not null default 0,
  created_at                  timestamptz not null default now(),

  constraint reserva_servicios_duracion_positiva check (duracion_minutos_snapshot > 0),
  constraint reserva_servicios_servicio_tenant_fkey foreign key (servicio_id, tenant_id)
    references public.servicios(id, tenant_id) on delete restrict,
  constraint reserva_servicios_reserva_servicio_unico unique (reserva_id, servicio_id)
);

comment on table public.reserva_servicios is
  'Servicios que componen una reserva. La suma de duracion_minutos_snapshot define reservas.fin_programado.';

create index idx_reserva_servicios_tenant_reserva on public.reserva_servicios (tenant_id, reserva_id);

alter table public.reserva_servicios enable row level security;
alter table public.reservas enable row level security;

-- Snapshot automático de duración si no se pasa explícita.
create or replace function public.fijar_snapshot_duracion_reserva_servicio()
returns trigger
language plpgsql
as $$
begin
  if new.duracion_minutos_snapshot is null then
    select duracion_minutos into new.duracion_minutos_snapshot
    from public.servicios
    where id = new.servicio_id;
  end if;

  if new.duracion_minutos_snapshot is null then
    raise exception 'No se pudo determinar duracion_minutos_snapshot para servicio_id=%', new.servicio_id;
  end if;

  return new;
end;
$$;

create trigger trg_reserva_servicios_snapshot
  before insert on public.reserva_servicios
  for each row execute function public.fijar_snapshot_duracion_reserva_servicio();

-- Recalcula reservas.fin_programado = inicio_programado + suma(duraciones) cada vez que
-- cambia la combinación de servicios de una reserva.
create or replace function public.recalcular_fin_reserva()
returns trigger
language plpgsql
as $$
declare
  v_reserva_id     uuid;
  v_inicio         timestamptz;
  v_total_minutos  integer;
begin
  v_reserva_id := coalesce(new.reserva_id, old.reserva_id);

  select inicio_programado into v_inicio
  from public.reservas
  where id = v_reserva_id
  for update; -- lock de la reserva padre: serializa recálculos concurrentes

  select coalesce(sum(duracion_minutos_snapshot), 0) into v_total_minutos
  from public.reserva_servicios
  where reserva_id = v_reserva_id;

  update public.reservas
  -- mínimo 1 minuto: evita rango degenerado (vacío) que rompería el exclude constraint
  set fin_programado = v_inicio + make_interval(mins => greatest(v_total_minutos, 1))
  where id = v_reserva_id;

  return coalesce(new, old);
end;
$$;

create trigger trg_reserva_servicios_recalcular
  after insert or update or delete on public.reserva_servicios
  for each row execute function public.recalcular_fin_reserva();

-- ── RLS: reservas ──────────────────────────────────────────────────────────
-- Staff ve/gestiona todas las reservas de su tenant. Cliente ve/gestiona solo las suyas.
create policy reservas_select on public.reservas
  for select
  using (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_del_cliente(cliente_id)
  );

create policy reservas_insert on public.reservas
  for insert
  with check (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_del_cliente(cliente_id)
  );

create policy reservas_update on public.reservas
  for update
  using (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_del_cliente(cliente_id)
  )
  with check (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_del_cliente(cliente_id)
  );

create policy reservas_delete on public.reservas
  for delete
  using (public.es_dueno_del_tenant(tenant_id));

-- ── RLS: reserva_servicios ───────────────────────────────────────────────
-- Hereda visibilidad de la reserva padre (mismo criterio, vía es_dueno_de_reserva).
create policy reserva_servicios_select on public.reserva_servicios
  for select
  using (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_de_reserva(reserva_id)
  );

create policy reserva_servicios_insert on public.reserva_servicios
  for insert
  with check (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_de_reserva(reserva_id)
  );

create policy reserva_servicios_update on public.reserva_servicios
  for update
  using (public.es_personal_del_tenant(tenant_id))
  with check (public.es_personal_del_tenant(tenant_id));

create policy reserva_servicios_delete on public.reserva_servicios
  for delete
  using (
    public.es_personal_del_tenant(tenant_id)
    or public.es_dueno_de_reserva(reserva_id)
  );
