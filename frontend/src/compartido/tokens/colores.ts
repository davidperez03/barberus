/**
 * Paleta de marca de Barberus.
 *
 * Deliberadamente NO es "fondo crema + serif + terracota" ni "negro + verde ácido":
 * base petróleo/carbón (no negro puro), acento latón (más cálido y menos manido que
 * terracota) reservado para marca/CTA, y un rojo de poste de barbería (`senal`) que SOLO
 * se usa para el estado "en vivo" de la fila -- nunca decorativo.
 *
 * Estos valores son la fuente de verdad; `globals.css` los expone como variables CSS
 * (`@theme`) para que Tailwind genere utilidades (`bg-carbon`, `text-laton`, etc).
 * Vive en `compartido/` porque no es lógica de negocio de ningún contexto -- es diseño.
 */
export const colores = {
  carbon: "#12181A",
  superficie: "#1B2326",
  superficieAlta: "#232C2F",
  hueso: "#F2EDE4",
  huesoAtenuado: "#96A0A3",
  laton: "#C08A3E",
  latonSuave: "#D9A75C",
  senal: "#D64545", // fondos/bordes/punto "en vivo" -- no usar como color de texto pequeño (falla AA)
  senalTexto: "#E26B6B", // misma familia, aclarado para pasar 4.5:1 sobre `carbon` cuando es texto
  musgo: "#4F7A5B",
  borde: "#2C3538",
} as const;

export type TokenColor = keyof typeof colores;
