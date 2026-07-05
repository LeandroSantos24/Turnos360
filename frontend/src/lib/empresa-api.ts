/**
 * Configuración de la empresa logueada: su rubro y el preset.
 * El preset define qué módulos se muestran y cómo se nombran las cosas.
 */

import { api } from "./api";

export interface PresetRubro {
  terminologia?: Record<string, string>;
  modulos?: Record<string, boolean>;
  campos_cliente?: Array<{ clave: string; etiqueta: string; tipo: string }>;
  [clave: string]: unknown;
}

export interface ConfigEmpresa {
  id: number;
  nombre: string;
  slug: string;
  rubro_codigo: string;
  rubro_nombre: string;
  preset: PresetRubro;
}

/** Trae la empresa actual + el preset de su rubro (GET /empresa/actual). */
export function obtenerConfigEmpresa(): Promise<ConfigEmpresa> {
  return api.get<ConfigEmpresa>("/empresa/actual");
}

// === Landing pública ("Mi página") ===

/** Una franja horaria: [abre, cierra], ej. ["09:00", "13:00"]. */
export type Franja = [string, string];

/** Horarios visibles por día (clave: lun..dom). Día ausente o [] = cerrado.
 *  Solo para mostrar en la landing; NO calcula huecos reservables. */
export type HorariosAtencion = Record<string, Franja[]>;

/** Links de redes. Claves conocidas + libres (sumar una red = agregar clave). */
export interface Redes {
  instagram?: string;
  facebook?: string;
  tiktok?: string;
  linkedin?: string;
  sitio_web?: string;
  [red: string]: string | undefined;
}

export interface LandingConfig {
  descripcion: string | null;
  direccion: string | null;
  telefono_publico: string | null;
  email_publico: string | null;
  logo_url: string | null;
  color_marca: string | null;
  horarios_atencion: HorariosAtencion | null;
  redes: Redes;
  /** Galería de la landing: lista de URLs de fotos (máx. 12). */
  galeria: string[];
}

/** Contenido actual de la landing del negocio (GET /empresa/landing). */
export function obtenerLanding(): Promise<LandingConfig> {
  return api.get<LandingConfig>("/empresa/landing");
}

/** Guarda el contenido de la landing (PUT /empresa/landing). Solo dueño. */
export function guardarLanding(datos: LandingConfig): Promise<LandingConfig> {
  return api.put<LandingConfig>("/empresa/landing", datos);
}