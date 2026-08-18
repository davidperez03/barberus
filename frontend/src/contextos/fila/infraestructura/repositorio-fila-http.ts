/**
 * Único adaptador de `fila` que hace `fetch` real. Implementa el puerto `RepositorioFila`
 * (`aplicacion/puertos.ts`) contra `GET /fila/publica` de
 * `api/contextos/fila/interfaces/router.py`. `aplicacion/` (hooks) nunca construye una
 * URL ni lee un `Response` directamente -- solo llama a este método.
 *
 * Sin autenticación a propósito: es el único endpoint cross-tenant de la plataforma
 * (comparador/mapa público), no lleva `Authorization` ni `X-Tenant-Id`.
 */
import type { RepositorioFila } from "@/contextos/fila/aplicacion/puertos";
import type { ResumenFilaNegocio } from "@/contextos/fila/dominio/tipos";

const URL_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ResumenFilaNegocioCrudo {
  tenant_id: string;
  nombre_sede: string;
  slug_sede: string;
  personas_en_fila: number;
  tiempo_espera_estimado_minutos: number | null;
  latitud: number | null;
  longitud: number | null;
}

function mapearResumen(crudo: ResumenFilaNegocioCrudo): ResumenFilaNegocio {
  return {
    tenantId: crudo.tenant_id,
    nombreSede: crudo.nombre_sede,
    slugSede: crudo.slug_sede,
    personasEnFila: crudo.personas_en_fila,
    tiempoEsperaEstimadoMinutos: crudo.tiempo_espera_estimado_minutos,
    latitud: crudo.latitud,
    longitud: crudo.longitud,
  };
}

export class RepositorioFilaHttp implements RepositorioFila {
  async listarNegociosPublicos(): Promise<ResumenFilaNegocio[]> {
    const respuesta = await fetch(`${URL_BASE}/fila/publica`, { method: "GET" });

    if (!respuesta.ok) {
      throw new Error(`No se pudo cargar el mapa de negocios (HTTP ${respuesta.status}).`);
    }

    const crudos = (await respuesta.json()) as ResumenFilaNegocioCrudo[];
    return crudos.map(mapearResumen);
  }
}
