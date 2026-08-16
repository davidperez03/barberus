"use client";

/**
 * Pantalla completa de "Crear cuenta" -- ruta propia (`app/registro/page.tsx`), separada
 * de "Entrar". Orquesta `useRegistro`; distingue con gracia `sesion_inmediata` (redirige)
 * de `pendiente_confirmacion` (se queda en la pantalla con el mensaje anti-enumeración,
 * igual sin importar si el correo era nuevo o ya existía -- ver `dominio/tipos.ts`).
 */
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { PantallaPartida } from "@/compartido/ui/pantalla-partida";
import { FormularioCredenciales } from "@/contextos/identidad/ui/formulario-credenciales";
import { AvisoMutacion } from "@/contextos/identidad/ui/aviso-mutacion";
import { useRegistro } from "@/contextos/identidad/aplicacion/use-registro";

export function PantallaRegistro() {
  const router = useRouter();
  const mutacionRegistro = useRegistro();

  const tieneSesionInmediata =
    mutacionRegistro.isSuccess && mutacionRegistro.data?.estado === "sesion_inmediata";

  useEffect(() => {
    if (!tieneSesionInmediata) return;
    const temporizador = setTimeout(() => router.push("/"), 700);
    return () => clearTimeout(temporizador);
  }, [tieneSesionInmediata, router]);

  return (
    <PantallaPartida
      numeroTicket="Nº02"
      tituloMarca="Tu turno empieza aquí."
      copyMarca="Crea tu cuenta Barberus una sola vez. Después de esto, entrar a la agenda y a la fila en vivo de cualquier negocio asociado toma segundos."
    >
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-hueso-atenuado">
        Nuevo en Barberus
      </p>
      <h2 className="mt-2 font-display text-2xl font-bold text-hueso sm:text-3xl">
        Crea tu cuenta
      </h2>

      <div className="mt-6">
        <FormularioCredenciales
          modo="crear"
          enviando={mutacionRegistro.isPending}
          deshabilitado={mutacionRegistro.isSuccess}
          alEnviar={(datos) => mutacionRegistro.mutate(datos)}
        />
      </div>

      <AvisoMutacion
        error={mutacionRegistro.isError ? mutacionRegistro.error : null}
        mensajeExito={
          mutacionRegistro.isSuccess
            ? tieneSesionInmediata
              ? "Cuenta creada. Un momento…"
              : "Si el correo es válido, revisa tu bandeja para confirmar la cuenta."
            : null
        }
      />

      <p className="mt-6 text-sm text-hueso-atenuado">
        ¿Ya tienes cuenta?{" "}
        <Link
          href="/iniciar-sesion"
          className="text-laton-suave underline-offset-4 hover:underline"
        >
          Entra
        </Link>
      </p>
    </PantallaPartida>
  );
}
