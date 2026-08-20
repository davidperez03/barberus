/**
 * Tipos puros del contexto `identidad`. Reflejan el contrato real de
 * `api/contextos/identidad/interfaces/esquemas.py` -- sin React, sin fetch, sin Next.
 * Se reusan desde `aplicacion/` (hooks) e `infraestructura/` (cliente HTTP) para que
 * ambas capas hablen el mismo idioma de dominio sin acoplarse entre sí.
 *
 * Estos son tipos de DOMINIO (camelCase, forma que usa el resto del frontend), no la
 * forma cruda del JSON que viaja por HTTP -- para eso, `infraestructura/` usa los tipos
 * generados en `src/compartido/tipos-api/openapi.d.ts` (`pnpm generar-tipos-api`) como
 * fuente de verdad y los mapea acá. `RolIdentidad` es la excepción: el backend expone
 * `rol` como `str` plano en `ContextoIdentidadRespuesta` (no como enum en el schema
 * Pydantic), así que OpenAPI no puede generar la unión de literales -- se mantiene escrita
 * a mano, sincronizada con `contextos.identidad.dominio.objetos_valor.Rol` del backend.
 */

/** Body de `POST /identidad/registro` e `/identidad/iniciar-sesion`. */
export interface Credenciales {
  correo: string;
  contrasena: string;
}

/**
 * Tokens de sesión devueltos por Supabase Auth vía el backend, cuando hay sesión
 * inmediata (login siempre; registro solo si el proyecto no exige confirmación de correo).
 */
export interface DatosSesionAuth {
  tokenAcceso: string;
  tokenActualizacion: string;
  usuarioId: string;
  expiraAt: string;
}

/** Roles posibles que puede resolver `/identidad/contexto`. */
export type RolIdentidad =
  | "cliente"
  | "profesional"
  | "dueno_sede"
  | "administrador_plataforma";

export interface SesionIdentidad {
  id: string;
  nivelAutenticacion: string;
  expiraAt: string;
  activa: boolean;
}

/** Respuesta de `GET /identidad/contexto` -- "quién soy, con qué rol, en qué tenant". */
export interface ContextoIdentidad {
  usuarioId: string;
  correo: string | null;
  tenantId: string | null;
  rol: RolIdentidad;
  sesion: SesionIdentidad | null;
}

/**
 * Resultado del caso de uso "registrar cuenta". `estado` distingue las dos formas en que
 * el backend responde éxito, sin filtrar el detalle anti-enumeración a la UI:
 *
 * - `sesion_inmediata`: hubo `access_token` de una (201) -- proyecto sin confirmación de
 *   correo obligatoria.
 * - `pendiente_confirmacion`: el backend respondió 202 con mensaje genérico (204/pending
 *   confirm) -- la UI SIEMPRE debe mostrar el mismo mensaje sin importar si el correo era
 *   nuevo o ya existía (ver `dominio.excepciones.RegistroSinSesionInmediata` del backend).
 */
export type ResultadoRegistro =
  | { estado: "sesion_inmediata"; sesion: DatosSesionAuth }
  | { estado: "pendiente_confirmacion"; mensaje: string };

/** Códigos de error de dominio que puede producir la infraestructura de identidad. */
export type CodigoErrorIdentidad =
  | "credenciales_invalidas"
  | "solicitud_invalida"
  | "sin_rol_asignado"
  | "tenant_ambiguo"
  | "tenant_no_autorizado"
  | "token_invalido"
  | "sesion_expirada"
  | "sesion_cerrada"
  | "desconocido";

/** Error de dominio -- nunca se propaga un `Response`/`Error` crudo de fetch más allá de
 * `infraestructura/`. */
export class ErrorIdentidad extends Error {
  readonly codigo: CodigoErrorIdentidad;

  constructor(codigo: CodigoErrorIdentidad, mensaje: string) {
    super(mensaje);
    this.name = "ErrorIdentidad";
    this.codigo = codigo;
  }
}
