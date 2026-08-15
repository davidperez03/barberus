/**
 * Invariantes de negocio del formulario de credenciales, como funciones/esquemas puros
 * (sin React). `zod` es una librería de validación, no de fetch/UI, así que vive acá --
 * `ui/` solo la conecta a `react-hook-form` vía `zodResolver`.
 *
 * El mínimo de 8 caracteres refleja el mínimo real de GoTrue (ver
 * `api/contextos/identidad/interfaces/esquemas.py::CredencialesPeticion`) -- si el
 * backend cambia esa regla, este es el único lugar que hay que tocar en el frontend.
 */
import { z } from "zod";

export const esquemaCorreo = z
  .string()
  .trim()
  .min(1, "Escribe tu correo.")
  .email("Ese correo no parece válido.");

export const esquemaContrasena = z
  .string()
  .min(8, "Mínimo 8 caracteres.");

export const esquemaCredenciales = z.object({
  correo: esquemaCorreo,
  contrasena: esquemaContrasena,
});

export type CredencialesFormulario = z.infer<typeof esquemaCredenciales>;
