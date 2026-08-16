"""Tests de `ListarNegociosConFilaPublica` con un fake de
`RepositorioResumenFilaPublicaPuerto` -- ninguna dependencia real de Supabase/red.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contextos.fila.aplicacion.listar_negocios_con_fila_publica import (
    ListarNegociosConFilaPublica,
)
from contextos.fila.dominio.objetos_valor import ResumenFilaNegocio


@dataclass
class RepositorioResumenFilaPublicaFake:
    resumenes: list[ResumenFilaNegocio] = field(default_factory=list)

    def listar_activos(self) -> list[ResumenFilaNegocio]:
        return self.resumenes


def _resumen(**overrides: object) -> ResumenFilaNegocio:
    valores = {
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "nombre_sede": "Barbería Central",
        "slug_sede": "barberia-central",
        "personas_en_fila": 3,
        "tiempo_espera_estimado_minutos": 15,
        "latitud": 4.710989,
        "longitud": -74.072092,
    }
    valores.update(overrides)
    return ResumenFilaNegocio(**valores)


def test_listar_negocios_con_fila_publica_devuelve_lo_que_expone_el_repositorio() -> None:
    resumen = _resumen()
    caso_de_uso = ListarNegociosConFilaPublica(
        repositorio=RepositorioResumenFilaPublicaFake(resumenes=[resumen])
    )

    resultado = caso_de_uso.ejecutar()

    assert resultado == [resumen]


def test_listar_negocios_con_fila_publica_sin_negocios_activos_devuelve_lista_vacia() -> None:
    caso_de_uso = ListarNegociosConFilaPublica(repositorio=RepositorioResumenFilaPublicaFake())

    resultado = caso_de_uso.ejecutar()

    assert resultado == []


def test_listar_negocios_con_fila_publica_no_inventa_tiempo_estimado_ni_coordenadas() -> None:
    """El caso de uso no debe rellenar los `None` de negocios sin historial reciente
    (tiempo estimado) o sin geolocalizar (lat/lng) -- los propaga tal cual, ver el
    docstring de `ResumenFilaNegocio`."""
    resumen_sin_datos_derivados = _resumen(
        tiempo_espera_estimado_minutos=None, latitud=None, longitud=None
    )
    caso_de_uso = ListarNegociosConFilaPublica(
        repositorio=RepositorioResumenFilaPublicaFake(resumenes=[resumen_sin_datos_derivados])
    )

    resultado = caso_de_uso.ejecutar()

    assert resultado[0].tiempo_espera_estimado_minutos is None
    assert resultado[0].latitud is None
    assert resultado[0].longitud is None
