"""Servicios de dominio del contexto `identidad`. Python puro, sin dependencias externas.

Concentra las dos reglas de negocio de este contexto que NO son responsabilidad de un
caso de uso ni de un adaptador:
  1. Cuál (tenant_id, rol) aplica a una request cuando un usuario tiene roles en varios
     tenants (sedes son negocios independientes y competidores).
  2. Cuánto dura una sesión según el rol activo (timeout corto para profesional/dueno_sede,
     dispositivo compartido en el local -- ver `docs/ARCHITECTURE.md`, sección "Política
     de sesión/inactividad por rol").
"""

from __future__ import annotations

from datetime import datetime, timedelta

from contextos.identidad.dominio.excepciones import (
    ReautenticacionRequerida,
    SesionCerrada,
    SesionExpirada,
    SinRolAsignado,
    TenantAmbiguo,
    TenantNoAutorizado,
)
from contextos.identidad.dominio.objetos_valor import AsignacionRol, Rol, RolActivo, Sesion

# Timeout corto: profesional/dueno_sede operan en un dispositivo compartido del local (ver
# docs/ARCHITECTURE.md). Timeout normal: cliente y administrador_plataforma (no comparten
# dispositivo en el mismo sentido operativo).
_TIMEOUT_ROLES_DISPOSITIVO_COMPARTIDO = timedelta(minutes=15)
_TIMEOUT_ROLES_NORMAL = timedelta(hours=8)

_ROLES_DISPOSITIVO_COMPARTIDO = frozenset({Rol.PROFESIONAL, Rol.DUENO_SEDE})

# Mismo umbral que el trigger SQL `exigir_reautenticacion_clientes`
# (`009_identidad_autenticacion.sql`) para cambios sensibles de correo/teléfono de un
# cliente -- se replica acá porque las operaciones sensibles de ESTE contexto
# (cambiar-contrasena, cambiar-correo, eliminar-cuenta) actúan sobre `auth.users`/Auth
# Admin API, que no tiene un trigger de Postgres equivalente que lo exija por sí solo.
UMBRAL_REAUTENTICACION_RECIENTE = timedelta(minutes=10)


def resolver_rol_activo(
    asignaciones: list[AsignacionRol],
    tenant_id_solicitado: str | None,
) -> RolActivo:
    """Decide qué (tenant_id, rol) aplica a esta request -- SIEMPRE explícito, nunca adivinado.

    Reglas (en este orden):
    - Sin ninguna asignación: `SinRolAsignado`.
    - `administrador_plataforma` (ve las 20 sedes) puede operar sobre cualquier
      `tenant_id_solicitado`, incluso `None` (contexto de plataforma, sin sede concreta).
    - Con `tenant_id_solicitado` explícito: debe existir una asignación para ese tenant
      exacto, si no `TenantNoAutorizado`.
    - Sin `tenant_id_solicitado` y una sola asignación no-admin: se resuelve esa (no hay
      ambigüedad posible con una sola opción).
    - Sin `tenant_id_solicitado` y más de una asignación: `TenantAmbiguo` -- el llamador
      DEBE especificar el tenant (header `X-Tenant-Id`). Este es el caso que el propio
      esquema ya identificó como bug de seguridad cuando se resolvía con un
      `... limit 1` sin `order by` (ver `docs/ARCHITECTURE.md`); acá se rechaza en vez de
      adivinar.
    """
    if not asignaciones:
        raise SinRolAsignado("El usuario no tiene ninguna fila en roles_usuario")

    asignacion_admin = next(
        (a for a in asignaciones if a.rol is Rol.ADMINISTRADOR_PLATAFORMA), None
    )
    if asignacion_admin is not None:
        return RolActivo(tenant_id=tenant_id_solicitado, rol=Rol.ADMINISTRADOR_PLATAFORMA)

    if tenant_id_solicitado is not None:
        asignacion = next(
            (a for a in asignaciones if a.tenant_id == tenant_id_solicitado), None
        )
        if asignacion is None:
            raise TenantNoAutorizado(
                f"El usuario no tiene ningún rol en el tenant {tenant_id_solicitado}"
            )
        return RolActivo(tenant_id=asignacion.tenant_id, rol=asignacion.rol)

    if len(asignaciones) > 1:
        raise TenantAmbiguo(
            "El usuario tiene roles en más de un tenant; debe especificar cuál con "
            "X-Tenant-Id"
        )

    unica = asignaciones[0]
    return RolActivo(tenant_id=unica.tenant_id, rol=unica.rol)


def calcular_expiracion_sesion(rol: Rol, desde: datetime) -> datetime:
    """Calcula `expira_at` de una sesión según la política de timeout diferenciada por rol."""
    timeout = (
        _TIMEOUT_ROLES_DISPOSITIVO_COMPARTIDO
        if rol in _ROLES_DISPOSITIVO_COMPARTIDO
        else _TIMEOUT_ROLES_NORMAL
    )
    return desde + timeout


def verificar_sesion_vigente(sesion: Sesion, ahora: datetime) -> None:
    """Levanta si la sesión ya no es utilizable. No hace nada si sigue vigente.

    Recibe `ahora` como parámetro (no usa `datetime.now()` internamente) para que el
    dominio siga siendo puro y determinista en tests -- la aplicación decide el reloj.
    """
    if not sesion.activa:
        raise SesionCerrada(f"La sesión {sesion.id} ya fue cerrada")
    if ahora >= sesion.expira_at:
        raise SesionExpirada(f"La sesión {sesion.id} expiró en {sesion.expira_at.isoformat()}")


def verificar_reautenticacion_reciente(emitido_en: datetime, ahora: datetime) -> None:
    """Exige que el JWT actual (`emitido_en`, claim `iat`) tenga menos de 10 minutos --
    mismo criterio que `exigir_reautenticacion_clientes` en el esquema SQL. Recibe
    `ahora` como parámetro (no usa `datetime.now()` internamente) por el mismo motivo
    que `verificar_sesion_vigente`: el dominio sigue siendo puro y determinista en tests.
    """
    if ahora - emitido_en > UMBRAL_REAUTENTICACION_RECIENTE:
        raise ReautenticacionRequerida(
            "Esta operación requiere una sesión reciente (menos de 10 minutos desde el "
            "último inicio de sesión). Vuelve a iniciar sesión e intenta de nuevo."
        )
