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
  cubierto_por_abono: boolean;
  notas: string | null;
  cliente_nombre: string | null;
  recurso_nombre: string | null;
  servicio_nombre: string | null;
  servicio_grupo: string | null;
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

/**
 * Lista TODOS los turnos del día (de todos los recursos), para las métricas.
 * No filtra por recurso: cuenta el total del local.
 */
export function listarTurnosDelDia(
  desde: string,
  hasta: string,
): Promise<TurnosPagina> {
  const params = new URLSearchParams({ desde, hasta });
  return api.get<TurnosPagina>(`/turnos?${params.toString()}`);
}

/** Cambia el estado de un turno (confirmar, cancelar, en curso, etc.). */
export function cambiarEstadoTurno(
  turnoId: number,
  estado: EstadoTurno,
  motivo?: string,
): Promise<Turno> {
  return api.patch<Turno>(`/turnos/${turnoId}/estado`, {
    estado,
    motivo_cancelacion: motivo,
  });
}

/** Lista todos los turnos de un cliente (su historial completo). */
export function listarTurnosDeCliente(clienteId: number): Promise<TurnosPagina> {
  const params = new URLSearchParams({ cliente_id: String(clienteId) });
  return api.get<TurnosPagina>(`/turnos?${params.toString()}`);
}

/** Datos para crear un turno. */
export interface TurnoCrear {
  cliente_id: number;
  servicio_id: number;
  recurso_id: number;
  fecha_inicio: string; // ISO
  es_sobreturno?: boolean;
}

/** Crea un turno. El backend valida disponibilidad (409 si choca). */
export function crearTurno(datos: TurnoCrear): Promise<Turno> {
  return api.post<Turno>("/turnos", datos);
}