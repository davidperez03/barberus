"""`Depends` de FastAPI: resuelven adaptadores concretos e inyectan el caso de uso.

Único lugar de `identidad` donde se decide QUÉ implementación concreta de cada puerto se
usa -- si mañana cambia el proveedor de datos, solo este módulo cambia.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from contextos.identidad.aplicacion.resolver_contexto_identidad import ResolverContextoIdentidad
from contextos.identidad.dominio.excepciones import (
    SesionCerrada,
    SesionExpirada,
    SinRolAsignado,
    TenantAmbiguo,
    TenantNoAutorizado,
    TokenInvalido,
)
from contextos.identidad.dominio.objetos_valor import ContextoIdentidad
from contextos.identidad.infraestructura.cliente_supabase import obtener_cliente_supabase
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
def obtener_caso_uso_resolver_contexto() -> ResolverContextoIdentidad:
    configuracion = obtener_configuracion()
    cliente_supabase = obtener_cliente_supabase()
    return ResolverContextoIdentidad(
        validador_token=ValidadorJwtSupabase(
            jwks_url=configuracion.supabase_jwks_url,
            audiencia=configuracion.supabase_jwt_audiencia,
        ),
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
