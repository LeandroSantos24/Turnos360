import { api } from "./api";

export interface MetodoTotal {
  metodo: string;
  total: number;
}
export interface ProfesionalTotal {
  recurso: string;
  total: number;
  turnos: number;
}
export interface DiaTotal {
  fecha: string;
  total: number;
}
export interface EstadisticasFacturacion {
  facturado_real: number;
  comision_total: number;
  neto: number;
  cantidad_pagos: number;
  ticket_promedio: number;
  por_metodo: MetodoTotal[];
  por_profesional: ProfesionalTotal[];
  por_dia: DiaTotal[];
}

export function obtenerFacturacion(
  desde: string,
  hasta: string,
): Promise<EstadisticasFacturacion> {
  const p = new URLSearchParams({ desde, hasta });
  return api.get<EstadisticasFacturacion>(
    `/estadisticas/facturacion?${p.toString()}`,
  );
}