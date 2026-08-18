/**
 * Composición: qué implementación concreta del puerto de `fila` usa la app. Único lugar
 * que lo decide -- mismo criterio que `contextos/identidad/infraestructura/instancias.ts`.
 */
import { RepositorioFilaHttp } from "@/contextos/fila/infraestructura/repositorio-fila-http";

export const repositorioFila = new RepositorioFilaHttp();
