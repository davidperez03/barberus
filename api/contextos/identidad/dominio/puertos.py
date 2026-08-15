"""Puertos del contexto `identidad`: lo que el dominio/aplicación necesita del mundo
exterior, expresado como `Protocol` -- sin saber NADA de cómo se implementa (Supabase,
otro proveedor, un fake de test).

`infraestructura/` implementa estos puertos contra Supabase; `aplicacion/` solo conoce
estas interfaces, nunca la implementación concreta.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from contextos.identidad.dominio.objetos_valor import (
    AsignacionRol,
    DatosToken,
    NivelAutenticacion,
    Sesion,
)


class ValidadorTokenPuerto(Protocol):
    """Valida un JWT crudo (de Supabase Auth/GoTrue) y extrae los datos que el dominio necesita.

    Implementación concreta: `infraestructura.validador_jwt_supabase.ValidadorJwtSupabase`.
    """

    def validar(self, token_jwt: str) -> DatosToken:
        """Levanta `dominio.excepciones.TokenInvalido` si el token no es válido/expiró."""
        ...


class RepositorioRolesPuerto(Protocol):
    """Lee asignaciones de rol (`roles_usuario`) de un usuario.

    Solo lectura a propósito: la escritura de `roles_usuario` (alta/baja de roles) es un
    caso de uso propio y más sensible (`auth-users.md` ya documenta quién puede asignar
    qué rol a quién), fuera del alcance de "resolver el contexto de una request".
    """

    def listar_roles(self, usuario_id: str) -> list[AsignacionRol]:
        ...


class RepositorioSesionesPuerto(Protocol):
    """Lee y actualiza metadata de sesión (`sesiones`) -- nunca valida el JWT en sí (eso
    lo sigue haciendo Supabase/GoTrue vía `ValidadorTokenPuerto`); esta tabla es para UX
    y para aplicar el timeout diferenciado por rol.
    """

    def obtener_sesion(self, usuario_id: str, sesion_id: str) -> Sesion | None:
        """`None` si no existe o no pertenece a `usuario_id`."""
        ...

    def iniciar_sesion(
        self,
        usuario_id: str,
        tenant_id: str | None,
        nivel_autenticacion: NivelAutenticacion,
        expira_at: datetime,
        dispositivo: str | None,
        ip: str | None,
    ) -> Sesion:
        """Crea la fila de sesión al iniciar sesión (fuera del alcance de este PR invocarlo
        desde un endpoint de login propio -- hoy el login lo resuelve Supabase Auth
        directo desde el frontend; este puerto queda listo para cuando el backend
        orqueste ese paso).
        """
        ...
