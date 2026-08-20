"""Adaptador concreto de `RepositorioSesionesPuerto` contra `public.sesiones`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from supabase import Client

from contextos.identidad.dominio.excepciones import SesionNoEncontrada
from contextos.identidad.dominio.objetos_valor import NivelAutenticacion, Sesion


def _fila_a_sesion(fila: dict) -> Sesion:
    return Sesion(
        id=fila["id"],
        usuario_id=fila["usuario_id"],
        tenant_id=fila.get("tenant_id"),
        dispositivo=fila.get("dispositivo"),
        ip=fila.get("ip"),
        nivel_autenticacion=NivelAutenticacion(fila["nivel_autenticacion"]),
        iniciada_at=datetime.fromisoformat(fila["iniciada_at"]),
        ultima_actividad_at=datetime.fromisoformat(fila["ultima_actividad_at"]),
        expira_at=datetime.fromisoformat(fila["expira_at"]),
        cerrada_at=datetime.fromisoformat(fila["cerrada_at"]) if fila.get("cerrada_at") else None,
    )


@dataclass(frozen=True, slots=True)
class RepositorioSesionesSupabase:
    cliente: Client

    def obtener_sesion(self, usuario_id: str, sesion_id: str) -> Sesion | None:
        respuesta = (
            self.cliente.table("sesiones")
            .select("*")
            .eq("id", sesion_id)
            .eq("usuario_id", usuario_id)
            .limit(1)
            .execute()
        )
        if not respuesta.data:
            return None
        return _fila_a_sesion(respuesta.data[0])

    def listar_sesiones(self, usuario_id: str) -> list[Sesion]:
        respuesta = (
            self.cliente.table("sesiones")
            .select("*")
            .eq("usuario_id", usuario_id)
            .order("iniciada_at", desc=True)
            .execute()
        )
        return [_fila_a_sesion(fila) for fila in respuesta.data]

    def cerrar_sesion(self, usuario_id: str, sesion_id: str) -> Sesion:
        # Idempotente a propósito: re-cerrar una sesión ya cerrada solo actualiza
        # `cerrada_at` de nuevo (no filtra por `cerrada_at is null`) -- no hay ambigüedad
        # de negocio en "cerrar dos veces algo ya cerrado", y filtrar por ese estado
        # convertiría un re-cierre legítimo en un falso `SesionNoEncontrada`.
        respuesta = (
            self.cliente.table("sesiones")
            .update({"cerrada_at": datetime.now(UTC).isoformat()})
            .eq("id", sesion_id)
            .eq("usuario_id", usuario_id)
            .execute()
        )
        if not respuesta.data:
            raise SesionNoEncontrada(
                f"No existe la sesión {sesion_id} para el usuario {usuario_id}"
            )
        return _fila_a_sesion(respuesta.data[0])

    def iniciar_sesion(
        self,
        usuario_id: str,
        tenant_id: str | None,
        nivel_autenticacion: NivelAutenticacion,
        expira_at: datetime,
        dispositivo: str | None,
        ip: str | None,
    ) -> Sesion:
        respuesta = (
            self.cliente.table("sesiones")
            .insert(
                {
                    "usuario_id": usuario_id,
                    "tenant_id": tenant_id,
                    "nivel_autenticacion": nivel_autenticacion.value,
                    "expira_at": expira_at.isoformat(),
                    "dispositivo": dispositivo,
                    "ip": ip,
                }
            )
            .execute()
        )
        return _fila_a_sesion(respuesta.data[0])
