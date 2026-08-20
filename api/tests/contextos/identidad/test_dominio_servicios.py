"""Tests del dominio de `identidad` -- Python puro, sin red ni base de datos, sin fixtures
de FastAPI/Supabase: exactamente lo que la arquitectura hexagonal promete que se puede
testear en aislamiento.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from contextos.identidad.dominio.excepciones import (
    ReautenticacionRequerida,
    SesionCerrada,
    SesionExpirada,
    SinRolAsignado,
    TenantAmbiguo,
    TenantNoAutorizado,
)
from contextos.identidad.dominio.objetos_valor import (
    AsignacionRol,
    NivelAutenticacion,
    Rol,
    Sesion,
)
from contextos.identidad.dominio.servicios import (
    calcular_expiracion_sesion,
    resolver_rol_activo,
    verificar_reautenticacion_reciente,
    verificar_sesion_vigente,
)

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"


class TestResolverRolActivo:
    def test_sin_asignaciones_levanta_sin_rol_asignado(self) -> None:
        with pytest.raises(SinRolAsignado):
            resolver_rol_activo([], tenant_id_solicitado=None)

    def test_una_sola_asignacion_se_resuelve_sin_pedir_tenant(self) -> None:
        asignaciones = [AsignacionRol(tenant_id=TENANT_A, rol=Rol.CLIENTE)]

        rol_activo = resolver_rol_activo(asignaciones, tenant_id_solicitado=None)

        assert rol_activo.tenant_id == TENANT_A
        assert rol_activo.rol is Rol.CLIENTE

    def test_multiples_asignaciones_sin_tenant_solicitado_es_ambiguo(self) -> None:
        """Caso central: dueno_sede en A + cliente en B (negocios independientes,
        competidores) -- nunca se adivina cuál aplica, replica el hallazgo de seguridad
        ya documentado en docs/ARCHITECTURE.md sobre el `limit 1` sin `order by`.
        """
        asignaciones = [
            AsignacionRol(tenant_id=TENANT_A, rol=Rol.DUENO_SEDE),
            AsignacionRol(tenant_id=TENANT_B, rol=Rol.CLIENTE),
        ]

        with pytest.raises(TenantAmbiguo):
            resolver_rol_activo(asignaciones, tenant_id_solicitado=None)

    def test_multiples_asignaciones_con_tenant_explicito_se_resuelve(self) -> None:
        asignaciones = [
            AsignacionRol(tenant_id=TENANT_A, rol=Rol.DUENO_SEDE),
            AsignacionRol(tenant_id=TENANT_B, rol=Rol.CLIENTE),
        ]

        rol_activo = resolver_rol_activo(asignaciones, tenant_id_solicitado=TENANT_B)

        assert rol_activo.tenant_id == TENANT_B
        assert rol_activo.rol is Rol.CLIENTE

    def test_tenant_solicitado_sin_asignacion_correspondiente_no_autorizado(self) -> None:
        asignaciones = [AsignacionRol(tenant_id=TENANT_A, rol=Rol.CLIENTE)]

        with pytest.raises(TenantNoAutorizado):
            resolver_rol_activo(asignaciones, tenant_id_solicitado=TENANT_B)

    def test_administrador_plataforma_puede_operar_sobre_cualquier_tenant_solicitado(self) -> None:
        asignaciones = [AsignacionRol(tenant_id=None, rol=Rol.ADMINISTRADOR_PLATAFORMA)]

        rol_activo = resolver_rol_activo(asignaciones, tenant_id_solicitado=TENANT_A)

        assert rol_activo.tenant_id == TENANT_A
        assert rol_activo.rol is Rol.ADMINISTRADOR_PLATAFORMA

    def test_administrador_plataforma_sin_tenant_solicitado_queda_sin_sede_concreta(self) -> None:
        asignaciones = [AsignacionRol(tenant_id=None, rol=Rol.ADMINISTRADOR_PLATAFORMA)]

        rol_activo = resolver_rol_activo(asignaciones, tenant_id_solicitado=None)

        assert rol_activo.tenant_id is None
        assert rol_activo.rol is Rol.ADMINISTRADOR_PLATAFORMA


class TestAsignacionRolInvariantes:
    def test_administrador_plataforma_con_tenant_id_es_invalido(self) -> None:
        with pytest.raises(ValueError):
            AsignacionRol(tenant_id=TENANT_A, rol=Rol.ADMINISTRADOR_PLATAFORMA)

    def test_rol_no_admin_sin_tenant_id_es_invalido(self) -> None:
        with pytest.raises(ValueError):
            AsignacionRol(tenant_id=None, rol=Rol.CLIENTE)


class TestCalcularExpiracionSesion:
    def test_profesional_tiene_timeout_corto_por_dispositivo_compartido(self) -> None:
        ahora = datetime(2026, 1, 1, tzinfo=UTC)

        expira_at = calcular_expiracion_sesion(Rol.PROFESIONAL, desde=ahora)

        assert expira_at == ahora + timedelta(minutes=15)

    def test_dueno_sede_tiene_timeout_corto_por_dispositivo_compartido(self) -> None:
        ahora = datetime(2026, 1, 1, tzinfo=UTC)

        expira_at = calcular_expiracion_sesion(Rol.DUENO_SEDE, desde=ahora)

        assert expira_at == ahora + timedelta(minutes=15)

    def test_cliente_tiene_timeout_normal(self) -> None:
        ahora = datetime(2026, 1, 1, tzinfo=UTC)

        expira_at = calcular_expiracion_sesion(Rol.CLIENTE, desde=ahora)

        assert expira_at == ahora + timedelta(hours=8)


def _sesion(*, expira_at: datetime, cerrada_at: datetime | None = None) -> Sesion:
    ahora = datetime(2026, 1, 1, tzinfo=UTC)
    return Sesion(
        id="sesion-1",
        usuario_id="usuario-1",
        tenant_id=TENANT_A,
        dispositivo="Chrome en Windows",
        ip="127.0.0.1",
        nivel_autenticacion=NivelAutenticacion.AAL1,
        iniciada_at=ahora,
        ultima_actividad_at=ahora,
        expira_at=expira_at,
        cerrada_at=cerrada_at,
    )


class TestVerificarSesionVigente:
    def test_sesion_vigente_no_levanta(self) -> None:
        ahora = datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
        sesion = _sesion(expira_at=ahora + timedelta(minutes=5))

        verificar_sesion_vigente(sesion, ahora=ahora)

    def test_sesion_expirada_levanta(self) -> None:
        ahora = datetime(2026, 1, 1, 0, 20, tzinfo=UTC)
        sesion = _sesion(expira_at=ahora - timedelta(minutes=1))

        with pytest.raises(SesionExpirada):
            verificar_sesion_vigente(sesion, ahora=ahora)

    def test_sesion_cerrada_levanta_aunque_no_haya_expirado(self) -> None:
        ahora = datetime(2026, 1, 1, tzinfo=UTC)
        sesion = _sesion(expira_at=ahora + timedelta(hours=1), cerrada_at=ahora)

        with pytest.raises(SesionCerrada):
            verificar_sesion_vigente(sesion, ahora=ahora)


class TestVerificarReautenticacionReciente:
    def test_jwt_reciente_no_levanta(self) -> None:
        emitido_en = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        ahora = emitido_en + timedelta(minutes=5)

        verificar_reautenticacion_reciente(emitido_en, ahora=ahora)

    def test_jwt_justo_en_el_umbral_no_levanta(self) -> None:
        emitido_en = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        ahora = emitido_en + timedelta(minutes=10)

        verificar_reautenticacion_reciente(emitido_en, ahora=ahora)

    def test_jwt_viejo_levanta_reautenticacion_requerida(self) -> None:
        emitido_en = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
        ahora = emitido_en + timedelta(minutes=10, seconds=1)

        with pytest.raises(ReautenticacionRequerida):
            verificar_reautenticacion_reciente(emitido_en, ahora=ahora)
