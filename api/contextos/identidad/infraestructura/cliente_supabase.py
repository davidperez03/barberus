"""Cliente `supabase-py` compartido por los adaptadores de este contexto.

Un único cliente por proceso, con la `service_role` key: el backend consulta
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
    return create_client(configuracion.supabase_url, configuracion.supabase_service_role_key)
