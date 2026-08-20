"""Tests de los casos de uso de gestión de cuenta (`aplicacion/`) con fakes de los
puertos -- ninguna dependencia real de Supabase/red.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from contextos.identidad.aplicacion.actualizar_perfil_cuenta import ActualizarPerfilCuenta
from contextos.identidad.aplicacion.cerrar_todas_las_sesiones import CerrarTodasLasSesiones
from contextos.identidad.aplicacion.eliminar_cuenta import EliminarCuenta
from contextos.identidad.aplicacion.obtener_perfil_cuenta import ObtenerPerfilCuenta
from contextos.identidad.aplicacion.restablecer_contrasena import RestablecerContrasena
from contextos.identidad.aplicacion.solicitar_recuperacion_contrasena import (
    SolicitarRecuperacionContrasena,
)
from contextos.identidad.dominio.excepciones import (
    PerfilNoEncontrado,
    ReautenticacionRequerida,
    SolicitudAutenticacionInvalida,
    TokenInvalido,
)
from contextos.identidad.dominio.objetos_valor import CambiosPerfil, PerfilCuenta

USUARIO_ID = "usuario-1"
JWT = "jwt-fake-del-usuario"


@dataclass
class RepositorioPerfilFake:
    """Fake de `RepositorioPerfilPuerto`: un único perfil en memoria, indexado por
    usuario_id. Ignora el JWT en sí (los fakes de dominio no simulan RLS -- eso lo cubre
    la infraestructura, no este nivel de test)."""

    perfiles: dict[str, PerfilCuenta] = field(default_factory=dict)

    def obtener_perfil(self, token_jwt: str, usuario_id: str) -> PerfilCuenta | None:
        return self.perfiles.get(usuario_id)

    def actualizar_perfil(
        self, token_jwt: str, usuario_id: str, cambios: CambiosPerfil
    ) -> PerfilCuenta:
        actual = self.perfiles[usuario_id]
        actualizado = PerfilCuenta(
            usuario_id=usuario_id,
            nombre_completo=cambios.nombre_completo or actual.nombre_completo,
            avatar_url=cambios.avatar_url or actual.avatar_url,
            terminos_aceptados_at=cambios.terminos_aceptados_at or actual.terminos_aceptados_at,
            terminos_version=cambios.terminos_version or actual.terminos_version,
            onboarding_completado_at=(
                cambios.onboarding_completado_at or actual.onboarding_completado_at
            ),
        )
        self.perfiles[usuario_id] = actualizado
        return actualizado


def _perfil_vacio(usuario_id: str = USUARIO_ID) -> PerfilCuenta:
    return PerfilCuenta(
        usuario_id=usuario_id,
        nombre_completo=None,
        avatar_url=None,
        terminos_aceptados_at=None,
        terminos_version=None,
        onboarding_completado_at=None,
    )


class TestObtenerPerfilCuenta:
    def test_devuelve_el_perfil_existente(self) -> None:
        repo = RepositorioPerfilFake(perfiles={USUARIO_ID: _perfil_vacio()})
        caso_de_uso = ObtenerPerfilCuenta(repositorio_perfil=repo)

        perfil = caso_de_uso.ejecutar(token_jwt=JWT, usuario_id=USUARIO_ID)

        assert perfil.usuario_id == USUARIO_ID

    def test_sin_fila_levanta_perfil_no_encontrado(self) -> None:
        caso_de_uso = ObtenerPerfilCuenta(repositorio_perfil=RepositorioPerfilFake())

        with pytest.raises(PerfilNoEncontrado):
            caso_de_uso.ejecutar(token_jwt=JWT, usuario_id=USUARIO_ID)


class TestActualizarPerfilCuenta:
    def test_actualiza_solo_los_campos_provistos(self) -> None:
        repo = RepositorioPerfilFake(perfiles={USUARIO_ID: _perfil_vacio()})
        caso_de_uso = ActualizarPerfilCuenta(repositorio_perfil=repo)

        perfil = caso_de_uso.ejecutar(
            token_jwt=JWT,
            usuario_id=USUARIO_ID,
            cambios=CambiosPerfil(nombre_completo="Ana Pérez"),
        )

        assert perfil.nombre_completo == "Ana Pérez"
        assert perfil.avatar_url is None

    def test_terminos_y_onboarding_se_pueden_fijar_juntos(self) -> None:
        repo = RepositorioPerfilFake(perfiles={USUARIO_ID: _perfil_vacio()})
        caso_de_uso = ActualizarPerfilCuenta(repositorio_perfil=repo)
        ahora = datetime(2026, 8, 20, tzinfo=UTC)

        perfil = caso_de_uso.ejecutar(
            token_jwt=JWT,
            usuario_id=USUARIO_ID,
            cambios=CambiosPerfil(
                terminos_aceptados_at=ahora,
                terminos_version="2026-08-20",
                onboarding_completado_at=ahora,
            ),
        )

        assert perfil.terminos_version == "2026-08-20"
        assert perfil.onboarding_completado_at == ahora


class TestCambiosPerfilVacio:
    def test_sin_ningun_campo_es_vacio(self) -> None:
        assert CambiosPerfil().vacio is True

    def test_con_un_campo_no_es_vacio(self) -> None:
        assert CambiosPerfil(nombre_completo="Ana").vacio is False


@dataclass
class AutenticadorRecuperacionFake:
    """Fake acotado a los dos métodos de recuperación de contraseña de `AutenticadorPuerto`."""

    correos_con_cuenta: set[str] = field(default_factory=set)
    sesion_recovery_valida: tuple[str, str] | None = None
    levantado: list[str] = field(default_factory=list)

    def enviar_recuperacion_contrasena(self, correo: str) -> None:
        # Nunca levanta -- ver dominio.puertos.AutenticadorPuerto (anti-enumeración).
        self.levantado.append(correo)

    def restablecer_contrasena(
        self, token_acceso: str, token_actualizacion: str, nueva_contrasena: str
    ) -> None:
        if (token_acceso, token_actualizacion) != self.sesion_recovery_valida:
            raise TokenInvalido("La sesión de recuperación no es válida o expiró")
        if len(nueva_contrasena) < 8:
            raise SolicitudAutenticacionInvalida("Contraseña no cumple la política")


class TestSolicitarRecuperacionContrasena:
    def test_nunca_levanta_exista_o_no_el_correo(self) -> None:
        autenticador = AutenticadorRecuperacionFake()
        caso_de_uso = SolicitarRecuperacionContrasena(autenticador=autenticador)

        caso_de_uso.ejecutar(correo="quien-sea@ejemplo.com")

        assert autenticador.levantado == ["quien-sea@ejemplo.com"]


class TestRestablecerContrasena:
    def test_sesion_de_recovery_valida_no_levanta(self) -> None:
        autenticador = AutenticadorRecuperacionFake(sesion_recovery_valida=("acc", "ref"))
        caso_de_uso = RestablecerContrasena(autenticador=autenticador)

        caso_de_uso.ejecutar(
            token_acceso="acc", token_actualizacion="ref", nueva_contrasena="clave-nueva-larga"
        )

    def test_sesion_de_recovery_invalida_levanta_token_invalido(self) -> None:
        autenticador = AutenticadorRecuperacionFake(sesion_recovery_valida=("acc", "ref"))
        caso_de_uso = RestablecerContrasena(autenticador=autenticador)

        with pytest.raises(TokenInvalido):
            caso_de_uso.ejecutar(
                token_acceso="otro",
                token_actualizacion="otro-ref",
                nueva_contrasena="clave-nueva-larga",
            )


@dataclass
class GestorCuentaFake:
    """Fake de `GestorCuentaPuerto`."""

    sesiones_cerradas_de: list[str] = field(default_factory=list)
    cuentas_eliminadas: list[str] = field(default_factory=list)

    def cerrar_todas_las_sesiones(self, token_acceso: str) -> None:
        self.sesiones_cerradas_de.append(token_acceso)

    def eliminar_cuenta(self, usuario_id: str) -> None:
        self.cuentas_eliminadas.append(usuario_id)


class TestCerrarTodasLasSesiones:
    def test_delega_el_token_de_acceso_actual_al_puerto(self) -> None:
        gestor = GestorCuentaFake()
        caso_de_uso = CerrarTodasLasSesiones(gestor_cuenta=gestor)

        caso_de_uso.ejecutar(token_acceso=JWT)

        assert gestor.sesiones_cerradas_de == [JWT]


class TestEliminarCuenta:
    def test_delega_el_usuario_id_del_contexto_resuelto_al_puerto(self) -> None:
        gestor = GestorCuentaFake()
        caso_de_uso = EliminarCuenta(gestor_cuenta=gestor)
        emitido_en = datetime(2026, 1, 1, tzinfo=UTC)

        caso_de_uso.ejecutar(
            usuario_id=USUARIO_ID, emitido_en=emitido_en, ahora=emitido_en + timedelta(minutes=1)
        )

        assert gestor.cuentas_eliminadas == [USUARIO_ID]

    def test_jwt_viejo_no_llega_a_eliminar_la_cuenta(self) -> None:
        gestor = GestorCuentaFake()
        caso_de_uso = EliminarCuenta(gestor_cuenta=gestor)
        emitido_en = datetime(2026, 1, 1, tzinfo=UTC)

        with pytest.raises(ReautenticacionRequerida):
            caso_de_uso.ejecutar(
                usuario_id=USUARIO_ID,
                emitido_en=emitido_en,
                ahora=emitido_en + timedelta(minutes=11),
            )

        assert gestor.cuentas_eliminadas == []
