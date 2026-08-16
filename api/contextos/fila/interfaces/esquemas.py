"""Esquemas Pydantic de respuesta de `fila`. Pydantic vive SOLO acá dentro del
contexto -- `dominio/` y `aplicacion/` no lo conocen.
"""

from __future__ import annotations

from pydantic import BaseModel

from contextos.fila.dominio.objetos_valor import ResumenFilaNegocio


class ResumenFilaNegocioRespuesta(BaseModel):
    """Un ítem de `GET /fila/publica` -- un negocio activo con su resumen de fila,
    pensado para un marcador en el mapa (lat/lng) con semáforo de ocupación
    (`personas_en_fila`).
    """

    tenant_id: str
    nombre_sede: str
    slug_sede: str
    personas_en_fila: int
    tiempo_espera_estimado_minutos: int | None
    latitud: float | None
    longitud: float | None

    @classmethod
    def desde_dominio(cls, resumen: ResumenFilaNegocio) -> ResumenFilaNegocioRespuesta:
        return cls(
            tenant_id=resumen.tenant_id,
            nombre_sede=resumen.nombre_sede,
            slug_sede=resumen.slug_sede,
            personas_en_fila=resumen.personas_en_fila,
            tiempo_espera_estimado_minutos=resumen.tiempo_espera_estimado_minutos,
            latitud=resumen.latitud,
            longitud=resumen.longitud,
        )
