"""Caso de uso: el usuario autenticado cambia su correo de cuenta.

Exige reautenticación reciente (JWT emitido hace menos de 10 minutos) -- mismo criterio
que `CambiarContrasena`/`EliminarCuenta`. A diferencia de `CambiarContrasena`, NO exige
reingresar la contraseña: el punto 4 del pedido de producto solo especifica el umbral de
`iat`, igual que el trigger SQL de referencia (`exigir_reautenticacion_clientes`), que
tampoco pide la contraseña de nuevo -- la reautenticación reciente ya es la señal
aceptada de "sigue siendo la misma persona".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from contextos.identidad.dominio.puertos import AutenticadorPuerto
from contextos.identidad.dominio.servicios import verificar_reautenticacion_reciente


@dataclass(frozen=True, slots=True)
class CambiarCorreo:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    autenticador: AutenticadorPuerto

    def ejecutar(
        self, token_acceso: str, emitido_en: datetime, ahora: datetime, nuevo_correo: str
    ) -> None:
        """Levanta `dominio.excepciones.ReautenticacionRequerida`,
        `dominio.excepciones.CorreoNoDisponible` o
        `dominio.excepciones.SolicitudAutenticacionInvalida` -- ver
        `AutenticadorPuerto.cambiar_correo`."""
        verificar_reautenticacion_reciente(emitido_en, ahora)
        self.autenticador.cambiar_correo(token_acceso=token_acceso, nuevo_correo=nuevo_correo)
