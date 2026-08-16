"use client";

/**
 * Formulario de correo/contraseña puro, sin decidir "entrar" vs "crear cuenta" -- esa
 * decisión ahora es de ruta (`/iniciar-sesion` y `/registro` son pantallas separadas, ver
 * `pantalla-iniciar-sesion.tsx` y `pantalla-registro.tsx`), no de una pestaña dentro de la
 * misma tarjeta. Orquesta validación (`dominio/validacion`) vía `react-hook-form`; no sabe
 * nada de `fetch` ni de cómo se guarda el token.
 */
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Campo } from "@/compartido/ui/campo";
import { Boton } from "@/compartido/ui/boton";
import {
  esquemaCredenciales,
  type CredencialesFormulario,
} from "@/contextos/identidad/dominio/validacion";

export function FormularioCredenciales({
  modo,
  alEnviar,
  enviando,
  deshabilitado = false,
}: {
  modo: "entrar" | "crear";
  alEnviar: (datos: CredencialesFormulario) => void;
  enviando: boolean;
  deshabilitado?: boolean;
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
        disabled={deshabilitado}
        {...register("correo")}
      />
      <Campo
        etiqueta="Contraseña"
        type="password"
        autoComplete={modo === "entrar" ? "current-password" : "new-password"}
        placeholder="mínimo 8 caracteres"
        error={errors.contrasena?.message}
        disabled={deshabilitado}
        {...register("contrasena")}
      />
      <Boton type="submit" cargando={enviando} disabled={deshabilitado} className="mt-1 w-full">
        {modo === "entrar" ? "Entrar" : "Crear cuenta"}
      </Boton>
    </form>
  );
}
