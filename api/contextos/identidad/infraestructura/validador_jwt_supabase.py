"""Adaptador concreto de `ValidadorTokenPuerto` contra los JWT que emite Supabase Auth/GoTrue.

Este proyecto firma sus JWT con claves asimétricas (ES256/RS256) publicadas en un JWKS
rotable (`SUPABASE_JWKS_URL`), no con un secreto simétrico compartido -- el sistema
"legacy" de `SUPABASE_JWT_SECRET`/HS256 no aplica acá. `jwt.PyJWKClient` resuelve, para
cada token, cuál de las claves publicadas en el JWKS lo firmó (por `kid`) y descarga/
cachea el JWK set; `jwt.decode` valida la firma con esa clave pública.

El resto del sistema (dominio, aplicación, `interfaces/`) no se entera de este mecanismo,
porque solo conoce `ValidadorTokenPuerto`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import jwt

from contextos.identidad.dominio.excepciones import TokenInvalido
from contextos.identidad.dominio.objetos_valor import DatosToken

ALGORITMOS_JWKS_SOPORTADOS = ("ES256", "RS256")


@dataclass(frozen=True, slots=True)
class ValidadorJwtSupabase:
    jwks_url: str
    audiencia: str = "authenticated"
    algoritmos: tuple[str, ...] = ALGORITMOS_JWKS_SOPORTADOS
    _cliente_jwks: jwt.PyJWKClient = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Un único `PyJWKClient` por instancia (y esta instancia vive una sola vez por
        # proceso, ver `interfaces/dependencias.py`): evita golpear el endpoint JWKS en
        # cada request -- `PyJWKClient` ya cachea el JWK set internamente, pero
        # instanciarlo una sola vez es la práctica recomendada, análoga al `lru_cache` de
        # `obtener_cliente_supabase`.
        #
        # Decisión consciente: `PyJWKClient` usa sus defaults (`cache_jwk_set=True`, TTL
        # de 5 minutos) sobre el JWK set completo. Esto implica que una clave revocada del
        # proyecto Supabase (removida del JWKS) puede seguir aceptándose hasta 5 minutos
        # si ya estaba cacheada -- ventana estándar de cualquier cliente JWKS (Auth0,
        # Firebase, etc.), no una regresión de este cambio. No se ajusta el TTL, solo se
        # documenta.
        object.__setattr__(self, "_cliente_jwks", jwt.PyJWKClient(self.jwks_url))

    def validar(self, token_jwt: str) -> DatosToken:
        try:
            clave_firma = self._cliente_jwks.get_signing_key_from_jwt(token_jwt)
            claims = jwt.decode(
                token_jwt,
                key=clave_firma.key,
                algorithms=list(self.algoritmos),
                audience=self.audiencia,
            )
        except jwt.PyJWTError as error:
            raise TokenInvalido(f"JWT inválido o expirado: {error}") from error

        usuario_id = claims.get("sub")
        if not usuario_id:
            raise TokenInvalido("El JWT no trae claim 'sub' (id de usuario)")

        emitido_en_raw = claims.get("iat")
        if emitido_en_raw is None:
            raise TokenInvalido("El JWT no trae claim 'iat' (emitido en)")

        return DatosToken(
            usuario_id=usuario_id,
            correo=claims.get("email"),
            emitido_en=datetime.fromtimestamp(emitido_en_raw, tz=UTC),
        )
