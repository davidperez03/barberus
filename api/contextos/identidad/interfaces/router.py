"""Router HTTP de `identidad`. Delgado a propósito: parsea (vía `Depends`), llama al caso
de uso (ya resuelto por la dependency) y mapea a respuesta. Cero lógica de negocio, cero
queries directas.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from contextos.identidad.dominio.excepciones import (
    CredencialesInvalidas,
    EdicionPerfilRechazada,
    PerfilNoEncontrado,
    RegistroSinSesionInmediata,
    SolicitudAutenticacionInvalida,
    TokenInvalido,
)
from contextos.identidad.interfaces.dependencias import (
    ActualizarPerfilCuentaDep,
    CerrarTodasLasSesionesDep,
    ContextoIdentidadDep,
    DatosTokenDep,
    EliminarCuentaDep,
    IniciarSesionConCredencialesDep,
    ObtenerPerfilCuentaDep,
    RegistrarUsuarioDep,
    RestablecerContrasenaDep,
    SolicitarRecuperacionContrasenaDep,
    obtener_token_jwt,
)
from contextos.identidad.interfaces.esquemas import (
    ActualizarPerfilPeticion,
    ContextoIdentidadRespuesta,
    CredencialesPeticion,
    DatosSesionAuthRespuesta,
    MensajeRespuesta,
    PerfilCuentaRespuesta,
    RecuperarContrasenaPeticion,
    RestablecerContrasenaPeticion,
)

router = APIRouter(prefix="/identidad", tags=["identidad"])

_MENSAJE_RECUPERACION_GENERICO = (
    "Si el correo tiene una cuenta registrada, recibirás un enlace para restablecer tu "
    "contraseña."
)


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


@router.get("/perfil", response_model=PerfilCuentaRespuesta)
def obtener_perfil(
    datos_token: DatosTokenDep,
    token_jwt: Annotated[str, Depends(obtener_token_jwt)],
    caso_de_uso: ObtenerPerfilCuentaDep,
) -> PerfilCuentaRespuesta:
    """Perfil de gestión de cuenta del usuario autenticado (`perfiles_usuario`,
    `011_perfil_cuenta_gestion.sql`).

    Usa `DatosTokenDep` (solo JWT validado), NO `ContextoIdentidadDep`: gestión de cuenta
    es tenant-agnóstica y debe funcionar incluso para un usuario sin ningún rol asignado
    todavía -- ver el docstring de `PerfilCuentaRespuesta` para el porqué completo.
    """
    try:
        perfil = caso_de_uso.ejecutar(token_jwt=token_jwt, usuario_id=datos_token.usuario_id)
    except PerfilNoEncontrado as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return PerfilCuentaRespuesta.desde_dominio(datos_token, perfil)


@router.patch("/perfil", response_model=PerfilCuentaRespuesta)
def actualizar_perfil(
    peticion: ActualizarPerfilPeticion,
    datos_token: DatosTokenDep,
    token_jwt: Annotated[str, Depends(obtener_token_jwt)],
    caso_de_uso: ActualizarPerfilCuentaDep,
) -> PerfilCuentaRespuesta:
    """El propio usuario edita `nombre_completo`/`avatar_url`/`terminos_aceptados_at`+
    `terminos_version`/`onboarding_completado_at`. QUÉ columnas puede tocar lo decide
    únicamente Postgres (RLS + `restringir_columnas_perfil_usuario`) -- este endpoint usa
    el JWT del propio usuario, nunca la `secret` key, para que esa sea la única fuente de
    verdad. Ver `obtener_perfil` para por qué usa `DatosTokenDep` y no `ContextoIdentidadDep`."""
    cambios = peticion.a_cambios_dominio()
    if cambios.vacio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se envió ningún campo para actualizar",
        )
    try:
        perfil = caso_de_uso.ejecutar(
            token_jwt=token_jwt, usuario_id=datos_token.usuario_id, cambios=cambios
        )
    except EdicionPerfilRechazada as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    return PerfilCuentaRespuesta.desde_dominio(datos_token, perfil)


@router.post(
    "/recuperar-contrasena",
    response_model=MensajeRespuesta,
    status_code=status.HTTP_202_ACCEPTED,
)
def recuperar_contrasena(
    peticion: RecuperarContrasenaPeticion, caso_de_uso: SolicitarRecuperacionContrasenaDep
) -> MensajeRespuesta:
    """Envía el correo de recuperación de contraseña vía Supabase Auth (`/recover`).

    Anti-enumeración: SIEMPRE responde el mismo mensaje genérico y el mismo código,
    exista o no una cuenta con ese correo -- ver
    `dominio.puertos.AutenticadorPuerto.enviar_recuperacion_contrasena`. El punto más
    sensible de este PR: nunca introducir una rama que distinga ambos casos acá.
    """
    caso_de_uso.ejecutar(correo=peticion.correo)
    return MensajeRespuesta(mensaje=_MENSAJE_RECUPERACION_GENERICO)


@router.post("/restablecer-contrasena", response_model=MensajeRespuesta)
def restablecer_contrasena(
    peticion: RestablecerContrasenaPeticion, caso_de_uso: RestablecerContrasenaDep
) -> MensajeRespuesta:
    """Fija una nueva contraseña sobre la sesión de recuperación (`token_acceso`/
    `token_actualizacion`) que el frontend obtuvo al abrir el enlace del correo -- llama
    `updateUser` de GoTrue."""
    try:
        caso_de_uso.ejecutar(
            token_acceso=peticion.token_acceso,
            token_actualizacion=peticion.token_actualizacion,
            nueva_contrasena=peticion.nueva_contrasena,
        )
    except TokenInvalido as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    except SolicitudAutenticacionInvalida as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return MensajeRespuesta(mensaje="Contraseña actualizada correctamente.")


@router.post("/cerrar-todas-las-sesiones", status_code=status.HTTP_204_NO_CONTENT)
def cerrar_todas_las_sesiones(
    datos_token: DatosTokenDep,
    token_jwt: Annotated[str, Depends(obtener_token_jwt)],
    caso_de_uso: CerrarTodasLasSesionesDep,
) -> None:
    """Revoca TODAS las sesiones (todos los dispositivos) del usuario autenticado vía Auth
    Admin API de Supabase (`admin.sign_out` con `scope="global"`) -- ver
    `dominio.puertos.GestorCuentaPuerto.cerrar_todas_las_sesiones` para por qué esto (y no
    solo marcar `sesiones.cerrada_at`) es el mecanismo que realmente invalida las sesiones.
    Usa `DatosTokenDep`, no `ContextoIdentidadDep` -- ver `obtener_perfil`: cerrar todas
    tus sesiones no depende de tener un rol asignado.
    """
    try:
        caso_de_uso.ejecutar(token_acceso=token_jwt)
    except SolicitudAutenticacionInvalida as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/eliminar-cuenta", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_cuenta(datos_token: DatosTokenDep, caso_de_uso: EliminarCuentaDep) -> None:
    """El usuario autenticado elimina (soft-delete) SU PROPIA cuenta.

    `usuario_id` viene únicamente de `datos_token` (ya resuelto desde el JWT, ver
    `obtener_perfil` para por qué `DatosTokenDep` y no `ContextoIdentidadDep`) -- nunca de
    un body, para que nadie pueda pedir la eliminación de una cuenta ajena. Usa el cliente
    con privilegio elevado (Auth Admin API) para marcar `auth.users.deleted_at`, que el
    trigger `sincronizar_perfil_usuario` ya espeja a `perfiles_usuario.eliminado_at` --
    ver `dominio.puertos.GestorCuentaPuerto.eliminar_cuenta`.
    """
    try:
        caso_de_uso.ejecutar(usuario_id=datos_token.usuario_id)
    except SolicitudAutenticacionInvalida as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
