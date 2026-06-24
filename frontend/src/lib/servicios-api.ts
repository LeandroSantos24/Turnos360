/**
 * Llamadas a la API para servicios (lo que ofrece cada negocio).
 * Espejo de los endpoints GET/POST/PATCH/DELETE /servicios.
 */

import { api } from "./api";

export interface Servicio {
  id: number;
  empresa_id: number;
  nombre: string;
  duracion_min: number;
  buffer_min: number;
  paso_turno_min: number;
  grupo_agenda: string | null;
  precio: number | null;
  activo: boolean;
  agendable: boolean;
}

export interface ServiciosPagina {
  total: number;
  items: Servicio[];
}

export interface ServicioCrear {
  nombre: string;
  duracion_min: number;
  buffer_min?: number;
  paso_turno_min?: number;
  grupo_agenda?: string | null;
  precio?: number;
  agendable?: boolean;
}

export function listarServicios(): Promise<ServiciosPagina> {
  return api.get<ServiciosPagina>("/servicios");
}

export function crearServicio(datos: ServicioCrear): Promise<Servicio> {
  return api.post<Servicio>("/servicios", datos);
}

export function desactivarServicio(id: number): Promise<void> {
  return api.delete<void>(`/servicios/${id}`);
}

/** Edita un servicio (PATCH). Solo manda los campos que cambian. */
export function editarServicio(
  id: number,
  datos: Partial<ServicioCrear>,
): Promise<Servicio> {
  return api.patch<Servicio>(`/servicios/${id}`, datos);
}

/** Borra (desactiva) un servicio. */
export function borrarServicio(id: number): Promise<void> {
  return api.delete<void>(`/servicios/${id}`);
}