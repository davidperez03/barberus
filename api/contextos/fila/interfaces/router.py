"""Router HTTP de `fila`. Delgado a propósito: llama al caso de uso (ya resuelto por
la dependency) y mapea a respuesta. Cero lógica de negocio, cero queries directas.
"""

from __future__ import annotations

from fastapi import APIRouter

from contextos.fila.interfaces.dependencias import ListarNegociosConFilaPublicaDep
from contextos.fila.interfaces.esquemas import ResumenFilaNegocioRespuesta

router = APIRouter(prefix="/fila", tags=["fila"])


@router.get("/publica", response_model=list[ResumenFilaNegocioRespuesta])
def listar_negocios_con_fila_publica(
    caso_de_uso: ListarNegociosConFilaPublicaDep,
) -> list[ResumenFilaNegocioRespuesta]:
    """Comparador/mapa público de fila entre negocios: SIN autenticación, SIN
    `tenant_id` -- es, a propósito, el único endpoint cross-tenant de toda la API
    (ver `supabase/migrations/011_fila_publica_agregada.sql`). Solo agregados
    (cantidad en fila, tiempo estimado, coordenadas) de negocios activos; nunca datos
    de clientes/profesionales individuales.
    """
    resumenes = caso_de_uso.ejecutar()
    return [ResumenFilaNegocioRespuesta.desde_dominio(resumen) for resumen in resumenes]
