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