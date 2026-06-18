/**
 * API de membresías / abonos (E11).
 *
 * Dos recursos: planes de abono (el molde) y membresías (cliente que compra).
 */

import { api } from "./api";

// ===== TIPOS =====

export interface PlanAbono {
  id: number;
  empresa_id: number;
  nombre: string;
  descripcion: string | null;
  precio: number;
  ilimitado: boolean;
  cantidad_cupos: number | null;
  servicios_cubiertos: number[];
  activo: boolean;
}

export interface PlanAbonoCrear {
  nombre: string;
  descripcion?: string;
  precio: number;
  ilimitado: boolean;
  cantidad_cupos?: number;
  servicios_cubiertos: number[];
}

export interface Membresia {
  id: number;
  empresa_id: number;
  cliente_id: number;
  plan_id: number;
  fecha_desde: string;
  fecha_hasta: string;
  estado: string;
  cupos_usados: number;
  plan_nombre: string | null;
  plan_precio: number | null;
  plan_ilimitado: boolean | null;
  vigente: boolean;
}

export interface MembresiaCrear {
  cliente_id: number;
  plan_id: number;
  fecha_desde: string; // yyyy-MM-dd
  fecha_hasta: string;
}

// ===== PLANES =====

export function listarPlanes(): Promise<PlanAbono[]> {
  return api.get<PlanAbono[]>("/planes-abono");
}

export function crearPlan(datos: PlanAbonoCrear): Promise<PlanAbono> {
  return api.post<PlanAbono>("/planes-abono", datos);
}

export function editarPlan(
  id: number,
  datos: Partial<PlanAbonoCrear> & { activo?: boolean },
): Promise<PlanAbono> {
  return api.patch<PlanAbono>(`/planes-abono/${id}`, datos);
}

export function borrarPlan(id: number): Promise<void> {
  return api.delete<void>(`/planes-abono/${id}`);
}

// ===== MEMBRESÍAS =====

/** Trae la membresía vigente de un cliente, o null si no tiene. */
export function membresiaDeCliente(clienteId: number): Promise<Membresia | null> {
  return api.get<Membresia | null>(`/clientes/${clienteId}/membresia`);
}

export function crearMembresia(datos: MembresiaCrear): Promise<Membresia> {
  return api.post<Membresia>("/membresias", datos);
}

export function cancelarMembresia(membresiaId: number): Promise<void> {
  return api.delete<void>(`/membresias/${membresiaId}`);
}