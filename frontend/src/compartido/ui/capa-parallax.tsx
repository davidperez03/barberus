"use client";

/**
 * Primitiva de profundidad reutilizable: desplaza su contenido a una fracción de la
 * velocidad real de scroll del contenedor que se le indique, produciendo parallax de
 * verdad (capas que se mueven a distinto ritmo), no un efecto decorativo suelto. Es el
 * mecanismo detrás del elemento firma de la landing (`HeroLanding`) y se reutiliza en el
 * fondo de las pantallas de acceso -- por eso vive en `compartido/ui/`, no en un contexto.
 *
 * Se apaga por completo bajo `prefers-reduced-motion`: en ese caso el contenido queda
 * estático, sin desplazamiento alguno.
 */
import type { RefObject } from "react";
import { motion, useScroll, useTransform, useReducedMotion } from "framer-motion";

interface CapaParallaxProps {
  /** Contenedor cuyo avance de scroll gobierna el desplazamiento de esta capa. */
  contenedorRef: RefObject<HTMLElement | null>;
  /** Recorrido vertical de la capa mientras el contenedor pasa por el viewport. */
  rango?: [string, string];
  /** Verdadero para capas puramente decorativas (numerales, franjas) sin valor semántico. */
  decorativa?: boolean;
  className?: string;
  children?: React.ReactNode;
}

export function CapaParallax({
  contenedorRef,
  rango = ["0%", "18%"],
  decorativa = false,
  className,
  children,
}: CapaParallaxProps) {
  const prefiereMenosMovimiento = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: contenedorRef,
    offset: ["start start", "end start"],
  });
  const y = useTransform(scrollYProgress, [0, 1], rango);

  return (
    <motion.div
      aria-hidden={decorativa || undefined}
      className={className}
      style={prefiereMenosMovimiento ? undefined : { y }}
    >
      {children}
    </motion.div>
  );
}
