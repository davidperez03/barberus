"use client";

/**
 * Pantalla completa de "Entrar" -- ruta propia (`app/iniciar-sesion/page.tsx`), no una
 * pestaña dentro de una tarjeta compartida con el registro. Orquesta el hook de caso de
 * uso `useIniciarSesion`; no sabe nada de `fetch` ni de dónde se guarda el token.
 */
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { PantallaPartida } from "@/compartido/ui/pantalla-partida";
import { FormularioCredenciales } from "@/contextos/identidad/ui/formulario-credenciales";
import { AvisoMutacion } from "@/contextos/identidad/ui/aviso-mutacion";
import { useIniciarSesion } from "@/contextos/identidad/aplicacion/use-iniciar-sesion";

export function PantallaIniciarSesion() {
  const router = useRouter();
  const mutacionLogin = useIniciarSesion();

  useEffect(() => {
    if (!mutacionLogin.isSuccess) return;
    const temporizador = setTimeout(() => router.push("/"), 700);
    return () => clearTimeout(temporizador);
  }, [mutacionLogin.isSuccess, router]);

  return (
    <PantallaPartida
      numeroTicket="Nº01"
      tituloMarca="Una cuenta, cualquier negocio asociado."
      copyMarca="Barberías, salones de uñas y otros negocios de belleza usan Barberus para su agenda y su fila en vivo. Con la misma cuenta entras a cualquiera."
    >
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-hueso-atenuado">
        Bienvenido de nuevo
      </p>
      <h2 className="mt-2 font-display text-2xl font-bold text-hueso sm:text-3xl">
        Entra a tu cuenta
      </h2>

      <div className="mt-6">
        <FormularioCredenciales
          modo="entrar"
          enviando={mutacionLogin.isPending}
          deshabilitado={mutacionLogin.isSuccess}
          alEnviar={(datos) => mutacionLogin.mutate(datos)}
        />
      </div>

      <AvisoMutacion
        error={mutacionLogin.isError ? mutacionLogin.error : null}
        mensajeExito={mutacionLogin.isSuccess ? "Sesión iniciada. Un momento…" : null}
      />

      <p className="mt-6 text-sm text-hueso-atenuado">
        ¿No tienes cuenta todavía?{" "}
        <Link href="/registro" className="text-laton-suave underline-offset-4 hover:underline">
          Crea una
        </Link>
      </p>
    </PantallaPartida>
  );
}
