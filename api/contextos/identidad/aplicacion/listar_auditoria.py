"""Caso de uso: historial de accesos/cambios sensibles del usuario autenticado
(`auditoria_autenticacion`), paginado.

`limite`/`offset` ya llegan validados en rango razonable desde `interfaces/esquemas.py`
(nunca "toda la tabla sin límite") -- este caso de uso no vuelve a acotarlos, solo los
reenvía al puerto.
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.identidad.dominio.objetos_valor import EventoAuditoria
from contextos.identidad.dominio.puertos import RepositorioAuditoriaPuerto


@dataclass(frozen=True, slots=True)
class ListarAuditoria:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    repositorio_auditoria: RepositorioAuditoriaPuerto

    def ejecutar(self, usuario_id: str, limite: int, offset: int) -> list[EventoAuditoria]:
        return self.repositorio_auditoria.listar_eventos(
            usuario_id=usuario_id, limite=limite, offset=offset
        )
