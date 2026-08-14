"""Configuración de la aplicación (variables de entorno).

Vive en `nucleo/` porque la conexión a Supabase (URL, service role key, JWT secret) la
necesita la capa de `infraestructura/` de CUALQUIER contexto, no solo `identidad` --
`agenda`, `fila`, `membresias` y `reportes` la reusarán tal cual cuando implementen sus
propios adaptadores contra Supabase.

Usa Pydantic (`pydantic-settings`), lo cual está permitido acá: `nucleo/` no es
`dominio/` -- la regla de "Python puro, sin Pydantic" aplica solo dentro de cada
`contextos/<contexto>/dominio/`.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfiguracionApp(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    entorno: str = Field(default="desarrollo", alias="ENTORNO")

    supabase_url: str = Field(alias="SUPABASE_URL")
    # service_role: el backend consulta roles_usuario/sesiones con privilegios que
    # bypasean RLS -- la autorización real ya la resolvió el propio backend (dominio de
    # `identidad`) antes de llegar a la query, RLS queda como segunda capa de defensa para
    # accesos directos (PostgREST desde el frontend), no como la única puerta acá.
    supabase_service_role_key: str = Field(alias="SUPABASE_SERVICE_ROLE_KEY")

    # Validación del JWT emitido por Supabase Auth (GoTrue). Proyectos "legacy" de
    # Supabase firman con HS256 y un secreto simétrico (SUPABASE_JWT_SECRET); proyectos
    # más nuevos pueden firmar con claves asimétricas (RS256/ES256) publicadas en un JWKS.
    # Se soporta el caso simétrico en este PR (el mecanismo hoy vigente en la mayoría de
    # proyectos Supabase); el adaptador JWKS queda como extensión futura documentada en
    # `contextos/identidad/infraestructura/validador_jwt_supabase.py`.
    supabase_jwt_secret: str = Field(alias="SUPABASE_JWT_SECRET")
    supabase_jwt_audiencia: str = Field(default="authenticated", alias="SUPABASE_JWT_AUDIENCIA")

    cors_origenes: str = Field(default="", alias="CORS_ORIGENES")

    @property
    def lista_cors_origenes(self) -> list[str]:
        return [origen.strip() for origen in self.cors_origenes.split(",") if origen.strip()]


@lru_cache
def obtener_configuracion() -> ConfiguracionApp:
    """Singleton de configuración por proceso (evita releer/revalidar el entorno en cada request)."""
    return ConfiguracionApp()
