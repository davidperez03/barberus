"use client";

/**
 * Input de formulario con etiqueta mono/utilitaria (parte de la identidad tipográfica del
 * sistema: display + body + mono para datos) y estado de error accesible.
 */
import { forwardRef, useId } from "react";
import { clsx } from "clsx";

interface CampoProps extends React.InputHTMLAttributes<HTMLInputElement> {
  etiqueta: string;
  error?: string;
}

export const Campo = forwardRef<HTMLInputElement, CampoProps>(
  ({ etiqueta, error, id, className, ...props }, ref) => {
    const idGenerado = useId();
    const idFinal = id ?? idGenerado;
    const idError = `${idFinal}-error`;

    return (
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor={idFinal}
          className="font-mono text-[11px] uppercase tracking-[0.14em] text-hueso-atenuado"
        >
          {etiqueta}
        </label>
        <input
          ref={ref}
          id={idFinal}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? idError : undefined}
          className={clsx(
            "rounded-lg border bg-superficie px-4 py-3 text-sm text-hueso placeholder:text-hueso-atenuado/70",
            "outline-none transition-colors focus:border-laton-suave",
            error ? "border-senal" : "border-borde",
            className,
          )}
          {...props}
        />
        {error ? (
          <p id={idError} role="alert" className="text-xs text-senal-texto">
            {error}
          </p>
        ) : null}
      </div>
    );
  },
);
Campo.displayName = "Campo";
