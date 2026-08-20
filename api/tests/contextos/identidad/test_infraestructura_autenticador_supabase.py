"""Tests del adaptador `AutenticadorSupabase` contra la Auth API de Supabase (GoTrue).

No golpea red real: mockea `cliente.auth.sign_up`/`sign_in_with_password` (el propio
`supabase-py`/`supabase_auth` ya tiene sus tests de que esas llamadas hacen lo correcto
contra la red -- acá se prueba el mapeo de este adaptador: `AuthResponse` -> `DatosSesionAuth`,
y qué excepción de dominio levanta según la respuesta/error de GoTrue).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from supabase_auth.errors import AuthApiError, AuthInvalidJwtError, AuthSessionMissingError
from supabase_auth.types import AuthResponse, Session, User

import contextos.identidad.infraestructura.autenticador_supabase as autenticador_supabase_modulo
from contextos.identidad.dominio.excepciones import (
    CredencialesInvalidas,
    RegistroSinSesionInmediata,
    SolicitudAutenticacionInvalida,
    TokenInvalido,
)
from contextos.identidad.infraestructura.autenticador_supabase import AutenticadorSupabase

USUARIO_ID = "11111111-1111-1111-1111-111111111111"
CORREO = "cliente@ejemplo.com"
CONTRASENA = "clave-super-segura"


def _usuario(*, identidades=None) -> User:
    return User(
        id=USUARIO_ID,
        app_metadata={},
        user_metadata={},
        aud="authenticated",
        email=CORREO,
        created_at=datetime.now(UTC),
        identities=identidades,
    )


def _respuesta_con_sesion() -> AuthResponse:
    usuario = _usuario()
    sesion = Session(
        access_token="access-token-real",
        refresh_token="refresh-token-real",
        expires_in=3600,
        token_type="bearer",
        user=usuario,
    )
    return AuthResponse(user=usuario, session=sesion)


@dataclass
class _ClienteFake:
    auth: MagicMock


def _cliente_con_auth(**metodos) -> _ClienteFake:
    auth = MagicMock()
    for nombre, comportamiento in metodos.items():
        getattr(auth, nombre).side_effect = comportamiento
    return _ClienteFake(auth=auth)


def test_registrar_devuelve_datos_de_sesion_cuando_gotrue_responde_con_sesion() -> None:
    cliente = _cliente_con_auth(sign_up=lambda credenciales: _respuesta_con_sesion())
    autenticador = AutenticadorSupabase(cliente=cliente)

    datos = autenticador.registrar(correo=CORREO, contrasena=CONTRASENA)

    assert datos.usuario_id == USUARIO_ID
    assert datos.token_acceso == "access-token-real"
    assert datos.token_actualizacion == "refresh-token-real"
    assert datos.expira_at > datetime.now(UTC)


def test_registrar_con_correo_duplicado_error_explicito_levanta_registro_sin_sesion_inmediata() -> (
    None
):
    """Proyecto con "Confirm email" deshabilitado: GoTrue levanta un error explícito de
    correo duplicado. Se remapea a la MISMA excepción que el resto de casos sin sesión --
    nunca un error distinguible, o filtraría que el correo ya tenía cuenta."""
    error = AuthApiError("User already registered", status=422, code="user_already_exists")
    cliente = _cliente_con_auth(
        sign_up=lambda credenciales: (_ for _ in ()).throw(error)
    )
    autenticador = AutenticadorSupabase(cliente=cliente)

    with pytest.raises(RegistroSinSesionInmediata):
        autenticador.registrar(correo=CORREO, contrasena=CONTRASENA)


def test_registrar_con_identidades_vacias_y_sin_sesion_no_filtra_correo_ya_registrado() -> None:
    """Comportamiento anti-enumeración de GoTrue con "Confirm email" habilitado: 200 sin
    sesión y sin identidades cuando el correo ya tenía cuenta confirmada. `identities`
    NUNCA debe usarse para bifurcar la respuesta -- misma excepción que un correo nuevo."""
    usuario_sin_identidades = _usuario(identidades=[])
    respuesta = AuthResponse(user=usuario_sin_identidades, session=None)
    cliente = _cliente_con_auth(sign_up=lambda credenciales: respuesta)
    autenticador = AutenticadorSupabase(cliente=cliente)

    with pytest.raises(RegistroSinSesionInmediata):
        autenticador.registrar(correo=CORREO, contrasena=CONTRASENA)


def test_registrar_sin_sesion_pero_con_identidades_levanta_registro_sin_sesion_inmediata() -> None:
    """Correo genuinamente nuevo, pero el proyecto exige confirmar el correo antes de
    emitir sesión -- misma excepción que el caso de correo ya registrado arriba: desde
    afuera, ambos casos son indistinguibles."""
    usuario_nuevo = _usuario(identidades=None)
    respuesta = AuthResponse(user=usuario_nuevo, session=None)
    cliente = _cliente_con_auth(sign_up=lambda credenciales: respuesta)
    autenticador = AutenticadorSupabase(cliente=cliente)

    with pytest.raises(RegistroSinSesionInmediata):
        autenticador.registrar(correo=CORREO, contrasena=CONTRASENA)


def test_registrar_casos_sin_sesion_inmediata_devuelven_el_mismo_mensaje() -> None:
    """Verificación explícita de anti-enumeración: el mensaje de la excepción (lo que
    termina en el `detail` del HTTP 202) es idéntico sea correo nuevo, correo ya
    registrado (confirm email ON) o correo ya registrado (confirm email OFF)."""
    error_duplicado = AuthApiError(
        "User already registered", status=422, code="user_already_exists"
    )
    autenticador_error_explicito = AutenticadorSupabase(
        cliente=_cliente_con_auth(
            sign_up=lambda credenciales: (_ for _ in ()).throw(error_duplicado)
        )
    )
    autenticador_identidades_vacias = AutenticadorSupabase(
        cliente=_cliente_con_auth(
            sign_up=lambda credenciales: AuthResponse(
                user=_usuario(identidades=[]), session=None
            )
        )
    )
    autenticador_correo_nuevo = AutenticadorSupabase(
        cliente=_cliente_con_auth(
            sign_up=lambda credenciales: AuthResponse(
                user=_usuario(identidades=None), session=None
            )
        )
    )

    mensajes = set()
    for autenticador in (
        autenticador_error_explicito,
        autenticador_identidades_vacias,
        autenticador_correo_nuevo,
    ):
        with pytest.raises(RegistroSinSesionInmediata) as excepcion:
            autenticador.registrar(correo=CORREO, contrasena=CONTRASENA)
        mensajes.add(str(excepcion.value))

    assert len(mensajes) == 1


def test_registrar_con_correo_de_dominio_invalido_levanta_solicitud_invalida() -> None:
    """Caso real reproducido contra el proyecto de Supabase: GoTrue rechaza dominios
    como `@example.com` con un `AuthApiError` que no es "correo ya registrado" -- antes
    de este fix, este `raise` desnudo se propagaba crudo hasta un 500 genérico."""
    error = AuthApiError(
        'Email address "cliente@example.com" is invalid',
        status=400,
        code="email_address_invalid",
    )
    cliente = _cliente_con_auth(sign_up=lambda credenciales: (_ for _ in ()).throw(error))
    autenticador = AutenticadorSupabase(cliente=cliente)

    with pytest.raises(SolicitudAutenticacionInvalida, match="invalid"):
        autenticador.registrar(correo="cliente@example.com", contrasena=CONTRASENA)


def test_registrar_con_rate_limit_de_gotrue_levanta_solicitud_invalida() -> None:
    """Caso real reproducido: dos registros seguidos con el mismo correo activan el
    throttle anti-abuso nativo de GoTrue."""
    error = AuthApiError(
        "For security purposes, you can only request this after 51 seconds.",
        status=429,
        code="over_email_send_rate_limit",
    )
    cliente = _cliente_con_auth(sign_up=lambda credenciales: (_ for _ in ()).throw(error))
    autenticador = AutenticadorSupabase(cliente=cliente)

    with pytest.raises(SolicitudAutenticacionInvalida, match="51 seconds"):
        autenticador.registrar(correo=CORREO, contrasena=CONTRASENA)


def test_iniciar_sesion_devuelve_datos_de_sesion() -> None:
    cliente = _cliente_con_auth(
        sign_in_with_password=lambda credenciales: _respuesta_con_sesion()
    )
    autenticador = AutenticadorSupabase(cliente=cliente)

    datos = autenticador.iniciar_sesion(correo=CORREO, contrasena=CONTRASENA)

    assert datos.usuario_id == USUARIO_ID


def test_iniciar_sesion_con_credenciales_incorrectas_levanta_credenciales_invalidas() -> None:
    error = AuthApiError("Invalid login credentials", status=400, code="invalid_credentials")
    cliente = _cliente_con_auth(
        sign_in_with_password=lambda credenciales: (_ for _ in ()).throw(error)
    )
    autenticador = AutenticadorSupabase(cliente=cliente)

    with pytest.raises(CredencialesInvalidas):
        autenticador.iniciar_sesion(correo=CORREO, contrasena="clave-incorrecta")


def test_iniciar_sesion_con_rate_limit_de_gotrue_no_se_confunde_con_credenciales_invalidas() -> None:
    """Un throttle/rate-limit de GoTrue en login NO debe mapearse a "credenciales
    inválidas": sería confuso decirle a un usuario real que su password está mal cuando
    en realidad Supabase lo está limitando."""
    error = AuthApiError(
        "For security purposes, you can only request this after 51 seconds.",
        status=429,
        code="over_request_rate_limit",
    )
    cliente = _cliente_con_auth(
        sign_in_with_password=lambda credenciales: (_ for _ in ()).throw(error)
    )
    autenticador = AutenticadorSupabase(cliente=cliente)

    with pytest.raises(SolicitudAutenticacionInvalida, match="51 seconds"):
        autenticador.iniciar_sesion(correo=CORREO, contrasena=CONTRASENA)


def test_iniciar_sesion_con_correo_no_confirmado_colapsa_a_credenciales_invalidas() -> None:
    """Anti-enumeración: `email_not_confirmed` se colapsa al mismo error genérico que
    credenciales inválidas -- distinguirlo (p.ej. como un 400 aparte) permitiría a
    cualquiera enumerar qué correos tienen cuenta sin confirmar."""
    error = AuthApiError("Email not confirmed", status=400, code="email_not_confirmed")
    cliente = _cliente_con_auth(
        sign_in_with_password=lambda credenciales: (_ for _ in ()).throw(error)
    )
    autenticador = AutenticadorSupabase(cliente=cliente)

    with pytest.raises(CredencialesInvalidas):
        autenticador.iniciar_sesion(correo=CORREO, contrasena=CONTRASENA)


def test_iniciar_sesion_con_error_no_reconocido_levanta_solicitud_invalida() -> None:
    """Catch-all: cualquier `AuthApiError` con un código que no sea `invalid_credentials`
    ni `email_not_confirmed` no debe propagarse crudo ni mapearse a `CredencialesInvalidas`."""
    error = AuthApiError(
        "Signups not allowed for this instance", status=422, code="signup_disabled"
    )
    cliente = _cliente_con_auth(
        sign_in_with_password=lambda credenciales: (_ for _ in ()).throw(error)
    )
    autenticador = AutenticadorSupabase(cliente=cliente)

    with pytest.raises(SolicitudAutenticacionInvalida, match="not allowed"):
        autenticador.iniciar_sesion(correo=CORREO, contrasena=CONTRASENA)


def test_enviar_recuperacion_contrasena_nunca_levanta_aunque_gotrue_rechace() -> None:
    """Anti-enumeración: incluso si GoTrue levanta (rate-limit, etc.), el adaptador se lo
    traga -- el llamador nunca puede distinguir "correo con cuenta" de "correo sin
    cuenta" ni de "GoTrue rechazó la solicitud" a partir de este método."""
    error = AuthApiError(
        "For security purposes, you can only request this after 51 seconds.",
        status=429,
        code="over_email_send_rate_limit",
    )
    cliente = _cliente_con_auth(
        reset_password_for_email=lambda correo, **_: (_ for _ in ()).throw(error)
    )
    autenticador = AutenticadorSupabase(cliente=cliente)

    autenticador.enviar_recuperacion_contrasena(correo=CORREO)


