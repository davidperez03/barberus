"""Esquemas Pydantic de request/response de `identidad`. Pydantic vive SOLO acá dentro
del contexto -- `dominio/` y `aplicacion/` no lo conocen.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, model_validator

from contextos.identidad.dominio.objetos_valor import (
    CambiosPerfil,
    ContextoIdentidad,
    DatosSesionAuth,
    DatosToken,
    EventoAuditoria,
    FactorMfa,
    InscripcionMfaTotp,
    PerfilCuenta,
    Sesion,
)


class SesionRespuesta(BaseModel):
    """Respuesta de `GET /identidad/sesiones` (una fila) y de `sesion` en
    `ContextoIdentidadRespuesta` -- dispositivo/IP/nivel de autenticación/timestamps de
    `public.sesiones`, nunca el JWT en sí."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    dispositivo: str | None
    ip: str | None
    nivel_autenticacion: str
    iniciada_at: datetime
    ultima_actividad_at: datetime
    expira_at: datetime
    cerrada_at: datetime | None
    activa: bool

    @classmethod
    def desde_dominio(cls, sesion: Sesion) -> SesionRespuesta:
        return cls(
            id=sesion.id,
            dispositivo=sesion.dispositivo,
            ip=sesion.ip,
            nivel_autenticacion=sesion.nivel_autenticacion.value,
            iniciada_at=sesion.iniciada_at,
            ultima_actividad_at=sesion.ultima_actividad_at,
            expira_at=sesion.expira_at,
            cerrada_at=sesion.cerrada_at,
            activa=sesion.activa,
        )


