-- Migración: clientes + notas_cliente (perfil de cliente enriquecido)
-- Autor: architect
--
-- Decisión de negocio ya cerrada: cliente aislado por sede. No hay identidad global
-- cruzada; un mismo humano que visita 2 sedes del grupo tiene 2 filas independientes
-- en clientes, sin FK entre ellas. tenant_id + correo/telefono NO son únicos globalmente,
-- solo dentro del tenant. Un mismo usuario_id de auth PUEDE aparecer en varias filas de
-- clientes (una por tenant) — es la decisión de negocio, no un bug.
--
-- Corrección de auditoría (multi-tenant-guard, hallazgo bloqueante): la versión anterior
-- tenía un índice único GLOBAL sobre usuario_id (idx_clientes_usuario_id), que en la
-- práctica impedía que un mismo login tuviera perfil de cliente en dos sedes — contradice
-- la decisión de negocio de arriba. Se eliminó; queda solo idx_clientes_tenant_usuario_unico
-- (único por tenant, que sí es la regla correcta). Esto es lo que habilitó el hallazgo
-- bloqueante hermano: las policies clientes_select/clientes_update tenían una rama
-- `usuario_id = auth.uid()` que confiaba en el valor de esa columna sin validarlo contra
-- roles_usuario (la fuente de verdad) ni impedir que un cliente reasignara el tenant_id de
-- su propia fila vía UPDATE. Con el índice único global esto era "seguro por accidente"
-- (un usuario_id solo podía tener una fila en todo el sistema); sin él, un cliente podía
-- mover su propio perfil a un tenant donde nunca se registró. Ver es_cliente_del_tenant()
-- en 001_extensiones_y_helpers.sql y su uso abajo.

create table public.clientes (
  id                  uuid primary key default gen_random_uuid(),
  tenant_id           uuid not null references public.negocios(id) on delete cascade,
  usuario_id          uuid null references auth.users(id) on delete set null,
  nombre_completo     text not null,
  telefono            text,
  correo              text,
  profesional_preferido_id uuid null,
  preferencias        jsonb not null default '{}'::jsonb, -- preferencias libres (estilo, alergias, etc.)
  activo              boolean not null default true,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  -- Habilita FK compuesta (cliente_id, tenant_id) desde reservas: la base de datos rechaza,
  -- además de RLS, que una reserva asigne un cliente de OTRO tenant.
  constraint clientes_id_tenant_unico unique (id, tenant_id),
  -- profesional_preferido_id debe pertenecer al MISMO tenant que el cliente.
  -- ON DELETE RESTRICT (no SET NULL): una FK compuesta con SET NULL pondría también
  -- tenant_id en null, violando su NOT NULL. Los profesionales se dan de baja con activo=false,
  -- no con DELETE físico, así que RESTRICT es el comportamiento esperado.
  constraint clientes_profesional_preferido_tenant_fkey
    foreign key (profesional_preferido_id, tenant_id) references public.profesionales(id, tenant_id) on delete restrict
);

comment on table public.clientes is
  'Perfil de cliente aislado por sede (tenant_id). Un mismo cliente en 2 sedes = 2 filas independientes, por decisión de negocio.';
comment on column public.clientes.usuario_id is
  'Cuenta auth.users si el cliente tiene login (OTP/magic link). Nullable: el staff puede crear clientes walk-in sin cuenta. Un mismo usuario_id puede repetirse en varias filas (una por tenant) — no es único globalmente, ver idx_clientes_tenant_usuario_unico.';
comment on column public.clientes.profesional_preferido_id is
  'Profesional preferido del cliente, siempre del mismo negocio (tenant_id compartido, reforzado por FK compuesta contra profesionales).';

create index idx_clientes_tenant_id on public.clientes (tenant_id);
create index idx_clientes_tenant_telefono on public.clientes (tenant_id, telefono);
-- Un mismo usuario_id de auth solo puede tener UN perfil de cliente POR sede (coherente con
-- "aislado por sede"), pero SÍ puede tener perfiles en varias sedes distintas — por eso el
-- único es (tenant_id, usuario_id), nunca (usuario_id) a secas. NO agregar un índice único
-- global sobre usuario_id: ya se intentó y contradice la decisión de negocio (ver nota de
-- auditoría arriba).
create unique index idx_clientes_tenant_usuario_unico on public.clientes (tenant_id, usuario_id) where usuario_id is not null;

create trigger trg_clientes_updated_at
  before update on public.clientes
  for each row execute function public.set_updated_at();

alter table public.clientes enable row level security;

