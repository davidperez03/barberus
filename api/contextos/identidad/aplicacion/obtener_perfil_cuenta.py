"""Caso de uso: obtener el perfil de gestión de cuenta del usuario autenticado.

Orquesta el dominio a través de `RepositorioPerfilPuerto`; no contiene reglas de negocio
propias ni sabe de HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.excepciones import PerfilNoEncontrado
from contextos.identidad.dominio.objetos_valor import PerfilCuenta
from contextos.identidad.dominio.puertos import RepositorioPerfilPuerto


@dataclass(frozen=True, slots=True)
class ObtenerPerfilCuenta:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    repositorio_perfil: RepositorioPerfilPuerto

    def ejecutar(self, token_jwt: str, usuario_id: str) -> PerfilCuenta:
        perfil = self.repositorio_perfil.obtener_perfil(token_jwt=token_jwt, usuario_id=usuario_id)
        if perfil is None:
            raise PerfilNoEncontrado(f"No existe perfil para el usuario {usuario_id}")
        return perfil
