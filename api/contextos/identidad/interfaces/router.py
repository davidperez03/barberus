"""Router HTTP de `identidad`. Delgado a propósito: parsea (vía `Depends`), llama al caso
de uso (ya resuelto por la dependency) y mapea a respuesta. Cero lógica de negocio, cero
queries directas.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from contextos.identidad.dominio.excepciones import (
    CredencialesInvalidas,
    RegistroSinSesionInmediata,
    SolicitudAutenticacionInvalida,
)
from contextos.identidad.interfaces.dependencias import (
    ContextoIdentidadDep,
    IniciarSesionConCredencialesDep,
    RegistrarUsuarioDep,
)
from contextos.identidad.interfaces.esquemas import (
    ContextoIdentidadRespuesta,
    CredencialesPeticion,
    DatosSesionAuthRespuesta,
)

router = APIRouter(prefix="/identidad", tags=["identidad"])


@router.get("/contexto", response_model=ContextoIdentidadRespuesta)
def obtener_contexto(contexto: ContextoIdentidadDep) -> ContextoIdentidadRespuesta:
    """Devuelve usuario/rol/tenant/sesión ya resueltos a partir del JWT de la request.

    Endpoint de verificación end-to-end de la capa de auth (útil para QA y para el
    frontend, todavía sin construir) -- equivalente a un `GET /me`.
    """
    return ContextoIdentidadRespuesta.desde_dominio(contexto)


@router.post(
    "/registro",
    response_model=DatosSesionAuthRespuesta,
    status_code=status.HTTP_201_CREATED,
)
def registrar(
    peticion: CredencialesPeticion, caso_de_uso: RegistrarUsuarioDep
) -> DatosSesionAuthRespuesta:
    """Registra una cuenta nueva en Supabase Auth. NO asigna ningún rol -- `cliente` se
    autoasigna recién en la primera reserva (ver `docs/ARCHITECTURE.md`).

    El backend hace de proxy de Supabase Auth (en vez de que el frontend llame a
    `supabase-js` directo) para poder probarlo desde `/docs` y para que la dependencia de
    Supabase Auth quede encerrada en `infraestructura/`.

    Anti-enumeración de cuentas: si no hay sesión inmediata, SIEMPRE responde `202` con
    el mismo mensaje genérico, sea el correo nuevo (confirmación pendiente) o ya
    registrado -- nunca un `409` ni ningún otro código que revele cuál de los dos casos
    ocurrió (ver `dominio.excepciones.RegistroSinSesionInmediata`).
    """
    try:
        datos = caso_de_uso.ejecutar(correo=peticion.correo, contrasena=peticion.contrasena)
    except RegistroSinSesionInmediata as error:
        raise HTTPException(status_code=status.HTTP_202_ACCEPTED, detail=str(error)) from error
    except SolicitudAutenticacionInvalida as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return DatosSesionAuthRespuesta.desde_dominio(datos)


@router.post("/iniciar-sesion", response_model=DatosSesionAuthRespuesta)
def iniciar_sesion(
    peticion: CredencialesPeticion, caso_de_uso: IniciarSesionConCredencialesDep
) -> DatosSesionAuthRespuesta:
    """Autentica un usuario ya registrado contra Supabase Auth y devuelve sus tokens."""
    try:
        datos = caso_de_uso.ejecutar(correo=peticion.correo, contrasena=peticion.contrasena)
    except CredencialesInvalidas as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    except SolicitudAutenticacionInvalida as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return DatosSesionAuthRespuesta.desde_dominio(datos)
