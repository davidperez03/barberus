"""Caso de uso: listar los factores MFA (verificados y no verificados) del usuario
autenticado -- necesario para que el frontend pueda mostrar "tienes 2FA activo" y ofrecer
`factor_id` para `DesactivarMfa` sin depender de que el cliente lo haya guardado desde la
respuesta de `InscribirMfa`.
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.objetos_valor import FactorMfa
from contextos.identidad.dominio.puertos import AutenticadorMfaPuerto


@dataclass(frozen=True, slots=True)
class ListarFactoresMfa:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    autenticador_mfa: AutenticadorMfaPuerto

    def ejecutar(self, token_acceso: str) -> list[FactorMfa]:
        return self.autenticador_mfa.listar_factores(token_acceso=token_acceso)
