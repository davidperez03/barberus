"""Caso de uso: el propio usuario edita campos de su perfil de cuenta.

Orquesta el dominio a través de `RepositorioPerfilPuerto`; la validación de FORMATO (URL
válida, string no vacío) ya ocurrió en `interfaces/esquemas.py` -- la validación de QUÉ
columnas puede tocar la aplica Postgres (RLS + trigger de whitelist), nunca este caso de
uso.
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.objetos_valor import CambiosPerfil, PerfilCuenta
from contextos.identidad.dominio.puertos import RepositorioPerfilPuerto


@dataclass(frozen=True, slots=True)
class ActualizarPerfilCuenta:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    repositorio_perfil: RepositorioPerfilPuerto

    def ejecutar(self, token_jwt: str, usuario_id: str, cambios: CambiosPerfil) -> PerfilCuenta:
        return self.repositorio_perfil.actualizar_perfil(
            token_jwt=token_jwt, usuario_id=usuario_id, cambios=cambios
        )
