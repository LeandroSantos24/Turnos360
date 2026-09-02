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
/** Un local en la comparación. Solo se muestra si el negocio tiene más de uno. */
export interface SucursalResumen {
  sucursal_id: number;
  sucursal: string;
  total: number;
  cantidad_pagos: number;
  turnos: number;
  ticket: number;
  pct: number;
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
  /**
   * Comparación entre locales. Viene con TODOS los locales aunque el panel
   * esté filtrado a uno: un gráfico de comparación con una sola barra no
   * compara nada.
   */
  por_sucursal: SucursalResumen[];
}

export function obtenerFacturacion(
  desde: string,
  hasta: string,
  recursoId?: number | null,
  sucursalId?: number | null,
): Promise<EstadisticasFacturacion> {
  const p = new URLSearchParams({ desde, hasta });
  if (recursoId != null) p.set("recurso_id", String(recursoId));
  if (sucursalId != null) p.set("sucursal_id", String(sucursalId));
  return api.get<EstadisticasFacturacion>(
    `/estadisticas/facturacion?${p.toString()}`,
  );
}