"""Caso de uso: solicitar el correo de recuperación de contraseña.

Orquesta el dominio a través de `AutenticadorPuerto`; no sabe de HTTP. Nunca levanta --
ver `AutenticadorPuerto.enviar_recuperacion_contrasena` para el porqué (anti-enumeración).
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.puertos import AutenticadorPuerto


@dataclass(frozen=True, slots=True)
class SolicitarRecuperacionContrasena:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    autenticador: AutenticadorPuerto

    def ejecutar(self, correo: str) -> None:
        self.autenticador.enviar_recuperacion_contrasena(correo=correo)
