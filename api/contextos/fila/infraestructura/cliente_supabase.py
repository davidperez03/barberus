"""Cliente `supabase-py` usado por los adaptadores de `fila`.

La instanciación genérica (`create_client` + cache de un cliente por proceso) vive en
`nucleo.cliente_supabase` -- este módulo solo decide, con su razonamiento propio, qué
key usa y la reexporta bajo el nombre que ya usa el resto de `fila`.

Único lugar de `fila` donde se decide qué key usar -- el resto de `infraestructura/`
recibe el cliente inyectado.
"""

from __future__ import annotations

from supabase import Client

from nucleo.cliente_supabase import (
    obtener_cliente_supabase_publico as _obtener_cliente_supabase_publico,
)


def obtener_cliente_supabase_publico() -> Client:
    """Cliente de `fila`, inicializado con la clave PÚBLICA (`publishable`) -- nunca
    con la `secret` key que usa `identidad`. `resumen_fila_publico` es la única tabla
    del esquema con una policy de lectura genuinamente pública (`using (activo)`,
    abierta a `anon` Y `authenticated`, ver
    `supabase/migrations/011_fila_publica_agregada.sql`): bypasear RLS con la `secret`
    key no otorga ningún dato adicional legítimo aquí y violaría el principio de menor
    privilegio (mismo criterio ya aplicado en
    `contextos.identidad.infraestructura.cliente_supabase.obtener_cliente_supabase_auth`
    para signup/login). Si esta clave se filtrara, solo permite leer lo que cualquier
    visitante anónimo ya puede leer desde el propio frontend.
    """
    return _obtener_cliente_supabase_publico()
