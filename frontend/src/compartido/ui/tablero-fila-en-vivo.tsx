"use client";

/**
 * Tablero tipo "salidas de aeropuerto" (split-flap) de cómo se ve la fila en vivo de un
 * negocio asociado -- la pieza central del hero con parallax (`HeroLanding`), que la usa
 * como capa de primer plano. Conectado a los mismos datos reales de `GET /fila/publica`
 * que ya consume el mapa de la landing (`useNegociosPublicos`, `contextos/fila/`).
 *
 * El endpoint público es cross-tenant pero nunca expone quién es el cliente en fila --
 * privacidad por diseño (ver `contextos/fila/dominio/tipos.ts`) -- así que el tablero ya
 * no puede simular "Diego M. - con Julián" como antes. En su lugar muestra, por negocio
 * activo: cuántas personas esperan, la espera estimada y el nivel de ocupación (misma
 * regla de negocio que colorea el semáforo del mapa, `dominio/semaforo.ts`). Con un solo
 * negocio activo el tablero queda fijo en sus datos; con varios, cicla entre ellos cada
 * pocos segundos -- la misma mecánica de "tandas" que antes ciclaba entre turnos
 * inventados, ahora entre negocios reales.
 *
 * Respeta `prefers-reduced-motion`: si el usuario lo pide, se congela en el primer negocio
 * en vez de ciclar.
 *
 * Elemento firma real: los números no solo "aparecen", cada dígito gira sobre su propio
 * eje como una ficha física de tablero de salidas de aeropuerto (`NumeroFlap` /
 * `FichaDigito` más abajo) cuando su valor cambia -- al refrescar datos (cada 30s, ver
 * `useNegociosPublicos`) o al ciclar de negocio. Antes el número solo "saltaba" de un
 * valor a otro sin transición propia; ahora la mecánica de la metáfora (split-flap) se
 * cumple de verdad, no solo en el nombre del componente.
 */
import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { clsx } from "clsx";
import { useNegociosPublicos } from "@/contextos/fila/aplicacion/use-negocios-publicos";
import {
  calcularNivelOcupacion,
  ETIQUETA_NIVEL_OCUPACION,
} from "@/contextos/fila/dominio/semaforo";
import { CLASE_CHIP_NIVEL } from "@/contextos/fila/ui/token-por-nivel";
import type { ResumenFilaNegocio } from "@/contextos/fila/dominio/tipos";
import { EncabezadoEnVivo } from "@/compartido/ui/encabezado-en-vivo";

const INTERVALO_CICLO_MS = 4200;

const CHIP_NEUTRO = "border-borde bg-superficie-alta text-hueso-atenuado";

interface FilaTablero {
  id: string;
  numero: string;
  etiqueta: string;
  detalle: string;
  estadoTexto: string;
  estadoClase: string;
  resaltado: boolean;
}

function padDosDigitos(valor: number): string {
  return Math.min(valor, 99).toString().padStart(2, "0");
}

function formatearPersonasEnFila(personasEnFila: number): string {
  if (personasEnFila === 0) return "sin fila ahora mismo";
  if (personasEnFila === 1) return "1 persona esperando";
  return `${personasEnFila} personas esperando`;
}

function filasDeNegocio(negocio: ResumenFilaNegocio): FilaTablero[] {
  const nivel = calcularNivelOcupacion(negocio);
  const { tenantId, nombreSede, personasEnFila, tiempoEsperaEstimadoMinutos } = negocio;

  return [
    {
      id: `${tenantId}-fila`,
      numero: padDosDigitos(personasEnFila),
      etiqueta: nombreSede,
      detalle: formatearPersonasEnFila(personasEnFila),
      estadoTexto: ETIQUETA_NIVEL_OCUPACION[nivel],
      estadoClase: CLASE_CHIP_NIVEL[nivel],
      resaltado: nivel === "saturado",
    },
    {
      id: `${tenantId}-espera`,
      numero: tiempoEsperaEstimadoMinutos === null ? "—" : padDosDigitos(tiempoEsperaEstimadoMinutos),
      etiqueta: "Espera estimada",
      detalle:
        tiempoEsperaEstimadoMinutos === null
          ? "aún sin datos suficientes"
          : "minutos aproximados",
      estadoTexto: "MIN",
      estadoClase: CHIP_NEUTRO,
      resaltado: false,
    },
  ];
}

/** Una ficha del split-flap: un dígito a la vez, cada uno gira sobre su propio eje cuando
 * cambia de valor -- `key={caracter}` es lo que dispara la animación de entrada/salida en
 * `AnimatePresence` solo cuando el carácter realmente cambia, no en cada render. */
