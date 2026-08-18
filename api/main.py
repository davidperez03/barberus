"""Composición de la API de Barberus: monta el router de cada contexto delimitado y hace
el wiring de dependencias vía `Depends` (ya resuelto dentro de cada `interfaces/`).

Este módulo NO contiene lógica de negocio ni de autorización -- solo ensambla la app.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from contextos.identidad.interfaces.router import router as router_identidad
from nucleo.configuracion import obtener_configuracion

configuracion = obtener_configuracion()

app = FastAPI(
    title="Barberus API",
    description=(
        "API de Barberus -- arquitectura hexagonal (puertos y adaptadores) + DDD por "
        "contextos delimitados. Ver docs/ARCHITECTURE.md y api/README.md."
    ),
    version="0.1.0",
)

if configuracion.lista_cors_origenes:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configuracion.lista_cors_origenes,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(router_identidad)

# Los routers de agenda/fila/membresias/reportes se agregan acá a medida que cada
# contexto tenga su capa `interfaces/` implementada (PRs futuros) -- misma convención:
# app.include_router(router_<contexto>)


@app.get("/salud", tags=["salud"])
def salud() -> dict[str, str]:
    """Liveness check simple, sin dependencias externas -- no confirma acceso a Supabase."""
    return {"estado": "ok"}
