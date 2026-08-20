"""Caso de uso: el usuario autenticado elimina (soft-delete) su PROPIA cuenta.

Orquesta el dominio a través de `GestorCuentaPuerto`; no sabe de HTTP. `usuario_id`
SIEMPRE llega desde el JWT ya validado (`DatosTokenDep` en `interfaces/`) -- nunca
desde el body de la request, para que nadie pueda pedir la eliminación de una cuenta
ajena.
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.puertos import GestorCuentaPuerto


@dataclass(frozen=True, slots=True)
class EliminarCuenta:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    gestor_cuenta: GestorCuentaPuerto

    def ejecutar(self, usuario_id: str) -> None:
        self.gestor_cuenta.eliminar_cuenta(usuario_id=usuario_id)
