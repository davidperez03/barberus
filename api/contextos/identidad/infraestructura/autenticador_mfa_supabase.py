"""Adaptador concreto de `AutenticadorMfaPuerto` -- proxea el soporte NATIVO de MFA TOTP
de Supabase Auth (`auth.mfa.*` de `supabase-py`/GoTrue), habilitado en
`supabase/config.toml` (`[auth.mfa.totp] enroll_enabled = true, verify_enabled = true`).

No hay tabla propia involucrada: GoTrue guarda los factores en su propio esquema
`auth.mfa_factors`/`auth.mfa_challenges` -- `factores_autenticacion`/
`retos_autenticacion` (`010_identidad_extendida.sql`) quedan MFA-ready pero sin uso, ver
la nota de arquitectura completa en `dominio.puertos.AutenticadorMfaPuerto`.
"""

from __future__ import annotations

from dataclasses import dataclass

from supabase_auth.errors import AuthApiError

from contextos.identidad.dominio.excepciones import (
    CodigoMfaInvalido,
    FactorMfaNoEncontrado,
    SolicitudAutenticacionInvalida,
)
from contextos.identidad.dominio.objetos_valor import (
    EstadoFactorMfa,
    FactorMfa,
    InscripcionMfaTotp,
    TipoFactorMfa,
)
from contextos.identidad.dominio.puertos import AutenticadorMfaPuerto
from contextos.identidad.infraestructura.cliente_supabase import (
    obtener_cliente_con_sesion_de_token,
)

# Códigos de GoTrue (`supabase_auth.errors.ErrorCode`) que indican "código TOTP
# incorrecto o reto vencido" al verificar -- se remapean a `CodigoMfaInvalido` (400), no
# a un error de autenticación (la identidad del llamador ya es conocida, JWT válido).
_CODIGOS_CODIGO_MFA_INVALIDO = frozenset(
    {"mfa_verification_failed", "mfa_verification_rejected", "mfa_challenge_expired"}
)


@dataclass(frozen=True, slots=True)
class AutenticadorMfaSupabase(AutenticadorMfaPuerto):
    def inscribir_totp(self, token_acceso: str, nombre_amistoso: str | None) -> InscripcionMfaTotp:
        cliente = obtener_cliente_con_sesion_de_token(token_acceso)
        parametros = {"factor_type": "totp"}
        if nombre_amistoso is not None:
            parametros["friendly_name"] = nombre_amistoso
        try:
            respuesta = cliente.auth.mfa.enroll(parametros)
        except AuthApiError as error:
            raise SolicitudAutenticacionInvalida(str(error)) from error
        if respuesta.totp is None:
            # No debería ocurrir pidiendo factor_type="totp" -- defensivo, mismo criterio
            # que `AutenticadorSupabase._mapear` con una respuesta exitosa incompleta.
            raise SolicitudAutenticacionInvalida(
                "Supabase Auth no devolvió los datos de inscripción TOTP esperados"
            )
        return InscripcionMfaTotp(
            factor_id=respuesta.id,
            secreto=respuesta.totp.secret,
            codigo_qr=respuesta.totp.qr_code,
            uri=respuesta.totp.uri,
            nombre_amistoso=respuesta.friendly_name,
        )

    def verificar_inscripcion(self, token_acceso: str, factor_id: str, codigo: str) -> None:
        cliente = obtener_cliente_con_sesion_de_token(token_acceso)
        try:
            cliente.auth.mfa.challenge_and_verify({"factor_id": factor_id, "code": codigo})
        except AuthApiError as error:
            if error.code in _CODIGOS_CODIGO_MFA_INVALIDO:
                raise CodigoMfaInvalido("El código ingresado no es válido o expiró") from error
            if error.code == "mfa_factor_not_found":
                raise FactorMfaNoEncontrado(
                    f"No existe el factor MFA {factor_id} para este usuario"
                ) from error
            raise SolicitudAutenticacionInvalida(str(error)) from error

    def desactivar(self, token_acceso: str, factor_id: str) -> None:
        cliente = obtener_cliente_con_sesion_de_token(token_acceso)
        try:
            cliente.auth.mfa.unenroll({"factor_id": factor_id})
        except AuthApiError as error:
            if error.code == "mfa_factor_not_found":
                raise FactorMfaNoEncontrado(
                    f"No existe el factor MFA {factor_id} para este usuario"
                ) from error
            raise SolicitudAutenticacionInvalida(str(error)) from error

    def listar_factores(self, token_acceso: str) -> list[FactorMfa]:
        cliente = obtener_cliente_con_sesion_de_token(token_acceso)
        try:
            respuesta = cliente.auth.mfa.list_factors()
        except AuthApiError as error:
            raise SolicitudAutenticacionInvalida(str(error)) from error
        return [
            FactorMfa(
                id=factor.id,
                tipo=TipoFactorMfa(factor.factor_type),
                estado=EstadoFactorMfa(factor.status),
                nombre_amistoso=factor.friendly_name,
                creado_at=factor.created_at,
                actualizado_at=factor.updated_at,
            )
            for factor in respuesta.all
        ]
