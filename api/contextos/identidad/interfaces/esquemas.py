"""Esquemas Pydantic de request/response de `identidad`. Pydantic vive SOLO acá dentro
del contexto -- `dominio/` y `aplicacion/` no lo conocen.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from contextos.identidad.dominio.objetos_valor import ContextoIdentidad


class SesionRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nivel_autenticacion: str
    expira_at: datetime
    activa: bool


class ContextoIdentidadRespuesta(BaseModel):
    """Respuesta de `GET /identidad/contexto` -- mapea `ContextoIdentidad` del dominio."""

    usuario_id: str
    correo: str | None
    tenant_id: str | None
    rol: str
    sesion: SesionRespuesta | None

    @classmethod
    def desde_dominio(cls, contexto: ContextoIdentidad) -> ContextoIdentidadRespuesta:
        sesion = None
        if contexto.sesion is not None:
            sesion = SesionRespuesta(
                id=contexto.sesion.id,
                nivel_autenticacion=contexto.sesion.nivel_autenticacion.value,
                expira_at=contexto.sesion.expira_at,
                activa=contexto.sesion.activa,
            )
        return cls(
            usuario_id=contexto.usuario_id,
            correo=contexto.correo,
            tenant_id=contexto.rol_activo.tenant_id,
            rol=contexto.rol_activo.rol.value,
            sesion=sesion,
        )
