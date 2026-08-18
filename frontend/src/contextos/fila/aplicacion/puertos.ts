/**
 * Puerto (interfaz) que `aplicacion/` necesita y que `infraestructura/` implementa. Vive
 * en `aplicacion/` porque es quien lo consume -- `dominio/` no sabe que existe. Permite
 * probar el hook de caso de uso con un doble sin red.
 */
import type { ResumenFilaNegocio } from "@/contextos/fila/dominio/tipos";

/** Puerto hacia el único endpoint público del contexto `fila`. */
export interface RepositorioFila {
  listarNegociosPublicos(): Promise<ResumenFilaNegocio[]>;
}
