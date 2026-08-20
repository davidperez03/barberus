"""Caso de uso: cerrar UNA sesión puntual del usuario autenticado (distinto de
`CerrarTodasLasSesiones`, que revoca de verdad todos los dispositivos vía Auth Admin
API).

Ver la limitación explícita en `dominio.puertos.RepositorioSesionesPuerto.cerrar_sesion`:
esto solo marca metadata de aplicación, no revoca el JWT real de ese dispositivo.
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.objetos_valor import Sesion
from contextos.identidad.dominio.puertos import RepositorioSesionesPuerto


@dataclass(frozen=True, slots=True)
class CerrarSesion:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    repositorio_sesiones: RepositorioSesionesPuerto

    def ejecutar(self, usuario_id: str, sesion_id: str) -> Sesion:
        """Levanta `dominio.excepciones.SesionNoEncontrada` si `sesion_id` no existe o
        no pertenece a `usuario_id`."""
        return self.repositorio_sesiones.cerrar_sesion(usuario_id=usuario_id, sesion_id=sesion_id)
