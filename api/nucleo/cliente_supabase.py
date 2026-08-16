"""Factory genérico de clientes `supabase-py`, compartido por todos los contextos.

Vive en `nucleo/` por la misma razón que `configuracion.py`: la instanciación de
`Client` (`create_client` + `@lru_cache` para un único cliente por proceso) es idéntica
en cualquier contexto -- lo único que cambia es QUÉ key se usa, y esa decisión (con su
razonamiento de seguridad/dominio) le corresponde a cada `contextos/<contexto>/
infraestructura/cliente_supabase.py`, que reexporta/envuelve las funciones de acá.

No decidas aquí cuál de las dos usar -- ese criterio (RLS sí/no) es responsabilidad de
cada contexto y debe quedar documentado en su propio módulo de infraestructura.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from nucleo.configuracion import obtener_configuracion


@lru_cache
def obtener_cliente_supabase_secreto() -> Client:
    """Cliente inicializado con la `secret` key: bypasea RLS por completo.

    Úsalo solo cuando el propio backend (dominio/aplicación del contexto) ya resolvió
    la autorización antes de llegar a la query, y necesita leer/escribir sin las
    restricciones de RLS (p. ej. `identidad` consultando `roles_usuario`/`sesiones`
    de cualquier usuario). Si esta key se filtra, otorga acceso total a los datos.
    """
    configuracion = obtener_configuracion()
    return create_client(configuracion.supabase_url, configuracion.supabase_secret_key)


@lru_cache
def obtener_cliente_supabase_publico() -> Client:
    """Cliente inicializado con la `publishable` key: respeta RLS, mismo privilegio
    que tendría un cliente anónimo (`anon`) o autenticado desde el frontend.

    Úsalo cuando la operación es legítimamente pública o cuando bypasear RLS no
    otorgaría ningún dato/privilegio adicional (p. ej. signup/login contra GoTrue, o
    lectura de una tabla con policy abierta). Si esta key se filtra, solo permite lo
    que cualquier visitante ya puede hacer/leer legítimamente.
    """
    configuracion = obtener_configuracion()
    return create_client(configuracion.supabase_url, configuracion.supabase_publishable_key)
