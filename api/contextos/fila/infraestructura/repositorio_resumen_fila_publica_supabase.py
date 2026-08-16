"""Adaptador concreto de `RepositorioResumenFilaPublicaPuerto` contra
`public.resumen_fila_publico`.

Solo lectura, con el cliente inicializado con la `publishable` key (ver
`cliente_supabase.py`) -- la policy `resumen_fila_publico_select_publico` ya filtra
`activo = true` en Postgres (RLS), este adaptador no duplica esa condición: confía en
RLS como fuente de verdad de qué filas son públicas, igual que hace el frontend
consultando PostgREST directo.
"""

from __future__ import annotations

from dataclasses import dataclass

from supabase import Client

from contextos.fila.dominio.objetos_valor import ResumenFilaNegocio

_COLUMNAS = (
    "tenant_id, nombre_sede, slug_sede, personas_en_fila, "
    "tiempo_espera_estimado_minutos, latitud, longitud"
)


@dataclass(frozen=True, slots=True)
class RepositorioResumenFilaPublicaSupabase:
    cliente: Client

    def listar_activos(self) -> list[ResumenFilaNegocio]:
        respuesta = (
            self.cliente.table("resumen_fila_publico")
            .select(_COLUMNAS)
            .order("nombre_sede")
            .execute()
        )
        return [
            ResumenFilaNegocio(
                tenant_id=fila["tenant_id"],
                nombre_sede=fila["nombre_sede"],
                slug_sede=fila["slug_sede"],
                personas_en_fila=fila["personas_en_fila"],
                tiempo_espera_estimado_minutos=fila["tiempo_espera_estimado_minutos"],
                latitud=fila["latitud"],
                longitud=fila["longitud"],
            )
            for fila in respuesta.data
        ]
