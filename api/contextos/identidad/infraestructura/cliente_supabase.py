"""Cliente `supabase-py` compartido por los adaptadores de este contexto.

Un único cliente por proceso, con la `secret` key (sistema nuevo de API keys de Supabase,
reemplaza a `service_role`): el backend consulta
`roles_usuario`/`sesiones` con privilegios que bypasean RLS a propósito -- la
autorización real la resuelve el propio caso de uso de `identidad` (dominio) antes de
que el resultado llegue a ningún otro contexto; RLS en Supabase queda como segunda capa
de defensa para accesos directos (PostgREST desde el frontend), no como la única, tal
como ya lo asume `docs/ARCHITECTURE.md`.

Único lugar de todo `identidad` (y, por convención, de cualquier contexto futuro) donde
se instancia el cliente de Supabase -- el resto de `infraestructura/` lo recibe inyectado.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client
from supabase_auth.errors import AuthInvalidJwtError, AuthSessionMissingError

from contextos.identidad.dominio.excepciones import TokenInvalido
from nucleo.configuracion import obtener_configuracion


@lru_cache
def obtener_cliente_supabase() -> Client:
    configuracion = obtener_configuracion()
    return create_client(configuracion.supabase_url, configuracion.supabase_secret_key)


@lru_cache
def obtener_cliente_supabase_auth() -> Client:
    """Segundo cliente, separado del de arriba a propósito: inicializado con la clave
    PÚBLICA (`publishable`), solo para las operaciones de Auth API (GoTrue) que
    `AutenticadorSupabase` expone (registro, inicio de sesión).

    Signup/login son operaciones que cualquier usuario anónimo puede invocar
    legítimamente contra GoTrue -- usar la `secret` key ahí no otorga ningún privilegio
    adicional (GoTrue no lo requiere para esas dos operaciones) y violaría el principio
    de menor privilegio: si esta clave se filtrara, solo permite lo que el propio
    endpoint público de Auth ya permite a cualquiera, nunca bypasear RLS de
    `roles_usuario`/`sesiones` como sí podría la `secret` key.
    """
    configuracion = obtener_configuracion()
    return create_client(configuracion.supabase_url, configuracion.supabase_publishable_key)


def obtener_cliente_con_sesion_de_token(token_acceso: str) -> Client:
    """Cliente efímero (ver `obtener_cliente_supabase_auth_efimero`) con la sesión del
    propio usuario ya materializada a partir de su access token.

    `set_session(token_acceso, "")`: el refresh token vacío es intencional en TODOS los
    llamadores de esta función -- el access token de la request YA fue validado como no
    expirado por `ValidadorJwtSupabase` antes de llegar acá, así que `set_session` toma la
    rama que NO necesita refresh token (ver su docstring: solo lo usa si el access token
    está vencido).

    Único punto donde se mapean `AuthSessionMissingError`/`AuthInvalidJwtError` a
    `TokenInvalido` para este patrón -- antes triplicado entre `cambiar_contrasena`,
    `cambiar_correo` (`autenticador_supabase.py`) y el `_cliente_con_sesion` local de
    `autenticador_mfa_supabase.py`.

    Nota: `restablecer_contrasena` (flujo de recuperación) NO usa esta función -- ahí el
    refresh token SÍ es real (el par access/refresh que el frontend obtuvo del enlace de
    recuperación), un caso distinto que conserva su propio mapeo de error.
    """
    cliente = obtener_cliente_supabase_auth_efimero()
    try:
        cliente.auth.set_session(token_acceso, "")
    except (AuthSessionMissingError, AuthInvalidJwtError) as error:
        raise TokenInvalido("El token de acceso no es válido o expiró") from error
    return cliente


def obtener_cliente_supabase_como_usuario(token_jwt: str) -> Client:
    """Cliente nuevo (clave `publishable`, la misma de `obtener_cliente_supabase_auth`)
    cuyas queries a PostgREST corren con el JWT del usuario -- no con la `secret` key.

    Uso: `RepositorioPerfilSupabase` (lectura/escritura de `perfiles_usuario`), donde la
    ESCRITURA debe respetar la RLS real y dejar que el trigger
    `restringir_columnas_perfil_usuario` sea la única fuente de verdad de qué columnas
    puede tocar el propio usuario -- si se usara la `secret` key, PostgREST correría como
    `service_role` y ese trigger la reconoce como bypass explícito (ver
    `011_perfil_cuenta_gestion.sql`), exactamente lo que NO queremos acá.

    Deliberadamente SIN `@lru_cache`, a diferencia de los otros dos clientes de este
    módulo: el JWT cambia en cada request, cachear por valor de JWT filtraría memoria sin
    límite (uno por token emitido) y cachear un único cliente compartido mezclaría el JWT
    de un usuario con las requests de otro.
    """
    configuracion = obtener_configuracion()
    cliente = create_client(configuracion.supabase_url, configuracion.supabase_publishable_key)
    cliente.postgrest.auth(token_jwt)
    return cliente


def obtener_cliente_supabase_auth_efimero() -> Client:
    """Cliente nuevo (clave `publishable`) para operaciones de `AutenticadorPuerto` que
    mutan el estado de sesión INTERNO del cliente GoTrue (`auth.set_session`).

    `GoTrueClient` guarda la sesión "activa" en un storage en memoria propio de la
    instancia (`_save_session`/`get_session`) -- si se reutilizara el cliente cacheado de
    `obtener_cliente_supabase_auth` (compartido por TODO el proceso), dos requests
    concurrentes de `restablecer_contrasena` (o una de esas junto con un `registro`/
    `iniciar_sesion` concurrente, que también tocan ese mismo storage como side-effect)
    podrían pisarse la sesión en memoria entre el `set_session()` y el `update_user()`
    posterior -- `update_user()` lee la sesión de ESE storage compartido para decidir a
    qué usuario aplica el cambio de contraseña. En el peor caso, eso aplicaría la nueva
    contraseña a la cuenta de OTRO usuario. Un cliente nuevo por llamada, con su propio
    storage aislado, elimina esa condición de carrera de raíz -- mismo criterio que
    `obtener_cliente_supabase_como_usuario`, deliberadamente SIN `@lru_cache`.
    """
    configuracion = obtener_configuracion()
    return create_client(configuracion.supabase_url, configuracion.supabase_publishable_key)
