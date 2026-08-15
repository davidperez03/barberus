/**
 * Composición: qué implementación concreta de cada puerto usa la app. Único lugar que lo
 * decide -- mismo criterio que `api/contextos/identidad/interfaces/dependencias.py` en el
 * backend. Si mañana cambia el transporte (ej. GraphQL) o el almacén de sesión (ej. cookie
 * `httpOnly` puesta por un route handler), solo este archivo cambia.
 */
import { AlmacenSesionCookie } from "@/contextos/identidad/infraestructura/almacen-sesion-cookie";
import { RepositorioIdentidadHttp } from "@/contextos/identidad/infraestructura/repositorio-identidad-http";

export { EVENTO_CAMBIO_SESION } from "@/contextos/identidad/infraestructura/almacen-sesion-cookie";
export const repositorioIdentidad = new RepositorioIdentidadHttp();
export const almacenSesion = new AlmacenSesionCookie();
