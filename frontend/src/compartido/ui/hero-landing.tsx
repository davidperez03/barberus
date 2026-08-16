"use client";

/**
 * Elemento firma de la landing: hero con profundidad real (parallax de scroll, ver
 * `CapaParallax`), no un hero de texto-izquierda/tarjeta-derecha estático. Tres capas se
 * mueven a distinto ritmo mientras el usuario hace scroll: el numeral de ticket gigante
 * (fondo, el más lento), la franja diagonal tipo poste de barbería (fondo, sentido
 * contrario) y el tablero de fila en vivo (primer plano, el más rápido) -- la misma
 * metáfora de "número de turno" que usa `TableroFilaEnVivo`, así el parallax no es
 * decoración suelta sino parte del lenguaje visual del producto.
 *
 * Vive en `compartido/ui/` (no en un contexto) porque es contenido de marketing puro,
 * parametrizado por props -- `app/page.tsx` sigue siendo cascarón, solo le pasa textos.
 */
import { useRef } from "react";
import Link from "next/link";
import { CapaParallax } from "@/compartido/ui/capa-parallax";
import { AparicionEscalonada, AparicionItem } from "@/compartido/ui/aparicion-escalonada";
import { TableroFilaEnVivo } from "@/compartido/ui/tablero-fila-en-vivo";

interface EnlaceCta {
  href: string;
  texto: string;
}

interface HeroLandingProps {
  kicker: string;
  titulo: React.ReactNode;
  subtitulo: string;
  ctaPrimario: EnlaceCta;
  ctaSecundario: EnlaceCta;
}

export function HeroLanding({
  kicker,
  titulo,
  subtitulo,
  ctaPrimario,
  ctaSecundario,
}: HeroLandingProps) {
  const heroRef = useRef<HTMLElement | null>(null);

  return (
    <section
      ref={heroRef}
      className="relative overflow-hidden pb-20 pt-14 sm:pb-28 sm:pt-20"
    >
      {/* Capa 1 (fondo, la más lenta): numeral de ticket -- misma tipografía de datos que
          usan los números de turno reales del tablero. */}
      <CapaParallax
        contenedorRef={heroRef}
        rango={["0%", "24%"]}
        decorativa
        className="pointer-events-none absolute -top-10 -right-6 select-none font-mono text-[8rem] font-semibold leading-none text-laton/[0.09] sm:-top-16 sm:-right-10 sm:text-[13rem] lg:text-[17rem]"
      >
        Nº07
      </CapaParallax>

      {/* Capa 2 (fondo, sentido contrario): franja diagonal tipo poste de barbería. */}
      <CapaParallax
        contenedorRef={heroRef}
        rango={["2%", "-16%"]}
        decorativa
        className="pointer-events-none absolute inset-x-[-10%] bottom-[-3rem] h-28 -rotate-3 bg-[repeating-linear-gradient(135deg,var(--color-senal)_0px,var(--color-senal)_3px,transparent_3px,transparent_22px)] opacity-[0.07] sm:h-36"
      />

      <div className="relative mx-auto max-w-6xl px-5 sm:px-8">
        <div className="grid gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:gap-16">
          <AparicionEscalonada className="flex flex-col items-start gap-6">
            <AparicionItem>
              <p className="font-mono text-xs uppercase tracking-[0.2em] text-laton-suave">
                {kicker}
              </p>
            </AparicionItem>
            <AparicionItem>
              <h1 className="font-display text-4xl font-bold leading-[1.05] text-hueso sm:text-5xl lg:text-[3.4rem]">
                {titulo}
              </h1>
            </AparicionItem>
            <AparicionItem>
              <p className="max-w-md text-base text-hueso-atenuado sm:text-lg">{subtitulo}</p>
            </AparicionItem>
            <AparicionItem className="flex flex-wrap gap-3 pt-2">
              <Link
                href={ctaPrimario.href}
                className="inline-flex items-center justify-center rounded-full bg-laton px-6 py-3 text-sm font-semibold text-carbon transition-colors hover:bg-laton-suave"
              >
                {ctaPrimario.texto}
              </Link>
              <Link
                href={ctaSecundario.href}
                className="inline-flex items-center justify-center rounded-full border border-borde px-6 py-3 text-sm text-hueso transition-colors hover:border-laton-suave hover:text-laton-suave"
              >
                {ctaSecundario.texto}
              </Link>
            </AparicionItem>
          </AparicionEscalonada>

          {/* Capa 3 (primer plano, la más rápida): el tablero real de la fila en vivo. */}
          <CapaParallax contenedorRef={heroRef} rango={["5%", "-11%"]} className="lg:pl-4">
            <TableroFilaEnVivo />
            <p className="mt-3 text-center font-mono text-[11px] text-hueso-atenuado lg:text-left">
              así se ve la fila de un negocio asociado, en tiempo real
            </p>
          </CapaParallax>
        </div>
      </div>
    </section>
  );
}
