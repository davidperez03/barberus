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
    PROFESIONAL = "profesional"
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
    dispositivo: str | None
    ip: str | None
    nivel_autenticacion: NivelAutenticacion
    iniciada_at: datetime
    ultima_actividad_at: datetime
    expira_at: datetime
    cerrada_at: datetime | None

    @property
    def activa(self) -> bool:
        return self.cerrada_at is None


@dataclass(frozen=True, slots=True)
class DatosSesionAuth:
    """Resultado de un registro o inicio de sesión exitoso contra Supabase Auth: lo mínimo
    que el cliente (frontend) necesita para operar a partir de ahí. No es "la respuesta
    de GoTrue" -- es lo que el dominio de `identidad` decide que le importa de esa
    respuesta (ver `dominio.puertos.AutenticadorPuerto`); el resto (metadata del
    proveedor, tipo de token, etc.) se descarta en el adaptador.
    """

    token_acceso: str
    token_actualizacion: str
    usuario_id: str
    expira_at: datetime


@dataclass(frozen=True, slots=True)
class PerfilCuenta:
    """Espejo de los campos de `perfiles_usuario` que el propio usuario gestiona sobre su
    cuenta (`011_perfil_cuenta_gestion.sql`) -- nombre/avatar transversales a todos los
    roles, consentimiento de términos y onboarding. No incluye `correo_verificado`,
    `telefono_verificado`, `eliminado_at`, `bloqueado_hasta` -- esos son estado que el
    propio usuario NUNCA edita (ver `restringir_columnas_perfil_usuario`) y no forman
    parte de "gestión de cuenta" en el sentido de este caso de uso.
    """

    usuario_id: str
    nombre_completo: str | None
    avatar_url: str | None
    terminos_aceptados_at: datetime | None
    terminos_version: str | None
    onboarding_completado_at: datetime | None


@dataclass(frozen=True, slots=True)
class CambiosPerfil:
    """Edición parcial de `PerfilCuenta` -- solo los campos que el llamador quiere tocar.

    Un campo en `None` significa "no lo toques" (el PATCH es parcial), NUNCA "bórralo a
    NULL" -- este contexto no tiene hoy un caso de uso real de "quitar mi nombre/avatar ya
    puesto", así que se prefiere esta semántica simple sobre un sentinel
    provisto/no-provisto que nadie necesita todavía.
    """

    nombre_completo: str | None = None
    avatar_url: str | None = None
    terminos_aceptados_at: datetime | None = None
    terminos_version: str | None = None
    onboarding_completado_at: datetime | None = None

    @property
    def vacio(self) -> bool:
        """`True` si no se pidió cambiar ningún campo -- el caso de uso lo puede rechazar
        antes de golpear la infraestructura."""
        return self == CambiosPerfil()


class EventoAutenticacion(str, Enum):
    """Espejo del check constraint `auditoria_autenticacion.evento`
    (`010_identidad_extendida.sql`)."""

    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FALLIDO = "login_fallido"
    CONTRASENA_CAMBIADA = "contrasena_cambiada"
    CONTRASENA_RECUPERADA = "contrasena_recuperada"
    BLOQUEO_APLICADO = "bloqueo_aplicado"
    BLOQUEO_REMOVIDO = "bloqueo_removido"
    MFA_ACTIVADO = "mfa_activado"
    MFA_DESACTIVADO = "mfa_desactivado"
    CORREO_CAMBIADO = "correo_cambiado"


@dataclass(frozen=True, slots=True)
class EventoAuditoria:
    """Espejo de una fila de `auditoria_autenticacion` -- historial de accesos/cambios
    sensibles del usuario autenticado (`GET /identidad/auditoria`)."""

    id: str
    evento: EventoAutenticacion
    tenant_id: str | None
    ip: str | None
    user_agent: str | None
    metadata: dict
    creado_at: datetime


class TipoFactorMfa(str, Enum):
    """Tipos de factor MFA que Supabase Auth (GoTrue) soporta hoy -- ver
    `supabase/config.toml` `[auth.mfa.totp]`/`[auth.mfa.phone]`. Solo TOTP está
    habilitado (`enroll_enabled`) en este proyecto; `PHONE` se deja modelado por si se
    habilita a futuro, pero ningún puerto de este contexto lo emite todavía."""

    TOTP = "totp"
    PHONE = "phone"


class EstadoFactorMfa(str, Enum):
    """Espejo del `status` que devuelve GoTrue para un factor MFA."""

    NO_VERIFICADO = "unverified"
    VERIFICADO = "verified"


@dataclass(frozen=True, slots=True)
class FactorMfa:
    """Un factor MFA tal como lo reporta GoTrue (`auth.mfa.list_factors`) -- no una fila
    de `factores_autenticacion` (esa tabla queda MFA-ready pero sin uso, ver
    `dominio.puertos.AutenticadorMfaPuerto`)."""

    id: str
    tipo: TipoFactorMfa
    estado: EstadoFactorMfa
    nombre_amistoso: str | None
    creado_at: datetime
    actualizado_at: datetime


@dataclass(frozen=True, slots=True)
class InscripcionMfaTotp:
    """Resultado de iniciar la inscripción de un factor TOTP (`auth.mfa.enroll`): secreto
    y QR para mostrar al usuario en su app authenticator. El factor queda `unverified`
    hasta que `VerificarInscripcionMfa` confirme un código válido."""

    factor_id: str
    secreto: str
    codigo_qr: str
    uri: str
    nombre_amistoso: str | None


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
