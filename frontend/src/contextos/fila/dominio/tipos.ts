/**
 * Tipos puros del contexto `fila`. Reflejan el contrato real de
 * `api/contextos/fila/interfaces/esquemas.py` (`GET /fila/publica`) -- sin React, sin
 * fetch, sin Next. Único endpoint cross-tenant de toda la plataforma: agregados de
 * negocios activos, nunca datos individuales de clientes/profesionales.
 */

/** Un ítem de `GET /fila/publica` -- un negocio activo con su resumen de fila, pensado
 * para un marcador en el mapa (lat/lng) con semáforo de ocupación. */
export interface ResumenFilaNegocio {
  tenantId: string;
  nombreSede: string;
  slugSede: string;
  personasEnFila: number;
  /** `null` cuando el negocio no tiene datos suficientes para estimar espera todavía. */
  tiempoEsperaEstimadoMinutos: number | null;
  /** `null` cuando el negocio no cargó ubicación -- se filtra antes de llegar al mapa,
   * nunca se ubica en (0,0). */
  latitud: number | null;
  longitud: number | null;
}

/** `ResumenFilaNegocio` con coordenadas garantizadas -- lo que realmente puede pintarse
 * como marcador en el mapa. Separarlo del tipo crudo evita que `ui/` tenga que volver a
 * chequear `null` en cada componente. */
export interface NegocioUbicable extends ResumenFilaNegocio {
  latitud: number;
  longitud: number;
}

export function esUbicable(resumen: ResumenFilaNegocio): resumen is NegocioUbicable {
  return resumen.latitud !== null && resumen.longitud !== null;
}
