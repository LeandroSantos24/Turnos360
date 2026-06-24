/**
 * Ítems adicionales de un turno (perfilado, productos...).
 * Refleja los endpoints del backend: GET/POST/DELETE /turnos/{id}/items.
 */

import { api } from "./api";

export interface ItemTurno {
  id: number;
  turno_id: number;
  descripcion: string;
  precio: number;
  cantidad: number;
  tipo: string;
  creado_en: string;
}

export interface ItemCrear {
  descripcion: string;
  precio: number;
  cantidad?: number;
  tipo?: string;
}

export function listarItems(turnoId: number): Promise<ItemTurno[]> {
  return api.get<ItemTurno[]>(`/turnos/${turnoId}/items`);
}

export function agregarItem(turnoId: number, datos: ItemCrear): Promise<ItemTurno> {
  return api.post<ItemTurno>(`/turnos/${turnoId}/items`, datos);
}

export function quitarItem(turnoId: number, itemId: number): Promise<void> {
  return api.delete<void>(`/turnos/${turnoId}/items/${itemId}`);
}