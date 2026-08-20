"""Caso de uso: el usuario autenticado elimina (soft-delete) su PROPIA cuenta.

Orquesta el dominio a través de `GestorCuentaPuerto`; no sabe de HTTP. `usuario_id`
SIEMPRE llega desde el JWT ya validado (`DatosTokenDep` en `interfaces/`) -- nunca
desde el body de la request, para que nadie pueda pedir la eliminación de una cuenta
ajena.

Exige reautenticación reciente (`emitido_en` del JWT, menos de 10 minutos) antes de
ejecutar -- eliminar la cuenta es tan sensible como cambiar contraseña/correo, mismo
criterio y umbral (ver `dominio.servicios.verificar_reautenticacion_reciente`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from contextos.identidad.dominio.puertos import GestorCuentaPuerto
from contextos.identidad.dominio.servicios import verificar_reautenticacion_reciente


@dataclass(frozen=True, slots=True)
class EliminarCuenta:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    gestor_cuenta: GestorCuentaPuerto

    def ejecutar(self, usuario_id: str, emitido_en: datetime, ahora: datetime) -> None:
        """Levanta `dominio.excepciones.ReautenticacionRequerida` si `emitido_en` (el
        `iat` del JWT actual) tiene más de 10 minutos."""
        verificar_reautenticacion_reciente(emitido_en, ahora)
        self.gestor_cuenta.eliminar_cuenta(usuario_id=usuario_id)
