"use client";

/**
 * Estado "con sesión iniciada": resuelve `/identidad/contexto` y maneja con gracia el
 * caso `sin_rol_asignado` (403) -- esperado hoy para cualquier cuenta nueva, porque el
 * rol `cliente` recién se autoasigna en la primera reserva (funcionalidad que no existe
 * todavía). No es un error catastrófico, es un estado más del producto.
 */
import { motion } from "framer-motion";
import { useContextoIdentidad } from "@/contextos/identidad/aplicacion/use-contexto-identidad";
import { useCerrarSesion } from "@/contextos/identidad/aplicacion/use-cerrar-sesion";
import { Boton } from "@/compartido/ui/boton";

const ETIQUETA_ROL: Record<string, string> = {
  cliente: "Cliente",
  profesional: "Profesional",
  dueno_sede: "Dueño de negocio",
  administrador_plataforma: "Administrador de plataforma",
};

export function PanelSesion() {
  const { data: contexto, isLoading, sinRolAsignado, error } = useContextoIdentidad();
  const cerrarSesion = useCerrarSesion();

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-borde bg-superficie p-6 sm:p-7"
    >
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-hueso-atenuado">
        Tu cuenta
      </p>

      {isLoading ? (
        <p className="mt-3 text-sm text-hueso-atenuado">Verificando tu cuenta…</p>
      ) : sinRolAsignado ? (
        <div className="mt-3 flex flex-col gap-2">
          <p className="text-sm text-hueso">
            Tu cuenta está creada y activa. Todavía no tiene un rol asignado en ningún
            negocio asociado.
          </p>
          <p className="text-xs text-hueso-atenuado">
            Esto es normal: el acceso como cliente se activa con tu primer turno agendado
            — la agenda llega en una próxima entrega de Barberus.
          </p>
        </div>
      ) : error ? (
        <p className="mt-3 text-sm text-senal-texto">
          No pudimos verificar tu cuenta ahora mismo. Intenta más tarde.
        </p>
      ) : contexto ? (
        <div className="mt-3 flex flex-col gap-1">
          <p className="text-lg font-semibold text-hueso">
            Hola, {contexto.correo ?? "de nuevo"}.
          </p>
          <p className="text-sm text-hueso-atenuado">
            Rol: {ETIQUETA_ROL[contexto.rol] ?? contexto.rol}
          </p>
        </div>
      ) : null}

      <Boton variante="fantasma" className="mt-5" onClick={cerrarSesion}>
        Cerrar sesión
      </Boton>
    </motion.div>
  );
}
