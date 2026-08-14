"""Adaptador concreto de `RepositorioRolesPuerto` contra `public.roles_usuario`.

Solo lectura -- ver la nota del puerto sobre por qué la escritura de roles queda fuera de
este caso de uso.
"""

from __future__ import annotations

from dataclasses import dataclass

from supabase import Client

from contextos.identidad.dominio.objetos_valor import AsignacionRol, Rol


@dataclass(frozen=True, slots=True)
class RepositorioRolesSupabase:
    cliente: Client

    def listar_roles(self, usuario_id: str) -> list[AsignacionRol]:
        respuesta = (
            self.cliente.table("roles_usuario")
            .select("tenant_id, rol")
            .eq("usuario_id", usuario_id)
            .execute()
        )
        return [
            AsignacionRol(tenant_id=fila["tenant_id"], rol=Rol(fila["rol"]))
            for fila in respuesta.data
        ]
