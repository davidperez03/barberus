/**
 * Único lugar donde se traduce `NivelOcupacion` (regla de negocio en `dominio/semaforo.ts`)
 * a color -- antes cada consumidor (`mapa-leaflet`, `mapa-negocios`, `tablero-fila-en-vivo`)
 * reinventaba su propia tabla, con riesgo real de drift entre ellas.
 *
 * Cada nivel tiene dos variantes de color, igual de intencionales:
 * - `superficie`: fondos sólidos, bordes, puntos/dots -- el token "de marca" tal cual
 *   (`laton`, `senal`, `musgo`).
 * - `texto`: la misma familia de color pero en su variante clara, para pasar contraste AA
 *   cuando el color pinta texto pequeño sobre `carbon`. Ver el porqué de cada par en
 *   `compartido/tokens/colores.ts` (`senal`/`senalTexto`, `laton`/`latonSuave`).
 *
 * Los mapas de clases Tailwind de abajo (`CLASE_PUNTO_NIVEL`, `CLASE_TEXTO_NIVEL`) son
 * literales a propósito -- Tailwind detecta clases por análisis estático del código fuente,
 * no puede resolver un `bg-${token}` construido en tiempo de ejecución -- pero ambos se
 * derivan 1:1 de `TOKEN_NIVEL_OCUPACION`. Si cambia un token acá, cambian sus clases.
 */
import type { NivelOcupacion } from "@/contextos/fila/dominio/semaforo";
import type { TokenColor } from "@/compartido/tokens/colores";

interface TokenPorNivel {
  superficie: TokenColor;
  texto: TokenColor;
}

export const TOKEN_NIVEL_OCUPACION: Record<NivelOcupacion, TokenPorNivel> = {
  libre: { superficie: "musgo", texto: "musgo" },
  moderado: { superficie: "laton", texto: "latonSuave" },
  saturado: { superficie: "senal", texto: "senalTexto" },
  sin_datos: { superficie: "huesoAtenuado", texto: "huesoAtenuado" },
};

/** Clase Tailwind `bg-*` -- puntos/dots de leyenda y marcadores. */
export const CLASE_PUNTO_NIVEL: Record<NivelOcupacion, string> = {
  libre: "bg-musgo",
  moderado: "bg-laton",
  saturado: "bg-senal",
  sin_datos: "bg-hueso-atenuado",
};

/** Clase Tailwind `text-*` -- variante AA para texto pequeño. */
export const CLASE_TEXTO_NIVEL: Record<NivelOcupacion, string> = {
  libre: "text-musgo",
  moderado: "text-laton-suave",
  saturado: "text-senal-texto",
  sin_datos: "text-hueso-atenuado",
};

/** Variable CSS -- para estilos inyectados fuera de Tailwind (ícono de Leaflet vía `L.divIcon`). */
export const VARIABLE_CSS_SUPERFICIE_NIVEL: Record<NivelOcupacion, string> = {
  libre: "var(--color-musgo)",
  moderado: "var(--color-laton)",
  saturado: "var(--color-senal)",
  sin_datos: "var(--color-hueso-atenuado)",
};

/** "Chip" de estado (borde + fondo tenue + texto) -- popup del mapa y fila del tablero
 * comparten el mismo lenguaje de "etiqueta de nivel", en vez de cada uno inventar su
 * propio tratamiento de texto suelto. Literales por la misma razón que `CLASE_PUNTO_NIVEL`. */
export const CLASE_CHIP_NIVEL: Record<NivelOcupacion, string> = {
  libre: "border-musgo/40 bg-musgo/10 text-musgo",
  moderado: "border-laton/40 bg-laton/10 text-laton-suave",
  saturado: "border-senal/40 bg-senal/10 text-senal-texto",
  sin_datos: "border-borde bg-superficie-alta text-hueso-atenuado",
};
