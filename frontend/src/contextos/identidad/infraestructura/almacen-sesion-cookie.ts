/**
 * Implementación concreta de `AlmacenSesion` (ver `aplicacion/puertos.ts`).
 *
 * Decisión: cookie legible desde JS (`document.cookie`, sin `httpOnly`), NO
 * `localStorage`.
 *
 * Por qué: el backend hoy es un simple proxy de Supabase Auth -- responde el JSON con
 * `access_token`/`refresh_token`, no un `Set-Cookie` (ver `router.py`), así que quien
 * decide dónde persistir el token es este adaptador, no el backend. Frente a esa
 * decisión, `localStorage` es invisible para el servidor; una cookie (aunque hoy se
 * escriba desde el cliente) SÍ viaja en cada request y la puede leer un middleware/Server
 * Component de Next para proteger rutas por SSR sin reescribir esta capa -- solo agregar
 * un adaptador de lectura server-side que lea la misma cookie. No nos encierra: si más
 * adelante el backend empieza a emitir `Set-Cookie` `httpOnly` (más seguro contra XSS),
 * el cambio es reemplazar este archivo, sin tocar `aplicacion/` ni `ui/`.
 *
 * Trade-off aceptado por ahora: al no ser `httpOnly`, es tan vulnerable a XSS como
 * `localStorage` -- se documenta como deuda conocida, no como decisión final.
 */
import type { AlmacenSesion } from "@/contextos/identidad/aplicacion/puertos";
import type { DatosSesionAuth } from "@/contextos/identidad/dominio/tipos";

const NOMBRE_COOKIE = "barberus_sesion";

/** Evento propio disparado en cada cambio de sesión, para que `ui/` reaccione sin tener
 * que hacer polling del token (ver `SeccionAcceso`). */
export const EVENTO_CAMBIO_SESION = "barberus:sesion-cambio";

function estaEnNavegador(): boolean {
  return typeof document !== "undefined";
}

function notificarCambio(): void {
  if (estaEnNavegador()) window.dispatchEvent(new Event(EVENTO_CAMBIO_SESION));
}

function leerCookie(nombre: string): string | null {
  if (!estaEnNavegador()) return null;
  const coincidencia = document.cookie
    .split("; ")
    .find((fila) => fila.startsWith(`${nombre}=`));
  return coincidencia ? decodeURIComponent(coincidencia.split("=").slice(1).join("=")) : null;
}

export class AlmacenSesionCookie implements AlmacenSesion {
  guardar(sesion: DatosSesionAuth): void {
    if (!estaEnNavegador()) return;
    const expira = new Date(sesion.expiraAt);
    const maxAgeSegundos = Math.max(
      0,
      Math.floor((expira.getTime() - Date.now()) / 1000),
    );
    const valor = encodeURIComponent(
      JSON.stringify({ tokenAcceso: sesion.tokenAcceso, usuarioId: sesion.usuarioId }),
    );
    const seguro = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${NOMBRE_COOKIE}=${valor}; Path=/; Max-Age=${maxAgeSegundos}; SameSite=Lax${seguro}`;
    notificarCambio();
  }

  obtenerAccessToken(): string | null {
    const crudo = leerCookie(NOMBRE_COOKIE);
    if (!crudo) return null;
    try {
      return (JSON.parse(crudo) as { tokenAcceso: string }).tokenAcceso ?? null;
    } catch {
      return null;
    }
  }

  limpiar(): void {
    if (!estaEnNavegador()) return;
    document.cookie = `${NOMBRE_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
    notificarCambio();
  }
}
