"use client";

/**
 * Botón genérico sin lógica de negocio -- variantes visuales del sistema de diseño.
 * `compartido/` porque cualquier contexto lo puede usar (no es específico de `identidad`).
 */
import { forwardRef } from "react";
import { motion, type HTMLMotionProps } from "framer-motion";
import { clsx } from "clsx";

type Variante = "primario" | "fantasma" | "enlace";

interface BotonProps extends Omit<HTMLMotionProps<"button">, "ref"> {
  variante?: Variante;
  cargando?: boolean;
}

const estilosPorVariante: Record<Variante, string> = {
  primario:
    "bg-laton text-carbon font-semibold hover:bg-laton-suave disabled:opacity-60 disabled:hover:bg-laton",
  fantasma:
    "border border-borde text-hueso hover:border-laton-suave hover:text-laton-suave disabled:opacity-60",
  enlace: "text-laton-suave underline-offset-4 hover:underline px-0",
};

export const Boton = forwardRef<HTMLButtonElement, BotonProps>(
  ({ variante = "primario", cargando = false, className, children, disabled, ...props }, ref) => {
    const esEnlace = variante === "enlace";
    return (
      <motion.button
        ref={ref}
        whileTap={esEnlace ? undefined : { scale: 0.98 }}
        disabled={disabled || cargando}
        className={clsx(
          "inline-flex items-center justify-center gap-2 rounded-full px-6 py-3 text-sm transition-colors",
          "focus-visible:outline-2 focus-visible:outline-laton-suave",
          estilosPorVariante[variante],
          className,
        )}
        {...props}
      >
        {cargando ? (
          <span className="flex items-center gap-2">
            <span
              aria-hidden
              className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
            />
            <span className="font-mono text-xs tracking-wide">procesando…</span>
          </span>
        ) : (
          children
        )}
      </motion.button>
    );
  },
);
Boton.displayName = "Boton";
