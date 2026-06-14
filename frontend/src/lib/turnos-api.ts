/**
 * Llamadas a la API para turnos.
 * Para la agenda usamos el listado filtrado por recurso y rango de fechas.
 */

import { api } from "./api";

export type EstadoTurno =
  | "pendiente"
  | "confirmado"
  | "en_curso"
  | "finalizado"
  | "cancelado"
  | "ausente";

export interface Turno {
  id: number;
  empresa_id: number;
  cliente_id: number;
  recurso_id: number;
  servicio_id: number | null;
  estado: EstadoTurno;
  fecha_inicio: string | null;
  fecha_fin: string | null;
  es_sobreturno: boolean;
  importe_previsto: number | null;
  notas: string | null;
  cliente_nombre: string | null;
  recurso_nombre: string | null;
  servicio_nombre: string | null;
}

export interface TurnosPagina {
  total: number;
  items: Turno[];
}

/**
 * Lista los turnos de un recurso en un rango de fechas (un día, normalmente).
 * desde/hasta en formato ISO (ej: "2026-06-16T00:00:00Z").
 */
export function listarTurnos(
  recursoId: number,
  desde: string,
  hasta: string,
): Promise<TurnosPagina> {
  const params = new URLSearchParams({
    recurso_id: String(recursoId),
    desde,
    hasta,
  });
  return api.get<TurnosPagina>(`/turnos?${params.toString()}`);
}