import { api } from "./api";

export interface MetodoTotal {
  metodo: string;
  total: number;
}
export interface ProfesionalTotal {
  recurso: string;
  total: number;
  turnos: number;
  ticket: number;
  pct: number;
}
export interface DiaTotal {
  fecha: string;
  total: number;
}
export interface EstadosResumen {
  finalizados: number;
  cancelados: number;
  ausentes: number;
  tasa_ausentismo: number;
}
export interface ServicioTotal {
  servicio: string;
  cantidad: number;
  total: number;
}
export interface HoraTotal {
  hora: number;
  cantidad: number;
}
export interface OrigenTotal {
  /** turno | abono | giftcard */
  origen: string;
  etiqueta: string;
  total: number;
  cantidad: number;
}
export interface CuponRendimiento {
  codigo: string;
  tipo: string;
  valor: number;
  activo: boolean;
  vence_el: string | null;
  max_usos: number | null;
  /** Turnos que usaron el código. */
  usos: number;
  /** Clientes DISTINTOS que lo usaron (no es lo mismo que usos). */
  personas: number;
  facturado: number;
  descuento_otorgado: number;
  finalizados: number;
  cancelados: number;
  ausentes: number;
  /** Finalizados ÷ usos, en %. */
  tasa_concrecion: number;
}
export interface CuponesResumen {
  usos: number;
  personas: number;
  facturado: number;
  descuento_otorgado: number;
}
export interface EstadisticasFacturacion {
  facturado_real: number;
  facturado_anterior: number;
  variacion_pct: number | null;
  comision_total: number;
  neto: number;
  cantidad_pagos: number;
  ticket_promedio: number;
  por_metodo: MetodoTotal[];
  por_profesional: ProfesionalTotal[];
  por_dia: DiaTotal[];
  estados: EstadosResumen;
  por_servicio: ServicioTotal[];
  por_hora: HoraTotal[];
  por_origen: OrigenTotal[];
  /** Solo la atención. Es la base del ticket promedio. */
  facturado_turnos: number;
  por_cupon: CuponRendimiento[];
  cupones_resumen: CuponesResumen;
}

export function obtenerFacturacion(
  desde: string,
  hasta: string,
  recursoId?: number | null,
): Promise<EstadisticasFacturacion> {
  const p = new URLSearchParams({ desde, hasta });
  if (recursoId != null) p.set("recurso_id", String(recursoId));
  return api.get<EstadisticasFacturacion>(
    `/estadisticas/facturacion?${p.toString()}`,
  );
}