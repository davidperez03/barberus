/**
 * Franja de rubros en movimiento continuo -- refuerza que Barberus es una plataforma para
 * MÚLTIPLES tipos de negocio asociado (barberías, salones de uñas, spas...), no una cadena
 * de barberías propia. Server component puro (sin hooks): la animación es CSS
 * (`@keyframes marquee` en `globals.css`), que se pausa sola bajo `prefers-reduced-motion`
 * vía media query -- no necesita JS ni "use client".
 *
 * `items` es contenido de dominio provisto por quien la use (ver `app/page.tsx`), así que
 * el componente en sí queda genérico y reusable.
 */
export function MarqueeCategorias({ items }: { items: string[] }) {
  // Se duplica la lista para lograr un loop continuo sin salto visible.
  const pista = [...items, ...items];

  return (
    <div
      role="presentation"
      aria-hidden
      className="group relative overflow-hidden border-y border-borde/60 bg-superficie/60 py-3"
    >
      <div className="animate-marquee flex w-max gap-10 group-hover:[animation-play-state:paused]">
        {pista.map((item, indice) => (
          <span
            key={`${item}-${indice}`}
            className="flex items-center gap-10 font-mono text-xs uppercase tracking-[0.22em] text-hueso-atenuado"
          >
            {item}
            <span className="text-laton">✦</span>
          </span>
        ))}
      </div>
    </div>
  );
}
