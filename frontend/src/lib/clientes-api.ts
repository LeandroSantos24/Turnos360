/**
 * Llamadas a la API para el CRM de clientes.
 * Refleja los endpoints del backend: GET/POST/PATCH/DELETE /clientes.
 */

import { api } from "./api";

/** Un cliente, tal como lo devuelve el backend (schema ClienteOut). */
export interface Cliente {
  id: number;
  empresa_id: number;
  nombre: string;
  apellido: string | null;
  dni: string | null;
  email: string | null;
  telefono: string | null;
  fecha_nacimiento: string | null;
  canal_adquisicion: string | null;
  etiquetas: string[];
  observaciones: string | null;
  activo: boolean;
  creado_en: string;
}

/** La respuesta paginada del listado (schema ClientesPagina). */
export interface ClientesPagina {
  total: number;
  items: Cliente[];
}

/** Datos para crear un cliente (schema ClienteCrear). */
export interface ClienteCrear {
  nombre: string;
  apellido?: string;
  dni?: string;
  email?: string;
  telefono?: string;
  fecha_nacimiento?: string; // formato yyyy-MM-dd
  canal_adquisicion?: string;
  etiquetas?: string[];
  observaciones?: string;
}

/** Lista clientes con búsqueda y paginación. */
export function listarClientes(
  buscar?: string,
  offset = 0,
  limite = 10,
): Promise<ClientesPagina> {
  const params = new URLSearchParams();
  if (buscar) params.set("buscar", buscar);
  params.set("offset", String(offset));
  params.set("limite", String(limite));
  return api.get<ClientesPagina>(`/clientes?${params.toString()}`);
}

/** Crea un cliente. */
export function crearCliente(datos: ClienteCrear): Promise<Cliente> {
  return api.post<Cliente>("/clientes", datos);
}

/** Da de baja (lógica) un cliente. */
export function desactivarCliente(id: number): Promise<void> {
  return api.delete<void>(`/clientes/${id}`);
}

/** Trae un cliente puntual por su id. */
export function obtenerCliente(id: number): Promise<Cliente> {
  return api.get<Cliente>(`/clientes/${id}`);
}

/** Edita un cliente (PATCH). */
export function editarCliente(
  id: number,
  datos: Partial<ClienteCrear>,
): Promise<Cliente> {
  return api.patch<Cliente>(`/clientes/${id}`, datos);
}

/** Borra (desactiva) un cliente. */
export function borrarCliente(id: number): Promise<void> {
  return api.delete<void>(`/clientes/${id}`);
}