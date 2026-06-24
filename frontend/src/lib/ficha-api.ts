/**
 * Llamadas a la API para la ficha clínica del paciente (pack nutrición).
 * Refleja los endpoints del backend: GET / PUT /pacientes/{id}/ficha.
 */

import { api, ApiError } from "./api";

/** La ficha tal como la devuelve el backend (schema FichaOut). */
export interface Ficha {
  id: number;
  empresa_id: number;
  cliente_id: number;
  motivo_consulta: string | null;
  objetivo: string | null;
  ocupacion: string | null;
  horario_trabajo: string | null;
  fum: string | null;
  horario_comidas: Record<string, string>;
  recordatorio_24h: Record<string, string>;
  frecuencia_consumo: Record<string, string>;
  actividad_fisica: string | null;
  enfermedades: string | null;
  operaciones: string | null;
  medicacion: string | null;
  antecedentes_familiares: string | null;
  consume_alcohol_drogas: string | null;
  fuma: string | null;
  sintomas_recurrentes: string | null;
  evacuacion: string | null;
  sueno: string | null;
  alimentos_no_consume: string | null;
  alimentos_no_tolera: string | null;
  alimentos_gustan: string | null;
  nutri_anterior: string | null;
  obra_social: string | null;
  plan_obra_social: string | null;
  nro_afiliado: string | null;
  datos_extra: Record<string, unknown>;
  creada_en: string;
  actualizada_en: string;
}

/** Lo que se manda al guardar (todo opcional: la ficha se llena de a poco). */
export interface FichaGuardar {
  motivo_consulta?: string | null;
  objetivo?: string | null;
  ocupacion?: string | null;
  horario_trabajo?: string | null;
  fum?: string | null;
  horario_comidas?: Record<string, string>;
  recordatorio_24h?: Record<string, string>;
  frecuencia_consumo?: Record<string, string>;
  actividad_fisica?: string | null;
  enfermedades?: string | null;
  operaciones?: string | null;
  medicacion?: string | null;
  antecedentes_familiares?: string | null;
  consume_alcohol_drogas?: string | null;
  fuma?: string | null;
  sintomas_recurrentes?: string | null;
  evacuacion?: string | null;
  sueno?: string | null;
  alimentos_no_consume?: string | null;
  alimentos_no_tolera?: string | null;
  alimentos_gustan?: string | null;
  nutri_anterior?: string | null;
  obra_social?: string | null;
  plan_obra_social?: string | null;
  nro_afiliado?: string | null;
}

/** Trae la ficha del paciente. Devuelve null si todavía no tiene (404). */
export async function obtenerFicha(clienteId: number): Promise<Ficha | null> {
  try {
    return await api.get<Ficha>(`/pacientes/${clienteId}/ficha`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/** Crea o actualiza la ficha (upsert). */
export function guardarFicha(clienteId: number, datos: FichaGuardar): Promise<Ficha> {
  return api.put<Ficha>(`/pacientes/${clienteId}/ficha`, datos);
}