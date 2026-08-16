"""Objetos de valor del contexto `fila`.

Python puro -- sin FastAPI, sin Pydantic, sin `supabase-py`. Debe poder importarse y
testearse sin red ni base de datos.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResumenFilaNegocio:
    """Espejo de una fila de `public.resumen_fila_publico` (ver
    `supabase/migrations/011_fila_publica_agregada.sql`): el ÚNICO agregado
    cross-tenant de lectura pública del esquema -- cantidad de personas en fila,
    tiempo de espera estimado y coordenadas de un negocio activo, pensado para un
    mapa público (sin login, sin ningún dato individual de cliente/profesional).

    `tiempo_espera_estimado_minutos`, `latitud` y `longitud` son `None` cuando el
    negocio no tiene base real para esa estimación o no ha sido geolocalizado
    todavía -- nunca un valor inventado (ver Decisión 4 y la nota final de la
    migración 011). El caso de uso no rellena esos huecos con nada: los propaga
    tal cual, la decisión de cómo mostrarlos es del frontend.
    """

    tenant_id: str
    nombre_sede: str
    slug_sede: str
    personas_en_fila: int
    tiempo_espera_estimado_minutos: int | None
    latitud: float | None
    longitud: float | None
