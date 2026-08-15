"use client";

/**
 * Punto de entrada público de `identidad/ui`: decide entre el formulario de acceso y el
 * panel de sesión ya iniciada. Es lo único que `app/page.tsx` importa de este contexto --
 * el cascarón de `app/` no sabe (ni debe saber) cómo se resuelve esa decisión.
 *
 * La lectura del token se hace en `useEffect` (no en el render inicial) a propósito: el
 * almacén de sesión vive en `document.cookie`, que no existe durante el render de
 * servidor -- evita el mismatch de hidratación de leerlo directo en el cuerpo del
 * componente.
 */
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  EVENTO_CAMBIO_SESION,
  almacenSesion,
} from "@/contextos/identidad/infraestructura/instancias";
import { FormularioAcceso } from "@/contextos/identidad/ui/formulario-acceso";
import { PanelSesion } from "@/contextos/identidad/ui/panel-sesion";

export function TarjetaIdentidad() {
  const [haySesion, setHaySesion] = useState<boolean | null>(null);

  useEffect(() => {
    const actualizar = () => setHaySesion(Boolean(almacenSesion.obtenerAccessToken()));
    actualizar();
    window.addEventListener(EVENTO_CAMBIO_SESION, actualizar);
    return () => window.removeEventListener(EVENTO_CAMBIO_SESION, actualizar);
  }, []);

  if (haySesion === null) {
    return (
      <div className="h-[21rem] animate-pulse rounded-2xl border border-borde bg-superficie" />
    );
  }

  return (
    <AnimatePresence mode="wait">
      {haySesion ? (
        <motion.div key="panel" exit={{ opacity: 0 }}>
          <PanelSesion />
        </motion.div>
      ) : (
        <motion.div key="formulario" exit={{ opacity: 0 }}>
          <FormularioAcceso />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
