/**
 * Llamadas a la API para recursos (lo reservable: persona/box/equipo).
 * Espejo de los endpoints GET/POST/PATCH/DELETE /recursos.
 */

import { api } from "./api";

/** Los tres tipos de recurso (coincide con el enum TipoRecurso del backend). */
export type TipoRecurso = "persona" | "box" | "equipo";

/** Roles de usuario (coincide con el enum RolUsuario del backend). */
export type Rol = "dueno" | "recepcion" | "profesional" | "admin";

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
  /** Usuario con login que opera este recurso (1-a-1). null = sin vincular. */
  usuario_id?: number | null;
}

/** Un usuario de la empresa que se puede vincular a un recurso. */
export interface UsuarioVinculable {
  id: number;
  nombre: string;
  email: string;
  rol: Rol;
  /** Recurso al que YA está vinculado, si lo hay (para respetar el 1-a-1). */
  recurso_id: number | null;
  recurso_nombre: string | null;
}

export function listarRecursos(): Promise<RecursosPagina> {
  return api.get<RecursosPagina>("/recursos");
}

/** Usuarios de la empresa para el selector "Usuario vinculado" (solo dueño). */
export function listarUsuariosVinculables(): Promise<UsuarioVinculable[]> {
  return api.get<UsuarioVinculable[]>("/recursos/usuarios-disponibles");
}

/** El recurso vinculado al usuario logueado (para "Mi día"). null si no tiene. */
export function miRecurso(): Promise<Recurso | null> {
  return api.get<Recurso | null>("/recursos/mi-recurso");
}

export function crearRecurso(datos: RecursoCrear): Promise<Recurso> {
  return api.post<Recurso>("/recursos", datos);
}

export function desactivarRecurso(id: number): Promise<void> {
  return api.delete<void>(`/recursos/${id}`);
}

/** Edita un recurso (PATCH). */
export function editarRecurso(
  id: number,
  datos: Partial<RecursoCrear>,
): Promise<Recurso> {
  return api.patch<Recurso>(`/recursos/${id}`, datos);
}

/** Borra (desactiva) un recurso. */
export function borrarRecurso(id: number): Promise<void> {
  return api.delete<void>(`/recursos/${id}`);
}

/** Trae un recurso por id (GET /recursos/{id}). */
export function obtenerRecurso(id: number): Promise<Recurso> {
  return api.get<Recurso>(`/recursos/${id}`);
}
