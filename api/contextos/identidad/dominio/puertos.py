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
    DatosSesionAuth,
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
        """Crea la fila de sesión al iniciar sesión.

        Nota: distinto de `AutenticadorPuerto.iniciar_sesion` (que autentica contra
        Supabase Auth/GoTrue) -- este puerto solo escribe la metadata de aplicación en
        `sesiones` (timeout diferenciado por rol, UX). Orquestar ambos desde un mismo
        caso de uso queda fuera del alcance de este PR: `aplicacion.iniciar_sesion_con_credenciales`
        hoy solo resuelve el `AutenticadorPuerto`.
        """
        ...


class AutenticadorPuerto(Protocol):
    """Registra e inicia sesión de usuarios contra Supabase Auth (GoTrue).

    El backend hace de proxy de estas dos operaciones (en vez de dejar que el frontend
    llame a `supabase-js` directo) para poder probarlas desde `/docs` y para que toda la
    dependencia de Supabase Auth quede encerrada en un adaptador de `infraestructura/` --
    mismo patrón que `ValidadorTokenPuerto`.

    Implementación concreta: `infraestructura.autenticador_supabase.AutenticadorSupabase`.
    """

    def registrar(self, correo: str, contrasena: str) -> DatosSesionAuth:
        """Crea una cuenta nueva en Supabase Auth.

        Levanta `dominio.excepciones.RegistroSinSesionInmediata` si no se obtuvo sesión
        de inmediato -- deliberadamente la MISMA excepción tanto si el correo era
        genuinamente nuevo (confirmación pendiente) como si ya tenía cuenta: nunca debe
        poder distinguirse cuál de los dos casos ocurrió a partir de la respuesta de este
        puerto (anti-enumeración de cuentas, ver `docs/ARCHITECTURE.md`).

        Nunca asigna ningún rol en `roles_usuario` -- eso ocurre recién en la primera
        reserva del cliente (ver `docs/ARCHITECTURE.md`), es responsabilidad de otro
        caso de uso, no de este puerto.
        """
        ...

    def iniciar_sesion(self, correo: str, contrasena: str) -> DatosSesionAuth:
        """Autentica un usuario ya registrado contra Supabase Auth.

        Levanta `dominio.excepciones.CredencialesInvalidas` si el correo/contraseña no
        corresponden a ninguna cuenta, si la contraseña es incorrecta, o si la cuenta
        existe pero no ha confirmado su correo -- deliberadamente el mismo error genérico
        en los tres casos (anti-enumeración: no revelar que un correo existe pero está
        sin confirmar).
        """
        ...
