"""Caso de uso: confirmar el código TOTP para activar un factor MFA recién inscrito."""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.puertos import AutenticadorMfaPuerto


@dataclass(frozen=True, slots=True)
class VerificarInscripcionMfa:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    autenticador_mfa: AutenticadorMfaPuerto

    def ejecutar(self, token_acceso: str, factor_id: str, codigo: str) -> None:
        """Levanta `dominio.excepciones.CodigoMfaInvalido`/`FactorMfaNoEncontrado` -- ver
        `AutenticadorMfaPuerto.verificar_inscripcion`."""
        self.autenticador_mfa.verificar_inscripcion(
            token_acceso=token_acceso, factor_id=factor_id, codigo=codigo
        )
