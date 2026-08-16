/**
 * Andamiaje de pantalla completa dividida en dos: panel de marca (izquierda en desktop,
 * arriba en mobile) + panel de contenido. Genérico y sin lógica de negocio -- lo usan las
 * pantallas de acceso del contexto `identidad` (login y registro YA NO son pestañas dentro
 * de una tarjeta, son rutas propias) pero cualquier flujo de pantalla completa futuro
 * (ej. onboarding de un negocio nuevo) lo puede reutilizar.
 *
 * Server component: el numeral de marca "respira" con una animación CSS ambiente
 * (`animate-flotar-ambiente`, definida en `globals.css`), sin JS ni scroll -- las
 * pantallas de acceso son cortas, así que un parallax de scroll real no tendría suficiente
 * recorrido para notarse; esta es la elección de diseño para esa superficie, distinta a la
 * del hero de la landing (que sí tiene el recorrido para un parallax de verdad).
 */
import Link from "next/link";

export function PantallaPartida({
  numeroTicket,
  tituloMarca,
  copyMarca,
  children,
}: {
  numeroTicket: string;
  tituloMarca: React.ReactNode;
  copyMarca: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="relative flex min-h-[38svh] flex-col justify-between overflow-hidden border-b border-borde/60 bg-superficie px-6 py-8 sm:px-10 sm:py-10 lg:min-h-svh lg:border-b-0 lg:border-r">
        <span
          aria-hidden
          className="animate-flotar-ambiente pointer-events-none absolute -right-8 top-6 select-none font-mono text-[7rem] font-semibold leading-none text-laton/[0.12] sm:text-[9rem] lg:-right-4 lg:top-16 lg:text-[11rem]"
        >
          {numeroTicket}
        </span>

        <Link
          href="/"
          className="relative w-fit font-display text-base font-bold tracking-tight text-hueso transition-colors hover:text-laton-suave"
        >
          BARBERUS
        </Link>

        <div className="relative flex max-w-sm flex-col gap-3">
          <h1 className="font-display text-2xl font-bold leading-tight text-hueso sm:text-3xl">
            {tituloMarca}
          </h1>
          <p className="text-sm text-hueso-atenuado">{copyMarca}</p>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-10 sm:px-10 sm:py-14">
        <div className="w-full max-w-sm">{children}</div>
      </div>
    </div>
  );
}
