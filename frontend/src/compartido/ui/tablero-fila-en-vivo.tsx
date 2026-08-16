"use client";

/**
 * Recreación tipo "tablero de salidas" (split-flap) de cómo se ve la fila en vivo de un
 * negocio asociado -- la pieza central del hero con parallax (`HeroLanding`), que la usa
 * como capa de primer plano. Es un MOCK decorativo con datos inventados para la landing,
 * no la implementación real del contexto `fila` (que no existe todavía) -- cuando se
 * construya `contextos/fila/`, esta pieza probablemente se reemplace por la versión
 * conectada a datos reales; por eso vive en `compartido/ui/`, no en un contexto.
 *
 * Respeta `prefers-reduced-motion`: si el usuario lo pide, se congela en un estado fijo
 * en vez de ciclar posiciones.
 */
import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { clsx } from "clsx";

interface TurnoFila {
  id: string;
  numero: string;
  cliente: string;
  profesional: string;
  estado: "en_corte" | "proximo" | "espera";
}

const ESTADOS: Record<TurnoFila["estado"], { etiqueta: string; color: string }> = {
  en_corte: { etiqueta: "EN CORTE", color: "text-laton-suave" },
  proximo: { etiqueta: "PRÓXIMO", color: "text-senal-texto" },
  espera: { etiqueta: "EN ESPERA", color: "text-hueso-atenuado" },
};

const TANDAS: TurnoFila[][] = [
  [
    { id: "a", numero: "04", cliente: "Camilo R.", profesional: "Andrés", estado: "en_corte" },
    { id: "b", numero: "05", cliente: "Diego M.", profesional: "Julián", estado: "proximo" },
    { id: "c", numero: "06", cliente: "Sara P.", profesional: "Andrés", estado: "espera" },
    { id: "d", numero: "07", cliente: "León G.", profesional: "Julián", estado: "espera" },
  ],
  [
    { id: "b", numero: "05", cliente: "Diego M.", profesional: "Julián", estado: "en_corte" },
    { id: "c", numero: "06", cliente: "Sara P.", profesional: "Andrés", estado: "proximo" },
    { id: "d", numero: "07", cliente: "León G.", profesional: "Julián", estado: "espera" },
    { id: "e", numero: "08", cliente: "Vale T.", profesional: "Andrés", estado: "espera" },
  ],
  [
    { id: "c", numero: "06", cliente: "Sara P.", profesional: "Andrés", estado: "en_corte" },
    { id: "d", numero: "07", cliente: "León G.", profesional: "Julián", estado: "proximo" },
    { id: "e", numero: "08", cliente: "Vale T.", profesional: "Andrés", estado: "espera" },
    { id: "f", numero: "09", cliente: "Iván C.", profesional: "Julián", estado: "espera" },
  ],
];

export function TableroFilaEnVivo() {
  const prefiereMenosMovimiento = useReducedMotion();
  const [indiceTanda, setIndiceTanda] = useState(0);

  useEffect(() => {
    if (prefiereMenosMovimiento) return;
    const intervalo = setInterval(() => {
      setIndiceTanda((actual) => (actual + 1) % TANDAS.length);
    }, 3200);
    return () => clearInterval(intervalo);
  }, [prefiereMenosMovimiento]);

  const turnos = TANDAS[indiceTanda];

  return (
    <div className="rounded-2xl border border-borde bg-superficie p-4 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.8)] sm:p-5">
      <div className="mb-4 flex items-center justify-between">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-hueso-atenuado">
          Fila en vivo — Barbería Chapinero
        </p>
        <span className="flex items-center gap-1.5 font-mono text-[11px] text-senal-texto">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-senal opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-senal" />
          </span>
          en directo
        </span>
      </div>

      <ul className="flex flex-col gap-2">
        <AnimatePresence mode="popLayout">
          {turnos.map((turno) => (
            <motion.li
              layout
              key={turno.id}
              initial={{ opacity: 0, y: -12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 12 }}
              transition={{ type: "spring", stiffness: 380, damping: 32 }}
              className={clsx(
                "flex items-center justify-between rounded-lg border px-3 py-2.5",
                turno.estado === "proximo"
                  ? "border-senal/40 bg-senal/[0.07]"
                  : "border-borde bg-superficie-alta",
              )}
            >
              <div className="flex items-center gap-3">
                <span className="font-mono text-lg font-semibold tabular-nums text-hueso">
                  #{turno.numero}
                </span>
                <div className="flex flex-col leading-tight">
                  <span className="text-sm text-hueso">{turno.cliente}</span>
                  <span className="text-xs text-hueso-atenuado">con {turno.profesional}</span>
                </div>
              </div>
              <span
                className={clsx(
                  "font-mono text-[11px] font-medium tracking-[0.1em]",
                  ESTADOS[turno.estado].color,
                )}
              >
                {ESTADOS[turno.estado].etiqueta}
              </span>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
    </div>
  );
}
