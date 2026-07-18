import { api } from "./api";

export interface GiftCard {
  id: number;
  empresa_id: number;
  codigo: string;
  beneficiario: string | null;
  de_parte_de: string | null;
  mensaje: string | null;
  monto: number;
  concepto: string | null;
  estado: "activa" | "canjeada" | "vencida";
  vence: string | null;
  canjeada_en: string | null;
  canjeada_por: string | null;
  creada_en: string;
}

export interface GiftCardCrear {
  monto: number;
  beneficiario?: string | null;
  de_parte_de?: string | null;
  mensaje?: string | null;
  concepto?: string | null;
  vence?: string | null;
}

export interface GiftCardVerificacion {
  valida: boolean;
  motivo: string | null; // "vencida" | "ya canjeada" | "no existe"
  gift_card: GiftCard | null;
}

export function listarGiftCards(): Promise<GiftCard[]> {
  return api.get<GiftCard[]>("/gift-cards");
}

export function crearGiftCard(datos: GiftCardCrear): Promise<GiftCard> {
  return api.post<GiftCard>("/gift-cards", datos);
}

/** Consulta si un código es válido SIN canjearlo (para el escáner). */
export function verificarGiftCard(codigo: string): Promise<GiftCardVerificacion> {
  return api.post<GiftCardVerificacion>("/gift-cards/verificar", { codigo });
}

/** Canjea el código (una sola vez). */
export function canjearGiftCard(codigo: string): Promise<GiftCardVerificacion> {
  return api.post<GiftCardVerificacion>("/gift-cards/canjear", { codigo });
}

export function borrarGiftCard(id: number): Promise<void> {
  return api.delete<void>(`/gift-cards/${id}`);
}
