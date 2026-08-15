/**
 * Caso de uso "quién soy" (`GET /identidad/contexto`). Expone el estado de forma que la
 * UI pueda distinguir con gracia el caso `sin_rol_asignado` -- ESPERADO hoy para un
 * usuario recién registrado, no un error catastrófico (el rol `cliente` se autoasigna
 * recién en la primera reserva, funcionalidad todavía no construida en el backend).
 */
import { useQuery } from "@tanstack/react-query";
import { almacenSesion, repositorioIdentidad } from "@/contextos/identidad/infraestructura/instancias";
import { ErrorIdentidad } from "@/contextos/identidad/dominio/tipos";

export const CLAVE_CONTEXTO_IDENTIDAD = ["identidad", "contexto"] as const;

export function useContextoIdentidad() {
  const accessToken = almacenSesion.obtenerAccessToken();

  const consulta = useQuery({
    queryKey: [...CLAVE_CONTEXTO_IDENTIDAD, accessToken],
    queryFn: () => repositorioIdentidad.obtenerContexto(accessToken as string),
    enabled: Boolean(accessToken),
    retry: false,
  });

  const sinRolAsignado =
    consulta.error instanceof ErrorIdentidad && consulta.error.codigo === "sin_rol_asignado";

  return { ...consulta, sinRolAsignado, haySesion: Boolean(accessToken) };
}
