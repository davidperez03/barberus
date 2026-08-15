/**
 * Caso de uso "crear cuenta". Orquesta estado (react-query) + llama al puerto de
 * infraestructura -- cero lógica de negocio propia (esa vive en `dominio/`).
 */
import { useMutation } from "@tanstack/react-query";
import { almacenSesion, repositorioIdentidad } from "@/contextos/identidad/infraestructura/instancias";
import type { Credenciales, ResultadoRegistro } from "@/contextos/identidad/dominio/tipos";

export function useRegistro() {
  return useMutation<ResultadoRegistro, Error, Credenciales>({
    mutationFn: async (credenciales) => {
      const resultado = await repositorioIdentidad.registrar(credenciales);
      if (resultado.estado === "sesion_inmediata") {
        almacenSesion.guardar(resultado.sesion);
      }
      return resultado;
    },
  });
}
