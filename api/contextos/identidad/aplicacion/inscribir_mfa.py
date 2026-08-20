"""Caso de uso: iniciar la inscripción de un factor MFA TOTP nuevo.

Orquesta el dominio a través de `AutenticadorMfaPuerto` (proxy del soporte nativo de
GoTrue -- ver el docstring de ese puerto para por qué no se reimplementa TOTP a mano).
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.objetos_valor import InscripcionMfaTotp
from contextos.identidad.dominio.puertos import AutenticadorMfaPuerto


@dataclass(frozen=True, slots=True)
class InscribirMfa:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    autenticador_mfa: AutenticadorMfaPuerto

    def ejecutar(self, token_acceso: str, nombre_amistoso: str | None) -> InscripcionMfaTotp:
        return self.autenticador_mfa.inscribir_totp(
            token_acceso=token_acceso, nombre_amistoso=nombre_amistoso
        )
