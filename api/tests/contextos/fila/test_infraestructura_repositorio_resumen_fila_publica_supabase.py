"""Tests del adaptador `RepositorioResumenFilaPublicaSupabase` contra PostgREST.

No golpea red real: mockea la cadena `table().select().order().execute()` de
`supabase-py` (acá se prueba el mapeo fila-de-PostgREST -> `ResumenFilaNegocio`, no que
`supabase-py` arme bien la query).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from contextos.fila.dominio.objetos_valor import ResumenFilaNegocio
from contextos.fila.infraestructura.repositorio_resumen_fila_publica_supabase import (
    RepositorioResumenFilaPublicaSupabase,
)

TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _cliente_con_filas(filas: list[dict]) -> MagicMock:
    cliente = MagicMock()
    respuesta = MagicMock()
    respuesta.data = filas
    cliente.table.return_value.select.return_value.order.return_value.execute.return_value = (
        respuesta
    )
    return cliente


def test_listar_activos_mapea_filas_de_postgrest_a_resumen_fila_negocio() -> None:
    cliente = _cliente_con_filas(
        [
            {
                "tenant_id": TENANT_ID,
                "nombre_sede": "Barbería Central",
                "slug_sede": "barberia-central",
                "personas_en_fila": 4,
                "tiempo_espera_estimado_minutos": 20,
                "latitud": 4.710989,
                "longitud": -74.072092,
            }
        ]
    )
    repositorio = RepositorioResumenFilaPublicaSupabase(cliente=cliente)

    resultado = repositorio.listar_activos()

    assert resultado == [
        ResumenFilaNegocio(
            tenant_id=TENANT_ID,
            nombre_sede="Barbería Central",
            slug_sede="barberia-central",
            personas_en_fila=4,
            tiempo_espera_estimado_minutos=20,
            latitud=4.710989,
            longitud=-74.072092,
        )
    ]
    cliente.table.assert_called_once_with("resumen_fila_publico")


def test_listar_activos_propaga_nulos_de_tiempo_estimado_y_coordenadas() -> None:
    """Negocio recién abierto sin historial reciente ni geolocalizar: la fila viene
    con `NULL` desde Postgres (ver Decisión 4 de la migración 011), el adaptador no
    debe inventar ningún valor por defecto."""
    cliente = _cliente_con_filas(
        [
            {
                "tenant_id": TENANT_ID,
                "nombre_sede": "Barbería Nueva",
                "slug_sede": "barberia-nueva",
                "personas_en_fila": 0,
                "tiempo_espera_estimado_minutos": None,
                "latitud": None,
                "longitud": None,
            }
        ]
    )
    repositorio = RepositorioResumenFilaPublicaSupabase(cliente=cliente)

    resultado = repositorio.listar_activos()

    assert resultado[0].tiempo_espera_estimado_minutos is None
    assert resultado[0].latitud is None
    assert resultado[0].longitud is None


def test_listar_activos_sin_negocios_devuelve_lista_vacia() -> None:
    cliente = _cliente_con_filas([])
    repositorio = RepositorioResumenFilaPublicaSupabase(cliente=cliente)

    assert repositorio.listar_activos() == []
