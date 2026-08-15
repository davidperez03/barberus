"""Router HTTP de `identidad`. Delgado a propósito: parsea (vía `Depends`), llama al caso
de uso (ya resuelto por la dependency) y mapea a respuesta. Cero lógica de negocio, cero
queries directas.
"""

from __future__ import annotations

from fastapi import APIRouter

from contextos.identidad.interfaces.dependencias import ContextoIdentidadDep
from contextos.identidad.interfaces.esquemas import ContextoIdentidadRespuesta

router = APIRouter(prefix="/identidad", tags=["identidad"])


@router.get("/contexto", response_model=ContextoIdentidadRespuesta)
def obtener_contexto(contexto: ContextoIdentidadDep) -> ContextoIdentidadRespuesta:
    """Devuelve usuario/rol/tenant/sesión ya resueltos a partir del JWT de la request.

    Endpoint de verificación end-to-end de la capa de auth (útil para QA y para el
    frontend, todavía sin construir) -- equivalente a un `GET /me`.
    """
    return ContextoIdentidadRespuesta.desde_dominio(contexto)
