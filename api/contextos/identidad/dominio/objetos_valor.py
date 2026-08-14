"""Objetos de valor del contexto `identidad`.

Python puro -- sin FastAPI, sin Pydantic, sin `supabase-py`. Debe poder importarse y
testearse sin red ni base de datos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Rol(str, Enum):
    """Espejo del enum `rol_app` de `supabase/migrations/001_extensiones_y_helpers.sql`."""

    ADMINISTRADOR_PLATAFORMA = "administrador_plataforma"
    DUENO_SEDE = "dueno_sede"
    BARBERO = "barbero"
    CLIENTE = "cliente"


class NivelAutenticacion(str, Enum):
    """Espejo de `sesiones.nivel_autenticacion` (equivalente simplificado al aal de Supabase)."""

    AAL1 = "aal1"
    AAL2 = "aal2"
    AAL3 = "aal3"


@dataclass(frozen=True, slots=True)
class AsignacionRol:
    """Una fila de `roles_usuario`: un rol concreto de un usuario en un tenant.

    `tenant_id` es `None` únicamente para `administrador_plataforma` (no tiene sede
    propia, ve las 20 -- mismo invariante que el constraint
    `roles_usuario_tenant_requerido_salvo_administrador_plataforma` del esquema).
    """

    tenant_id: str | None
    rol: Rol

    def __post_init__(self) -> None:
        if self.rol is Rol.ADMINISTRADOR_PLATAFORMA and self.tenant_id is not None:
            raise ValueError("administrador_plataforma no lleva tenant_id (ve las 20 sedes)")
        if self.rol is not Rol.ADMINISTRADOR_PLATAFORMA and self.tenant_id is None:
            raise ValueError(f"el rol {self.rol.value} requiere tenant_id")


@dataclass(frozen=True, slots=True)
class RolActivo:
    """El (tenant_id, rol) que aplica a la request actual, ya resuelto sin ambigüedad.

    Nunca se construye "adivinando" -- ver `servicios.resolver_rol_activo`, que es la
    única forma legítima de producir uno a partir de las asignaciones de un usuario.
    """

    tenant_id: str | None
    rol: Rol


@dataclass(frozen=True, slots=True)
class DatosToken:
    """Resultado de validar un JWT de Supabase Auth: quién es el portador y cuándo se emitió.

    No es "el JWT" ni un objeto de infraestructura -- es lo mínimo del token que el
    dominio necesita para razonar (identidad del usuario, frescura de la sesión para
    exigir reautenticación reciente, igual que hace el trigger
    `exigir_reautenticacion_clientes` en el esquema).
    """

    usuario_id: str
    correo: str | None
    emitido_en: datetime


@dataclass(frozen=True, slots=True)
class Sesion:
    """Espejo de una fila de `sesiones` -- metadata de aplicación, no el JWT en sí."""

    id: str
    usuario_id: str
    tenant_id: str | None
    nivel_autenticacion: NivelAutenticacion
    iniciada_at: datetime
    ultima_actividad_at: datetime
    expira_at: datetime
    cerrada_at: datetime | None

    @property
    def activa(self) -> bool:
        return self.cerrada_at is None


@dataclass(frozen=True, slots=True)
class ContextoIdentidad:
    """Resultado final del caso de uso `ResolverContextoIdentidad`.

    Lo que cualquier endpoint (de `identidad` o de cualquier otro contexto, vía el puerto
    público de `identidad`) necesita para autorizar una operación: quién es el usuario,
    qué rol tiene activo y en qué tenant, y el estado de su sesión si aplica.
    """

    usuario_id: str
    correo: str | None
    rol_activo: RolActivo
    sesion: Sesion | None