class ContextoIdentidadRespuesta(BaseModel):
    """Respuesta de `GET /identidad/contexto` -- mapea `ContextoIdentidad` del dominio."""

    usuario_id: str
    correo: str | None
    tenant_id: str | None
    rol: str
    sesion: SesionRespuesta | None

    @classmethod
    def desde_dominio(cls, contexto: ContextoIdentidad) -> ContextoIdentidadRespuesta:
        sesion = (
            SesionRespuesta.desde_dominio(contexto.sesion) if contexto.sesion is not None else None
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


class PerfilCuentaRespuesta(BaseModel):
    """Respuesta de `GET`/`PATCH /identidad/perfil`.

    Deliberadamente NO incluye `tenant_id`/`rol` (a diferencia de
    `ContextoIdentidadRespuesta`): `perfiles_usuario` no tiene `tenant_id` -- es una fila
    por usuario, no por (usuario, tenant) -- y gestión de cuenta debe funcionar para
    CUALQUIER usuario autenticado, incluso uno recién registrado sin ninguna fila en
    `roles_usuario` todavía (`cliente` se autoasigna recién en su primera reserva) o con
    roles en varios tenants sin `X-Tenant-Id` explícito. Exigir un rol/tenant ya resuelto
    acá (vía `ContextoIdentidadDep`) bloquearía a esos usuarios con un 403 que no tiene
    nada que ver con poder ver/editar su propio perfil -- por eso este endpoint usa
    `DatosTokenDep` (solo JWT validado), no `ContextoIdentidadDep`. Reusa igual la MISMA
    validación de JWT que `ContextoIdentidadRespuesta` (`ValidadorTokenPuerto`
    compartido), solo que sin la resolución de rol/tenant que no aplica acá.
    """

    usuario_id: str
    correo: str | None
    nombre_completo: str | None
    avatar_url: str | None
    terminos_aceptados_at: datetime | None
    terminos_version: str | None
    onboarding_completado_at: datetime | None

    @classmethod
    def desde_dominio(cls, datos_token: DatosToken, perfil: PerfilCuenta) -> PerfilCuentaRespuesta:
        return cls(
            usuario_id=datos_token.usuario_id,
            correo=datos_token.correo,
            nombre_completo=perfil.nombre_completo,
            avatar_url=perfil.avatar_url,
            terminos_aceptados_at=perfil.terminos_aceptados_at,
            terminos_version=perfil.terminos_version,
            onboarding_completado_at=perfil.onboarding_completado_at,
        )


class ActualizarPerfilPeticion(BaseModel):
    """Body de `PATCH /identidad/perfil` -- edición PARCIAL: un campo ausente/`None`
    significa "no lo toques", nunca "bórralo" (ver `dominio.objetos_valor.CambiosPerfil`).
    Solo valida FORMATO acá (URL válida, string no vacío) -- QUÉ columnas se pueden tocar
    lo decide únicamente Postgres (RLS + `restringir_columnas_perfil_usuario`), nunca este
    esquema ni el caso de uso.
    """

    nombre_completo: str | None = Field(default=None, min_length=1, max_length=200)
    avatar_url: HttpUrl | None = None
    terminos_aceptados_at: datetime | None = None
    terminos_version: str | None = Field(default=None, min_length=1)
    onboarding_completado_at: datetime | None = None

    @model_validator(mode="after")
    def _validar_terminos_van_juntos(self) -> ActualizarPerfilPeticion:
        if (self.terminos_aceptados_at is None) != (self.terminos_version is None):
            raise ValueError(
                "terminos_aceptados_at y terminos_version deben enviarse juntos (o ninguno)"
            )
        return self

    def a_cambios_dominio(self) -> CambiosPerfil:
        return CambiosPerfil(
            nombre_completo=self.nombre_completo,
            avatar_url=str(self.avatar_url) if self.avatar_url is not None else None,
            terminos_aceptados_at=self.terminos_aceptados_at,
            terminos_version=self.terminos_version,
            onboarding_completado_at=self.onboarding_completado_at,
        )


class MensajeRespuesta(BaseModel):
    """Respuesta genérica de un endpoint sin datos propios que devolver más allá de un
    mensaje de confirmación (recuperación de contraseña, restablecimiento)."""

    mensaje: str


class RecuperarContrasenaPeticion(BaseModel):
    """Body de `POST /identidad/recuperar-contrasena`."""

    correo: EmailStr


class RestablecerContrasenaPeticion(BaseModel):
    """Body de `POST /identidad/restablecer-contrasena`.

    `token_acceso`/`token_actualizacion` son el par access/refresh token de la sesión de
    RECUPERACIÓN que el frontend obtuvo al abrir el enlace del correo (no la sesión normal
    de login) -- Supabase ya validó que ese enlace es legítimo antes de emitirlos.
    """

    token_acceso: str
    token_actualizacion: str
    nueva_contrasena: str = Field(min_length=8, description="Mínimo 8 caracteres (mínimo de GoTrue).")


class EventoAuditoriaRespuesta(BaseModel):
    """Una fila de `GET /identidad/auditoria`."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    evento: str
    tenant_id: str | None
    ip: str | None
    user_agent: str | None
    metadata: dict
    creado_at: datetime

    @classmethod
    def desde_dominio(cls, evento: EventoAuditoria) -> EventoAuditoriaRespuesta:
        return cls(
            id=evento.id,
            evento=evento.evento.value,
            tenant_id=evento.tenant_id,
            ip=evento.ip,
            user_agent=evento.user_agent,
            metadata=evento.metadata,
            creado_at=evento.creado_at,
        )


class CambiarContrasenaPeticion(BaseModel):
    """Body de `POST /identidad/cambiar-contrasena` -- distinto de
    `RestablecerContrasenaPeticion` (esa es el flujo SIN sesión vía correo). Exige la
    contraseña ACTUAL: nunca basta con estar logueado para poder cambiarla (ver
    `aplicacion.cambiar_contrasena`)."""

    contrasena_actual: str = Field(min_length=8)
    nueva_contrasena: str = Field(min_length=8, description="Mínimo 8 caracteres (mínimo de GoTrue).")


class CambiarCorreoPeticion(BaseModel):
    """Body de `POST /identidad/cambiar-correo`. Requiere reautenticación reciente (JWT
    < 10 minutos) -- ver `aplicacion.cambiar_correo`. GoTrue envía confirmación por
    correo (`double_confirm_changes = true`): el cambio queda pendiente hasta que se
    confirme, esta petición solo lo inicia."""

    nuevo_correo: EmailStr


class InscribirMfaPeticion(BaseModel):
    """Body de `POST /identidad/mfa/inscribir`."""

    nombre_amistoso: str | None = Field(
        default=None, min_length=1, max_length=100, description='p.ej. "iPhone de Ana"'
    )


class InscripcionMfaRespuesta(BaseModel):
    """Respuesta de `POST /identidad/mfa/inscribir`: secreto/QR para configurar la app
    authenticator. El factor queda `unverified` hasta
    `POST /identidad/mfa/verificar-inscripcion`."""

    factor_id: str
    secreto: str
    codigo_qr: str
    uri: str
    nombre_amistoso: str | None

    @classmethod
    def desde_dominio(cls, inscripcion: InscripcionMfaTotp) -> InscripcionMfaRespuesta:
        return cls(
            factor_id=inscripcion.factor_id,
            secreto=inscripcion.secreto,
            codigo_qr=inscripcion.codigo_qr,
            uri=inscripcion.uri,
            nombre_amistoso=inscripcion.nombre_amistoso,
        )


class VerificarInscripcionMfaPeticion(BaseModel):
    """Body de `POST /identidad/mfa/verificar-inscripcion`."""

    factor_id: str
    codigo: str = Field(min_length=6, max_length=10, description="Código TOTP de la app authenticator.")


class DesactivarMfaPeticion(BaseModel):
    """Body de `POST /identidad/mfa/desactivar`. Exige reautenticación reciente (JWT <
    10 minutos) -- ver `aplicacion.desactivar_mfa`."""

    factor_id: str


class FactorMfaRespuesta(BaseModel):
    """Una fila de `GET /identidad/mfa/factores`."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tipo: str
    estado: str
    nombre_amistoso: str | None
    creado_at: datetime
    actualizado_at: datetime

    @classmethod
    def desde_dominio(cls, factor: FactorMfa) -> FactorMfaRespuesta:
        return cls(
            id=factor.id,
            tipo=factor.tipo.value,
            estado=factor.estado.value,
            nombre_amistoso=factor.nombre_amistoso,
            creado_at=factor.creado_at,
            actualizado_at=factor.actualizado_at,
        )
