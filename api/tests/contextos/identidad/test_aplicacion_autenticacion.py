"""Tests de `RegistrarUsuario`/`IniciarSesionConCredenciales` con un fake de
`AutenticadorPuerto` -- ninguna dependencia real de Supabase/red.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from contextos.identidad.aplicacion.iniciar_sesion_con_credenciales import (
    IniciarSesionConCredenciales,
)
from contextos.identidad.aplicacion.registrar_usuario import RegistrarUsuario
from contextos.identidad.dominio.excepciones import (
    CredencialesInvalidas,
    RegistroSinSesionInmediata,
)
from contextos.identidad.dominio.objetos_valor import DatosSesionAuth

CORREO = "cliente@ejemplo.com"
CONTRASENA = "clave-super-segura"


@dataclass
class AutenticadorFake:
    """Fake del puerto: correos ya "registrados" y credenciales válidas configurables por test."""

    correos_registrados: set[str] = field(default_factory=set)
    credenciales_validas: dict[str, str] = field(default_factory=dict)

    def registrar(self, correo: str, contrasena: str) -> DatosSesionAuth:
        if correo in self.correos_registrados:
            # Mismo mensaje genérico que un correo nuevo pendiente de confirmar -- el
            # puerto nunca debe distinguir "correo ya registrado" de "correo nuevo" de
            # cara al llamador (anti-enumeración de cuentas).
            raise RegistroSinSesionInmediata(
                "Solicitud de registro procesada. Si el correo es válido y no tenía "
                "cuenta, revisa tu bandeja de entrada para confirmarla."
            )
        self.correos_registrados.add(correo)
        self.credenciales_validas[correo] = contrasena
        return _datos_sesion(correo)

    def iniciar_sesion(self, correo: str, contrasena: str) -> DatosSesionAuth:
        if self.credenciales_validas.get(correo) != contrasena:
            raise CredencialesInvalidas("Correo o contraseña incorrectos")
        return _datos_sesion(correo)


def _datos_sesion(correo: str) -> DatosSesionAuth:
    return DatosSesionAuth(
        access_token="access-token-fake",
        refresh_token="refresh-token-fake",
        usuario_id=f"usuario-de-{correo}",
        expira_at=datetime.now(UTC),
    )


def test_registrar_usuario_devuelve_datos_de_sesion() -> None:
    caso_de_uso = RegistrarUsuario(autenticador=AutenticadorFake())

    datos = caso_de_uso.ejecutar(correo=CORREO, contrasena=CONTRASENA)

    assert datos.usuario_id == f"usuario-de-{CORREO}"
    assert datos.access_token


def test_registrar_usuario_con_correo_duplicado_propaga_excepcion_de_dominio() -> None:
    autenticador = AutenticadorFake(correos_registrados={CORREO})
    caso_de_uso = RegistrarUsuario(autenticador=autenticador)

    with pytest.raises(RegistroSinSesionInmediata):
        caso_de_uso.ejecutar(correo=CORREO, contrasena=CONTRASENA)


def test_iniciar_sesion_con_credenciales_correctas_devuelve_datos_de_sesion() -> None:
    autenticador = AutenticadorFake(credenciales_validas={CORREO: CONTRASENA})
    caso_de_uso = IniciarSesionConCredenciales(autenticador=autenticador)

    datos = caso_de_uso.ejecutar(correo=CORREO, contrasena=CONTRASENA)

    assert datos.usuario_id == f"usuario-de-{CORREO}"


def test_iniciar_sesion_con_credenciales_incorrectas_propaga_excepcion_de_dominio() -> None:
    autenticador = AutenticadorFake(credenciales_validas={CORREO: CONTRASENA})
    caso_de_uso = IniciarSesionConCredenciales(autenticador=autenticador)

    with pytest.raises(CredencialesInvalidas):
        caso_de_uso.ejecutar(correo=CORREO, contrasena="clave-incorrecta")
