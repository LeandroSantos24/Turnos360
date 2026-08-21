/**
 * WhatsApp del negocio: saldo, packs, historial y prueba de números.
 *
 * Solo el dueño. El candado real está en el backend (gate_dueno en el router
 * de whatsapp); esto es la puerta de entrada desde el panel.
 */

import { api } from "./api";

export interface PackWhatsapp {
  cantidad: number;
  precio_ars: number;
  precio_por_mensaje: number;
}

export interface EstadoWhatsapp {
  /**
   * "simulado" = el circuito corre entero pero NO sale nada a la calle.
   * "meta"     = está conectado y los mensajes llegan de verdad.
   */
  proveedor: string;
  conectado: boolean;
  numero: string | null;
  disponible: number;
  consumidos: number;
  precio_mensaje_ars: number;
  packs: PackWhatsapp[];
  plantillas_activas: number;
  /** Clientes activos cuyo teléfono NO sirve para mandar. Nunca van a recibir nada. */
  clientes_sin_telefono_valido: number;
}

export type EstadoMensaje =
  | "pendiente"
  | "enviado"
  | "entregado"
  | "leido"
  | "fallido";

export interface MensajeWhatsapp {
  id: number;
  cliente: string | null;
  telefono: string | null;
  plantilla: string | null;
  estado: EstadoMensaje;
  error: string | null;
  fecha: string;
}

export interface MovimientoWhatsapp {
  id: number;
  /** Positivo: se cargaron mensajes. Negativo: se consumió uno. */
  cantidad: number;
  motivo: string;
  detalle: string | null;
  precio_ars: number | null;
  fecha: string;
}

export interface PruebaNumero {
  enviado: boolean;
  proveedor: string;
  destino: string;
  texto: string;
  detalle: string | null;
}

export function estadoWhatsapp(signal?: AbortSignal): Promise<EstadoWhatsapp> {
  return api.get<EstadoWhatsapp>("/whatsapp/estado", signal);
}

export function mensajesWhatsapp(
  limite = 30,
  signal?: AbortSignal,
): Promise<MensajeWhatsapp[]> {
  return api.get<MensajeWhatsapp[]>(`/whatsapp/mensajes?limite=${limite}`, signal);
}

export function movimientosWhatsapp(
  limite = 30,
  signal?: AbortSignal,
): Promise<MovimientoWhatsapp[]> {
  return api.get<MovimientoWhatsapp[]>(
    `/whatsapp/movimientos?limite=${limite}`,
    signal,
  );
}

/** Diagnóstico de un número. No consume crédito ni deja registro. */
export function probarNumero(telefono: string): Promise<PruebaNumero> {
  return api.post<PruebaNumero>("/whatsapp/prueba", { telefono });
}

export const ESTADO_LABEL: Record<EstadoMensaje, string> = {
  pendiente: "En camino",
  enviado: "Enviado",
  entregado: "Entregado",
  leido: "Leído",
  fallido: "No llegó",
};

/** Clases de color por estado. Solo "no llegó" pide atención. */
export const ESTADO_CLASE: Record<EstadoMensaje, string> = {
  pendiente: "bg-muted text-muted-foreground",
  enviado: "bg-muted text-muted-foreground",
  entregado: "bg-primary/10 text-primary",
  leido: "bg-primary/15 text-primary",
  fallido: "bg-red-500/10 text-red-600 dark:text-red-400",
};

export const MOTIVO_LABEL: Record<string, string> = {
  pack: "Pack cargado",
  regalo: "Mensajes de regalo",
  ajuste: "Ajuste",
  envio: "Mensaje enviado",
  devolucion: "Devolución (no salió)",
};
