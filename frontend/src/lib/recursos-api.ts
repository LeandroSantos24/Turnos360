/**
 * Llamadas a la API para recursos (lo reservable: persona/box/equipo).
 * Espejo de los endpoints GET/POST/PATCH/DELETE /recursos.
 */

import { api } from "./api";

/** Los tres tipos de recurso (coincide con el enum TipoRecurso del backend). */
export type TipoRecurso = "persona" | "box" | "equipo";

export interface EspecialidadEmbebida {
  id: number;
  nombre: string;
}

export interface Recurso {
  id: number;
  empresa_id: number;
  nombre: string;
  tipo: TipoRecurso;
  color: string | null;
  sucursal_id: number | null;
  usuario_id: number | null;
  activo: boolean;
  especialidades: EspecialidadEmbebida[];
}

export interface RecursosPagina {
  total: number;
  items: Recurso[];
}

export interface RecursoCrear {
  nombre: string;
  tipo: TipoRecurso;
  color?: string;
}

export function listarRecursos(): Promise<RecursosPagina> {
  return api.get<RecursosPagina>("/recursos");
}

export function crearRecurso(datos: RecursoCrear): Promise<Recurso> {
  return api.post<Recurso>("/recursos", datos);
}

export function desactivarRecurso(id: number): Promise<void> {
  return api.delete<void>(`/recursos/${id}`);
}