def test_enviar_recuperacion_contrasena_llama_a_gotrue_con_el_correo() -> None:
    cliente = _cliente_con_auth(reset_password_for_email=lambda correo, **_: None)
    autenticador = AutenticadorSupabase(cliente=cliente)

    autenticador.enviar_recuperacion_contrasena(correo=CORREO)

    cliente.auth.reset_password_for_email.assert_called_once_with(CORREO)


def _mockear_cliente_efimero(monkeypatch: pytest.MonkeyPatch, cliente_efimero) -> None:
    """`restablecer_contrasena` deliberadamente NO usa `self.cliente` (el compartido/
    cacheado por `registrar`/`iniciar_sesion`) -- construye un cliente nuevo por llamada
    vía `obtener_cliente_supabase_auth_efimero` para evitar la condición de carrera del
    storage de sesión en memoria de `GoTrueClient` (ver
    `cliente_supabase.obtener_cliente_supabase_auth_efimero`). Estos tests mockean esa
    factory a nivel de módulo, no `self.cliente`.
    """
    monkeypatch.setattr(
        autenticador_supabase_modulo, "obtener_cliente_supabase_auth_efimero", lambda: cliente_efimero
    )


def test_restablecer_contrasena_con_sesion_de_recovery_valida_llama_update_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente_efimero = _cliente_con_auth(set_session=lambda *_: None, update_user=lambda *_: None)
    _mockear_cliente_efimero(monkeypatch, cliente_efimero)
    autenticador = AutenticadorSupabase(cliente=_cliente_con_auth())

    autenticador.restablecer_contrasena(
        token_acceso="acc", token_actualizacion="ref", nueva_contrasena="clave-nueva-larga"
    )

    cliente_efimero.auth.set_session.assert_called_once_with("acc", "ref")
    cliente_efimero.auth.update_user.assert_called_once_with({"password": "clave-nueva-larga"})


