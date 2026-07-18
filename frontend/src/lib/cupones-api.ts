/** API de cupones de descuento. */

import { api } from "@/lib/api";

export interface Cupon {
  id: number;
  codigo: string;
  tipo: "porcentaje" | "monto";
  valor: number;
  vence_el: string | null;
  max_usos: number | null;
  usos: number;
  servicios_ids: number[]; // vacío = todos los servicios
  activo: boolean;
}

export type CuponDatos = Omit<Cupon, "id" | "usos">;

export function listarCupones(): Promise<Cupon[]> {
  return api.get<Cupon[]>("/cupones");
}

export function crearCupon(datos: CuponDatos): Promise<Cupon> {
  return api.post<Cupon>("/cupones", datos);
}

export function editarCupon(id: number, datos: CuponDatos): Promise<Cupon> {
  return api.put<Cupon>(`/cupones/${id}`, datos);
}

export function borrarCupon(id: number): Promise<unknown> {
  return api.delete(`/cupones/${id}`);
}
