"""Caso de uso: dado un JWT crudo, producir el `ContextoIdentidad` resuelto de esa request.

Es el bloque del que todo endpoint de dominio futuro depende (agenda, fila, membresias,
reportes lo consumirán a través del puerto/caso de uso público de `identidad`, nunca
importando sus entidades internas -- ver `contexto_publico.py`).

Orquesta el dominio a través de sus puertos; no contiene reglas de negocio propias (esas
viven en `dominio.servicios`) ni sabe de HTTP -- recibe el JWT y el `tenant_id`
solicitado ya extraídos por `interfaces/`, nunca los resuelve leyendo un header él mismo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from contextos.identidad.dominio.objetos_valor import ContextoIdentidad
from contextos.identidad.dominio.puertos import (
    RepositorioRolesPuerto,
    RepositorioSesionesPuerto,
    ValidadorTokenPuerto,
)
from contextos.identidad.dominio.servicios import resolver_rol_activo, verificar_sesion_vigente


@dataclass(frozen=True, slots=True)
class ResolverContextoIdentidad:
    """Caso de uso. Recibe sus puertos por constructor (inyectados desde `interfaces/`)."""

    validador_token: ValidadorTokenPuerto
    repositorio_roles: RepositorioRolesPuerto
    repositorio_sesiones: RepositorioSesionesPuerto

    def ejecutar(
        self,
        token_jwt: str,
        tenant_id_solicitado: str | None = None,
        sesion_id: str | None = None,
    ) -> ContextoIdentidad:
        """Resuelve identidad, rol activo (tenant explícito, nunca adivinado) y sesión.

        `tenant_id_solicitado` y `sesion_id` llegan explícitos desde `interfaces/`
        (headers `X-Tenant-Id`/`X-Sesion-Id`) -- este caso de uso nunca los infiere de
        un "contexto ambiente".
        """
        datos_token = self.validador_token.validar(token_jwt)
        asignaciones = self.repositorio_roles.listar_roles(datos_token.usuario_id)
        rol_activo = resolver_rol_activo(asignaciones, tenant_id_solicitado)

        sesion = None
        if sesion_id is not None:
            sesion = self.repositorio_sesiones.obtener_sesion(datos_token.usuario_id, sesion_id)
            if sesion is not None:
                verificar_sesion_vigente(sesion, ahora=datetime.now(UTC))

        return ContextoIdentidad(
            usuario_id=datos_token.usuario_id,
            correo=datos_token.correo,
            rol_activo=rol_activo,
            sesion=sesion,
        )
