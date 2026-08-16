"use client";

/**
 * Punto de entrada público de `identidad/ui` en la landing: decide entre mostrar el panel
 * de sesión ya iniciada o dos tarjetas de acceso que llevan a las pantallas completas de
 * "Entrar" y "Crear cuenta" (`/iniciar-sesion` y `/registro`) -- login y registro dejaron
 * de ser pestañas dentro de una tarjeta embebida. Es lo único que `app/page.tsx` importa de
 * este contexto para esta sección -- el cascarón de `app/` no sabe (ni debe saber) cómo se
 * resuelve esa decisión.
 *
 * La lectura del token se hace en `useEffect` (no en el render inicial) a propósito: el
 * almacén de sesión vive en `document.cookie`, que no existe durante el render de
 * servidor -- evita el mismatch de hidratación de leerlo directo en el cuerpo del
 * componente.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  EVENTO_CAMBIO_SESION,
  almacenSesion,
} from "@/contextos/identidad/infraestructura/instancias";
import { PanelSesion } from "@/contextos/identidad/ui/panel-sesion";

const TARJETAS = [
  {
    href: "/iniciar-sesion",
    numero: "Nº01",
    titulo: "Ya tengo cuenta",
    texto: "Entra con tu correo y contraseña.",
  },
  {
    href: "/registro",
    numero: "Nº02",
    titulo: "Soy nuevo aquí",
    texto: "Crea tu cuenta en menos de un minuto.",
  },
] as const;

export function SeccionAcceso() {
  const [haySesion, setHaySesion] = useState<boolean | null>(null);

  useEffect(() => {
    const actualizar = () => setHaySesion(Boolean(almacenSesion.obtenerAccessToken()));
    actualizar();
    window.addEventListener(EVENTO_CAMBIO_SESION, actualizar);
    return () => window.removeEventListener(EVENTO_CAMBIO_SESION, actualizar);
  }, []);

  if (haySesion === null) {
    return (
      <div className="h-[15rem] animate-pulse rounded-2xl border border-borde bg-superficie" />
    );
  }

  return (
    <AnimatePresence mode="wait">
      {haySesion ? (
        <motion.div key="panel" exit={{ opacity: 0 }}>
          <PanelSesion />
        </motion.div>
      ) : (
        <motion.div
          key="tarjetas"
          exit={{ opacity: 0 }}
          className="grid gap-4 sm:grid-cols-2"
        >
          {TARJETAS.map((tarjeta) => (
            <Link
              key={tarjeta.href}
              href={tarjeta.href}
              className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-borde bg-superficie p-6 transition-colors hover:border-laton-suave"
            >
              <span
                aria-hidden
                className="absolute -right-3 -top-3 font-mono text-5xl font-semibold text-laton/[0.1] transition-colors group-hover:text-laton/[0.18]"
              >
                {tarjeta.numero}
              </span>
              <div>
                <h3 className="font-display text-lg font-semibold text-hueso">
                  {tarjeta.titulo}
                </h3>
                <p className="mt-1 text-sm text-hueso-atenuado">{tarjeta.texto}</p>
              </div>
              <span className="mt-6 inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-[0.16em] text-laton-suave transition-transform group-hover:translate-x-1">
                Continuar →
              </span>
            </Link>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
