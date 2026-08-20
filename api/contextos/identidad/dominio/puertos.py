"""Puertos del contexto `identidad`: lo que el dominio/aplicación necesita del mundo
exterior, expresado como `Protocol` -- sin saber NADA de cómo se implementa (Supabase,
otro proveedor, un fake de test).

`infraestructura/` implementa estos puertos contra Supabase; `aplicacion/` solo conoce
estas interfaces, nunca la implementación concreta.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from contextos.identidad.dominio.objetos_valor import (
    AsignacionRol,
    CambiosPerfil,
    DatosSesionAuth,
    DatosToken,
    EventoAuditoria,
    FactorMfa,
    InscripcionMfaTotp,
    NivelAutenticacion,
    PerfilCuenta,
    Sesion,
)


class ValidadorTokenPuerto(Protocol):
    """Valida un JWT crudo (de Supabase Auth/GoTrue) y extrae los datos que el dominio necesita.

    Implementación concreta: `infraestructura.validador_jwt_supabase.ValidadorJwtSupabase`.
    """

    def validar(self, token_jwt: str) -> DatosToken:
        """Levanta `dominio.excepciones.TokenInvalido` si el token no es válido/expiró."""
        ...


class RepositorioRolesPuerto(Protocol):
    """Lee asignaciones de rol (`roles_usuario`) de un usuario.

    Solo lectura a propósito: la escritura de `roles_usuario` (alta/baja de roles) es un
    caso de uso propio y más sensible (`auth-users.md` ya documenta quién puede asignar
    qué rol a quién), fuera del alcance de "resolver el contexto de una request".
    """

    def listar_roles(self, usuario_id: str) -> list[AsignacionRol]:
        ...


class RepositorioSesionesPuerto(Protocol):
    """Lee y actualiza metadata de sesión (`sesiones`) -- nunca valida el JWT en sí (eso
    lo sigue haciendo Supabase/GoTrue vía `ValidadorTokenPuerto`); esta tabla es para UX
    y para aplicar el timeout diferenciado por rol.
    """

    def obtener_sesion(self, usuario_id: str, sesion_id: str) -> Sesion | None:
        """`None` si no existe o no pertenece a `usuario_id`."""
        ...

    def listar_sesiones(self, usuario_id: str) -> list[Sesion]:
        """Todas las sesiones (activas y cerradas) del usuario, más recientes primero --
        `GET /identidad/sesiones`."""
        ...

    def cerrar_sesion(self, usuario_id: str, sesion_id: str) -> Sesion:
        """Marca `cerrada_at` de una sesión puntual (no todas -- ver
        `GestorCuentaPuerto.cerrar_todas_las_sesiones` para eso).

        LIMITACIÓN EXPLÍCITA: esto solo actualiza la metadata de aplicación en
        `sesiones` -- NO revoca el JWT/refresh token real de ESE dispositivo. La Auth
        Admin API de Supabase (`admin.sign_out`) solo expone revocación GLOBAL
        (`scope="global"`, todas las sesiones del usuario) o de la sesión ACTUAL del
        propio caller (`scope="local"`/`"others"`, que opera sobre el JWT de quien hace
        la llamada, identificado por un `session_id` embebido en ESE JWT) -- no existe
        una operación de Admin API que reciba un `sesion_id` arbitrario (como el que
        vive en nuestra tabla `sesiones`) y revoque ESA sesión específica sin poseer su
        JWT, que este backend nunca almacena (correctamente: guardar tokens ajenos sería
        un riesgo de seguridad mayor que esta limitación). En la práctica: cerrar una
        sesión puntual aquí es una acción de UX/auditoría ("ya no la veo en mi lista",
        útil si el dispositivo se perdió y se quiere dejar de confiar en él a nivel de
        producto) -- el JWT de ese dispositivo sigue siendo válido por firma hasta que
        expira naturalmente (`jwt_expiry`, hoy 1h) o hasta `cerrar_todas_las_sesiones`.

        Levanta `dominio.excepciones.SesionNoEncontrada` si no existe o no pertenece a
        `usuario_id`.
        """
        ...

    def iniciar_sesion(
        self,
        usuario_id: str,
        tenant_id: str | None,
        nivel_autenticacion: NivelAutenticacion,
        expira_at: datetime,
        dispositivo: str | None,
        ip: str | None,
    ) -> Sesion:
        """Crea la fila de sesión al iniciar sesión.

        Nota: distinto de `AutenticadorPuerto.iniciar_sesion` (que autentica contra
        Supabase Auth/GoTrue) -- este puerto solo escribe la metadata de aplicación en
        `sesiones` (timeout diferenciado por rol, UX). Orquestar ambos desde un mismo
        caso de uso queda fuera del alcance de este PR: `aplicacion.iniciar_sesion_con_credenciales`
        hoy solo resuelve el `AutenticadorPuerto`.
        """
        ...


class AutenticadorPuerto(Protocol):
    """Registra e inicia sesión de usuarios contra Supabase Auth (GoTrue).

    El backend hace de proxy de estas dos operaciones (en vez de dejar que el frontend
    llame a `supabase-js` directo) para poder probarlas desde `/docs` y para que toda la
    dependencia de Supabase Auth quede encerrada en un adaptador de `infraestructura/` --
    mismo patrón que `ValidadorTokenPuerto`.

    Implementación concreta: `infraestructura.autenticador_supabase.AutenticadorSupabase`.
    """

    def registrar(self, correo: str, contrasena: str) -> DatosSesionAuth:
        """Crea una cuenta nueva en Supabase Auth.

        Levanta `dominio.excepciones.RegistroSinSesionInmediata` si no se obtuvo sesión
        de inmediato -- deliberadamente la MISMA excepción tanto si el correo era
        genuinamente nuevo (confirmación pendiente) como si ya tenía cuenta: nunca debe
        poder distinguirse cuál de los dos casos ocurrió a partir de la respuesta de este
        puerto (anti-enumeración de cuentas, ver `docs/ARCHITECTURE.md`).

        Nunca asigna ningún rol en `roles_usuario` -- eso ocurre recién en la primera
        reserva del cliente (ver `docs/ARCHITECTURE.md`), es responsabilidad de otro
        caso de uso, no de este puerto.
        """
        ...

    def iniciar_sesion(self, correo: str, contrasena: str) -> DatosSesionAuth:
        """Autentica un usuario ya registrado contra Supabase Auth.

        Levanta `dominio.excepciones.CredencialesInvalidas` si el correo/contraseña no
        corresponden a ninguna cuenta, si la contraseña es incorrecta, o si la cuenta
        existe pero no ha confirmado su correo -- deliberadamente el mismo error genérico
        en los tres casos (anti-enumeración: no revelar que un correo existe pero está
        sin confirmar).
        """
        ...

    def enviar_recuperacion_contrasena(self, correo: str) -> None:
        """Dispara el correo de recuperación de contraseña de GoTrue (`/recover`).

        Nunca levanta -- GoTrue ya responde 200 sin distinguir "correo con cuenta" de
        "correo sin cuenta" en este endpoint (anti-enumeración propia de GoTrue); cualquier
        error que sí levante (p.ej. rate-limit) se traga en el adaptador, nunca se propaga,
        para que el router pueda responder SIEMPRE el mismo mensaje genérico sin importar
        qué ocurrió -- ver `interfaces.router`.
        """
        ...

    def restablecer_contrasena(
        self, token_acceso: str, token_actualizacion: str, nueva_contrasena: str
    ) -> None:
        """Establece una nueva contraseña sobre la sesión de recuperación ya validada por
        Supabase (el par access/refresh token que el frontend obtuvo al abrir el enlace del
        correo de recuperación) -- llama `updateUser` de GoTrue.

        Levanta `dominio.excepciones.TokenInvalido` si la sesión de recuperación no es
        válida/expiró, `dominio.excepciones.SolicitudAutenticacionInvalida` para cualquier
        otro rechazo de GoTrue (p.ej. política de contraseña).
        """
        ...

    def verificar_contrasena(self, correo: str, contrasena: str) -> None:
        """Prueba que `contrasena` es la contraseña ACTUAL de la cuenta de `correo`,
        reautenticando contra GoTrue (`sign_in_with_password`) y descartando la sesión
        resultante -- nunca confía en "el JWT de la request es válido" como prueba de
        que el llamador conoce la contraseña actual (eso solo prueba que inició sesión
        en algún momento dentro de la ventana de reautenticación reciente).

        Usado por `aplicacion.cambiar_contrasena.CambiarContrasena` antes de aplicar la
        nueva contraseña. Levanta `dominio.excepciones.CredencialesActualesIncorrectas`
        si no coincide.
        """
        ...

    def cambiar_contrasena(self, token_acceso: str, nueva_contrasena: str) -> None:
        """Fija una nueva contraseña sobre la sesión ACTIVA (no de recuperación) del
        propio usuario -- llama `updateUser({"password": ...})` de GoTrue con el JWT de
        la request ya validado. Distinto de `restablecer_contrasena`: ese es el flujo
        SIN sesión normal (enlace de correo); este SÍ requiere estar logueado, y el
        caso de uso ya validó `verificar_contrasena` antes de llegar acá.

        Levanta `dominio.excepciones.TokenInvalido` si el token no es utilizable,
        `dominio.excepciones.SolicitudAutenticacionInvalida` para cualquier otro rechazo
        de GoTrue (p.ej. política de contraseña).
        """
        ...

    def cambiar_correo(self, token_acceso: str, nuevo_correo: str) -> None:
        """Inicia el cambio de correo vía GoTrue nativo (`updateUser({"email": ...})`).

        Con `double_confirm_changes = true` (`supabase/config.toml`), GoTrue envía un
        correo de confirmación a AMBAS direcciones (la actual y la nueva) y el cambio
        solo se aplica cuando ambas confirman -- este puerto solo INICIA ese flujo, no
        lo completa.

        Levanta `dominio.excepciones.CorreoNoDisponible` si GoTrue rechaza el correo por
        pertenecer ya a otra cuenta (ver nota de anti-enumeración en el adaptador
        concreto -- esta es una fuga parcial aceptada del flujo nativo, no del todo
        evitable sin dejar de usarlo), `dominio.excepciones.TokenInvalido` si el token no
        es utilizable, `dominio.excepciones.SolicitudAutenticacionInvalida` para
        cualquier otro rechazo.
        """
        ...


class RepositorioAuditoriaPuerto(Protocol):
    """Lee `auditoria_autenticacion` -- historial de accesos/cambios sensibles. Solo
    lectura: la escritura de eventos de auditoría es responsabilidad de cada caso de uso
    que los genera (login, cambio de contraseña, etc.), no de este puerto -- fuera del
    alcance de este PR (ver docstring de `interfaces.router.listar_auditoria`).
    """

    def listar_eventos(self, usuario_id: str, limite: int, offset: int) -> list[EventoAuditoria]:
        """Eventos del propio usuario, más recientes primero. `limite`/`offset` ya
        validados por `interfaces/` (tope razonable, nunca "toda la tabla")."""
        ...


class AutenticadorMfaPuerto(Protocol):
    """Proxy del soporte NATIVO de MFA TOTP de Supabase Auth (`auth.mfa.*` de GoTrue,
    habilitado en `supabase/config.toml` `[auth.mfa.totp]`).

    DECISIÓN DE ARQUITECTURA: `factores_autenticacion`/`retos_autenticacion`
    (`010_identidad_extendida.sql`) quedan "MFA-ready" en el esquema pero SIN uso -- este
    contexto no reimplementa generación/validación de secretos TOTP a mano sobre esas
    tablas. GoTrue ya lo resuelve (genera el secreto, produce el QR/URI
    `otpauth://`, valida el código TOTP contra una ventana de tiempo, y eleva la sesión a
    `aal2` tras la primera verificación exitosa) -- mismo criterio que el resto del
    proyecto: nunca reinventar lo que Supabase Auth ya da (identity linking, recuperación
    de contraseña). Si en el futuro se necesitara un factor que GoTrue no soporte
    (WebAuthn, por ejemplo, si no se habilita nativamente), esas tablas siguen ahí para
    ese caso -- no para TOTP, que este puerto ya cubre.

    Implementación concreta: `infraestructura.autenticador_mfa_supabase.AutenticadorMfaSupabase`.
    """

    def inscribir_totp(self, token_acceso: str, nombre_amistoso: str | None) -> InscripcionMfaTotp:
        """Inicia la inscripción de un factor TOTP nuevo (`auth.mfa.enroll`) -- el factor
        queda `unverified` hasta `verificar_inscripcion`."""
        ...

    def verificar_inscripcion(self, token_acceso: str, factor_id: str, codigo: str) -> None:
        """Confirma el código generado por la app authenticator del usuario contra el
        factor recién inscrito (`auth.mfa.challenge_and_verify`) -- lo activa
        (`verified`) y eleva la sesión actual a `aal2`.

        Levanta `dominio.excepciones.CodigoMfaInvalido` si el código no corresponde,
        `dominio.excepciones.FactorMfaNoEncontrado` si `factor_id` no existe/no
        pertenece al usuario.
        """
        ...

    def desactivar(self, token_acceso: str, factor_id: str) -> None:
        """Elimina un factor MFA (`auth.mfa.unenroll`). Levanta
        `dominio.excepciones.FactorMfaNoEncontrado` si `factor_id` no existe/no
        pertenece al usuario."""
        ...

    def listar_factores(self, token_acceso: str) -> list[FactorMfa]:
        """Factores MFA (verificados y no verificados) del usuario autenticado."""
        ...


class RepositorioPerfilPuerto(Protocol):
    """Lee y actualiza los campos de gestión de cuenta de `perfiles_usuario`
    (`011_perfil_cuenta_gestion.sql`).

    La actualización SIEMPRE corre con el JWT del propio usuario (nunca con la `secret`
    key) para que la whitelist de columnas editables la siga aplicando el trigger
    `restringir_columnas_perfil_usuario` en Postgres -- este puerto/adaptador nunca
    reimplementa esa validación en Python, solo pasa el JWT y deja que RLS+trigger decidan.
    """

    def obtener_perfil(self, token_jwt: str, usuario_id: str) -> PerfilCuenta | None:
        """`None` si no existe la fila (no debería ocurrir para un usuario ya autenticado
        -- `crear_perfil_usuario` la crea al registrarse -- pero el puerto no lo asume)."""
        ...

    def actualizar_perfil(
        self, token_jwt: str, usuario_id: str, cambios: CambiosPerfil
    ) -> PerfilCuenta:
        """Levanta `dominio.excepciones.PerfilNoEncontrado` si RLS no deja ver/editar la
        fila (JWT no corresponde a `usuario_id`, o la fila no existe)."""
        ...


class GestorCuentaPuerto(Protocol):
    """Operaciones de cuenta que requieren el cliente con privilegio elevado (`secret`
    key / Auth Admin API) porque ningún cliente con JWT de usuario puede invocarlas --
    ver `infraestructura.administrador_cuenta_supabase` para el detalle de por qué cada
    una es una excepción consciente y acotada, no una forma de bypasear RLS en general.
    """

    def cerrar_todas_las_sesiones(self, token_acceso: str) -> None:
        """Revoca TODAS las sesiones (todos los dispositivos) del usuario dueño de
        `token_acceso` -- vía Auth Admin API (`admin.sign_out` con `scope="global"`), el
        único mecanismo que realmente invalida sesiones a nivel de Supabase Auth (marcar
        `sesiones.cerrada_at` en nuestra tabla de metadata NO invalida el JWT real).
        """
        ...

    def eliminar_cuenta(self, usuario_id: str) -> None:
        """Soft-delete de la cuenta vía Auth Admin API
        (`admin.delete_user(usuario_id, should_soft_delete=True)`), que marca
        `auth.users.deleted_at` -- el trigger `sincronizar_perfil_usuario`
        (`010_identidad_extendida.sql`) ya lo espeja a `perfiles_usuario.eliminado_at`,
        así que este puerto nunca escribe esa columna directo: usa la misma fuente de
        verdad (`auth.users`) que el resto del esquema, en vez de duplicarla.
        """
        ...
