import type { Metadata } from "next";
import { Bricolage_Grotesque, Inter, JetBrains_Mono } from "next/font/google";
import { ProveedorAplicacion } from "@/compartido/proveedores/proveedor-aplicacion";
import "./globals.css";

const bricolage = Bricolage_Grotesque({
  variable: "--font-bricolage",
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Barberus — negocios de belleza, sin fila de pie",
  description:
    "Barberus conecta a barberías, salones de uñas y otros negocios de belleza y cuidado personal con sus clientes: agenda en 30 segundos y fila en vivo, para que nadie espere de pie adivinando su turno.",
};

export default function LayoutRaiz({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="es"
      className={`${bricolage.variable} ${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-carbon text-hueso">
        <ProveedorAplicacion>{children}</ProveedorAplicacion>
      </body>
    </html>
  );
}
