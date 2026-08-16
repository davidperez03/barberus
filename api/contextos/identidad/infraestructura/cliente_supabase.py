"""Clientes `supabase-py` usados por los adaptadores de `identidad`.

La instanciación genérica (`create_client` + cache de un cliente por proceso) vive en
`nucleo.cliente_supabase` -- este módulo solo decide, con su razonamiento propio, qué
key usa cada cliente y lo reexporta bajo el nombre que ya usa el resto de `identidad`.

Único lugar de `identidad` donde se decide qué key usar -- el resto de
`infraestructura/` recibe el cliente inyectado.
"""

from __future__ import annotations

from supabase import Client

from nucleo.cliente_supabase import (
    obtener_cliente_supabase_publico,
    obtener_cliente_supabase_secreto,
)


def obtener_cliente_supabase() -> Client:
    """Cliente con la `secret` key (sistema nuevo de API keys de Supabase, reemplaza a
    `service_role`): el backend consulta `roles_usuario`/`sesiones` con privilegios que
    bypasean RLS a propósito -- la autorización real la resuelve el propio caso de uso
    de `identidad` (dominio) antes de que el resultado llegue a ningún otro contexto;
    RLS en Supabase queda como segunda capa de defensa para accesos directos (PostgREST
    desde el frontend), no como la única, tal como ya lo asume `docs/ARCHITECTURE.md`.
    """
    return obtener_cliente_supabase_secreto()


def obtener_cliente_supabase_auth() -> Client:
    """Segundo cliente, separado del de arriba a propósito: inicializado con la clave
    PÚBLICA (`publishable`), solo para las operaciones de Auth API (GoTrue) que
    `AutenticadorSupabase` expone (registro, inicio de sesión).

    Signup/login son operaciones que cualquier usuario anónimo puede invocar
    legítimamente contra GoTrue -- usar la `secret` key ahí no otorga ningún privilegio
    adicional (GoTrue no lo requiere para esas dos operaciones) y violaría el principio
    de menor privilegio: si esta clave se filtrara, solo permite lo que el propio
    endpoint público de Auth ya permite a cualquiera, nunca bypasear RLS de
    `roles_usuario`/`sesiones` como sí podría la `secret` key.
    """
    return obtener_cliente_supabase_publico()
