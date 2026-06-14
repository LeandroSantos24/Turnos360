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
  canal_adquisicion?: string;
}

/** Lista los clientes, con búsqueda opcional. */
export function listarClientes(buscar?: string): Promise<ClientesPagina> {
  const params = new URLSearchParams();
  if (buscar) params.set("buscar", buscar);
  const query = params.toString();
  return api.get<ClientesPagina>(`/clientes${query ? `?${query}` : ""}`);
}

/** Crea un cliente. */
export function crearCliente(datos: ClienteCrear): Promise<Cliente> {
  return api.post<Cliente>("/clientes", datos);
}

/** Da de baja (lógica) un cliente. */
export function desactivarCliente(id: number): Promise<void> {
  return api.delete<void>(`/clientes/${id}`);
}