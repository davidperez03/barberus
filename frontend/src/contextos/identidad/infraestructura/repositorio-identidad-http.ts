/**
 * Único adaptador de `identidad` que hace `fetch` real. Implementa el puerto
 * `RepositorioIdentidad` (`aplicacion/puertos.ts`) contra los 3 endpoints reales de
 * `api/contextos/identidad/interfaces/router.py`. `aplicacion/` (hooks) nunca construye
 * una URL ni lee un `Response` directamente -- solo llama a estos métodos.
 *
 * La forma "cruda" del JSON que viaja por HTTP (`DatosSesionAuthCruda`/
 * `ContextoIdentidadCrudo` más abajo) NO se escribe a mano: son alias de los tipos que
 * genera `pnpm generar-tipos-api` a partir del OpenAPI schema real de FastAPI (ver
 * `src/compartido/tipos-api/openapi.d.ts` y `frontend/README.md`). Así, si un esquema
 * Pydantic del backend cambia de forma (renombra un campo, agrega uno requerido), este
 * archivo deja de compilar en vez de fallar en runtime con un `undefined` silencioso.
 */
import type { RepositorioIdentidad } from "@/contextos/identidad/aplicacion/puertos";
import type {
  SchemaContextoIdentidadRespuesta,
  SchemaDatosSesionAuthRespuesta,
} from "@/compartido/tipos-api/openapi";
import {
  ErrorIdentidad,
  type CodigoErrorIdentidad,
  type ContextoIdentidad,
  type Credenciales,
  type DatosSesionAuth,
  type ResultadoRegistro,
  type RolIdentidad,
} from "@/contextos/identidad/dominio/tipos";

const URL_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Alias del tipo generado -- ver el comentario de archivo para el porqué. */
type DatosSesionAuthCruda = SchemaDatosSesionAuthRespuesta;

/** Alias del tipo generado -- ver el comentario de archivo para el porqué. */
type ContextoIdentidadCrudo = SchemaContextoIdentidadRespuesta;

function mapearSesion(cruda: DatosSesionAuthCruda): DatosSesionAuth {
  return {
    tokenAcceso: cruda.token_acceso,
    tokenActualizacion: cruda.token_actualizacion,
    usuarioId: cruda.usuario_id,
    expiraAt: cruda.expira_at,
  };
}

function mapearContexto(crudo: ContextoIdentidadCrudo): ContextoIdentidad {
  return {
    usuarioId: crudo.usuario_id,
    correo: crudo.correo,
    tenantId: crudo.tenant_id,
    rol: crudo.rol as RolIdentidad,
    sesion: crudo.sesion
      ? {
          id: crudo.sesion.id,
          nivelAutenticacion: crudo.sesion.nivel_autenticacion,
          expiraAt: crudo.sesion.expira_at,
          activa: crudo.sesion.activa,
        }
      : null,
  };
}

async function extraerDetalle(respuesta: Response): Promise<string> {
  try {
    const cuerpo = (await respuesta.json()) as { detail?: string };
    return cuerpo.detail ?? respuesta.statusText;
  } catch {
    return respuesta.statusText || "Error de red desconocido.";
  }
}

function codigoDesde403(detalle: string): CodigoErrorIdentidad {
  if (detalle.includes("TenantAmbiguo")) return "tenant_ambiguo";
  if (detalle.includes("TenantNoAutorizado")) return "tenant_no_autorizado";
  if (detalle.includes("SesionExpirada")) return "sesion_expirada";
  if (detalle.includes("SesionCerrada")) return "sesion_cerrada";
  return "sin_rol_asignado";
}

export class RepositorioIdentidadHttp implements RepositorioIdentidad {
  async registrar(credenciales: Credenciales): Promise<ResultadoRegistro> {
    const respuesta = await fetch(`${URL_BASE}/identidad/registro`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credenciales),
    });

    if (respuesta.status === 201 || respuesta.status === 200) {
      const cruda = (await respuesta.json()) as DatosSesionAuthCruda;
      return { estado: "sesion_inmediata", sesion: mapearSesion(cruda) };
    }

    if (respuesta.status === 202) {
      const mensaje = await extraerDetalle(respuesta);
      return { estado: "pendiente_confirmacion", mensaje };
    }

    if (respuesta.status === 400) {
      throw new ErrorIdentidad("solicitud_invalida", await extraerDetalle(respuesta));
    }

    throw new ErrorIdentidad("desconocido", await extraerDetalle(respuesta));
  }

  async iniciarSesion(credenciales: Credenciales): Promise<DatosSesionAuth> {
    const respuesta = await fetch(`${URL_BASE}/identidad/iniciar-sesion`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credenciales),
    });

    if (respuesta.ok) {
      const cruda = (await respuesta.json()) as DatosSesionAuthCruda;
      return mapearSesion(cruda);
    }

    if (respuesta.status === 401) {
      throw new ErrorIdentidad("credenciales_invalidas", await extraerDetalle(respuesta));
    }
    if (respuesta.status === 400) {
      throw new ErrorIdentidad("solicitud_invalida", await extraerDetalle(respuesta));
    }
    throw new ErrorIdentidad("desconocido", await extraerDetalle(respuesta));
  }

  async obtenerContexto(accessToken: string, tenantId?: string): Promise<ContextoIdentidad> {
    const cabeceras: Record<string, string> = { Authorization: `Bearer ${accessToken}` };
    if (tenantId) cabeceras["X-Tenant-Id"] = tenantId;

    const respuesta = await fetch(`${URL_BASE}/identidad/contexto`, {
      method: "GET",
      headers: cabeceras,
    });

    if (respuesta.ok) {
      const crudo = (await respuesta.json()) as ContextoIdentidadCrudo;
      return mapearContexto(crudo);
    }

    if (respuesta.status === 401) {
      throw new ErrorIdentidad("token_invalido", await extraerDetalle(respuesta));
    }
    if (respuesta.status === 403) {
      const detalle = await extraerDetalle(respuesta);
      throw new ErrorIdentidad(codigoDesde403(detalle), detalle);
    }
    throw new ErrorIdentidad("desconocido", await extraerDetalle(respuesta));
  }
}
