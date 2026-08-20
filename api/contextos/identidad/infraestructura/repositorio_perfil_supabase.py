"""Adaptador concreto de `RepositorioPerfilPuerto` contra `public.perfiles_usuario`.

Construye un cliente nuevo por operación, autenticado con el JWT del propio usuario (ver
`cliente_supabase.obtener_cliente_supabase_como_usuario`) -- nunca con la `secret` key:
la ESCRITURA debe pasar por RLS + el trigger `restringir_columnas_perfil_usuario`
(`011_perfil_cuenta_gestion.sql`), que es la única fuente de verdad de qué columnas puede
tocar el propio usuario. Este adaptador nunca reimplementa esa whitelist en Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from postgrest.exceptions import APIError

from contextos.identidad.dominio.excepciones import EdicionPerfilRechazada
from contextos.identidad.dominio.objetos_valor import CambiosPerfil, PerfilCuenta
from contextos.identidad.dominio.puertos import RepositorioPerfilPuerto
from contextos.identidad.infraestructura.cliente_supabase import (
    obtener_cliente_supabase_como_usuario,
)

_COLUMNAS = (
    "usuario_id, nombre_completo, avatar_url, terminos_aceptados_at, "
    "terminos_version, onboarding_completado_at"
)


def _fila_a_perfil(fila: dict) -> PerfilCuenta:
    return PerfilCuenta(
        usuario_id=fila["usuario_id"],
        nombre_completo=fila.get("nombre_completo"),
        avatar_url=fila.get("avatar_url"),
        terminos_aceptados_at=(
            datetime.fromisoformat(fila["terminos_aceptados_at"])
            if fila.get("terminos_aceptados_at")
            else None
        ),
        terminos_version=fila.get("terminos_version"),
        onboarding_completado_at=(
            datetime.fromisoformat(fila["onboarding_completado_at"])
            if fila.get("onboarding_completado_at")
            else None
        ),
    )


@dataclass(frozen=True, slots=True)
class RepositorioPerfilSupabase(RepositorioPerfilPuerto):
    def obtener_perfil(self, token_jwt: str, usuario_id: str) -> PerfilCuenta | None:
        cliente = obtener_cliente_supabase_como_usuario(token_jwt)
        respuesta = (
            cliente.table("perfiles_usuario")
            .select(_COLUMNAS)
            .eq("usuario_id", usuario_id)
            .limit(1)
            .execute()
        )
        if not respuesta.data:
            return None
        return _fila_a_perfil(respuesta.data[0])

    def actualizar_perfil(
        self, token_jwt: str, usuario_id: str, cambios: CambiosPerfil
    ) -> PerfilCuenta:
        cliente = obtener_cliente_supabase_como_usuario(token_jwt)
        payload: dict[str, str] = {}
        if cambios.nombre_completo is not None:
            payload["nombre_completo"] = cambios.nombre_completo
        if cambios.avatar_url is not None:
            payload["avatar_url"] = cambios.avatar_url
        if cambios.terminos_aceptados_at is not None:
            payload["terminos_aceptados_at"] = cambios.terminos_aceptados_at.isoformat()
        if cambios.terminos_version is not None:
            payload["terminos_version"] = cambios.terminos_version
        if cambios.onboarding_completado_at is not None:
            payload["onboarding_completado_at"] = cambios.onboarding_completado_at.isoformat()

        try:
            respuesta = (
                cliente.table("perfiles_usuario")
                .update(payload)
                .eq("usuario_id", usuario_id)
                .select(_COLUMNAS)
                .execute()
            )
        except APIError as error:
            # RLS (`with check`) o el trigger de whitelist rechazaron el UPDATE -- no
            # debería ocurrir con un `CambiosPerfil` armado desde `interfaces/esquemas.py`
            # (solo expone los campos ya permitidos), pero si ocurre es un 403, nunca un
            # 500: Postgres sí entendió la solicitud, solo la rechazó por autorización.
            raise EdicionPerfilRechazada(str(error)) from error

        if not respuesta.data:
            # RLS bloqueó incluso ver la fila afectada (JWT no corresponde a usuario_id) --
            # mismo resultado observable que "no existe", no se distingue de más.
            raise EdicionPerfilRechazada(
                f"No se pudo actualizar el perfil de {usuario_id}: RLS no devolvió fila"
            )
        return _fila_a_perfil(respuesta.data[0])
