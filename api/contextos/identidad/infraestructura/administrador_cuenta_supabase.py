"""Adaptador concreto de `GestorCuentaPuerto` contra la Auth Admin API de Supabase.

Usa el cliente con la `secret` key (`obtener_cliente_supabase`, el mismo de
`RepositorioRolesSupabase`/`RepositorioSesionesSupabase`) porque las dos operaciones que
expone SOLO existen en la Admin API de GoTrue -- ningún cliente autenticado con el JWT de
un usuario puede invocarlas, sin importar su rol. Excepción consciente y acotada a estas
dos operaciones (nunca una forma de bypasear RLS/el trigger de whitelist de
`perfiles_usuario` para ningún otro campo) -- mismo criterio de "excepción explícita,
documentada, mínima" que `barberus.contexto=sync_interno` en
`010_identidad_extendida.sql`.
"""

from __future__ import annotations

from dataclasses import dataclass

from supabase import Client
from supabase_auth.errors import AuthApiError

from contextos.identidad.dominio.excepciones import SolicitudAutenticacionInvalida
from contextos.identidad.dominio.puertos import GestorCuentaPuerto


@dataclass(frozen=True, slots=True)
class AdministradorCuentaSupabase(GestorCuentaPuerto):
    cliente: Client

    def cerrar_todas_las_sesiones(self, token_acceso: str) -> None:
        # `admin.sign_out(jwt, scope="global")` es el mecanismo real de GoTrue para
        # "cerrar sesión en todos los dispositivos": revoca TODOS los refresh tokens del
        # usuario dueño de `token_acceso` (no solo la sesión actual -- eso sería
        # scope="local"/"others"). Los access tokens (JWT) ya emitidos siguen siendo
        # válidos por firma hasta su propia expiración (son stateless, igual que en
        # Auth0/Firebase) pero dejan de poder refrescarse: es la MISMA limitación
        # estructural de cualquier JWT sin estado, no algo que este adaptador pueda evitar.
        # Requiere la `secret` key (Admin API) -- con la `publishable` key el usuario solo
        # puede cerrar SU sesión actual (`auth.sign_out()`), no forzar la revocación de
        # todas desde el backend.
        try:
            self.cliente.auth.admin.sign_out(token_acceso, "global")
        except AuthApiError as error:
            raise SolicitudAutenticacionInvalida(str(error)) from error

    def eliminar_cuenta(self, usuario_id: str) -> None:
        # Soft-delete vía Admin API (`should_soft_delete=True`): marca
        # `auth.users.deleted_at`. NO se escribe `perfiles_usuario.eliminado_at`
        # directamente -- el trigger `sincronizar_perfil_usuario`
        # (`010_identidad_extendida.sql`) ya lo espeja desde `auth.users` en la misma
        # transacción, que es la fuente de verdad real del esquema para este campo (ver su
        # comentario: "No es la fuente de verdad -- esa sigue siendo auth.users").
        # Escribir `perfiles_usuario` a mano duplicaría esa fuente de verdad y podría
        # desincronizarse si alguna vez cambia cómo se deriva `eliminado_at`.
        try:
            self.cliente.auth.admin.delete_user(usuario_id, should_soft_delete=True)
        except AuthApiError as error:
            raise SolicitudAutenticacionInvalida(str(error)) from error