def test_restablecer_contrasena_no_reutiliza_el_cliente_compartido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verificación explícita de la corrección de la condición de carrera: el cliente
    inyectado por constructor (`self.cliente`, compartido entre requests) NUNCA se toca
    en este método."""
    cliente_compartido = _cliente_con_auth()
    cliente_efimero = _cliente_con_auth(set_session=lambda *_: None, update_user=lambda *_: None)
    _mockear_cliente_efimero(monkeypatch, cliente_efimero)
    autenticador = AutenticadorSupabase(cliente=cliente_compartido)

    autenticador.restablecer_contrasena(
        token_acceso="acc", token_actualizacion="ref", nueva_contrasena="clave-nueva-larga"
    )

    cliente_compartido.auth.set_session.assert_not_called()
    cliente_compartido.auth.update_user.assert_not_called()


def test_restablecer_contrasena_con_sesion_invalida_levanta_token_invalido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente_efimero = _cliente_con_auth(
        set_session=lambda *_: (_ for _ in ()).throw(AuthSessionMissingError())
    )
    _mockear_cliente_efimero(monkeypatch, cliente_efimero)
    autenticador = AutenticadorSupabase(cliente=_cliente_con_auth())

    with pytest.raises(TokenInvalido):
        autenticador.restablecer_contrasena(
            token_acceso="acc", token_actualizacion="ref", nueva_contrasena="clave-nueva-larga"
        )


def test_restablecer_contrasena_con_jwt_malformado_levanta_token_invalido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente_efimero = _cliente_con_auth(
        set_session=lambda *_: (_ for _ in ()).throw(AuthInvalidJwtError("Invalid JWT structure"))
    )
    _mockear_cliente_efimero(monkeypatch, cliente_efimero)
    autenticador = AutenticadorSupabase(cliente=_cliente_con_auth())

    with pytest.raises(TokenInvalido):
        autenticador.restablecer_contrasena(
            token_acceso="no-es-un-jwt",
            token_actualizacion="ref",
            nueva_contrasena="clave-nueva-larga",
        )


def test_restablecer_contrasena_con_politica_de_password_rechazada_levanta_solicitud_invalida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = AuthApiError("Password should be at least 8 characters", status=422, code="weak_password")
    cliente_efimero = _cliente_con_auth(
        set_session=lambda *_: None,
        update_user=lambda *_: (_ for _ in ()).throw(error),
    )
    _mockear_cliente_efimero(monkeypatch, cliente_efimero)
    autenticador = AutenticadorSupabase(cliente=_cliente_con_auth())

    with pytest.raises(SolicitudAutenticacionInvalida):
        autenticador.restablecer_contrasena(
            token_acceso="acc", token_actualizacion="ref", nueva_contrasena="short12"
        )
