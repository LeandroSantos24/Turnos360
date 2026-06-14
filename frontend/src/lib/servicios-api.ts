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
  precio: number | null;
  activo: boolean;
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
  precio?: number;
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