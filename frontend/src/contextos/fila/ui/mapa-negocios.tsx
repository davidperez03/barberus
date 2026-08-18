"use client";

/**
 * Punto de entrada público de `fila/ui` para la landing: pide los negocios activos
 * (`useNegociosPublicos`), filtra los que no tienen coordenadas cargadas -- nunca se
 * ubican en (0,0) -- y decide qué mostrar: mapa real, carga, error o vacío. `app/page.tsx`
 * solo compone este componente junto con su propio copy de sección, como el resto de
 * piezas de la landing (cascarón, sin fetch propio).
 *
 * Leaflet depende de `window` (no soporta render de servidor); el mapa real
 * (`mapa-leaflet.tsx`) se carga acá con `next/dynamic` y `ssr: false`.
 */
import dynamic from "next/dynamic";
import { useMemo } from "react";
import { useNegociosPublicos } from "@/contextos/fila/aplicacion/use-negocios-publicos";
import { esUbicable, type NegocioUbicable } from "@/contextos/fila/dominio/tipos";
import {
  calcularNivelOcupacion,
  ETIQUETA_NIVEL_OCUPACION,
  type NivelOcupacion,
} from "@/contextos/fila/dominio/semaforo";
import { CLASE_PUNTO_NIVEL } from "@/contextos/fila/ui/token-por-nivel";
import { EncabezadoEnVivo } from "@/compartido/ui/encabezado-en-vivo";

const MapaLeaflet = dynamic(() => import("@/contextos/fila/ui/mapa-leaflet"), {
  ssr: false,
  loading: () => <IndicadorDeCarga />,
});

const NIVELES_LEYENDA: NivelOcupacion[] = ["libre", "moderado", "saturado", "sin_datos"];

function IndicadorDeCarga() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-superficie-alta">
      <span
        aria-hidden
        className="h-8 w-8 animate-spin rounded-full border-2 border-borde border-t-laton-suave"
      />
      <span className="sr-only">Cargando mapa de negocios activos…</span>
    </div>
  );
}

function EstadoVacio({ titulo, texto }: { titulo: string; texto: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1.5 bg-superficie-alta px-6 text-center">
      <p className="font-display text-sm font-semibold text-hueso">{titulo}</p>
      <p className="max-w-xs text-xs text-hueso-atenuado">{texto}</p>
    </div>
  );
}

/** Texto del contador de negocios -- se lee distinto con 1 que con varios, y es la señal
 * de que esto es una plataforma con muchos negocios asociados, no un demo de un solo
 * punto en el mapa. Escala igual con 1 que con 200: nunca enumera negocios acá, solo
 * cuenta -- la leyenda de abajo hace lo mismo (conteo por nivel, no lista por nombre). */
function textoContador(cantidad: number): string {
  if (cantidad === 1) return "1 negocio activo ahora";
  return `${cantidad} negocios activos ahora`;
}

export function MapaNegocios() {
  const { data, isLoading, isError } = useNegociosPublicos();

  const ubicables = useMemo<NegocioUbicable[]>(() => (data ?? []).filter(esUbicable), [data]);

  const conteoPorNivel = useMemo(() => {
    const conteo: Record<NivelOcupacion, number> = {
      libre: 0,
      moderado: 0,
      saturado: 0,
      sin_datos: 0,
    };
    for (const negocio of ubicables) {
      conteo[calcularNivelOcupacion(negocio)] += 1;
    }
    return conteo;
  }, [ubicables]);

  return (
    <div className="rounded-2xl border border-borde bg-superficie shadow-[0_20px_60px_-30px_rgba(0,0,0,0.8)]">
      <div className="border-b border-borde/60 px-4 py-3.5 sm:px-5">
        <EncabezadoEnVivo titulo="Mapa en vivo — negocios asociados" />
      </div>
      {!isLoading && !isError && ubicables.length > 0 && (
        <p className="border-b border-borde/60 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.12em] text-hueso-atenuado sm:px-5">
          {textoContador(ubicables.length)}
        </p>
      )}

      <div className="relative h-[22rem] overflow-hidden rounded-b-2xl sm:h-[26rem]">
        {isLoading ? (
          <IndicadorDeCarga />
        ) : isError ? (
          <EstadoVacio
            titulo="No pudimos cargar el mapa"
            texto="Reintenta en unos segundos -- el resto de Barberus sigue funcionando normal."
          />
        ) : ubicables.length === 0 ? (
          <EstadoVacio
            titulo="Todavía no hay negocios visibles en el mapa"
            texto="En cuanto un negocio asociado cargue su ubicación, aparece acá en vivo."
          />
        ) : (
          <>
            <div className="mapa-negocios relative h-full w-full">
              <MapaLeaflet negocios={ubicables} />
            </div>
            <div className="pointer-events-none absolute bottom-3 left-3 z-[400] flex max-w-[calc(100%-1.5rem)] flex-wrap gap-x-3 gap-y-1 rounded-xl border border-borde/70 bg-carbon/85 px-3 py-2 backdrop-blur">
              {NIVELES_LEYENDA.map((nivel) => (
                <span
                  key={nivel}
                  className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-hueso-atenuado"
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${CLASE_PUNTO_NIVEL[nivel]}`}
                    aria-hidden
                  />
                  {ETIQUETA_NIVEL_OCUPACION[nivel]}
                  <span className="tabular-nums text-hueso/70">{conteoPorNivel[nivel]}</span>
                </span>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
