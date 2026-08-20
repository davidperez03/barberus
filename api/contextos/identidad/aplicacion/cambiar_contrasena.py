"""Caso de uso: el usuario autenticado cambia su propia contraseña (distinto de
`RestablecerContrasena`, que es el flujo SIN sesión vía enlace de correo).

Exige reautenticación reciente (JWT emitido hace menos de 10 minutos) Y prueba que el
llamador conoce la contraseña ACTUAL reautenticando contra GoTrue -- ninguna de las dos
sola alcanza: un JWT reciente prueba que alguien inició sesión hace poco (podría ser un
dispositivo desatendido), no que quien hace ESTE request conoce la contraseña.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from contextos.identidad.dominio.puertos import AutenticadorPuerto
from contextos.identidad.dominio.servicios import verificar_reautenticacion_reciente


@dataclass(frozen=True, slots=True)
class CambiarContrasena:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    autenticador: AutenticadorPuerto

    def ejecutar(
        self,
        correo: str,
        token_acceso: str,
        emitido_en: datetime,
        ahora: datetime,
        contrasena_actual: str,
        nueva_contrasena: str,
    ) -> None:
        """Levanta `dominio.excepciones.ReautenticacionRequerida`,
        `dominio.excepciones.CredencialesActualesIncorrectas` o
        `dominio.excepciones.SolicitudAutenticacionInvalida` -- ver
        `AutenticadorPuerto.verificar_contrasena`/`cambiar_contrasena`."""
        verificar_reautenticacion_reciente(emitido_en, ahora)
        self.autenticador.verificar_contrasena(correo=correo, contrasena=contrasena_actual)
        self.autenticador.cambiar_contrasena(
            token_acceso=token_acceso, nueva_contrasena=nueva_contrasena
        )
