/**
 * Traduce un error de dominio (`ErrorIdentidad`) a un mensaje de UI. Utilidad puramente de
 * presentación (no de negocio) compartida entre `pantalla-iniciar-sesion.tsx` y
 * `pantalla-registro.tsx` -- por eso vive en `ui/`, no en `dominio/`.
 */
import { ErrorIdentidad } from "@/contextos/identidad/dominio/tipos";

export function mensajeErrorIdentidad(error: unknown): string {
  if (error instanceof ErrorIdentidad) return error.message;
  return "No pudimos conectar con el servidor. Intenta de nuevo.";
}
