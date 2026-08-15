/**
 * Landing de Barberus. Cascarón: solo compone piezas de `compartido/ui/` y de
 * `contextos/identidad/ui/` -- sin `useState`, sin fetch propio, sin lógica de negocio.
 * `agenda`/`fila` no existen todavía como contextos; esta página los INSINÚA (texto +
 * el mock del tablero en vivo) sin implementarlos, como pide el alcance de este PR.
 */
import { TarjetaIdentidad } from "@/contextos/identidad/ui/tarjeta-identidad";
import { TableroFilaEnVivo } from "@/compartido/ui/tablero-fila-en-vivo";
import { AparicionEscalonada, AparicionItem } from "@/compartido/ui/aparicion-escalonada";

const RAZONES = [
  {
    titulo: "Reserva en 30 segundos",
    texto: "Tu cliente agenda desde el celular, sin llamadas ni ida y vuelta por WhatsApp.",
  },
  {
    titulo: "Fila visible en vivo",
    texto: "Nadie hace fila de pie adivinando cuánto falta: el tablero se actualiza solo.",
  },
  {
    titulo: "Guía visual del corte",
    texto: "Antes/después de cada servicio, para que el cliente vuelva sabiendo qué pedir.",
  },
];

export default function PaginaPrincipal() {
  return (
    <>
      <header className="sticky top-0 z-20 border-b border-borde/60 bg-carbon/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <span className="font-display text-lg font-bold tracking-tight text-hueso">
            BARBERUS
          </span>
          <a
            href="#acceso"
            className="rounded-full border border-borde px-4 py-2 text-sm text-hueso transition-colors hover:border-laton-suave hover:text-laton-suave"
          >
            Entrar
          </a>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-6xl px-5 pt-14 pb-16 sm:px-8 sm:pt-20">
          <div className="grid gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:gap-16">
            <AparicionEscalonada className="flex flex-col items-start gap-6">
              <AparicionItem>
                <p className="font-mono text-xs uppercase tracking-[0.2em] text-laton-suave">
                  Software para barberías multi-sede
                </p>
              </AparicionItem>
              <AparicionItem>
                <h1 className="font-display text-4xl font-bold leading-[1.05] text-hueso sm:text-5xl lg:text-[3.4rem]">
                  Tu barbería, <span className="text-laton">sin fila de pie</span>.
                </h1>
              </AparicionItem>
              <AparicionItem>
                <p className="max-w-md text-base text-hueso-atenuado sm:text-lg">
                  Barberus conecta la agenda de tu sede con la fila en vivo: tus clientes
                  ven su turno en tiempo real y tú reduces los no-shows.
                </p>
              </AparicionItem>
              <AparicionItem className="flex flex-wrap gap-3 pt-2">
                <a
                  href="#acceso"
                  className="inline-flex items-center justify-center rounded-full bg-laton px-6 py-3 text-sm font-semibold text-carbon transition-colors hover:bg-laton-suave"
                >
                  Crear cuenta gratis
                </a>
                <a
                  href="#como-funciona"
                  className="inline-flex items-center justify-center rounded-full border border-borde px-6 py-3 text-sm text-hueso transition-colors hover:border-laton-suave hover:text-laton-suave"
                >
                  Ver cómo funciona
                </a>
              </AparicionItem>
            </AparicionEscalonada>

            <div className="lg:pl-4">
              <TableroFilaEnVivo />
              <p className="mt-3 text-center font-mono text-[11px] text-hueso-atenuado lg:text-left">
                así se ve la fila de una sede en tiempo real
              </p>
            </div>
          </div>
        </section>

        <section id="como-funciona" className="border-y border-borde/60 bg-superficie/40">
          <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8">
            <h2 className="font-display text-2xl font-bold text-hueso sm:text-3xl">
              Todo lo que hace perder clientes a una barbería, resuelto.
            </h2>
            <div className="mt-10 grid gap-6 sm:grid-cols-3">
              {RAZONES.map((razon) => (
                <div
                  key={razon.titulo}
                  className="rounded-2xl border border-borde bg-superficie p-6"
                >
                  <h3 className="font-display text-lg font-semibold text-hueso">
                    {razon.titulo}
                  </h3>
                  <p className="mt-2 text-sm text-hueso-atenuado">{razon.texto}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="acceso" className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-20">
          <div className="mx-auto max-w-md">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-laton-suave">
              Empieza ahora
            </p>
            <h2 className="mt-2 font-display text-2xl font-bold text-hueso sm:text-3xl">
              Entra o crea tu cuenta
            </h2>
            <p className="mt-2 text-sm text-hueso-atenuado">
              Una cuenta te sirve para cualquier sede Barberus. La agenda y la fila en
              vivo llegan en la próxima entrega.
            </p>
            <div className="mt-7">
              <TarjetaIdentidad />
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-borde/60">
        <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
          <p className="font-mono text-[11px] text-hueso-atenuado">
            Barberus — hecho para barberías que no quieren perder clientes en la fila.
          </p>
        </div>
      </footer>
    </>
  );
}
