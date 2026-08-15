"""Tipos compartidos genuinamente transversales.

Alias de tipo, no entidades de dominio -- cualquier contexto (identidad, agenda, fila,
membresias, reportes) los usa para identificar filas de tablas multi-tenant sin acoplarse
a un tipo concreto de infraestructura (uuid de Postgres, str, etc.).
"""

from typing import NewType

# Los ids de fila en el esquema son uuid (texto en Python, sin validación de formato acá
# a propósito -- eso es responsabilidad del adaptador de infraestructura o del esquema
# Pydantic en `interfaces/`, no de este alias).
IdTenant = NewType("IdTenant", str)
IdUsuario = NewType("IdUsuario", str)
