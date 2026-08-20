"""Caso de uso: fijar una nueva contraseña sobre una sesión de recuperación ya validada
por Supabase.

Orquesta el dominio a través de `AutenticadorPuerto`; no sabe de HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.puertos import AutenticadorPuerto


@dataclass(frozen=True, slots=True)
class RestablecerContrasena:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    autenticador: AutenticadorPuerto

    def ejecutar(self, token_acceso: str, token_actualizacion: str, nueva_contrasena: str) -> None:
        """Levanta `dominio.excepciones.TokenInvalido`/`SolicitudAutenticacionInvalida` --
        ver `AutenticadorPuerto.restablecer_contrasena`."""
        self.autenticador.restablecer_contrasena(
            token_acceso=token_acceso,
            token_actualizacion=token_actualizacion,
            nueva_contrasena=nueva_contrasena,
        )
