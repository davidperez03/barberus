"""Caso de uso: cerrar sesión en todos los dispositivos del usuario autenticado.

Orquesta el dominio a través de `GestorCuentaPuerto`; no sabe de HTTP. `token_acceso` es
el JWT de la request actual, ya validado por `ContextoIdentidadDep` en `interfaces/` --
este caso de uso no vuelve a validarlo, solo lo reenvía a la Admin API de GoTrue para que
identifique de quién son las sesiones a revocar (ver
`dominio.puertos.GestorCuentaPuerto.cerrar_todas_las_sesiones`).
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.puertos import GestorCuentaPuerto


@dataclass(frozen=True, slots=True)
class CerrarTodasLasSesiones:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    gestor_cuenta: GestorCuentaPuerto

    def ejecutar(self, token_acceso: str) -> None:
        self.gestor_cuenta.cerrar_todas_las_sesiones(token_acceso=token_acceso)
