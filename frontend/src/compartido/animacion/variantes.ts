/**
 * Variantes de framer-motion reutilizables entre contextos. Utilidad transversal, no
 * lógica de negocio -- por eso vive en `compartido/`.
 */
import type { Variants } from "framer-motion";

export const apareceDesdeAbajo: Variants = {
  oculto: { opacity: 0, y: 16 },
  visible: (retraso = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, delay: retraso, ease: [0.22, 1, 0.36, 1] },
  }),
};

export const contenedorEscalonado: Variants = {
  oculto: {},
  visible: {
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
};
