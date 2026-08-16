/** Caso de uso "iniciar sesión". Guarda la sesión en el almacén y la deja disponible
 * para que `useContextoIdentidad` la use enseguida. */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { almacenSesion, repositorioIdentidad } from "@/contextos/identidad/infraestructura/instancias";
import type { Credenciales, DatosSesionAuth } from "@/contextos/identidad/dominio/tipos";
import { CLAVE_CONTEXTO_IDENTIDAD } from "@/contextos/identidad/aplicacion/use-contexto-identidad";

export function useIniciarSesion() {
  const clienteConsultas = useQueryClient();

  return useMutation<DatosSesionAuth, Error, Credenciales>({
    mutationFn: async (credenciales) => repositorioIdentidad.iniciarSesion(credenciales),
    onSuccess: (sesion) => {
      almacenSesion.guardar(sesion);
      // Invalida el contexto (rol/tenant) para que se resuelva de nuevo con el token nuevo.
      clienteConsultas.invalidateQueries({ queryKey: CLAVE_CONTEXTO_IDENTIDAD });
    },
  });
}
