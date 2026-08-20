"""Tests de los casos de uso de "gestión de cuenta avanzada" (sesiones individuales,
auditoría, cambiar contraseña/correo, MFA) con fakes de los puertos -- ninguna
dependencia real de Supabase/red.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from contextos.identidad.aplicacion.cambiar_contrasena import CambiarContrasena
from contextos.identidad.aplicacion.cambiar_correo import CambiarCorreo
from contextos.identidad.aplicacion.cerrar_sesion import CerrarSesion
from contextos.identidad.aplicacion.desactivar_mfa import DesactivarMfa
from contextos.identidad.aplicacion.inscribir_mfa import InscribirMfa
from contextos.identidad.aplicacion.listar_auditoria import ListarAuditoria
from contextos.identidad.aplicacion.listar_factores_mfa import ListarFactoresMfa
from contextos.identidad.aplicacion.listar_sesiones import ListarSesiones
from contextos.identidad.aplicacion.verificar_inscripcion_mfa import VerificarInscripcionMfa
from contextos.identidad.dominio.excepciones import (
    CodigoMfaInvalido,
    CorreoNoDisponible,
    CredencialesActualesIncorrectas,
    FactorMfaNoEncontrado,
    ReautenticacionRequerida,
    SesionNoEncontrada,
)
from contextos.identidad.dominio.objetos_valor import (
    EstadoFactorMfa,
    EventoAuditoria,
    EventoAutenticacion,
    FactorMfa,
    InscripcionMfaTotp,
    NivelAutenticacion,
    Sesion,
    TipoFactorMfa,
)

USUARIO_ID = "usuario-1"
CORREO = "cliente@ejemplo.com"
JWT = "jwt-fake-del-usuario"
EMITIDO_RECIENTE = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
AHORA_RECIENTE = EMITIDO_RECIENTE + timedelta(minutes=1)
AHORA_VIEJO = EMITIDO_RECIENTE + timedelta(minutes=11)


def _sesion(id_: str, *, usuario_id: str = USUARIO_ID, cerrada_at: datetime | None = None) -> Sesion:
    ahora = datetime(2026, 1, 1, tzinfo=UTC)
    return Sesion(
        id=id_,
        usuario_id=usuario_id,
        tenant_id=None,
        dispositivo="Chrome en Windows",
        ip="127.0.0.1",
        nivel_autenticacion=NivelAutenticacion.AAL1,
        iniciada_at=ahora,
        ultima_actividad_at=ahora,
        expira_at=ahora + timedelta(hours=8),
        cerrada_at=cerrada_at,
    )


@dataclass
class RepositorioSesionesGestionFake:
    """Fake acotado a `listar_sesiones`/`cerrar_sesion` (no todo `RepositorioSesionesPuerto`)."""

    sesiones: dict[str, Sesion] = field(default_factory=dict)

    def listar_sesiones(self, usuario_id: str) -> list[Sesion]:
        return [s for s in self.sesiones.values() if s.usuario_id == usuario_id]

    def cerrar_sesion(self, usuario_id: str, sesion_id: str) -> Sesion:
        sesion = self.sesiones.get(sesion_id)
        if sesion is None or sesion.usuario_id != usuario_id:
            raise SesionNoEncontrada(f"No existe la sesión {sesion_id}")
        cerrada = Sesion(
            id=sesion.id,
            usuario_id=sesion.usuario_id,
            tenant_id=sesion.tenant_id,
            dispositivo=sesion.dispositivo,
            ip=sesion.ip,
            nivel_autenticacion=sesion.nivel_autenticacion,
            iniciada_at=sesion.iniciada_at,
            ultima_actividad_at=sesion.ultima_actividad_at,
            expira_at=sesion.expira_at,
            cerrada_at=datetime.now(UTC),
        )
        self.sesiones[sesion_id] = cerrada
        return cerrada


class TestListarSesiones:
    def test_devuelve_solo_las_sesiones_del_usuario(self) -> None:
        repo = RepositorioSesionesGestionFake(
            sesiones={
                "s1": _sesion("s1", usuario_id=USUARIO_ID),
                "s2": _sesion("s2", usuario_id="otro-usuario"),
            }
        )
        caso_de_uso = ListarSesiones(repositorio_sesiones=repo)

        sesiones = caso_de_uso.ejecutar(usuario_id=USUARIO_ID)

        assert [s.id for s in sesiones] == ["s1"]


class TestCerrarSesion:
    def test_cierra_una_sesion_propia(self) -> None:
        repo = RepositorioSesionesGestionFake(sesiones={"s1": _sesion("s1")})
        caso_de_uso = CerrarSesion(repositorio_sesiones=repo)

        sesion = caso_de_uso.ejecutar(usuario_id=USUARIO_ID, sesion_id="s1")

        assert sesion.activa is False

    def test_sesion_ajena_o_inexistente_levanta_no_encontrada(self) -> None:
        repo = RepositorioSesionesGestionFake(sesiones={"s1": _sesion("s1", usuario_id="otro")})
        caso_de_uso = CerrarSesion(repositorio_sesiones=repo)

        with pytest.raises(SesionNoEncontrada):
            caso_de_uso.ejecutar(usuario_id=USUARIO_ID, sesion_id="s1")


@dataclass
class RepositorioAuditoriaFake:
    eventos: list[EventoAuditoria] = field(default_factory=list)

    def listar_eventos(self, usuario_id: str, limite: int, offset: int) -> list[EventoAuditoria]:
        return self.eventos[offset : offset + limite]


def _evento(id_: str) -> EventoAuditoria:
    return EventoAuditoria(
        id=id_,
        evento=EventoAutenticacion.LOGIN,
        tenant_id=None,
        ip="127.0.0.1",
        user_agent="pytest",
        metadata={},
        creado_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestListarAuditoria:
    def test_pagina_los_eventos(self) -> None:
        repo = RepositorioAuditoriaFake(eventos=[_evento(str(i)) for i in range(5)])
        caso_de_uso = ListarAuditoria(repositorio_auditoria=repo)

        pagina = caso_de_uso.ejecutar(usuario_id=USUARIO_ID, limite=2, offset=2)

        assert [e.id for e in pagina] == ["2", "3"]


@dataclass
class AutenticadorCambiosFake:
    """Fake acotado a `verificar_contrasena`/`cambiar_contrasena`/`cambiar_correo`."""

    contrasena_real: str = "clave-actual-larga"
    contrasenas_aplicadas: list[str] = field(default_factory=list)
    correos_ya_registrados: set[str] = field(default_factory=set)
    correos_aplicados: list[str] = field(default_factory=list)

    def verificar_contrasena(self, correo: str, contrasena: str) -> None:
        if contrasena != self.contrasena_real:
            raise CredencialesActualesIncorrectas("La contraseña actual no es correcta")

    def cambiar_contrasena(self, token_acceso: str, nueva_contrasena: str) -> None:
        self.contrasenas_aplicadas.append(nueva_contrasena)

    def cambiar_correo(self, token_acceso: str, nuevo_correo: str) -> None:
        if nuevo_correo in self.correos_ya_registrados:
            raise CorreoNoDisponible("No se pudo actualizar el correo")
        self.correos_aplicados.append(nuevo_correo)


class TestCambiarContrasena:
    def test_contrasena_actual_correcta_y_jwt_reciente_aplica_el_cambio(self) -> None:
        autenticador = AutenticadorCambiosFake()
        caso_de_uso = CambiarContrasena(autenticador=autenticador)

        caso_de_uso.ejecutar(
            correo=CORREO,
            token_acceso=JWT,
            emitido_en=EMITIDO_RECIENTE,
            ahora=AHORA_RECIENTE,
            contrasena_actual="clave-actual-larga",
            nueva_contrasena="clave-nueva-larga",
        )

        assert autenticador.contrasenas_aplicadas == ["clave-nueva-larga"]

    def test_jwt_viejo_no_llega_a_verificar_la_contrasena(self) -> None:
        autenticador = AutenticadorCambiosFake()
        caso_de_uso = CambiarContrasena(autenticador=autenticador)

        with pytest.raises(ReautenticacionRequerida):
            caso_de_uso.ejecutar(
                correo=CORREO,
                token_acceso=JWT,
                emitido_en=EMITIDO_RECIENTE,
                ahora=AHORA_VIEJO,
                contrasena_actual="clave-actual-larga",
                nueva_contrasena="clave-nueva-larga",
            )
        assert autenticador.contrasenas_aplicadas == []

    def test_contrasena_actual_incorrecta_no_aplica_el_cambio(self) -> None:
        autenticador = AutenticadorCambiosFake()
        caso_de_uso = CambiarContrasena(autenticador=autenticador)

        with pytest.raises(CredencialesActualesIncorrectas):
            caso_de_uso.ejecutar(
                correo=CORREO,
                token_acceso=JWT,
                emitido_en=EMITIDO_RECIENTE,
                ahora=AHORA_RECIENTE,
                contrasena_actual="clave-incorrecta",
                nueva_contrasena="clave-nueva-larga",
            )
        assert autenticador.contrasenas_aplicadas == []


class TestCambiarCorreo:
    def test_jwt_reciente_inicia_el_cambio(self) -> None:
        autenticador = AutenticadorCambiosFake()
        caso_de_uso = CambiarCorreo(autenticador=autenticador)

        caso_de_uso.ejecutar(
            token_acceso=JWT,
            emitido_en=EMITIDO_RECIENTE,
            ahora=AHORA_RECIENTE,
            nuevo_correo="nuevo@ejemplo.com",
        )

        assert autenticador.correos_aplicados == ["nuevo@ejemplo.com"]

    def test_jwt_viejo_levanta_reautenticacion_requerida(self) -> None:
        autenticador = AutenticadorCambiosFake()
        caso_de_uso = CambiarCorreo(autenticador=autenticador)

        with pytest.raises(ReautenticacionRequerida):
            caso_de_uso.ejecutar(
                token_acceso=JWT,
                emitido_en=EMITIDO_RECIENTE,
                ahora=AHORA_VIEJO,
                nuevo_correo="nuevo@ejemplo.com",
            )
        assert autenticador.correos_aplicados == []

    def test_correo_ya_registrado_por_otra_cuenta_levanta_correo_no_disponible(self) -> None:
        autenticador = AutenticadorCambiosFake(correos_ya_registrados={"ocupado@ejemplo.com"})
        caso_de_uso = CambiarCorreo(autenticador=autenticador)

        with pytest.raises(CorreoNoDisponible):
            caso_de_uso.ejecutar(
                token_acceso=JWT,
                emitido_en=EMITIDO_RECIENTE,
                ahora=AHORA_RECIENTE,
                nuevo_correo="ocupado@ejemplo.com",
            )


@dataclass
class AutenticadorMfaFake:
    factores: dict[str, FactorMfa] = field(default_factory=dict)
    codigo_valido: str = "123456"
    _contador: int = 0

    def inscribir_totp(self, token_acceso: str, nombre_amistoso: str | None) -> InscripcionMfaTotp:
        self._contador += 1
        factor_id = f"factor-{self._contador}"
        self.factores[factor_id] = FactorMfa(
            id=factor_id,
            tipo=TipoFactorMfa.TOTP,
            estado=EstadoFactorMfa.NO_VERIFICADO,
            nombre_amistoso=nombre_amistoso,
            creado_at=datetime.now(UTC),
            actualizado_at=datetime.now(UTC),
        )
        return InscripcionMfaTotp(
            factor_id=factor_id,
            secreto="SECRETO-BASE32",
            codigo_qr="data:image/svg+xml;utf-8,<svg/>",
            uri=f"otpauth://totp/Barberus:{CORREO}?secret=SECRETO-BASE32",
            nombre_amistoso=nombre_amistoso,
        )

    def verificar_inscripcion(self, token_acceso: str, factor_id: str, codigo: str) -> None:
        factor = self.factores.get(factor_id)
        if factor is None:
            raise FactorMfaNoEncontrado(f"No existe el factor {factor_id}")
        if codigo != self.codigo_valido:
            raise CodigoMfaInvalido("El código ingresado no es válido o expiró")
        self.factores[factor_id] = FactorMfa(
            id=factor.id,
            tipo=factor.tipo,
            estado=EstadoFactorMfa.VERIFICADO,
            nombre_amistoso=factor.nombre_amistoso,
            creado_at=factor.creado_at,
            actualizado_at=datetime.now(UTC),
        )

    def desactivar(self, token_acceso: str, factor_id: str) -> None:
        if factor_id not in self.factores:
            raise FactorMfaNoEncontrado(f"No existe el factor {factor_id}")
        del self.factores[factor_id]

    def listar_factores(self, token_acceso: str) -> list[FactorMfa]:
        return list(self.factores.values())


class TestInscribirMfa:
    def test_devuelve_un_factor_no_verificado(self) -> None:
        autenticador = AutenticadorMfaFake()
        caso_de_uso = InscribirMfa(autenticador_mfa=autenticador)

        inscripcion = caso_de_uso.ejecutar(token_acceso=JWT, nombre_amistoso="iPhone de Ana")

        assert inscripcion.factor_id in autenticador.factores
        assert autenticador.factores[inscripcion.factor_id].estado is EstadoFactorMfa.NO_VERIFICADO


class TestVerificarInscripcionMfa:
    def test_codigo_correcto_activa_el_factor(self) -> None:
        autenticador = AutenticadorMfaFake()
        inscripcion = autenticador.inscribir_totp(JWT, None)
        caso_de_uso = VerificarInscripcionMfa(autenticador_mfa=autenticador)

        caso_de_uso.ejecutar(token_acceso=JWT, factor_id=inscripcion.factor_id, codigo="123456")

        assert autenticador.factores[inscripcion.factor_id].estado is EstadoFactorMfa.VERIFICADO

    def test_codigo_incorrecto_levanta_codigo_mfa_invalido(self) -> None:
        autenticador = AutenticadorMfaFake()
        inscripcion = autenticador.inscribir_totp(JWT, None)
        caso_de_uso = VerificarInscripcionMfa(autenticador_mfa=autenticador)

        with pytest.raises(CodigoMfaInvalido):
            caso_de_uso.ejecutar(token_acceso=JWT, factor_id=inscripcion.factor_id, codigo="000000")

    def test_factor_inexistente_levanta_factor_no_encontrado(self) -> None:
        autenticador = AutenticadorMfaFake()
        caso_de_uso = VerificarInscripcionMfa(autenticador_mfa=autenticador)

        with pytest.raises(FactorMfaNoEncontrado):
            caso_de_uso.ejecutar(token_acceso=JWT, factor_id="no-existe", codigo="123456")


class TestDesactivarMfa:
    def test_jwt_reciente_desactiva_el_factor(self) -> None:
        autenticador = AutenticadorMfaFake()
        inscripcion = autenticador.inscribir_totp(JWT, None)
        caso_de_uso = DesactivarMfa(autenticador_mfa=autenticador)

        caso_de_uso.ejecutar(
            token_acceso=JWT,
            factor_id=inscripcion.factor_id,
            emitido_en=EMITIDO_RECIENTE,
            ahora=AHORA_RECIENTE,
        )

        assert inscripcion.factor_id not in autenticador.factores

    def test_jwt_viejo_no_desactiva_el_factor(self) -> None:
        autenticador = AutenticadorMfaFake()
        inscripcion = autenticador.inscribir_totp(JWT, None)
        caso_de_uso = DesactivarMfa(autenticador_mfa=autenticador)

        with pytest.raises(ReautenticacionRequerida):
            caso_de_uso.ejecutar(
                token_acceso=JWT,
                factor_id=inscripcion.factor_id,
                emitido_en=EMITIDO_RECIENTE,
                ahora=AHORA_VIEJO,
            )
        assert inscripcion.factor_id in autenticador.factores


class TestListarFactoresMfa:
    def test_devuelve_los_factores_inscritos(self) -> None:
        autenticador = AutenticadorMfaFake()
        autenticador.inscribir_totp(JWT, "iPhone de Ana")
        caso_de_uso = ListarFactoresMfa(autenticador_mfa=autenticador)

        factores = caso_de_uso.ejecutar(token_acceso=JWT)

        assert len(factores) == 1
        assert factores[0].nombre_amistoso == "iPhone de Ana"
