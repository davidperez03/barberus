"use client";

/**
 * Banner de error/éxito para las mutaciones de identidad (login/registro). Encapsula el
 * `AnimatePresence` + los dos estilos de aviso (`senal` para error, `musgo` para éxito) que
 * se repetían byte a byte entre `pantalla-iniciar-sesion.tsx` y `pantalla-registro.tsx`.
 */
import { AnimatePresence, motion } from "framer-motion";
import { mensajeErrorIdentidad } from "@/contextos/identidad/ui/mensaje-error";

interface AvisoMutacionProps {
  error: unknown;
  mensajeExito: React.ReactNode | null;
}

export function AvisoMutacion({ error, mensajeExito }: AvisoMutacionProps) {
  return (
    <AnimatePresence>
      {error ? (
        <motion.p
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          role="alert"
          className="mt-3 rounded-lg border border-senal/40 bg-senal/[0.08] px-3 py-2 text-sm text-hueso"
        >
          {mensajeErrorIdentidad(error)}
        </motion.p>
      ) : null}
      {mensajeExito ? (
        <motion.p
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className="mt-3 rounded-lg border border-musgo/40 bg-musgo/[0.1] px-3 py-2 text-sm text-hueso"
        >
          {mensajeExito}
        </motion.p>
      ) : null}
    </AnimatePresence>
  );
}
