"""`Depends` de FastAPI: resuelven adaptadores concretos e inyectan el caso de uso.

Único lugar de `identidad` donde se decide QUÉ implementación concreta de cada puerto se
usa -- si mañana cambia el proveedor de datos, solo este módulo cambia.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from contextos.identidad.aplicacion.actualizar_perfil_cuenta import ActualizarPerfilCuenta
from contextos.identidad.aplicacion.cerrar_todas_las_sesiones import CerrarTodasLasSesiones
from contextos.identidad.aplicacion.eliminar_cuenta import EliminarCuenta
from contextos.identidad.aplicacion.iniciar_sesion_con_credenciales import (
    IniciarSesionConCredenciales,
)
from contextos.identidad.aplicacion.obtener_perfil_cuenta import ObtenerPerfilCuenta
from contextos.identidad.aplicacion.registrar_usuario import RegistrarUsuario
from contextos.identidad.aplicacion.resolver_contexto_identidad import ResolverContextoIdentidad
from contextos.identidad.aplicacion.restablecer_contrasena import RestablecerContrasena
from contextos.identidad.aplicacion.solicitar_recuperacion_contrasena import (
    SolicitarRecuperacionContrasena,
)
from contextos.identidad.dominio.excepciones import (
    SesionCerrada,
    SesionExpirada,
    SinRolAsignado,
    TenantAmbiguo,
    TenantNoAutorizado,
    TokenInvalido,
)
from contextos.identidad.dominio.objetos_valor import ContextoIdentidad, DatosToken
from contextos.identidad.dominio.puertos import ValidadorTokenPuerto
from contextos.identidad.infraestructura.administrador_cuenta_supabase import (
    AdministradorCuentaSupabase,
)
from contextos.identidad.infraestructura.autenticador_supabase import AutenticadorSupabase
from contextos.identidad.infraestructura.cliente_supabase import (
    obtener_cliente_supabase,
    obtener_cliente_supabase_auth,
)
from contextos.identidad.infraestructura.repositorio_perfil_supabase import (
    RepositorioPerfilSupabase,
)
from contextos.identidad.infraestructura.repositorio_roles_supabase import RepositorioRolesSupabase
from contextos.identidad.infraestructura.repositorio_sesiones_supabase import (
    RepositorioSesionesSupabase,
)
from contextos.identidad.infraestructura.validador_jwt_supabase import ValidadorJwtSupabase
from nucleo.configuracion import obtener_configuracion


def obtener_token_jwt(authorization: Annotated[str | None, Header()] = None) -> str:
    """Extrae el JWT del header `Authorization: Bearer <token>`. 401 si falta o está mal formado."""
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el header Authorization: Bearer <token>",
        )
    return authorization.split(" ", 1)[1].strip()


def obtener_tenant_id_solicitado(
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> str | None:
    """Tenant explícito para esta request, si el llamador lo especificó.

    Nunca se adivina un default cuando hay ambigüedad -- ver
    `dominio.servicios.resolver_rol_activo`.
    """
    return x_tenant_id


def obtener_sesion_id(x_sesion_id: Annotated[str | None, Header()] = None) -> str | None:
    return x_sesion_id


@lru_cache
def obtener_validador_token() -> ValidadorTokenPuerto:
    """Único `ValidadorJwtSupabase` por proceso -- compartido entre `ResolverContextoIdentidad`
    (identidad + rol/tenant) y `obtener_datos_token` (solo identidad, ver más abajo) para no
    instanciar dos `PyJWKClient`/pegarle dos veces al JWKS.
    """
    configuracion = obtener_configuracion()
    return ValidadorJwtSupabase(
        jwks_url=configuracion.supabase_jwks_url,
        audiencia=configuracion.supabase_jwt_audiencia,
    )


@lru_cache
def obtener_caso_uso_resolver_contexto() -> ResolverContextoIdentidad:
    cliente_supabase = obtener_cliente_supabase()
    return ResolverContextoIdentidad(
        validador_token=obtener_validador_token(),
        repositorio_roles=RepositorioRolesSupabase(cliente=cliente_supabase),
        repositorio_sesiones=RepositorioSesionesSupabase(cliente=cliente_supabase),
    )


def obtener_contexto_identidad(
    token_jwt: Annotated[str, Depends(obtener_token_jwt)],
    tenant_id_solicitado: Annotated[str | None, Depends(obtener_tenant_id_solicitado)],
    sesion_id: Annotated[str | None, Depends(obtener_sesion_id)],
    caso_de_uso: Annotated[ResolverContextoIdentidad, Depends(obtener_caso_uso_resolver_contexto)],
) -> ContextoIdentidad:
    """Dependency principal: cualquier endpoint (de `identidad` o de otro contexto) que
    necesite saber "quién hace esta request, con qué rol, en qué tenant" depende de esto,
    nunca de leer el JWT o `roles_usuario` a mano.
    """
    try:
        return caso_de_uso.ejecutar(
            token_jwt=token_jwt,
            tenant_id_solicitado=tenant_id_solicitado,
            sesion_id=sesion_id,
        )
    except TokenInvalido as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    except (SinRolAsignado, TenantNoAutorizado, TenantAmbiguo, SesionExpirada, SesionCerrada) as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


ContextoIdentidadDep = Annotated[ContextoIdentidad, Depends(obtener_contexto_identidad)]


def obtener_datos_token(
    token_jwt: Annotated[str, Depends(obtener_token_jwt)],
    validador: Annotated[ValidadorTokenPuerto, Depends(obtener_validador_token)],
) -> DatosToken:
    """Dependency liviana: SOLO valida el JWT (quién es el usuario), sin resolver rol/tenant.

    Gestión de cuenta (`perfil`, `cerrar-todas-las-sesiones`, `eliminar-cuenta`) es
    deliberadamente tenant-agnóstica -- `perfiles_usuario` no tiene `tenant_id`, y un
    usuario recién registrado (sin ninguna fila en `roles_usuario` todavía: `cliente` se
    autoasigna recién en su primera reserva, ver `aplicacion.registrar_usuario`) debe
    poder gestionar SU cuenta igual. Usar `ContextoIdentidadDep` acá sería incorrecto dos
    veces: 403 `SinRolAsignado` para ese usuario recién registrado, y 403 `TenantAmbiguo`
    para cualquier usuario con roles en más de un tenant que no mande `X-Tenant-Id` a
    propósito -- ninguno de los dos tiene que ver con poder ver/editar su propio perfil.
    """
    try:
        return validador.validar(token_jwt)
    except TokenInvalido as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error


DatosTokenDep = Annotated[DatosToken, Depends(obtener_datos_token)]


@lru_cache
def obtener_caso_uso_registrar_usuario() -> RegistrarUsuario:
    cliente_auth = obtener_cliente_supabase_auth()
    return RegistrarUsuario(autenticador=AutenticadorSupabase(cliente=cliente_auth))


@lru_cache
def obtener_caso_uso_iniciar_sesion_con_credenciales() -> IniciarSesionConCredenciales:
    cliente_auth = obtener_cliente_supabase_auth()
    return IniciarSesionConCredenciales(autenticador=AutenticadorSupabase(cliente=cliente_auth))


RegistrarUsuarioDep = Annotated[RegistrarUsuario, Depends(obtener_caso_uso_registrar_usuario)]
IniciarSesionConCredencialesDep = Annotated[
    IniciarSesionConCredenciales, Depends(obtener_caso_uso_iniciar_sesion_con_credenciales)
]


@lru_cache
def obtener_caso_uso_solicitar_recuperacion_contrasena() -> SolicitarRecuperacionContrasena:
    cliente_auth = obtener_cliente_supabase_auth()
    return SolicitarRecuperacionContrasena(autenticador=AutenticadorSupabase(cliente=cliente_auth))


@lru_cache
def obtener_caso_uso_restablecer_contrasena() -> RestablecerContrasena:
    cliente_auth = obtener_cliente_supabase_auth()
    return RestablecerContrasena(autenticador=AutenticadorSupabase(cliente=cliente_auth))


SolicitarRecuperacionContrasenaDep = Annotated[
    SolicitarRecuperacionContrasena, Depends(obtener_caso_uso_solicitar_recuperacion_contrasena)
]
RestablecerContrasenaDep = Annotated[
    RestablecerContrasena, Depends(obtener_caso_uso_restablecer_contrasena)
]


# `ObtenerPerfilCuenta`/`ActualizarPerfilCuenta` NO se cachean con `@lru_cache` como el
# resto de casos de uso de este módulo: `RepositorioPerfilSupabase` no guarda ningún
# cliente en su constructor (lo crea por operación, con el JWT de esa request -- ver
# `cliente_supabase.obtener_cliente_supabase_como_usuario`), así que no hay nada costoso
# que reutilizar entre requests.
def obtener_caso_uso_obtener_perfil() -> ObtenerPerfilCuenta:
    return ObtenerPerfilCuenta(repositorio_perfil=RepositorioPerfilSupabase())


def obtener_caso_uso_actualizar_perfil() -> ActualizarPerfilCuenta:
    return ActualizarPerfilCuenta(repositorio_perfil=RepositorioPerfilSupabase())


ObtenerPerfilCuentaDep = Annotated[
    ObtenerPerfilCuenta, Depends(obtener_caso_uso_obtener_perfil)
]
ActualizarPerfilCuentaDep = Annotated[
    ActualizarPerfilCuenta, Depends(obtener_caso_uso_actualizar_perfil)
]


@lru_cache
def obtener_caso_uso_cerrar_todas_las_sesiones() -> CerrarTodasLasSesiones:
    cliente_secreto = obtener_cliente_supabase()
    return CerrarTodasLasSesiones(gestor_cuenta=AdministradorCuentaSupabase(cliente=cliente_secreto))


@lru_cache
def obtener_caso_uso_eliminar_cuenta() -> EliminarCuenta:
    cliente_secreto = obtener_cliente_supabase()
    return EliminarCuenta(gestor_cuenta=AdministradorCuentaSupabase(cliente=cliente_secreto))


CerrarTodasLasSesionesDep = Annotated[
    CerrarTodasLasSesiones, Depends(obtener_caso_uso_cerrar_todas_las_sesiones)
]
EliminarCuentaDep = Annotated[EliminarCuenta, Depends(obtener_caso_uso_eliminar_cuenta)]
