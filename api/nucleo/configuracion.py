"""Configuración de la aplicación (variables de entorno).

Vive en `nucleo/` porque la conexión a Supabase (URL, secret key, JWKS) la necesita la
capa de `infraestructura/` de CUALQUIER contexto, no solo `identidad` -- `agenda`, `fila`,
`membresias` y `reportes` la reusarán tal cual cuando implementen sus propios adaptadores
contra Supabase.

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
    # secret key (sistema nuevo de API keys de Supabase, reemplaza a `service_role`): el
    # backend consulta roles_usuario/sesiones con privilegios que bypasean RLS -- la
    # autorización real ya la resolvió el propio backend (dominio de `identidad`) antes de
    # llegar a la query, RLS queda como segunda capa de defensa para accesos directos
    # (PostgREST desde el frontend), no como la única puerta acá.
    supabase_secret_key: str = Field(alias="SUPABASE_SECRET_KEY")

    # Clave pública nueva (sistema nuevo de API keys de Supabase, reemplaza a `anon`). El
    # backend hoy no la necesita para nada -- ninguno de sus adaptadores llama a Supabase
    # sin privilegios elevados -- pero se documenta acá para cuando el frontend la consuma
    # (cliente `supabase-js` en el navegador).
    supabase_publishable_key: str = Field(default="", alias="SUPABASE_PUBLISHABLE_KEY")

    # Validación del JWT emitido por Supabase Auth (GoTrue). Este proyecto firma con
    # claves asimétricas (ES256/RS256) publicadas en un JWKS rotable -- no expone un
    # secreto simétrico compartido. `SUPABASE_JWKS_URL` es el endpoint público desde el
    # que `infraestructura/validador_jwt_supabase.py` obtiene la clave de firma vigente
    # para cada JWT.
    supabase_jwks_url: str = Field(alias="SUPABASE_JWKS_URL")
    supabase_jwt_audiencia: str = Field(default="authenticated", alias="SUPABASE_JWT_AUDIENCIA")

    cors_origenes: str = Field(default="", alias="CORS_ORIGENES")

    @property
    def lista_cors_origenes(self) -> list[str]:
        return [origen.strip() for origen in self.cors_origenes.split(",") if origen.strip()]


@lru_cache
def obtener_configuracion() -> ConfiguracionApp:
    """Singleton de configuración por proceso (evita releer/revalidar el entorno en cada request)."""
    return ConfiguracionApp()
