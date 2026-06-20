/**
 * Llamadas a la API para los horarios de atención de un recurso (barbero).
 * Cada franja es una fila independiente: un día puede tener varias
 * (ej. 9–13 y 16–20 para el corte de mediodía).
 * Espejo de /recursos/{id}/horarios (GET / POST / DELETE).
 */

import { api } from "./api";

/** Una franja de atención semanal. Las horas vienen como "HH:MM:SS". */
export interface Horario {
  id: number;
  recurso_id: number;
  dia_semana: number; // 0=lunes … 6=domingo
  hora_desde: string;
  hora_hasta: string;
  vigencia_desde: string | null;
  vigencia_hasta: string | null;
}

/** Datos para crear una franja. La vigencia la dejamos para más adelante. */
export interface HorarioCrear {
  dia_semana: number;
  hora_desde: string; // "HH:MM" alcanza, el backend lo acepta
  hora_hasta: string;
}

export function listarHorarios(recursoId: number): Promise<Horario[]> {
  return api.get<Horario[]>(`/recursos/${recursoId}/horarios`);
}

export function agregarHorario(
  recursoId: number,
  datos: HorarioCrear,
): Promise<Horario> {
  return api.post<Horario>(`/recursos/${recursoId}/horarios`, datos);
}

export function eliminarHorario(
  recursoId: number,
  horarioId: number,
): Promise<void> {
  return api.delete<void>(`/recursos/${recursoId}/horarios/${horarioId}`);
}