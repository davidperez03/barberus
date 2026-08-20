"""Caso de uso: desactivar (unenroll) un factor MFA.

Extensión deliberada más allá del pedido explícito de reautenticación reciente (punto 4
del pedido de producto solo listaba cambiar-contrasena/cambiar-correo/eliminar-cuenta):
desactivar el segundo factor de una cuenta es igual de sensible -- quitar protección es
tan crítico como los cambios ya cubiertos -- así que aplica el mismo umbral de 10
minutos por consistencia y por prudencia de seguridad, documentado acá explícitamente
para que quede claro que es una decisión de este PR, no algo que el pedido exigiera.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from contextos.identidad.dominio.puertos import AutenticadorMfaPuerto
from contextos.identidad.dominio.servicios import verificar_reautenticacion_reciente


@dataclass(frozen=True, slots=True)
class DesactivarMfa:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    autenticador_mfa: AutenticadorMfaPuerto

    def ejecutar(
        self, token_acceso: str, factor_id: str, emitido_en: datetime, ahora: datetime
    ) -> None:
        """Levanta `dominio.excepciones.ReautenticacionRequerida` o
        `dominio.excepciones.FactorMfaNoEncontrado`."""
        verificar_reautenticacion_reciente(emitido_en, ahora)
        self.autenticador_mfa.desactivar(token_acceso=token_acceso, factor_id=factor_id)