function FichaDigito({ caracter, reducirMovimiento }: { caracter: string; reducirMovimiento: boolean }) {
  return (
    <span
      className="relative inline-flex h-8 w-[1.15rem] items-center justify-center overflow-hidden rounded-[4px] border border-borde bg-carbon sm:h-9 sm:w-6"
      style={{ perspective: 240 }}
    >
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={caracter}
          initial={
            reducirMovimiento ? { opacity: 0 } : { rotateX: 100, opacity: 0.4 }
          }
          animate={{ rotateX: 0, opacity: 1 }}
          exit={reducirMovimiento ? { opacity: 0 } : { rotateX: -100, opacity: 0.4 }}
          transition={
            reducirMovimiento
              ? { duration: 0.15 }
              : { duration: 0.36, ease: [0.45, 0, 0.2, 1] }
          }
          className="absolute inset-0 flex items-center justify-center font-mono text-base font-bold tabular-nums text-hueso sm:text-lg"
          style={{ transformOrigin: "50% 50%", backfaceVisibility: "hidden" }}
        >
          {caracter}
        </motion.span>
      </AnimatePresence>
      {/* Línea de bisagra -- el detalle que vende la metáfora de "ficha física". */}
      <span className="pointer-events-none absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-carbon/90" />
    </span>
  );
}

function NumeroFlap({ valor, reducirMovimiento }: { valor: string; reducirMovimiento: boolean }) {
  return (
    <span className="flex gap-[3px]" aria-hidden>
      {valor.split("").map((caracter, indice) => (
        <FichaDigito key={indice} caracter={caracter} reducirMovimiento={reducirMovimiento} />
      ))}
    </span>
  );
}

function EstadoTablero({ texto }: { texto: string }) {
  return (
    <div className="flex h-[168px] flex-col items-center justify-center gap-1 rounded-lg border border-borde bg-superficie-alta px-4 text-center">
      <p className="text-xs text-hueso-atenuado">{texto}</p>
    </div>
  );
}

export function TableroFilaEnVivo() {
  const { data, isLoading, isError } = useNegociosPublicos();
  const prefiereMenosMovimiento = useReducedMotion();
  const [indiceNegocio, setIndiceNegocio] = useState(0);

  const negocios = data ?? [];
  // Si la lista se encoge entre refrescos (ej. un negocio cierra su fila), el índice
  // anterior podría quedar fuera de rango -- se recalcula acá en vez de con un efecto que
  // dispare `setState` en cascada.
  const indiceSeguro = negocios.length === 0 ? 0 : indiceNegocio % negocios.length;

  useEffect(() => {
    if (prefiereMenosMovimiento || negocios.length < 2) return;
    const intervalo = setInterval(() => {
      setIndiceNegocio((actual) => (actual + 1) % negocios.length);
    }, INTERVALO_CICLO_MS);
    return () => clearInterval(intervalo);
  }, [prefiereMenosMovimiento, negocios.length]);

  const negocioActivo = negocios[indiceSeguro];
  const filas = negocioActivo ? filasDeNegocio(negocioActivo) : [];

  return (
    <div className="relative overflow-hidden rounded-2xl border border-borde bg-superficie p-4 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.8)] sm:p-5">
      {/* Bisel superior -- acabado tipo tablero físico, no decoración suelta: marca el
          borde "de vidrio" del panel, igual que un tablero de salidas real tiene un marco
          metálico visible. */}
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-laton/70 via-laton-suave/40 to-transparent"
      />
      <div className="mb-4">
        <EncabezadoEnVivo titulo="Fila en vivo — negocios asociados" />
      </div>

      {isLoading ? (
        <EstadoTablero texto="Cargando la fila de los negocios activos…" />
      ) : isError ? (
        <EstadoTablero texto="No pudimos cargar la fila en vivo -- reintenta en unos segundos." />
      ) : negocios.length === 0 ? (
        <EstadoTablero texto="Ningún negocio asociado tiene fila activa en este momento." />
      ) : (
        <ul className="flex flex-col gap-2">
          <AnimatePresence mode="popLayout">
            {filas.map((fila) => (
              <motion.li
                layout
                key={fila.id}
                initial={{ opacity: 0, y: -12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 12 }}
                transition={{ type: "spring", stiffness: 380, damping: 32 }}
                className={clsx(
                  "flex items-center justify-between rounded-lg border px-3 py-2.5",
                  fila.resaltado
                    ? "border-senal/40 bg-senal/[0.07]"
                    : "border-borde bg-superficie-alta",
                )}
              >
                <div className="flex items-center gap-3">
                  <NumeroFlap valor={fila.numero} reducirMovimiento={!!prefiereMenosMovimiento} />
                  <div className="flex flex-col leading-tight">
                    <span className="text-sm text-hueso">{fila.etiqueta}</span>
                    <span className="text-xs text-hueso-atenuado">{fila.detalle}</span>
                  </div>
                </div>
                <span
                  className={clsx(
                    "shrink-0 rounded-full border px-2 py-0.5 font-mono text-[10px] font-medium tracking-[0.08em]",
                    fila.estadoClase,
                  )}
                >
                  {fila.estadoTexto}
                </span>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}
