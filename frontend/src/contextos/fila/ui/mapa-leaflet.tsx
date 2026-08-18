"use client";

/**
 * Adaptador visual real de Leaflet -- el único archivo del contexto `fila` que importa
 * `leaflet`/`react-leaflet` y toca el DOM del mapa directamente. Vive separado de
 * `mapa-negocios.tsx` porque Leaflet depende de `window` (no soporta SSR): se carga con
 * `next/dynamic` y `ssr: false` desde ahí.
 *
 * Tiles: CARTO "dark_all" (gratuitos, sin API key, subdominio `basemaps.cartocdn.com`) --
 * NO son los tiles claros de OpenStreetMap recoloreados con un `filter` CSS. Un tile
 * genuinamente diseñado para fondo oscuro tiene contraste y jerarquía tipográfica propios
 * (vías, parques, agua ya pensados para verse bien en negro); invertir/rotar el matiz de
 * un tile claro con CSS (lo que había antes) se nota -- se ve "instagram sobre Google
 * Maps", no un mapa oscuro de verdad. Sigue siendo data de OpenStreetMap, solo la
 * renderiza CARTO. Atribución obligatoria a ambos.
 *
 * Elemento firma: cada negocio es un marcador propio (no el pin por defecto de Leaflet)
 * que "late" con el mismo lenguaje visual que el indicador "en directo" del tablero de
 * fila del hero (`TableroFilaEnVivo`) -- el mapa no es un directorio estático, es el pulso
 * real de la plataforma ahora mismo. Cuando un negocio tiene gente esperando, el número
 * aparece como badge sobre el propio marcador -- se lee el dato clave sin abrir el popup,
 * como en una herramienta de operación real, no un directorio de puntos genéricos.
 */
import "leaflet/dist/leaflet.css";
import { useEffect } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import {
  calcularNivelOcupacion,
  ETIQUETA_NIVEL_OCUPACION,
  type NivelOcupacion,
} from "@/contextos/fila/dominio/semaforo";
import {
  CLASE_CHIP_NIVEL,
  CLASE_PUNTO_NIVEL,
  VARIABLE_CSS_SUPERFICIE_NIVEL,
} from "@/contextos/fila/ui/token-por-nivel";
import type { NegocioUbicable } from "@/contextos/fila/dominio/tipos";

const CENTRO_COLOMBIA: [number, number] = [4.5709, -74.2973];
const ZOOM_COLOMBIA = 5.2;

const TAMANO_ICONO = 30;

function crearIcono(nivel: NivelOcupacion, personasEnFila: number): L.DivIcon {
  const pulsa = nivel !== "sin_datos";
  const mostrarBadge = personasEnFila > 0;
  return L.divIcon({
    className: "",
    html: `
      <span class="marcador-negocio" style="--color-marcador:${VARIABLE_CSS_SUPERFICIE_NIVEL[nivel]}">
        ${pulsa ? '<span class="marcador-negocio__pulso" aria-hidden="true"></span>' : ""}
        <span class="marcador-negocio__nucleo"></span>
        ${mostrarBadge ? `<span class="marcador-negocio__badge">${Math.min(personasEnFila, 99)}</span>` : ""}
      </span>
    `,
    iconSize: [TAMANO_ICONO, TAMANO_ICONO],
    iconAnchor: [TAMANO_ICONO / 2, TAMANO_ICONO / 2],
    popupAnchor: [0, -TAMANO_ICONO / 2 - 4],
  });
}

/** Centra/ajusta el zoom para que todos los negocios ubicables queden visibles -- no un
 * centro fijo arbitrario cuando ya sabemos dónde están. */
function AjustarLimites({ negocios }: { negocios: NegocioUbicable[] }) {
  const mapa = useMap();

  useEffect(() => {
    if (negocios.length === 0) return;
    if (negocios.length === 1) {
      mapa.setView([negocios[0].latitud, negocios[0].longitud], 13);
      return;
    }
    const limites = L.latLngBounds(
      negocios.map((negocio) => [negocio.latitud, negocio.longitud] as [number, number]),
    );
    mapa.fitBounds(limites, { padding: [32, 32], maxZoom: 14 });
  }, [mapa, negocios]);

  return null;
}

export default function MapaLeaflet({ negocios }: { negocios: NegocioUbicable[] }) {
  return (
    <MapContainer
      center={CENTRO_COLOMBIA}
      zoom={ZOOM_COLOMBIA}
      scrollWheelZoom={false}
      className="h-full w-full"
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        subdomains="abcd"
        maxZoom={20}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
      />
      <AjustarLimites negocios={negocios} />
      {negocios.map((negocio) => {
        const nivel = calcularNivelOcupacion(negocio);
        return (
          <Marker
            key={negocio.tenantId}
            position={[negocio.latitud, negocio.longitud]}
            icon={crearIcono(nivel, negocio.personasEnFila)}
          >
            <Popup minWidth={200} maxWidth={240}>
              <div className="font-body">
                <p className="font-display text-sm font-semibold text-hueso">
                  {negocio.nombreSede}
                </p>
                <p className="mt-1.5 text-xs text-hueso-atenuado">
                  <strong className="font-mono text-hueso">{negocio.personasEnFila}</strong>{" "}
                  {negocio.personasEnFila === 1 ? "persona en fila" : "personas en fila"}
                </p>
                <p className="mt-0.5 text-xs text-hueso-atenuado">
                  {negocio.tiempoEsperaEstimadoMinutos !== null
                    ? `~${negocio.tiempoEsperaEstimadoMinutos} min de espera`
                    : "Sin estimado de espera todavía"}
                </p>
                <span
                  className={`mt-2 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.08em] ${CLASE_CHIP_NIVEL[nivel]}`}
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${CLASE_PUNTO_NIVEL[nivel]}`} aria-hidden />
                  {ETIQUETA_NIVEL_OCUPACION[nivel]}
                </span>
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
