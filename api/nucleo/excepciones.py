"""Excepciones base compartidas.

Solo la raíz común y las categorías genuinamente transversales (toda excepción de
dominio en cualquier contexto es, en el fondo, "una regla de negocio se violó" o
"el llamador pidió algo a lo que no tiene derecho"). Las excepciones concretas
(`SinRolAsignado`, `TenantAmbiguo`, etc.) viven en el `dominio/` de cada contexto y
heredan de estas -- nunca al revés.
"""


class ExcepcionBarberus(Exception):
    """Raíz de toda excepción propia de Barberus (dominio o aplicación)."""


class ReglaDeNegocioViolada(ExcepcionBarberus):
    """Un invariante de un agregado/servicio de dominio no se cumplió."""


class AccesoNoAutorizado(ExcepcionBarberus):
    """El llamador está identificado pero no tiene derecho sobre el recurso/tenant pedido.

    Se mapea a HTTP 403 en `interfaces/`, nunca a 401 (401 es "no sé quién eres", 403 es
    "sé quién eres y no puedes").
    """


class RecursoNoEncontrado(ExcepcionBarberus):
    """El recurso solicitado no existe (o no es visible para este tenant/usuario)."""
