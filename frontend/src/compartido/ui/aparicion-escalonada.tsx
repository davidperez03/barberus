"use client";

/**
 * Orquesta la secuencia de entrada del hero (aparición escalonada) -- el tipo de
 * micro-interacción "orquestada" que pesa más que animaciones sueltas. Respeta
 * `prefers-reduced-motion` vía `useReducedMotion` de framer-motion (desactiva el
 * desplazamiento, deja solo un fundido corto).
 */
import { motion, useReducedMotion } from "framer-motion";
import { apareceDesdeAbajo, contenedorEscalonado } from "@/compartido/animacion/variantes";

export function AparicionEscalonada({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const prefiereMenosMovimiento = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial="oculto"
      animate="visible"
      variants={prefiereMenosMovimiento ? undefined : contenedorEscalonado}
    >
      {children}
    </motion.div>
  );
}

export function AparicionItem({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const prefiereMenosMovimiento = useReducedMotion();
  return (
    <motion.div
      className={className}
      variants={prefiereMenosMovimiento ? undefined : apareceDesdeAbajo}
    >
      {children}
    </motion.div>
  );
}
