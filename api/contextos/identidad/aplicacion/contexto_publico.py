"""Superficie pública del contexto `identidad` para OTROS contextos delimitados.

Convención para `agenda`/`fila`/`membresias`/`reportes`: si necesitan algo de
`identidad` (p.ej. "¿este usuario es barbero activo de este tenant?"), importan SOLO de
este módulo -- nunca `contextos.identidad.dominio.*` ni
`contextos.identidad.infraestructura.*` directamente. Hoy solo re-exporta el caso de uso
y los tipos de resultado que un consumidor externo necesita para razonar; a medida que
existan casos de uso reales en otros contextos que necesiten preguntas más específicas
("es_barbero_activo", "tiene_membresia_vigente"), se agregan acá como funciones
concretas, sin obligar al contexto llamante a conocer `RolActivo`/`Sesion` internos si no
los necesita.
"""

from __future__ import annotations

from contextos.identidad.aplicacion.resolver_contexto_identidad import ResolverContextoIdentidad
from contextos.identidad.dominio.objetos_valor import ContextoIdentidad, Rol
from contextos.identidad.interfaces.dependencias import (
    ContextoIdentidadDep,
    obtener_contexto_identidad,
)

__all__ = [
    "ContextoIdentidad",
    "ContextoIdentidadDep",
    "ResolverContextoIdentidad",
    "Rol",
    "obtener_contexto_identidad",
]
