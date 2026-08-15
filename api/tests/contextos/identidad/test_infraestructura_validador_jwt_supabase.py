"""Tests del adaptador `ValidadorJwtSupabase` contra JWKS (firma asimétrica ES256).

No golpea red real: mockea `jwt.PyJWKClient.get_signing_key_from_jwt` para que devuelva
la clave pública de un par ES256 generado en el propio test, y firma los JWT de prueba
con la clave privada correspondiente -- así se ejercita el flujo real de
`jwt.decode(..., key=clave_publica, algorithms=[...])` sin depender del endpoint JWKS de
ningún proyecto Supabase real.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from contextos.identidad.dominio.excepciones import TokenInvalido
from contextos.identidad.infraestructura.validador_jwt_supabase import ValidadorJwtSupabase

USUARIO_ID = "11111111-1111-1111-1111-111111111111"


@dataclass
class _ClaveFirmaFake:
    key: object


@pytest.fixture
def par_de_claves_es256():
    clave_privada = ec.generate_private_key(ec.SECP256R1())
    return clave_privada, clave_privada.public_key()


def _emitir_token(clave_privada, *, audiencia="authenticated", emitido_en=None, sub=USUARIO_ID, correo="cliente@ejemplo.com"):
    ahora = emitido_en or datetime.now(UTC)
    claims = {
        "sub": sub,
        "email": correo,
        "aud": audiencia,
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(claims, key=clave_privada, algorithm="ES256")


def _validador_con_clave_mockeada(clave_publica) -> ValidadorJwtSupabase:
    with patch("jwt.PyJWKClient.__init__", return_value=None):
        validador = ValidadorJwtSupabase(jwks_url="https://ejemplo.supabase.co/auth/v1/.well-known/jwks.json")
    return validador, _ClaveFirmaFake(key=clave_publica)


def test_valida_jwt_firmado_con_clave_jwks_es256(par_de_claves_es256) -> None:
    clave_privada, clave_publica = par_de_claves_es256
    validador, clave_firma_fake = _validador_con_clave_mockeada(clave_publica)
    token = _emitir_token(clave_privada)

    with patch.object(validador._cliente_jwks, "get_signing_key_from_jwt", return_value=clave_firma_fake):
        datos = validador.validar(token)

    assert datos.usuario_id == USUARIO_ID
    assert datos.correo == "cliente@ejemplo.com"


def test_rechaza_jwt_firmado_con_otra_clave(par_de_claves_es256) -> None:
    _, clave_publica = par_de_claves_es256
    otra_clave_privada = ec.generate_private_key(ec.SECP256R1())
    validador, clave_firma_fake = _validador_con_clave_mockeada(clave_publica)
    token = _emitir_token(otra_clave_privada)

    with (
        patch.object(validador._cliente_jwks, "get_signing_key_from_jwt", return_value=clave_firma_fake),
        pytest.raises(TokenInvalido),
    ):
        validador.validar(token)


def test_rechaza_jwt_con_audiencia_incorrecta(par_de_claves_es256) -> None:
    clave_privada, clave_publica = par_de_claves_es256
    validador, clave_firma_fake = _validador_con_clave_mockeada(clave_publica)
    token = _emitir_token(clave_privada, audiencia="otra-audiencia")

    with (
        patch.object(validador._cliente_jwks, "get_signing_key_from_jwt", return_value=clave_firma_fake),
        pytest.raises(TokenInvalido),
    ):
        validador.validar(token)


def test_rechaza_jwt_sin_claim_sub(par_de_claves_es256) -> None:
    clave_privada, clave_publica = par_de_claves_es256
    validador, clave_firma_fake = _validador_con_clave_mockeada(clave_publica)
    token = _emitir_token(clave_privada, sub="")

    with (
        patch.object(validador._cliente_jwks, "get_signing_key_from_jwt", return_value=clave_firma_fake),
        pytest.raises(TokenInvalido),
    ):
        validador.validar(token)
