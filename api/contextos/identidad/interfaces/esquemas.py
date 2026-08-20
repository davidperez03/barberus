"""Esquemas Pydantic de request/response de `identidad`. Pydantic vive SOLO acá dentro
del contexto -- `dominio/` y `aplicacion/` no lo conocen.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from contextos.identidad.dominio.objetos_valor import ContextoIdentidad, DatosSesionAuth


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


class CredencialesPeticion(BaseModel):
    """Body de `POST /identidad/registro` y `POST /identidad/iniciar-sesion`."""

    correo: EmailStr
    contrasena: str = Field(min_length=8, description="Mínimo 8 caracteres (mínimo de GoTrue).")


class DatosSesionAuthRespuesta(BaseModel):
    """Respuesta de `POST /identidad/registro` y `POST /identidad/iniciar-sesion`."""

    token_acceso: str
    token_actualizacion: str
    usuario_id: str
    expira_at: datetime

    @classmethod
    def desde_dominio(cls, datos: DatosSesionAuth) -> DatosSesionAuthRespuesta:
        return cls(
            token_acceso=datos.token_acceso,
            token_actualizacion=datos.token_actualizacion,
            usuario_id=datos.usuario_id,
            expira_at=datos.expira_at,
        )
