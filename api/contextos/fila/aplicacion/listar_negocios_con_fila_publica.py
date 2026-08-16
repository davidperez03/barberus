"""Caso de uso: listar negocios activos con su resumen de fila público.

Orquesta el dominio a través de `RepositorioResumenFilaPublicaPuerto`; no contiene
lógica de negocio propia -- el cálculo de personas en fila y tiempo estimado ya lo
hace el trigger de Postgres (ver `supabase/migrations/011_fila_publica_agregada.sql`),
esto solo lo lee y lo expone. Tampoco recibe `tenant_id`/`usuario_id`: es
deliberadamente el único caso de uso de toda la API sin scoping por tenant, porque el
endpoint que lo invoca es público y cross-tenant a propósito (comparador/mapa sin
login).
"""

from __future__ import annotations

from dataclasses import dataclass

from contextos.fila.dominio.objetos_valor import ResumenFilaNegocio
from contextos.fila.dominio.puertos import RepositorioResumenFilaPublicaPuerto


@dataclass(frozen=True, slots=True)
class ListarNegociosConFilaPublica:
    """Caso de uso. Recibe su puerto por constructor (inyectado desde `interfaces/`)."""

    repositorio: RepositorioResumenFilaPublicaPuerto

    def ejecutar(self) -> list[ResumenFilaNegocio]:
        return self.repositorio.listar_activos()
