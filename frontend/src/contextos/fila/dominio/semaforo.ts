/**
 * Regla de negocio "semáforo de ocupación" -- cómo se traduce el resumen público de fila
 * de un negocio en un nivel visual (color) para el mapa. Función pura, sin React ni
 * Tailwind: `ui/` decide qué token de color pintar para cada nivel.
 *
 * Criterio: el tiempo estimado de espera es la señal más honesta para el cliente ("¿me
 * conviene ir ahora?") -- más que la cantidad cruda de personas en fila, porque la
 * duración de un servicio varía por rubro y por negocio (una manicura y un corte no
 * tardan lo mismo). Cuando el negocio todavía no tiene datos suficientes para estimarlo
 * (`tiempoEsperaEstimadoMinutos === null`), NO se inventa un color de ocupación --
 * se marca como `sin_datos`, un nivel neutro aparte.
 */
import type { ResumenFilaNegocio } from "@/contextos/fila/dominio/tipos";

export type NivelOcupacion = "libre" | "moderado" | "saturado" | "sin_datos";

/** Umbrales en minutos de espera estimada. Ajustables acá, en un único lugar. */
const UMBRAL_LIBRE_MINUTOS = 15;
const UMBRAL_MODERADO_MINUTOS = 30;

export function calcularNivelOcupacion(resumen: ResumenFilaNegocio): NivelOcupacion {
  const { tiempoEsperaEstimadoMinutos } = resumen;

  if (tiempoEsperaEstimadoMinutos === null) return "sin_datos";
  if (tiempoEsperaEstimadoMinutos <= UMBRAL_LIBRE_MINUTOS) return "libre";
  if (tiempoEsperaEstimadoMinutos <= UMBRAL_MODERADO_MINUTOS) return "moderado";
  return "saturado";
}

export const ETIQUETA_NIVEL_OCUPACION: Record<NivelOcupacion, string> = {
  libre: "Libre",
  moderado: "Espera moderada",
  saturado: "Fila larga",
  sin_datos: "Sin datos suficientes",
};
