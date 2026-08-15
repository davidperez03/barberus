"""Excepciones de dominio del contexto `identidad`. Python puro."""

from __future__ import annotations

from nucleo.excepciones import AccesoNoAutorizado, ExcepcionBarberus


class TokenInvalido(ExcepcionBarberus):
    """El JWT no es válido, expiró, o su firma no corresponde al proyecto Supabase configurado.

    Se mapea a HTTP 401 en `interfaces/` (no sabemos quién es el llamador).
    """


class SinRolAsignado(AccesoNoAutorizado):
    """El usuario está autenticado pero no tiene ninguna fila en `roles_usuario`."""


class TenantNoAutorizado(AccesoNoAutorizado):
    """El usuario pidió actuar sobre un `tenant_id` en el que no tiene ningún rol asignado."""


class TenantAmbiguo(AccesoNoAutorizado):
    """El usuario tiene roles en más de un tenant y no especificó cuál aplica a esta request.

    Nunca se resuelve "adivinando" (p.ej. tomar el primero sin `order by`) -- eso fue
    exactamente el hallazgo de seguridad corregido en el esquema (ver
    `docs/ARCHITECTURE.md`, sección "Cómo se resuelve el aislamiento"). El llamador debe
    especificar el tenant explícitamente (header `X-Tenant-Id`).
    """


class SesionExpirada(AccesoNoAutorizado):
    """La sesión referenciada superó su `expira_at` (timeout diferenciado por rol)."""


class SesionCerrada(AccesoNoAutorizado):
    """La sesión referenciada ya fue cerrada (logout explícito o forzado)."""
