/**
 * Cliente de la capa pública (landing por slug). Sin login: lo usa la página
 * pública del negocio (turnos360.com/<slug>) y el wizard de reserva.
 */

import { api } from "./api";

export interface ServicioPublico {
  id: number;
  nombre: string;
  precio: number | null;
  duracion_min: number;
}

export interface RecursoPublico {
  id: number;
  nombre: string;
}

/** [abre, cierra], ej. ["09:00", "13:00"]. */
export type Franja = [string, string];

export interface Vidriera {
  nombre: string;
  slug: string;
  descripcion: string | null;
  direccion: string | null;
  telefono_publico: string | null;
  email_publico: string | null;
  logo_url: string | null;
  color_marca: string | null;
  horarios_atencion: Record<string, Franja[]> | null;
  redes: Record<string, string>;
  servicios: ServicioPublico[];
  recursos: RecursoPublico[];
}

export interface HuecosDia {
  fecha: string; // ISO date (YYYY-MM-DD)
  horas: string[]; // ISO datetimes
}

export interface DatosReserva {
  servicio_id: number;
  recurso_id: number | null; // null = sin preferencia
  inicio: string; // ISO datetime (uno de los huecos)
  cliente: { nombre: string; telefono: string; email?: string | null };
}

export interface ReservaResultado {
  turno_id: number;
  servicio: string;
  recurso: string;
  inicio: string;
  estado: string;
  mensaje: string;
}

/** Datos de la página del negocio (GET /publico/{slug}). */
export function obtenerVidriera(slug: string): Promise<Vidriera> {
  return api.get<Vidriera>(`/publico/${encodeURIComponent(slug)}`);
}

/** Horarios libres por día (GET /publico/{slug}/horarios). recursoId null = cualquiera. */
export function obtenerHuecos(
  slug: string,
  servicioId: number,
  recursoId: number | null,
  dias = 14,
): Promise<HuecosDia[]> {
  const p = new URLSearchParams({
    servicio_id: String(servicioId),
    dias: String(dias),
  });
  if (recursoId != null) p.set("recurso_id", String(recursoId));
  return api.get<HuecosDia[]>(
    `/publico/${encodeURIComponent(slug)}/horarios?${p.toString()}`,
  );
}

/** Crea la reserva (POST /publico/{slug}/reservar). El turno queda pendiente. */
export function reservar(slug: string, datos: DatosReserva): Promise<ReservaResultado> {
  return api.post<ReservaResultado>(
    `/publico/${encodeURIComponent(slug)}/reservar`,
    datos,
  );
}