"""Caso de uso: listar las sesiones (activas y cerradas) del usuario autenticado."""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.objetos_valor import Sesion
from contextos.identidad.dominio.puertos import RepositorioSesionesPuerto


@dataclass(frozen=True, slots=True)
class ListarSesiones:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    repositorio_sesiones: RepositorioSesionesPuerto

    def ejecutar(self, usuario_id: str) -> list[Sesion]:
        return self.repositorio_sesiones.listar_sesiones(usuario_id=usuario_id)
