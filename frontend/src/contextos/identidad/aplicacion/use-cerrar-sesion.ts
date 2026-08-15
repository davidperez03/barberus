/** Caso de uso "cerrar sesión" (logout local -- el backend no expone /identidad/logout
 * todavía; limpiar el almacén local es lo que hay). */
import { useQueryClient } from "@tanstack/react-query";
import { almacenSesion } from "@/contextos/identidad/infraestructura/instancias";
import { CLAVE_CONTEXTO_IDENTIDAD } from "@/contextos/identidad/aplicacion/use-contexto-identidad";

export function useCerrarSesion() {
  const clienteConsultas = useQueryClient();
  return () => {
    almacenSesion.limpiar();
    clienteConsultas.removeQueries({ queryKey: CLAVE_CONTEXTO_IDENTIDAD });
  };
}
