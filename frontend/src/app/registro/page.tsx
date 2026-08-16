/**
 * Ruta `/registro`. Cascarón: solo compone `PantallaRegistro` de `contextos/identidad/ui/`
 * -- sin `useState`, sin fetch propio, sin lógica de negocio.
 */
import type { Metadata } from "next";
import { PantallaRegistro } from "@/contextos/identidad/ui/pantalla-registro";

export const metadata: Metadata = {
  title: "Crear cuenta — Barberus",
  description: "Crea tu cuenta Barberus: una sola cuenta para cualquier negocio asociado.",
};

export default function PaginaRegistro() {
  return <PantallaRegistro />;
}
