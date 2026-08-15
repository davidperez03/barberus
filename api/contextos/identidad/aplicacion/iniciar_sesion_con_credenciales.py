"""Caso de uso: iniciar sesión con correo/contraseña contra Supabase Auth.

Orquesta el dominio a través de `AutenticadorPuerto`; no contiene reglas de negocio
propias ni sabe de HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.objetos_valor import DatosSesionAuth
from contextos.identidad.dominio.puertos import AutenticadorPuerto


@dataclass(frozen=True, slots=True)
class IniciarSesionConCredenciales:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    autenticador: AutenticadorPuerto

    def ejecutar(self, correo: str, contrasena: str) -> DatosSesionAuth:
        """Levanta `dominio.excepciones.CredencialesInvalidas` -- ver
        `AutenticadorPuerto.iniciar_sesion`.
        """
        return self.autenticador.iniciar_sesion(correo=correo, contrasena=contrasena)
