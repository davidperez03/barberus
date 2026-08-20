"""Tests de validación de formato de `ActualizarPerfilPeticion` -- lo que Pydantic debe
rechazar ANTES de llegar al caso de uso (URL inválida, `terminos_version` vacío, términos
sin versión, etc.)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from contextos.identidad.interfaces.esquemas import ActualizarPerfilPeticion


def test_acepta_nombre_completo_solo() -> None:
    peticion = ActualizarPerfilPeticion(nombre_completo="Ana Pérez")

    cambios = peticion.a_cambios_dominio()

    assert cambios.nombre_completo == "Ana Pérez"
    assert cambios.avatar_url is None


def test_acepta_avatar_url_valida() -> None:
    peticion = ActualizarPerfilPeticion(avatar_url="https://cdn.ejemplo.com/avatar.png")

    cambios = peticion.a_cambios_dominio()

    assert cambios.avatar_url == "https://cdn.ejemplo.com/avatar.png"


def test_rechaza_avatar_url_invalida() -> None:
    with pytest.raises(ValidationError):
        ActualizarPerfilPeticion(avatar_url="no-es-una-url")


def test_rechaza_nombre_completo_vacio() -> None:
    with pytest.raises(ValidationError):
        ActualizarPerfilPeticion(nombre_completo="")


def test_terminos_aceptados_sin_version_es_invalido() -> None:
    with pytest.raises(ValidationError, match="deben enviarse juntos"):
        ActualizarPerfilPeticion(terminos_aceptados_at=datetime.now(UTC))


def test_terminos_version_sin_aceptados_at_es_invalido() -> None:
    with pytest.raises(ValidationError, match="deben enviarse juntos"):
        ActualizarPerfilPeticion(terminos_version="2026-08-20")


def test_terminos_version_vacia_es_invalida() -> None:
    with pytest.raises(ValidationError):
        ActualizarPerfilPeticion(
            terminos_aceptados_at=datetime.now(UTC), terminos_version=""
        )


def test_terminos_aceptados_at_y_version_juntos_son_validos() -> None:
    ahora = datetime.now(UTC)

    peticion = ActualizarPerfilPeticion(terminos_aceptados_at=ahora, terminos_version="2026-08-20")

    cambios = peticion.a_cambios_dominio()
    assert cambios.terminos_aceptados_at == ahora
    assert cambios.terminos_version == "2026-08-20"


def test_sin_ningun_campo_produce_cambios_vacios() -> None:
    peticion = ActualizarPerfilPeticion()

    assert peticion.a_cambios_dominio().vacio is True
