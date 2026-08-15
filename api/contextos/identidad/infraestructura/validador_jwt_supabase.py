"""Adaptador concreto de `ValidadorTokenPuerto` contra los JWT que emite Supabase Auth/GoTrue.

Implementa la validación con el secreto simétrico del proyecto (`SUPABASE_JWT_SECRET`,
HS256) -- el mecanismo hoy vigente en la mayoría de proyectos Supabase ("legacy JWT
secret"). Si el proyecto migra a firma asimétrica (RS256/ES256 vía JWKS rotable), este
adaptador es el único lugar a cambiar: se reemplaza `jwt.decode(..., key=secreto, ...)`
por un `jwt.PyJWKClient(jwks_url).get_signing_key_from_jwt(token)` -- el resto del
sistema (dominio, aplicación, `interfaces/`) no se entera, porque solo conoce
`ValidadorTokenPuerto`. Pendiente explícito para un PR futuro, no bloqueante para este.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import jwt

from contextos.identidad.dominio.excepciones import TokenInvalido
from contextos.identidad.dominio.objetos_valor import DatosToken


@dataclass(frozen=True, slots=True)
class ValidadorJwtSupabase:
    secreto: str
    audiencia: str = "authenticated"

    def validar(self, token_jwt: str) -> DatosToken:
        try:
            claims = jwt.decode(
                token_jwt,
                key=self.secreto,
                algorithms=["HS256"],
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
