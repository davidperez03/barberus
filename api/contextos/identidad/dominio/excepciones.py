"""Excepciones de dominio del contexto `identidad`. Python puro."""

from __future__ import annotations

from nucleo.excepciones import AccesoNoAutorizado, ExcepcionBarberus, RecursoNoEncontrado


class TokenInvalido(ExcepcionBarberus):
    """El JWT no es válido, expiró, o su firma no corresponde al proyecto Supabase configurado.

    Se mapea a HTTP 401 en `interfaces/` (no sabemos quién es el llamador).
    """


class SinRolAsignado(AccesoNoAutorizado):
    """El usuario está autenticado pero no tiene ninguna fila en `roles_usuario`."""


class TenantNoAutorizado(AccesoNoAutorizado):
    """El usuario pidió actuar sobre un `tenant_id` en el que no tiene ningún rol asignado."""


class TenantAmbiguo(AccesoNoAutorizado):
    """El usuario tiene roles en más de un tenant y no especificó cuál aplica a esta request.

    Nunca se resuelve "adivinando" (p.ej. tomar el primero sin `order by`) -- eso fue
    exactamente el hallazgo de seguridad corregido en el esquema (ver
    `docs/ARCHITECTURE.md`, sección "Cómo se resuelve el aislamiento"). El llamador debe
    especificar el tenant explícitamente (header `X-Tenant-Id`).
    """


class SesionExpirada(AccesoNoAutorizado):
    """La sesión referenciada superó su `expira_at` (timeout diferenciado por rol)."""


class SesionCerrada(AccesoNoAutorizado):
    """La sesión referenciada ya fue cerrada (logout explícito o forzado)."""


class CredencialesInvalidas(ExcepcionBarberus):
    """El correo/contraseña no corresponden a ningún usuario, o la contraseña es incorrecta.

    Deliberadamente NO hereda de `AccesoNoAutorizado`: acá no sabemos quién es el
    llamador (no hay identidad resuelta todavía), así que se mapea a HTTP 401 en
    `interfaces/` -- mismo criterio que `TokenInvalido` (401 = "no sé quién eres", 403 =
    "sé quién eres y no puedes").
    """


class SolicitudAutenticacionInvalida(ExcepcionBarberus):
    """Supabase Auth (GoTrue) rechazó la solicitud de registro/login por un motivo
    distinto a "correo ya registrado" o "credenciales inválidas" -- p.ej. correo con
    dominio inválido, rate-limit anti-abuso (`over_request_rate_limit`,
    `over_email_send_rate_limit`), o cualquier otro `AuthApiError` no anticipado.

    Catch-all deliberado: sin esto, cualquier código de error de GoTrue no mapeado
    explícitamente se propagaba crudo hasta el router y terminaba en un 500 genérico.
    Se mapea a HTTP 400 en `interfaces/` (el mensaje original de GoTrue queda en
    `detail`) -- no es un 401/403 porque todavía no hay identidad resuelta, y no es un
    500 porque GoTrue sí entendió y respondió la solicitud, solo la rechazó.
    """


class RegistroSinSesionInmediata(ExcepcionBarberus):
    """`registrar()` no obtuvo una sesión utilizable de inmediato tras la solicitud a
    Supabase Auth.

    Deliberadamente la MISMA excepción (mismo mensaje genérico, mismo HTTP 202 en
    `interfaces/`) para los tres casos que GoTrue no distingue -- o que decidimos no
    distinguir nosotros -- de cara al llamador, precisamente para no reintroducir la
    fuga de enumeración de cuentas que `docs/ARCHITECTURE.md` (sección "Recuperación de
    contraseña y enumeración de usuarios") ya prohíbe para el resto del contexto:

    1. Correo genuinamente nuevo, proyecto con "Confirm email" habilitado: GoTrue acepta
       el signup pero no emite `access_token` hasta que el usuario confirma el enlace.
    2. Correo YA registrado y confirmado, proyecto con "Confirm email" habilitado:
       GoTrue responde 200 sin sesión (mismo shape que el caso 1) -- por diseño, GoTrue
       no revela la diferencia vía error; la única señal (`identities == []` en el
       usuario devuelto) es client-side y NUNCA debe usarse para bifurcar la respuesta.
    3. Correo YA registrado, proyecto con "Confirm email" deshabilitado: GoTrue sí
       levanta un `AuthApiError` explícito (`user_already_exists`/`email_exists`) -- se
       captura y se remapea a esta misma excepción en vez de propagarlo como un error
       distinguible.

    No es un error del llamador: es la respuesta esperada cuando no podemos (o no
    queremos) confirmar una sesión en el acto.
    """


