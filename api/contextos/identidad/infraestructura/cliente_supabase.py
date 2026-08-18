"""Cliente `supabase-py` compartido por los adaptadores de este contexto.

Un único cliente por proceso, con la `secret` key (sistema nuevo de API keys de Supabase,
reemplaza a `service_role`): el backend consulta
`roles_usuario`/`sesiones` con privilegios que bypasean RLS a propósito -- la
autorización real la resuelve el propio caso de uso de `identidad` (dominio) antes de
que el resultado llegue a ningún otro contexto; RLS en Supabase queda como segunda capa
de defensa para accesos directos (PostgREST desde el frontend), no como la única, tal
como ya lo asume `docs/ARCHITECTURE.md`.

Único lugar de todo `identidad` (y, por convención, de cualquier contexto futuro) donde
se instancia el cliente de Supabase -- el resto de `infraestructura/` lo recibe inyectado.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from nucleo.configuracion import obtener_configuracion


@lru_cache
def obtener_cliente_supabase() -> Client:
    configuracion = obtener_configuracion()
    return create_client(configuracion.supabase_url, configuracion.supabase_secret_key)


@lru_cache
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
    configuracion = obtener_configuracion()
    return create_client(configuracion.supabase_url, configuracion.supabase_publishable_key)
