/**
 * Los locales del negocio.
 *
 * Solo el dueño. El candado real está en el backend (gate_dueno en el router
 * de sucursales); esto es la puerta de entrada desde el panel.
 *
 * Toda empresa tiene al menos un local, incluso la de una sola silla: se crea
 * en el alta y nadie lo configura. Lo que decide si esta pantalla existe en el
 * menú es `limite_sucursales` del plan — con tope 1, el negocio de un local
 * nunca ve la palabra "sucursal".
 */

import { api } from "./api";

export interface Sucursal {
  id: number;
  nombre: string;
  direccion: string | null;
  telefono: string | null;
  activa: boolean;
  /** Cuánta gente trabaja acá. Es lo que hay que mirar antes de cerrarlo. */
  profesionales: number;
  /** El local original, el que nació con el negocio. */
  es_principal: boolean;
}

export interface SucursalesRespuesta {
  sucursales: Sucursal[];
  /** Cuántos locales activos permite el plan. */
  tope: number;
  /** Cuántos hay activos hoy. */
  usadas: number;
  plan_etiqueta: string;
}

export function listarSucursales(): Promise<SucursalesRespuesta> {
  return api.get<SucursalesRespuesta>("/sucursales");
}

export function crearSucursal(datos: {
  nombre: string;
  direccion?: string | null;
  telefono?: string | null;
}): Promise<Sucursal> {
  return api.post<Sucursal>("/sucursales", datos);
}

export function editarSucursal(
  id: number,
  datos: {
    nombre?: string;
    direccion?: string | null;
    telefono?: string | null;
    activa?: boolean;
  },
): Promise<Sucursal> {
  return api.patch<Sucursal>(`/sucursales/${id}`, datos);
}
