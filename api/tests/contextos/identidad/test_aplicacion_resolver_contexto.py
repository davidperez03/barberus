"""Tests del caso de uso `ResolverContextoIdentidad` con adaptadores fake (implementan los
puertos del dominio) -- ninguna dependencia real de Supabase/red, tal como exige la
arquitectura para la capa de aplicación.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from contextos.identidad.aplicacion.resolver_contexto_identidad import ResolverContextoIdentidad
from contextos.identidad.dominio.excepciones import TenantAmbiguo, TokenInvalido
from contextos.identidad.dominio.objetos_valor import (
    AsignacionRol,
    DatosToken,
    NivelAutenticacion,
    Rol,
    Sesion,
)

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
USUARIO_ID = "usuario-1"


@dataclass
class ValidadorTokenFake:
    datos_token: DatosToken | None = None

    def validar(self, token_jwt: str) -> DatosToken:
        if self.datos_token is None:
            raise TokenInvalido("token de prueba inválido")
        return self.datos_token


@dataclass
class RepositorioRolesFake:
    asignaciones_por_usuario: dict[str, list[AsignacionRol]] = field(default_factory=dict)

    def listar_roles(self, usuario_id: str) -> list[AsignacionRol]:
        return self.asignaciones_por_usuario.get(usuario_id, [])


@dataclass
class RepositorioSesionesFake:
    sesiones_por_id: dict[str, Sesion] = field(default_factory=dict)

    def obtener_sesion(self, usuario_id: str, sesion_id: str) -> Sesion | None:
        sesion = self.sesiones_por_id.get(sesion_id)
        if sesion is None or sesion.usuario_id != usuario_id:
            return None
        return sesion

    def iniciar_sesion(self, usuario_id, tenant_id, nivel_autenticacion, expira_at, dispositivo, ip):
        raise NotImplementedError("no usado en estos tests")

    def listar_sesiones(self, usuario_id):
        raise NotImplementedError("no usado en estos tests")

    def cerrar_sesion(self, usuario_id, sesion_id):
        raise NotImplementedError("no usado en estos tests")


def _datos_token() -> DatosToken:
    return DatosToken(
        usuario_id=USUARIO_ID,
        correo="cliente@ejemplo.com",
        emitido_en=datetime.now(UTC),
    )


def test_resuelve_contexto_con_un_solo_rol_sin_pedir_tenant() -> None:
    caso_de_uso = ResolverContextoIdentidad(
        validador_token=ValidadorTokenFake(datos_token=_datos_token()),
        repositorio_roles=RepositorioRolesFake(
            {USUARIO_ID: [AsignacionRol(tenant_id=TENANT_A, rol=Rol.CLIENTE)]}
        ),
        repositorio_sesiones=RepositorioSesionesFake(),
    )

    contexto = caso_de_uso.ejecutar(token_jwt="token-valido")

    assert contexto.usuario_id == USUARIO_ID
    assert contexto.rol_activo.tenant_id == TENANT_A
    assert contexto.rol_activo.rol is Rol.CLIENTE
    assert contexto.sesion is None


def test_usuario_con_roles_en_dos_tenants_sin_especificar_uno_falla() -> None:
    """dueno_sede en A + cliente en B: el caso de uso NUNCA elige por su cuenta."""
    caso_de_uso = ResolverContextoIdentidad(
        validador_token=ValidadorTokenFake(datos_token=_datos_token()),
        repositorio_roles=RepositorioRolesFake(
            {
                USUARIO_ID: [
                    AsignacionRol(tenant_id=TENANT_A, rol=Rol.DUENO_SEDE),
                    AsignacionRol(tenant_id=TENANT_B, rol=Rol.CLIENTE),
                ]
            }
        ),
        repositorio_sesiones=RepositorioSesionesFake(),
    )

    with pytest.raises(TenantAmbiguo):
        caso_de_uso.ejecutar(token_jwt="token-valido")


def test_usuario_con_roles_en_dos_tenants_especificando_uno_se_resuelve() -> None:
    caso_de_uso = ResolverContextoIdentidad(
        validador_token=ValidadorTokenFake(datos_token=_datos_token()),
        repositorio_roles=RepositorioRolesFake(
            {
                USUARIO_ID: [
                    AsignacionRol(tenant_id=TENANT_A, rol=Rol.DUENO_SEDE),
                    AsignacionRol(tenant_id=TENANT_B, rol=Rol.CLIENTE),
                ]
            }
        ),
        repositorio_sesiones=RepositorioSesionesFake(),
    )

    contexto = caso_de_uso.ejecutar(token_jwt="token-valido", tenant_id_solicitado=TENANT_A)

    assert contexto.rol_activo.tenant_id == TENANT_A
    assert contexto.rol_activo.rol is Rol.DUENO_SEDE


def test_token_invalido_propaga_excepcion_de_dominio() -> None:
    caso_de_uso = ResolverContextoIdentidad(
        validador_token=ValidadorTokenFake(datos_token=None),
        repositorio_roles=RepositorioRolesFake(),
        repositorio_sesiones=RepositorioSesionesFake(),
    )

    with pytest.raises(TokenInvalido):
        caso_de_uso.ejecutar(token_jwt="token-invalido")


def test_incluye_sesion_vigente_cuando_se_pide_sesion_id() -> None:
    ahora = datetime.now(UTC)
    sesion = Sesion(
        id="sesion-1",
        usuario_id=USUARIO_ID,
        tenant_id=TENANT_A,
        dispositivo="Chrome en Windows",
        ip="127.0.0.1",
        nivel_autenticacion=NivelAutenticacion.AAL1,
        iniciada_at=ahora,
        ultima_actividad_at=ahora,
        expira_at=ahora + timedelta(minutes=15),
        cerrada_at=None,
    )
    caso_de_uso = ResolverContextoIdentidad(
        validador_token=ValidadorTokenFake(datos_token=_datos_token()),
        repositorio_roles=RepositorioRolesFake(
            {USUARIO_ID: [AsignacionRol(tenant_id=TENANT_A, rol=Rol.PROFESIONAL)]}
        ),
        repositorio_sesiones=RepositorioSesionesFake({"sesion-1": sesion}),
    )

    contexto = caso_de_uso.ejecutar(token_jwt="token-valido", sesion_id="sesion-1")

    assert contexto.sesion is not None
    assert contexto.sesion.id == "sesion-1"
