"""Caso de uso: registrar una cuenta nueva en Supabase Auth.

Orquesta el dominio a través de `AutenticadorPuerto`; no contiene reglas de negocio
propias ni sabe de HTTP. Deliberadamente NO toca `roles_usuario`: el registro no asigna
ningún rol -- `cliente` se autoasigna recién en la primera reserva (ver
`docs/ARCHITECTURE.md`), es responsabilidad de un caso de uso propio de `agenda`, no de
`identidad`.
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.objetos_valor import DatosSesionAuth
from contextos.identidad.dominio.puertos import AutenticadorPuerto


@dataclass(frozen=True, slots=True)
class RegistrarUsuario:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    autenticador: AutenticadorPuerto

    def ejecutar(self, correo: str, contrasena: str) -> DatosSesionAuth:
        """Levanta `dominio.excepciones.RegistroSinSesionInmediata` si no hay sesión de
        inmediato -- ver `AutenticadorPuerto.registrar`.
        """
        return self.autenticador.registrar(correo=correo, contrasena=contrasena)
