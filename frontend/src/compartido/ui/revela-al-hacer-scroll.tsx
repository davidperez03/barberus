"use client";

/**
 * Revela su contenido con un fundido + ascenso corto cuando entra al viewport (no al
 * montar, como `AparicionEscalonada`) -- pensado para secciones bajo el pliegue, como la
 * lista de "cómo funciona". Se ejecuta una sola vez (`viewport.once`) para no repetir la
 * animación cada vez que el usuario sube y baja. Respeta `prefers-reduced-motion`.
 */
import { motion, useReducedMotion } from "framer-motion";

export function RevelaAlHacerScroll({
  children,
  className,
  retraso = 0,
}: {
  children: React.ReactNode;
  className?: string;
  retraso?: number;
}) {
  const prefiereMenosMovimiento = useReducedMotion();

  if (prefiereMenosMovimiento) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 22 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.55, delay: retraso, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
