"""Adaptador concreto de `AutenticadorPuerto` contra la Auth API de Supabase (GoTrue).

Usa el cliente `supabase-py` (`obtener_cliente_supabase_auth`, inicializado con la
`publishable` key -- ver `cliente_supabase.py`) en vez de llamar al endpoint REST de Auth
directo con `httpx`: `supabase-py` ya empaqueta el cliente de GoTrue (`supabase_auth`,
antes `gotrue-py`) con `sign_up`/`sign_in_with_password` server-side, maneja el armado de
headers (`apikey`) y el parseo de la respuesta a tipos (`AuthResponse`/`Session`/`User`)
-- reimplementar eso a mano con `httpx` no aportaría nada, solo más superficie para
mantener sincronizada con la API de GoTrue.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from supabase import Client
from supabase_auth.errors import AuthApiError, AuthInvalidJwtError, AuthSessionMissingError
from supabase_auth.types import AuthResponse

from contextos.identidad.dominio.excepciones import (
    CorreoNoDisponible,
    CredencialesActualesIncorrectas,
    CredencialesInvalidas,
    RegistroSinSesionInmediata,
    SolicitudAutenticacionInvalida,
    TokenInvalido,
)
from contextos.identidad.dominio.objetos_valor import DatosSesionAuth
from contextos.identidad.infraestructura.cliente_supabase import (
    obtener_cliente_con_sesion_de_token,
    obtener_cliente_supabase_auth_efimero,
)

# Códigos de error de GoTrue (`supabase_auth.errors.ErrorCode`) que indican "correo ya
# tiene cuenta" al intentar registrar -- ambos existen según la versión/configuración del
# proyecto (`email_exists` es el código más nuevo, `user_already_exists` el histórico).
# Se remapean a `RegistroSinSesionInmediata`, la MISMA excepción (mismo HTTP, mismo
# mensaje) que el caso "registro aceptado, sesión pendiente" -- nunca a un error
# distinguible: revelaría que el correo ya tenía cuenta (fuga de enumeración).
_CODIGOS_CORREO_YA_REGISTRADO = frozenset({"user_already_exists", "email_exists"})

# Códigos de GoTrue (`supabase_auth.errors.ErrorCode`) que en login se mapean al mismo
# error genérico `CredencialesInvalidas`. `invalid_credentials` es el caso real de
# password incorrecta o cuenta inexistente; `email_not_confirmed` se colapsa a propósito
# al mismo error -- distinguirlo del resto (p.ej. como un 400 aparte) permitiría a
# cualquiera enumerar qué correos tienen cuenta sin confirmar, mismo criterio
# anti-enumeración que rige `registrar()`. Cualquier OTRO `AuthApiError` (rate-limit,
# etc.) NO debe mapearse acá -- sería decirle al usuario que su password está mal cuando
# en realidad Supabase está rechazando la solicitud por otro motivo.
_CODIGOS_CREDENCIALES_INVALIDAS = frozenset({"invalid_credentials", "email_not_confirmed"})


def _registro_sin_sesion_inmediata() -> RegistroSinSesionInmediata:
    """Único mensaje/excepción para TODO caso de `registrar()` sin sesión inmediata --
    ver `RegistroSinSesionInmediata` para por qué es deliberadamente indistinguible entre
    "correo nuevo" y "correo ya registrado". Centralizado acá para que no puedan
    divergir por accidente entre los distintos puntos donde se levanta.
    """
    return RegistroSinSesionInmediata(
        "Solicitud de registro procesada. Si el correo es válido y no tenía cuenta, "
        "revisa tu bandeja de entrada para confirmarla."
    )


@dataclass(frozen=True, slots=True)
class AutenticadorSupabase:
    cliente: Client

    def registrar(self, correo: str, contrasena: str) -> DatosSesionAuth:
        try:
            respuesta = self.cliente.auth.sign_up({"email": correo, "password": contrasena})
        except AuthApiError as error:
            if error.code in _CODIGOS_CORREO_YA_REGISTRADO:
                # Proyecto con "Confirm email" deshabilitado: GoTrue sí levanta un error
                # explícito para un correo ya registrado. Se remapea a la MISMA excepción
                # (mismo HTTP, mismo mensaje genérico) que el resto de casos sin sesión
                # más abajo -- nunca un error distinguible, o filtraría que el correo ya
                # tenía cuenta.
                raise _registro_sin_sesion_inmediata() from error
            # Catch-all: cualquier otro `AuthApiError` no anticipado (correo con dominio
            # inválido, rate-limit anti-abuso de GoTrue, etc.) -- se mapea a una excepción
            # de dominio explícita en vez de propagarse crudo hasta un 500 genérico.
            raise SolicitudAutenticacionInvalida(str(error)) from error

        if respuesta.session is not None:
            return self._mapear(respuesta)

        # Si el proyecto tiene "Confirm email" habilitado, GoTrue responde 200 sin
        # sesión tanto para un correo genuinamente nuevo (pendiente de confirmar) como,
        # por diseño anti-enumeración, para un correo YA registrado y confirmado -- no
        # revela la diferencia vía error. La única señal del lado cliente (`identities`
        # vacía cuando la cuenta ya existía) es deliberadamente IGNORADA acá: usarla para
        # bifurcar la respuesta reintroduciría la fuga de enumeración que GoTrue evita.
        raise _registro_sin_sesion_inmediata()

    def iniciar_sesion(self, correo: str, contrasena: str) -> DatosSesionAuth:
        try:
            respuesta = self.cliente.auth.sign_in_with_password(
                {"email": correo, "password": contrasena}
            )
        except AuthApiError as error:
            if error.code in _CODIGOS_CREDENCIALES_INVALIDAS:
                raise CredencialesInvalidas("Correo o contraseña incorrectos") from error
            # Cualquier otro `AuthApiError` (rate-limit, etc.) NO es "credenciales
            # inválidas" -- catch-all genérico, mismo criterio que en `registrar`.
            raise SolicitudAutenticacionInvalida(str(error)) from error
        return self._mapear(respuesta)

    def enviar_recuperacion_contrasena(self, correo: str) -> None:
        try:
            self.cliente.auth.reset_password_for_email(correo)
        except AuthApiError:
            # GoTrue ya responde 200 en `/recover` sin distinguir "correo con cuenta" de
            # "correo sin cuenta" (anti-enumeración propia de GoTrue) -- cualquier error
            # que SÍ levante acá (p.ej. `over_email_send_rate_limit`) se traga: nunca debe
            # ser observable desde la respuesta de este puerto, mismo criterio que
            # `registrar()`. El router responde siempre el mismo mensaje genérico.
            pass

    def restablecer_contrasena(
        self, token_acceso: str, token_actualizacion: str, nueva_contrasena: str
    ) -> None:
        # Cliente NUEVO (no `self.cliente`, que es el compartido/cacheado de
        # `registrar`/`iniciar_sesion`): `set_session()`+`update_user()` dependen del
        # storage de sesión EN MEMORIA del cliente GoTrue -- reusar el compartido
        # arriesgaría que dos requests concurrentes se pisen esa sesión y `update_user`
        # termine aplicando la nueva contraseña a otro usuario. Ver
        # `cliente_supabase.obtener_cliente_supabase_auth_efimero`.
        cliente_efimero = obtener_cliente_supabase_auth_efimero()
        try:
            # `update_user` de supabase-py exige una sesión ya "activa" en el cliente
            # (`get_session()` interno) -- `set_session` la materializa a partir del par
            # access/refresh token de recuperación que el frontend obtuvo al abrir el
            # enlace del correo (flujo estándar de GoTrue: la sesión de recovery YA es un
            # access_token válido, solo de corta vida / propósito limitado a esta
            # operación).
            cliente_efimero.auth.set_session(token_acceso, token_actualizacion)
            cliente_efimero.auth.update_user({"password": nueva_contrasena})
        except AuthApiError as error:
            raise SolicitudAutenticacionInvalida(str(error)) from error
        except (AuthSessionMissingError, AuthInvalidJwtError) as error:
            raise TokenInvalido("La sesión de recuperación no es válida o expiró") from error

    def verificar_contrasena(self, correo: str, contrasena: str) -> None:
        # Cliente NUEVO, mismo motivo que `restablecer_contrasena`: `sign_in_with_password`
        # muta el storage de sesión en memoria del cliente -- nunca el compartido. La
        # sesión que devuelve (si la contraseña es correcta) se descarta a propósito: este
        # método solo prueba conocimiento de la contraseña, no produce tokens utilizables.
        cliente_efimero = obtener_cliente_supabase_auth_efimero()
        try:
            cliente_efimero.auth.sign_in_with_password({"email": correo, "password": contrasena})
        except AuthApiError as error:
            if error.code in _CODIGOS_CREDENCIALES_INVALIDAS:
                raise CredencialesActualesIncorrectas(
                    "La contraseña actual no es correcta"
                ) from error
            raise SolicitudAutenticacionInvalida(str(error)) from error

    def cambiar_contrasena(self, token_acceso: str, nueva_contrasena: str) -> None:
        # `obtener_cliente_con_sesion_de_token` ya materializa la sesión (`set_session`
        # con refresh token vacío -- el access token de la request YA fue validado como
        # no expirado por `ValidadorJwtSupabase`) y mapea sesión inválida/expirada a
        # `TokenInvalido`; acá solo queda encadenar la operación de dominio propia.
        cliente_efimero = obtener_cliente_con_sesion_de_token(token_acceso)
        try:
            cliente_efimero.auth.update_user({"password": nueva_contrasena})
        except AuthApiError as error:
            raise SolicitudAutenticacionInvalida(str(error)) from error

    def cambiar_correo(self, token_acceso: str, nuevo_correo: str) -> None:
        cliente_efimero = obtener_cliente_con_sesion_de_token(token_acceso)
        try:
            cliente_efimero.auth.update_user({"email": nuevo_correo})
        except AuthApiError as error:
            if error.code == "email_exists":
                # ANTI-ENUMERACIÓN, DECISIÓN DOCUMENTADA: a diferencia de
                # registrar()/iniciar_sesion() (donde GoTrue mismo ya evita revelar si
                # un correo tiene cuenta), acá GoTrue SÍ distingue con un código propio
                # (`email_exists`) cuando el correo nuevo ya pertenece a otra cuenta --
                # es el propio backend de GoTrue el que impone unicidad de email y
                # responde distinto. No se puede ocultar del todo sin dejar de usar el
                # flujo nativo de `update_user` (que es justamente lo que este proyecto
                # prefiere sobre reimplementar el cambio de correo a mano). Mitigación
                # aplicada: el mensaje que ve el cliente es genérico (no repite "ya está
                # registrado" textual de GoTrue) -- pero el HECHO de que la operación
                # falle sigue siendo observable (a diferencia del 202 uniforme de
                # registro/recuperación). Aceptado porque quien dispara este endpoint ya
                # está autenticado y pasó reautenticación reciente (`CambiarCorreo`
                # exige JWT < 10 min) -- el costo de intentarlo repetidamente para
                # enumerar cuentas ajenas es mucho más alto que en un endpoint anónimo.
                raise CorreoNoDisponible(
                    "No se pudo actualizar el correo. Verifica que sea válido e intenta "
                    "con otro."
                ) from error
            raise SolicitudAutenticacionInvalida(str(error)) from error

    @staticmethod
    def _mapear(respuesta: AuthResponse) -> DatosSesionAuth:
        sesion = respuesta.session
        if sesion is None or respuesta.user is None:
            raise RegistroSinSesionInmediata(
                "Supabase Auth no devolvió sesión ni usuario en una respuesta exitosa"
            )
        # `Session.expires_at` está tipado `Optional[int]` pero el propio modelo de
        # `supabase_auth` lo calcula siempre a partir de `expires_in` si GoTrue no lo
        # trae (ver `supabase_auth.types.Session.validator`) -- el fallback a "ahora" es
        # solo defensivo, no se espera alcanzarlo con la librería actual.
        expira_at = (
            datetime.fromtimestamp(sesion.expires_at, tz=UTC)
            if sesion.expires_at is not None
            else datetime.now(UTC)
        )
        return DatosSesionAuth(
            token_acceso=sesion.access_token,
            token_actualizacion=sesion.refresh_token,
            usuario_id=respuesta.user.id,
            expira_at=expira_at,
        )
