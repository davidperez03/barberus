"""`Depends` de FastAPI: resuelven adaptadores concretos e inyectan el caso de uso.

Único lugar de `fila` donde se decide QUÉ implementación concreta de cada puerto se
usa -- si mañana cambia el proveedor de datos, solo este módulo cambia.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from contextos.fila.aplicacion.listar_negocios_con_fila_publica import (
    ListarNegociosConFilaPublica,
)
from contextos.fila.infraestructura.cliente_supabase import obtener_cliente_supabase_publico
from contextos.fila.infraestructura.repositorio_resumen_fila_publica_supabase import (
    RepositorioResumenFilaPublicaSupabase,
)


@lru_cache
def obtener_caso_uso_listar_negocios_con_fila_publica() -> ListarNegociosConFilaPublica:
    cliente = obtener_cliente_supabase_publico()
    return ListarNegociosConFilaPublica(
        repositorio=RepositorioResumenFilaPublicaSupabase(cliente=cliente)
    )


ListarNegociosConFilaPublicaDep = Annotated[
    ListarNegociosConFilaPublica, Depends(obtener_caso_uso_listar_negocios_con_fila_publica)
]
