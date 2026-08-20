"""Adaptador concreto de `RepositorioAuditoriaPuerto` contra
`public.auditoria_autenticacion`.

Cliente con `secret` key (mismo criterio que `RepositorioSesionesSupabase`/
`RepositorioRolesSupabase`): la tabla no tiene política de INSERT/UPDATE/DELETE para
PostgREST (solo el backend escribe), y la lectura acá ya está explícitamente acotada a
`usuario_id` del caller (nunca a un `tenant_id`/usuario arbitrario del body) por el caso
de uso -- RLS queda como segunda capa de defensa para accesos directos, no la única.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from supabase import Client

from contextos.identidad.dominio.objetos_valor import EventoAuditoria, EventoAutenticacion


def _fila_a_evento(fila: dict) -> EventoAuditoria:
    return EventoAuditoria(
        id=fila["id"],
        evento=EventoAutenticacion(fila["evento"]),
        tenant_id=fila.get("tenant_id"),
        ip=fila.get("ip"),
        user_agent=fila.get("user_agent"),
        metadata=fila.get("metadata") or {},
        creado_at=datetime.fromisoformat(fila["creado_at"]),
    )


@dataclass(frozen=True, slots=True)
class RepositorioAuditoriaSupabase:
    cliente: Client

    def listar_eventos(self, usuario_id: str, limite: int, offset: int) -> list[EventoAuditoria]:
        respuesta = (
            self.cliente.table("auditoria_autenticacion")
            .select("*")
            .eq("usuario_id", usuario_id)
            .order("creado_at", desc=True)
            .range(offset, offset + limite - 1)
            .execute()
        )
        return [_fila_a_evento(fila) for fila in respuesta.data]
