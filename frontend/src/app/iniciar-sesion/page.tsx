/**
 * Ruta `/iniciar-sesion`. Cascarón: solo compone `PantallaIniciarSesion` de
 * `contextos/identidad/ui/` -- sin `useState`, sin fetch propio, sin lógica de negocio.
 */
import type { Metadata } from "next";
import { PantallaIniciarSesion } from "@/contextos/identidad/ui/pantalla-iniciar-sesion";

export const metadata: Metadata = {
  title: "Entrar — Barberus",
  description: "Entra a tu cuenta Barberus para acceder a cualquier negocio asociado.",
};

export default function PaginaIniciarSesion() {
  return <PantallaIniciarSesion />;
}
