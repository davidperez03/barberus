-- Migración: resumen_fila_publico (comparador público de fila entre negocios) + coordenadas
-- Autor: architect
--
-- Requisito de negocio: un visitante SIN LOGIN (navegación pública, "ver el mapa antes de
-- entrar a la app") debe poder comparar el estado de la fila entre varios de los negocios de
-- la plataforma antes de decidir a cuál ir, y ubicarlos en un mapa (Leaflet/react-leaflet en
-- el frontend). Es el PRIMER caso legítimo de lectura pública cross-tenant en todo el esquema
-- -- hasta ahora TODA lectura estaba scoped a "soy miembro de este tenant" (ver
-- 001_extensiones_y_helpers.sql). Se diseña con cuidado para no abrir una fuga mayor.
--
-- Alcance confirmado (no expandir):
--   - Solo agregado por negocio: cantidad de personas en fila + tiempo de espera estimado +
--     coordenadas para el mapa.
--   - NUNCA el detalle de quién está en la fila, ni cualquier dato de clientes/profesionales.
--   - Público, sin autenticación (rol `anon`, sin JWT, sin pertenecer a ningún tenant).
--
-- Decisión 1 -- tabla resumen derivada, NUNCA una policy pública sobre turnos_fila cruda:
-- se crea una tabla nueva `resumen_fila_publico` con SOLO columnas agregadas (nunca
-- cliente_id/profesional_id/numero_turno/horas individuales). Ninguna policy de `turnos_fila`
-- se toca ni se relaja para `anon`. Es más seguro y más simple de auditar que intentar
-- limitar columnas de una tabla ya RLS-protegida a otro rol -- lang-guard/multi-tenant-guard
-- pueden verificar la superficie pública mirando UNA tabla con pocas columnas, todas agregadas.
--
-- Decisión 2 -- tabla mantenida por trigger, NO una vista calculada al vuelo:
-- el tráfico de lectura de este comparador es público (potencialmente alto, sin control de
-- cuántos visitantes anónimos lo consultan) mientras que las escrituras en turnos_fila
-- ocurren al ritmo humano de check-ins/atenciones de UN negocio (bajo volumen). Un trigger
-- AFTER INSERT/UPDATE/DELETE en turnos_fila recalcula una sola fila de resumen_fila_publico
-- por tenant afectado: la lectura pública es un lookup por PK (barato, un puñado de filas en
-- total), el costo de recálculo se paga solo cuando de verdad cambia la fila real. Se prefiere
-- un recálculo completo (COUNT/AVG) sobre el tenant afectado, no contadores incrementales: el
-- volumen por negocio es bajo (una barbería/salón no atiende miles de personas/día) y un
-- recálculo completo es inmune a drift, que sí es un riesgo real en contadores incrementales.
--
-- Decisión 3 -- "personas en fila" NO se filtra por fecha_fila = current_date:
-- se cuenta cualquier turno en estado esperando/llamado/en_servicio del tenant, sin importar
-- el día en que se creó. Filtrar por current_date en el propio trigger introduce un edge
-- case real: si nadie hace check-in justo después de medianoche, la fila pública queda
-- "congelada" mostrando el conteo de ayer hasta el primer write del nuevo día. Contar por
-- estado a secas es además más correcto semánticamente ("¿hay fila ahora mismo?") y un turno
-- esperando que cruza medianoche sin resolverse es, de por sí, algo que el staff debería
-- cerrar -- no algo que el comparador público deba ocultar.
--
-- Decisión 4 -- tiempo_espera_estimado_minutos: SOLO si hay base real, si no, NULL:
-- turnos_fila ya guarda hora_inicio/hora_completado de cada turno completado, así que la
-- duración PROMEDIO real de atención de un negocio en las últimas 24h es un dato genuino, no
-- inventado. La estimación es:
--   duracion_promedio_reciente_minutos * personas_esperando / profesionales_atendiendo_ahora
-- Si el negocio no tiene ningún turno completado en las últimas 24h (recién abrió, sin
-- tráfico), NO hay base real para estimar -- la función retorna NULL explícito en vez de un
-- número inventado o una constante mágica ("20 minutos por defecto"). El frontend decide
-- cómo mostrar ese NULL (p.ej. ocultar el dato, mostrar solo "cantidad en fila"). Esto
-- respeta el alcance: "si no hay dato suficiente para tiempo estimado real, limitar a
-- cantidad de personas en fila".
--
-- Decisión 5 -- anti-abuso, los negocios son COMPETIDORES entre sí:
-- ninguna policy de escritura se otorga a es_personal_del_tenant/es_dueno_del_tenant sobre
-- resumen_fila_publico. Si se permitiera a un dueno_sede escribir directamente su propia
-- fila de resumen, podría inflar/deflactar su propio número para verse mejor que los demás
-- negocios en el comparador público -- un incentivo real dado que compiten por el mismo
-- cliente. La tabla es 100% derivada: solo la escriben los triggers (SECURITY DEFINER) sobre
-- turnos_fila/negocios, más una policy de emergencia solo para administrador_plataforma
-- (corrección manual de datos, no operación de negocio).
--
-- Decisión 6 (nueva, no existía en el diseño original) -- coordenadas en negocios,
-- desnormalizadas también en resumen_fila_publico:
-- el requisito de mostrar los negocios en un mapa (Leaflet) con marcadores tipo semáforo
-- según ocupación exige exponer latitud/longitud. `negocios` hoy solo tiene `direccion` como
-- texto libre, sin geolocalización -- se agregan columnas `latitud numeric`/`longitud
-- numeric` ahí (dato propio del negocio, PostGIS sería sobre-ingeniería para simplemente
-- ubicar puntos en Leaflet; lat/lng numéricos alcanzan). Pero `negocios` NO tiene lectura
-- pública (solo `es_miembro_del_tenant`, ver 002_negocios.sql) y `resumen_fila_publico` es la
-- ÚNICA superficie de lectura pública del esquema -- así que se desnormalizan `latitud`/
-- `longitud` también en `resumen_fila_publico`, mantenidas por el mismo trigger que ya
-- sincroniza nombre_sede/slug_sede/activo desde negocios. Alternativa descartada: abrir una
-- policy pública nueva sobre `negocios` (aunque fuera solo id/nombre/lat/lng) -- eso
-- duplicaría la superficie pública en dos tablas en vez de una, contradiciendo la Decisión 1
-- de este mismo archivo (una sola tabla auditable). El frontend hace UN solo query público.
--
-- Limitación conocida (documentada, no resuelta en este esquema): esta tabla no tiene
-- concepto de "negocio cerrado ahora mismo" (no existe horario de atención modelado). El
-- conteo puede mostrar personas en fila fuera de horario si el staff no cierra los turnos
-- pendientes al final del día -- es un problema de higiene operativa de datos, no de este
-- mecanismo. Fuera de alcance: agregar horario de atención/reset programado (pg_cron) queda
-- para una migración futura si el negocio lo pide. Tampoco se valida aquí que
-- latitud/longitud estén pobladas -- un negocio sin coordenadas simplemente no puede
-- ubicarse en el mapa (el frontend decide cómo tratar ese caso), no es un error de datos.

-- Coordenadas del negocio (para ubicarlo en un mapa Leaflet/react-leaflet). Ambas nullable:
-- un negocio puede existir sin coordenadas todavía (dato opcional a completar por
-- administrador_plataforma/dueno_sede), pero si se informa una, la otra también es obligatoria
-- (un punto no existe a medias) y ambas deben caer en el rango físico válido.
alter table public.negocios
  add column latitud  numeric(9, 6),
  add column longitud numeric(9, 6);

alter table public.negocios
  add constraint negocios_latitud_rango check (latitud between -90 and 90),
  add constraint negocios_longitud_rango check (longitud between -180 and 180),
  add constraint negocios_latitud_longitud_consistentes check (
    (latitud is null) = (longitud is null)
  );

comment on column public.negocios.latitud is
  'Latitud del negocio para ubicarlo en el mapa público (Leaflet). Nullable: negocio sin geolocalizar todavía. Siempre poblada junto con longitud (constraint negocios_latitud_longitud_consistentes).';
comment on column public.negocios.longitud is
  'Longitud del negocio para ubicarlo en el mapa público (Leaflet). Nullable: negocio sin geolocalizar todavía. Siempre poblada junto con latitud (constraint negocios_latitud_longitud_consistentes).';

create table public.resumen_fila_publico (
  tenant_id                      uuid primary key references public.negocios(id) on delete cascade,
  nombre_sede                    text not null,
  slug_sede                      text not null,
  activo                         boolean not null default true,
  latitud                        numeric(9, 6),
  longitud                       numeric(9, 6),
  personas_en_fila               integer not null default 0,
  tiempo_espera_estimado_minutos integer,
  actualizado_at                 timestamptz not null default now()
);

comment on table public.resumen_fila_publico is
  'Único punto de lectura pública cross-tenant del esquema: agregado por negocio (cantidad en fila + tiempo estimado + coordenadas para el mapa público), sin ningún dato individual de cliente/profesional. Mantenida 100% por trigger desde turnos_fila/negocios -- nunca escrita directamente por la app ni por staff de un negocio (anti-abuso: negocios competidores).';
comment on column public.resumen_fila_publico.personas_en_fila is
  'Conteo de turnos_fila en estado esperando+llamado+en_servicio de este negocio, sin filtrar por fecha_fila (ver nota de diseño en el encabezado de esta migración).';
comment on column public.resumen_fila_publico.tiempo_espera_estimado_minutos is
  'Estimación real basada en duración promedio de atención (hora_completado - hora_inicio) de las últimas 24h de este negocio, dividida entre profesionales actualmente en_servicio. NULL si el negocio no tiene suficiente historial reciente -- nunca un valor inventado.';
comment on column public.resumen_fila_publico.latitud is
  'Desnormalizado desde negocios.latitud (ver Decisión 6 del encabezado): resumen_fila_publico es la única tabla con lectura pública, así el frontend del mapa hace un solo query.';
comment on column public.resumen_fila_publico.longitud is
  'Desnormalizado desde negocios.longitud (ver Decisión 6 del encabezado): resumen_fila_publico es la única tabla con lectura pública, así el frontend del mapa hace un solo query.';

-- Duración promedio real de atención (últimas 24h) x personas esperando, repartido entre
-- profesionales actualmente atendiendo. NULL explícito si no hay historial reciente de
-- servicios completados -- ver Decisión 4 en el encabezado.
create or replace function public.calcular_tiempo_espera_estimado_minutos(p_tenant_id uuid)
returns integer
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_duracion_promedio_minutos numeric;
  v_personas_esperando        integer;
  v_profesionales_atendiendo  integer;
begin
  select avg(extract(epoch from (hora_completado - hora_inicio)) / 60.0)
    into v_duracion_promedio_minutos
    from public.turnos_fila
    where tenant_id = p_tenant_id
      and estado = 'completado'
      and hora_inicio is not null
      and hora_completado is not null
      and hora_completado >= now() - interval '24 hours';

  if v_duracion_promedio_minutos is null then
    return null;
  end if;

  select count(*) into v_personas_esperando
    from public.turnos_fila
    where tenant_id = p_tenant_id
      and estado in ('esperando', 'llamado');

  select count(distinct profesional_id) into v_profesionales_atendiendo
    from public.turnos_fila
    where tenant_id = p_tenant_id
      and estado = 'en_servicio';

  return round(v_duracion_promedio_minutos * v_personas_esperando / greatest(v_profesionales_atendiendo, 1))::integer;
end;
$$;

comment on function public.calcular_tiempo_espera_estimado_minutos(uuid) is
  'Estimación de espera basada en datos reales de turnos_fila (duración promedio reciente x personas esperando / profesionales atendiendo). Retorna NULL si no hay historial suficiente -- nunca inventa un valor por defecto.';

-- SECURITY DEFINER sin REVOKE quedaría invocable directo por RPC (anon/authenticated) para
-- cualquier tenant_id, bypaseando la policy resumen_fila_publico_select_publico (using (activo))
-- -- un negocio inactivo/oculto del comparador público seguiría respondiendo su tiempo de
-- espera. Se revoca de PUBLIC/anon/authenticated; el trigger que la invoca conserva el
-- privilegio de owner (SECURITY DEFINER propio) independientemente de este REVOKE.
revoke execute on function public.calcular_tiempo_espera_estimado_minutos(uuid) from public, anon, authenticated;

-- Cuenta personas en fila activa (esperando/llamado/en_servicio) de un tenant. Extraída para
-- no duplicar el mismo predicado entre el trigger de sincronización y el backfill inicial.
create or replace function public.contar_personas_en_fila_activa(p_tenant_id uuid)
returns integer
language sql
stable
security definer
set search_path = public
as $$
  select count(*)::integer
  from public.turnos_fila
  where tenant_id = p_tenant_id
    and estado in ('esperando', 'llamado', 'en_servicio');
$$;

comment on function public.contar_personas_en_fila_activa(uuid) is
  'Conteo de turnos_fila en estado esperando+llamado+en_servicio de un tenant, sin filtrar por fecha_fila (ver Decisión 3 en el encabezado de esta migración). Reusada por el trigger de sincronización y por el backfill inicial.';

-- Mismo motivo que calcular_tiempo_espera_estimado_minutos: no dejarla invocable como RPC
-- pública sin necesidad, aunque esta no filtre por activo.
revoke execute on function public.contar_personas_en_fila_activa(uuid) from public, anon, authenticated;

-- Recalcula la fila de resumen del tenant afectado cada vez que cambia turnos_fila.
-- SECURITY DEFINER a propósito: quien dispara el cambio real (staff O el propio cliente
-- vía es_dueno_del_cliente, ver turnos_fila_insert/update en 007_turnos_fila.sql) no
-- necesariamente tiene permiso de escritura directa sobre resumen_fila_publico -- y no debe
-- tenerlo (ver Decisión 5). El trigger es el único camino de escritura derivada.
create or replace function public.sincronizar_resumen_fila_publico()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_tenant_id uuid;
begin
  v_tenant_id := coalesce(new.tenant_id, old.tenant_id);

  update public.resumen_fila_publico
  set personas_en_fila = public.contar_personas_en_fila_activa(v_tenant_id),
      tiempo_espera_estimado_minutos = public.calcular_tiempo_espera_estimado_minutos(v_tenant_id),
      actualizado_at = now()
  where tenant_id = v_tenant_id;

  return coalesce(new, old);
end;
$$;

create trigger trg_turnos_fila_sincronizar_resumen_publico
  after insert or update or delete on public.turnos_fila
  for each row execute function public.sincronizar_resumen_fila_publico();

-- Mantiene nombre_sede/slug_sede/activo/latitud/longitud en resumen_fila_publico
-- sincronizados con negocios, y crea la fila inicial cuando se da de alta un negocio nuevo.
-- Misma razón SECURITY DEFINER que arriba: quien crea/edita un negocio
-- (administrador_plataforma) no necesita permiso explícito sobre resumen_fila_publico.
create or replace function public.sincronizar_resumen_fila_publico_desde_negocio()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.resumen_fila_publico (tenant_id, nombre_sede, slug_sede, activo, latitud, longitud)
  values (new.id, new.nombre, new.slug, new.activo, new.latitud, new.longitud)
  on conflict (tenant_id) do update
    set nombre_sede = excluded.nombre_sede,
        slug_sede   = excluded.slug_sede,
        activo      = excluded.activo,
        latitud     = excluded.latitud,
        longitud    = excluded.longitud;
  return new;
end;
$$;

create trigger trg_negocios_sincronizar_resumen_publico
  after insert or update of nombre, slug, activo, latitud, longitud on public.negocios
  for each row execute function public.sincronizar_resumen_fila_publico_desde_negocio();

-- Backfill: negocios que ya existían antes de esta migración.
insert into public.resumen_fila_publico (tenant_id, nombre_sede, slug_sede, activo, latitud, longitud, personas_en_fila, tiempo_espera_estimado_minutos)
select
  n.id,
  n.nombre,
  n.slug,
  n.activo,
  n.latitud,
  n.longitud,
  public.contar_personas_en_fila_activa(n.id),
  public.calcular_tiempo_espera_estimado_minutos(n.id)
from public.negocios n
on conflict (tenant_id) do nothing;

alter table public.resumen_fila_publico enable row level security;

-- Único SELECT verdaderamente público del esquema: sin auth.uid(), abierto a anon Y
-- authenticated. Solo negocios activos -- un negocio desactivado no debe aparecer en el
-- comparador público ni en el mapa.
create policy resumen_fila_publico_select_publico on public.resumen_fila_publico
  for select
  to anon, authenticated
  using (activo);

-- Escape hatch de corrección manual, solo para administrador_plataforma (ve también negocios
-- inactivos). Deliberadamente NO existe policy de escritura para es_personal_del_tenant ni
-- es_dueno_del_tenant -- ver Decisión 5 del encabezado (anti-abuso entre negocios competidores).
create policy resumen_fila_publico_administrador_plataforma_all on public.resumen_fila_publico
  for all
  using (public.es_administrador_plataforma())
  with check (public.es_administrador_plataforma());