class PerfilNoEncontrado(RecursoNoEncontrado):
    """No existe (o RLS no deja ver) la fila de `perfiles_usuario` del usuario autenticado.

    No debería ocurrir en operación normal (`crear_perfil_usuario` la crea al registrarse
    -- ver `010_identidad_extendida.sql`), pero el puerto no lo asume.
    """


class EdicionPerfilRechazada(AccesoNoAutorizado):
    """Postgres (RLS o `restringir_columnas_perfil_usuario`) rechazó la edición.

    El request ya venía validado por Pydantic a solo los campos permitidos por diseño --
    esto solo debería dispararse ante una condición de carrera o un cambio de esquema no
    reflejado todavía en `interfaces/esquemas.py`, nunca por un intento normal del cliente.
    """


class SesionNoEncontrada(RecursoNoEncontrado):
    """No existe (o no pertenece al usuario autenticado) la fila de `sesiones` pedida --
    `GET /identidad/sesiones/{sesion_id}/cerrar` u operaciones similares por id."""


class ReautenticacionRequerida(AccesoNoAutorizado):
    """El JWT de la request tiene un `iat` (emitido en) de más de 10 minutos y la
    operación pedida es sensible (cambiar contraseña, cambiar correo, eliminar cuenta) --
    mismo umbral/criterio que el trigger SQL `exigir_reautenticacion_clientes`
    (`009_identidad_autenticacion.sql`), replicado en la capa de aplicación porque no
    hay un trigger equivalente para `auth.users`/Auth Admin API. El llamador debe volver
    a iniciar sesión (obtener un JWT nuevo) e intentar de nuevo -- nunca se resuelve
    "refrescando" el token existente, porque `refresh_token` no vuelve a probar que el
    usuario conoce su contraseña.
    """


class CredencialesActualesIncorrectas(ExcepcionBarberus):
    """`cambiar-contrasena`: la `contrasena_actual` enviada no coincide con la real.

    Excepción propia (no reutiliza `CredencialesInvalidas`) porque acá SÍ sabemos quién
    es el llamador (JWT ya validado) -- es un rechazo de validación de la operación, no
    un fallo de autenticación anónima; se mapea a HTTP 400 en `interfaces/`, no a 401.
    """


class CorreoNoDisponible(ExcepcionBarberus):
    """`cambiar-correo`: GoTrue rechazó el nuevo correo porque ya pertenece a otra cuenta.

    Mensaje deliberadamente genérico en `interfaces/` -- no repite el texto literal de
    GoTrue ("ya está registrado"), aunque el HECHO de que la operación falle (a
    diferencia de un 202 genérico como en registro/recuperación) sigue siendo una señal
    observable: ver la nota de anti-enumeración en
    `infraestructura.autenticador_supabase.AutenticadorSupabase.cambiar_correo` para por
    qué esta fuga parcial es una limitación aceptada de GoTrue en este flujo
    autenticado (no del flujo anónimo de registro/login, que sí queda 100% mitigado),
    no algo que este contexto pueda cerrar del todo sin dejar de usar el flujo nativo.
    """


class CodigoMfaInvalido(ExcepcionBarberus):
    """El código TOTP ingresado no corresponde al factor/reto, o el reto ya expiró.

    Se mapea a HTTP 400 en `interfaces/` -- la identidad del llamador ya es conocida
    (JWT válido), esto es un rechazo de validación de la operación, no de autenticación.
    """


class FactorMfaNoEncontrado(RecursoNoEncontrado):
    """El `factor_id` dado no existe (o no pertenece al usuario autenticado) según GoTrue."""
