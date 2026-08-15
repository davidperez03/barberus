"use client";

/**
 * Formulario de acceso (entrar / crear cuenta) del contexto `identidad`. Orquesta los
 * hooks de caso de uso de `aplicacion/` -- no sabe nada de `fetch` ni de cómo se guarda
 * el token, eso vive en `infraestructura/`.
 */
import { useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AnimatePresence, motion } from "framer-motion";
import { clsx } from "clsx";
import { Campo } from "@/compartido/ui/campo";
import { Boton } from "@/compartido/ui/boton";
import { useIniciarSesion } from "@/contextos/identidad/aplicacion/use-iniciar-sesion";
import { useRegistro } from "@/contextos/identidad/aplicacion/use-registro";
import {
  esquemaCredenciales,
  type CredencialesFormulario,
} from "@/contextos/identidad/dominio/validacion";
import { ErrorIdentidad } from "@/contextos/identidad/dominio/tipos";

function mensajeError(error: unknown): string {
  if (error instanceof ErrorIdentidad) return error.message;
  return "No pudimos conectar con el servidor. Intenta de nuevo.";
}

function FormularioCredenciales({
  modo,
  alEnviar,
  enviando,
}: {
  modo: "entrar" | "crear";
  alEnviar: (datos: CredencialesFormulario) => void;
  enviando: boolean;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CredencialesFormulario>({
    resolver: zodResolver(esquemaCredenciales),
    mode: "onBlur",
  });

  return (
    <form onSubmit={handleSubmit(alEnviar)} className="flex flex-col gap-4" noValidate>
      <Campo
        etiqueta="Correo"
        type="email"
        autoComplete="email"
        placeholder="tu@correo.com"
        error={errors.correo?.message}
        {...register("correo")}
      />
      <Campo
        etiqueta="Contraseña"
        type="password"
        autoComplete={modo === "entrar" ? "current-password" : "new-password"}
        placeholder="mínimo 8 caracteres"
        error={errors.contrasena?.message}
        {...register("contrasena")}
      />
      <Boton type="submit" cargando={enviando} className="mt-1 w-full">
        {modo === "entrar" ? "Entrar" : "Crear cuenta"}
      </Boton>
    </form>
  );
}

export function FormularioAcceso() {
  const [pestana, setPestana] = useState<"entrar" | "crear">("entrar");

  const mutacionLogin = useIniciarSesion();
  const mutacionRegistro = useRegistro();

  return (
    <div className="rounded-2xl border border-borde bg-superficie p-6 sm:p-7">
      <Tabs.Root
        value={pestana}
        onValueChange={(valor) => setPestana(valor as "entrar" | "crear")}
      >
        <Tabs.List className="mb-6 flex gap-1 rounded-full border border-borde bg-carbon p-1">
          {(["entrar", "crear"] as const).map((valor) => (
            <Tabs.Trigger
              key={valor}
              value={valor}
              className={clsx(
                "flex-1 rounded-full py-2 text-sm font-medium transition-colors",
                "data-[state=active]:bg-laton data-[state=active]:text-carbon",
                "data-[state=inactive]:text-hueso-atenuado data-[state=inactive]:hover:text-hueso",
              )}
            >
              {valor === "entrar" ? "Entrar" : "Crear cuenta"}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="entrar" tabIndex={-1}>
          <FormularioCredenciales
            modo="entrar"
            enviando={mutacionLogin.isPending}
            alEnviar={(datos) => mutacionLogin.mutate(datos)}
          />
          <AnimatePresence>
            {mutacionLogin.isError ? (
              <motion.p
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                role="alert"
                className="mt-3 rounded-lg border border-senal/40 bg-senal/[0.08] px-3 py-2 text-sm text-hueso"
              >
                {mensajeError(mutacionLogin.error)}
              </motion.p>
            ) : null}
            {mutacionLogin.isSuccess ? (
              <motion.p
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 rounded-lg border border-musgo/40 bg-musgo/[0.1] px-3 py-2 text-sm text-hueso"
              >
                Sesión iniciada. Un momento…
              </motion.p>
            ) : null}
          </AnimatePresence>
        </Tabs.Content>

        <Tabs.Content value="crear" tabIndex={-1}>
          <FormularioCredenciales
            modo="crear"
            enviando={mutacionRegistro.isPending}
            alEnviar={(datos) => mutacionRegistro.mutate(datos)}
          />
          <AnimatePresence>
            {mutacionRegistro.isError ? (
              <motion.p
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                role="alert"
                className="mt-3 rounded-lg border border-senal/40 bg-senal/[0.08] px-3 py-2 text-sm text-hueso"
              >
                {mensajeError(mutacionRegistro.error)}
              </motion.p>
            ) : null}
            {mutacionRegistro.isSuccess ? (
              <motion.p
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 rounded-lg border border-musgo/40 bg-musgo/[0.1] px-3 py-2 text-sm text-hueso"
              >
                {mutacionRegistro.data?.estado === "sesion_inmediata"
                  ? "Cuenta creada. Un momento…"
                  : /* Mismo mensaje sin importar si el correo era nuevo o ya existía --
                       anti-enumeración, igual que hace el backend. */
                    "Si el correo es válido, revisa tu bandeja para confirmar la cuenta."}
              </motion.p>
            ) : null}
          </AnimatePresence>
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