-- El propio cliente (rol 'cliente') solo ve/edita su propia fila, y SOLO si roles_usuario
-- confirma que tiene rol 'cliente' en ESE tenant específico (es_cliente_del_tenant, no un
-- chequeo aislado de usuario_id) — así un UPDATE no puede "mover" la fila a un tenant donde
-- el usuario nunca se registró como cliente: el WITH CHECK se re-evalúa contra el
-- tenant_id NUEVO, y si no hay fila en roles_usuario para ese tenant, falla.
create policy clientes_select on public.clientes
  for select
  using (
    public.es_personal_del_tenant(tenant_id)
    or (usuario_id = auth.uid() and public.es_cliente_del_tenant(tenant_id))
  );

create policy clientes_insert on public.clientes
  for insert
  with check (
    public.es_personal_del_tenant(tenant_id)
    -- auto-registro de cliente: solo puede crear su propia fila, en un tenant donde
    -- roles_usuario ya lo tiene registrado como 'cliente' (esa fila la crea auth-users,
    -- nunca este INSERT).
    or (usuario_id = auth.uid() and public.es_cliente_del_tenant(tenant_id))
  );

create policy clientes_update on public.clientes
  for update
  using (
    public.es_personal_del_tenant(tenant_id)
    or (usuario_id = auth.uid() and public.es_cliente_del_tenant(tenant_id))
  )
  with check (
    public.es_personal_del_tenant(tenant_id)
    or (usuario_id = auth.uid() and public.es_cliente_del_tenant(tenant_id))
  );

create policy clientes_delete on public.clientes
  for delete
  using (public.es_dueno_del_tenant(tenant_id));

-- ¿El usuario autenticado ES el cliente p_cliente_id? A diferencia de un simple
-- `c.usuario_id = auth.uid()`, valida también contra roles_usuario (rol='cliente' en el
-- tenant de esa fila) — mismo criterio que clientes_select/update de arriba. Se define
-- aquí (no en 001) porque depende de la tabla clientes, que recién existe en esta
-- migración. La usan 006/007/008 para las ramas de autoservicio de reservas, turnos_fila y
-- membresías. No hace falta que incluya es_administrador_plataforma(): las policies que la
-- usan siempre la combinan con es_personal_del_tenant(tenant_id), que ya cubre admin.
create or replace function public.es_dueno_del_cliente(p_cliente_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.clientes c
    where c.id = p_cliente_id
      and c.usuario_id = auth.uid()
      and public.es_cliente_del_tenant(c.tenant_id)
  );
$$;

comment on function public.es_dueno_del_cliente(uuid) is
  'true si el usuario autenticado ES el cliente p_cliente_id (usuario_id propio + rol cliente vigente en roles_usuario para el tenant de esa fila).';

-- Notas del profesional sobre el cliente: histórico de observaciones internas (no confundir
-- con "preferencias" del cliente, que puede ser autodeclarado). Solo visibles para staff,
-- nunca para el propio cliente.
create table public.notas_cliente (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references public.negocios(id) on delete cascade,
  cliente_id  uuid not null,
  profesional_id  uuid null,
  nota        text not null,
  created_at  timestamptz not null default now(),

  constraint notas_cliente_cliente_tenant_fkey foreign key (cliente_id, tenant_id)
    references public.clientes(id, tenant_id) on delete cascade,
  -- ON DELETE RESTRICT (no SET NULL): mismo motivo que clientes_profesional_preferido_tenant_fkey
  -- — una FK compuesta con SET NULL pondría también tenant_id en null, violando su NOT NULL.
  constraint notas_cliente_profesional_tenant_fkey foreign key (profesional_id, tenant_id)
    references public.profesionales(id, tenant_id) on delete restrict
);

comment on table public.notas_cliente is
  'Notas internas del profesional sobre un cliente (preferencias observadas, incidencias). No visibles para el cliente.';

create index idx_notas_cliente_tenant_cliente on public.notas_cliente (tenant_id, cliente_id, created_at desc);

alter table public.notas_cliente enable row level security;

create policy notas_cliente_select on public.notas_cliente
  for select
  using (public.es_personal_del_tenant(tenant_id));

create policy notas_cliente_insert on public.notas_cliente
  for insert
  with check (public.es_personal_del_tenant(tenant_id));

create policy notas_cliente_update on public.notas_cliente
  for update
  using (public.es_personal_del_tenant(tenant_id))
  with check (public.es_personal_del_tenant(tenant_id));

create policy notas_cliente_delete on public.notas_cliente
  for delete
  using (public.es_dueno_del_tenant(tenant_id));
