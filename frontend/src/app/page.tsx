/**
 * Landing de Barberus. Cascarón: solo compone piezas de `compartido/ui/` y de
 * `contextos/identidad/ui/` -- sin `useState`, sin fetch propio, sin lógica de negocio.
 * `agenda`/`fila` no existen todavía como contextos; esta página los INSINÚA (texto +
 * el mock del tablero en vivo) sin implementarlos, como pide el alcance de este PR.
 *
 * Barberus es una plataforma intermediaria entre negocios de belleza/cuidado personal
 * INDEPENDIENTES (barberías, salones de uñas, spas...) y sus clientes -- no una cadena
 * dueña de "sucursales" propias. El copy de esta página lo refleja: "negocio asociado",
 * nunca "sede Barberus".
 */
import Link from "next/link";
import { SeccionAcceso } from "@/contextos/identidad/ui/seccion-acceso";
import { HeroLanding } from "@/compartido/ui/hero-landing";
import { MarqueeCategorias } from "@/compartido/ui/marquee-categorias";
import { RevelaAlHacerScroll } from "@/compartido/ui/revela-al-hacer-scroll";

const CATEGORIAS = [
  "Barberías",
  "Salones de uñas",
  "Spas",
  "Centros de estética",
  "Peluquerías",
  "Barbershops",
];

const PASOS = [
  {
    numero: "01",
    titulo: "Reserva en 30 segundos",
    texto:
      "Tu cliente agenda desde el celular con cualquier negocio asociado, sin llamadas ni ida y vuelta por WhatsApp.",
  },
  {
    numero: "02",
    titulo: "Fila visible en vivo",
    texto:
      "Nadie hace fila de pie adivinando cuánto falta: el tablero de cada negocio se actualiza solo.",
  },
  {
    numero: "03",
    titulo: "Guía visual del resultado",
    texto:
      "Antes/después de cada servicio -- corte, manicura, tratamiento -- para que el cliente vuelva sabiendo qué pedir.",
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
          <nav className="flex items-center gap-3">
            <Link
              href="/iniciar-sesion"
              className="rounded-full border border-borde px-4 py-2 text-sm text-hueso transition-colors hover:border-laton-suave hover:text-laton-suave"
            >
              Entrar
            </Link>
            <Link
              href="/registro"
              className="rounded-full bg-laton px-4 py-2 text-sm font-semibold text-carbon transition-colors hover:bg-laton-suave"
            >
              Crear cuenta
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <HeroLanding
          kicker="Barberías · salones de uñas · spas — una sola plataforma"
          titulo={
            <>
              Cero fila de pie, en <span className="text-laton">cualquier negocio</span>{" "}
              asociado.
            </>
          }
          subtitulo="Barberus conecta a tus clientes con la agenda y la fila en vivo de tu negocio, sin importar el rubro. Ellos ven su turno en tiempo real, tú reduces los no-shows."
          ctaPrimario={{ href: "/registro", texto: "Crear cuenta gratis" }}
          ctaSecundario={{ href: "#como-funciona", texto: "Ver cómo funciona" }}
        />

        <MarqueeCategorias items={CATEGORIAS} />

        <section id="como-funciona" className="bg-superficie/40">
          <div className="mx-auto max-w-3xl px-5 py-16 sm:px-8 sm:py-24">
            <RevelaAlHacerScroll>
              <h2 className="font-display text-2xl font-bold text-hueso sm:text-3xl">
                Todo lo que hace perder clientes a un negocio de belleza, resuelto.
              </h2>
            </RevelaAlHacerScroll>

            <ol className="mt-12 flex flex-col">
              {PASOS.map((paso, indice) => (
                <RevelaAlHacerScroll key={paso.numero} retraso={indice * 0.08}>
                  <li className="flex gap-5 border-t border-borde/60 py-7 first:border-t-0 sm:gap-8 sm:py-9">
                    <span className="font-mono text-sm text-laton-suave sm:text-base">
                      {paso.numero}
                    </span>
                    <div>
                      <h3 className="font-display text-lg font-semibold text-hueso sm:text-xl">
                        {paso.titulo}
                      </h3>
                      <p className="mt-2 max-w-lg text-sm text-hueso-atenuado sm:text-base">
                        {paso.texto}
                      </p>
                    </div>
                  </li>
                </RevelaAlHacerScroll>
              ))}
            </ol>
          </div>
        </section>

        <section id="acceso" className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-20">
          <div className="mx-auto max-w-xl">
            <RevelaAlHacerScroll>
              <p className="font-mono text-xs uppercase tracking-[0.2em] text-laton-suave">
                Empieza ahora
              </p>
              <h2 className="mt-2 font-display text-2xl font-bold text-hueso sm:text-3xl">
                Entra o crea tu cuenta
              </h2>
              <p className="mt-2 text-sm text-hueso-atenuado">
                Una cuenta te sirve para cualquier negocio asociado a Barberus. La agenda y
                la fila en vivo llegan completas en la próxima entrega.
              </p>
            </RevelaAlHacerScroll>
            <div className="mt-7">
              <SeccionAcceso />
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-borde/60">
        <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
          <p className="font-mono text-[11px] text-hueso-atenuado">
            Barberus — la plataforma que conecta negocios de belleza y cuidado personal con
            sus clientes, sin fila de pie.
          </p>
        </div>
      </footer>
    </>
  );
}
