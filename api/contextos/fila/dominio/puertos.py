"""Puertos del contexto `fila`: lo que la aplicación necesita del mundo exterior,
expresado como `Protocol` -- sin saber NADA de cómo se implementa (Supabase, otro
proveedor, un fake de test).
"""

from __future__ import annotations

from typing import Protocol

from contextos.fila.dominio.objetos_valor import ResumenFilaNegocio


class RepositorioResumenFilaPublicaPuerto(Protocol):
    """Lee el comparador público de fila (`resumen_fila_publico`).

    Solo lectura -- la tabla la mantiene un trigger de Postgres (ver migración 011),
    ningún caso de uso de este contexto escribe ahí.
    """

    def listar_activos(self) -> list[ResumenFilaNegocio]:
        """Negocios activos con su resumen de fila, para el mapa/comparador público.

        Un negocio inactivo ya no aparece aquí -- lo filtra la propia policy de RLS
        (`using (activo)`), no una condición añadida por este puerto.
        """
        ...
