/**
 * Puertos (interfaces) que `aplicacion/` necesita y que `infraestructura/` implementa.
 * Vive en `aplicacion/` porque es quien los consume -- `dominio/` no sabe que existen.
 * Gracias a esto, los hooks de caso de uso se pueden probar con un doble de prueba sin
 * red, y `infraestructura/` puede cambiar de fetch a otra cosa sin tocar `aplicacion/ui`.
 */
import type {
  ContextoIdentidad,
  Credenciales,
  DatosSesionAuth,
  ResultadoRegistro,
} from "@/contextos/identidad/dominio/tipos";

/** Puerto hacia el backend de identidad (los 3 endpoints reales de `api/`). */
export interface RepositorioIdentidad {
  registrar(credenciales: Credenciales): Promise<ResultadoRegistro>;
  iniciarSesion(credenciales: Credenciales): Promise<DatosSesionAuth>;
  obtenerContexto(accessToken: string, tenantId?: string): Promise<ContextoIdentidad>;
}

/**
 * Puerto de persistencia de la sesión entre navegaciones. La implementación concreta
 * decide DÓNDE vive el token (ver `infraestructura/almacen-sesion-cookie.ts`) -- el
 * resto de la app solo conoce esta interfaz.
 */
export interface AlmacenSesion {
  guardar(sesion: DatosSesionAuth): void;
  obtenerAccessToken(): string | null;
  limpiar(): void;
}
