/**
 * Caso de uso "ver negocios activos con su fila en vivo" -- alimenta el mapa público de
 * la landing. Sin autenticación, sin `tenant_id`: cualquier visitante lo ve. Se refresca
 * solo cada cierto tiempo para que el semáforo del mapa no quede desactualizado mientras
 * el visitante lo mira, sin necesidad de que recargue la página.
 */
import { useQuery } from "@tanstack/react-query";
import { repositorioFila } from "@/contextos/fila/infraestructura/instancias";

export const CLAVE_NEGOCIOS_PUBLICOS = ["fila", "negocios-publicos"] as const;

const INTERVALO_REFRESCO_MS = 30_000;

export function useNegociosPublicos() {
  return useQuery({
    queryKey: CLAVE_NEGOCIOS_PUBLICOS,
    queryFn: () => repositorioFila.listarNegociosPublicos(),
    refetchInterval: INTERVALO_REFRESCO_MS,
    staleTime: INTERVALO_REFRESCO_MS,
  });
}
