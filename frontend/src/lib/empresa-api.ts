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

// ============================================================
// Señas con Mercado Pago (config del negocio, solo dueño)
// ============================================================

export interface SenasConfig {
  sena_activa: boolean;
  sena_monto: number | null;
  cobro_modo: "ninguno" | "sena" | "total";
  mp_conectado: boolean;
}

export function obtenerSenas(): Promise<SenasConfig> {
  return api.get<SenasConfig>("/empresa/senas");
}

/** El token solo viaja si se está cargando uno nuevo (nunca se lee de vuelta). */
export function guardarSenas(datos: {
  sena_activa: boolean;
  sena_monto: number | null;
  cobro_modo: "ninguno" | "sena" | "total";
  mp_access_token?: string;
}): Promise<SenasConfig> {
  return api.put<SenasConfig>("/empresa/senas", datos);
}


// ============================================================
// Campañas / automatizaciones (solo dueño)
// ============================================================

export interface AutomSwitch {
  activa: boolean;
}
export interface AutomCumple extends AutomSwitch {
  dias_antes: number;
  mensaje: string;
}
export interface AutomResena extends AutomSwitch {
  link: string;
}
export interface AutomInactivos extends AutomSwitch {
  dias: number;
  mensaje: string;
}
export interface Automatizaciones {
  recordatorio_24h: AutomSwitch;
  recordatorio_2h: AutomSwitch;
  cumple: AutomCumple;
  resena_google: AutomResena;
  inactivos: AutomInactivos;
}

export function obtenerAutomatizaciones(): Promise<Automatizaciones> {
  return api.get<Automatizaciones>("/empresa/automatizaciones");
}

export function guardarAutomatizaciones(datos: Automatizaciones): Promise<Automatizaciones> {
  return api.put<Automatizaciones>("/empresa/automatizaciones", datos);
}


export function probarCampana(tipo: string, destino: string): Promise<{ detalle: string }> {
  return api.post<{ detalle: string }>(
    `/empresa/automatizaciones/probar?tipo=${encodeURIComponent(tipo)}&destino=${encodeURIComponent(destino)}`,
    {},
  );
}

export interface Suscripcion {
  plan: string;
  estado: "activa" | "prorroga" | "vencida" | "sin_vencimiento";
  vence: string | null;
  dias_restantes: number | null;
  en_prorroga: boolean;
  mensaje: string;
}

export function obtenerSuscripcion(): Promise<Suscripcion> {
  return api.get<Suscripcion>("/empresa/suscripcion");
}
