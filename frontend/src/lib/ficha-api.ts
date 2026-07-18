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
// ============================================================
// Evolución (controles de seguimiento)
// ============================================================

export interface Entrada {
  id: number;
  empresa_id: number;
  cliente_id: number;
  fecha: string;
  tipo: string; // primera_consulta / control / antropometria
  turno_id: number | null;
  como_se_sintio: string | null;
  noto_diferencia: string | null;
  apetito: string | null;
  entrenamiento: string | null;
  descanso: string | null;
  estres: string | null;
  resumen_antropometria: string | null;
  prescripcion: string | null;
  proximo_turno: string | null;
  creada_en: string;
}

export interface EntradaCrear {
  fecha: string;
  tipo?: string;
  como_se_sintio?: string | null;
  noto_diferencia?: string | null;
  apetito?: string | null;
  entrenamiento?: string | null;
  descanso?: string | null;
  estres?: string | null;
  resumen_antropometria?: string | null;
  prescripcion?: string | null;
  proximo_turno?: string | null;
}

export function listarEntradas(clienteId: number): Promise<Entrada[]> {
  return api.get<Entrada[]>(`/pacientes/${clienteId}/entradas`);
}
export function crearEntrada(clienteId: number, datos: EntradaCrear): Promise<Entrada> {
  return api.post<Entrada>(`/pacientes/${clienteId}/entradas`, datos);
}
export function borrarEntrada(clienteId: number, entradaId: number): Promise<void> {
  return api.delete<void>(`/pacientes/${clienteId}/entradas/${entradaId}`);
}

// ============================================================
// Mediciones antropométricas
// ============================================================

export interface Medicion {
  id: number;
  empresa_id: number;
  cliente_id: number;
  fecha: string;
  evaluador: string | null;
  origen: string; // manual / isakmetry
  entrada_id: number | null;
  peso_kg: number | null;
  talla_cm: number | null;
  imc: number | null;
  talla_sentado_cm: number | null;
  envergadura_cm: number | null;
  pl_triceps: number | null;
  pl_subescapular: number | null;
  pl_biceps: number | null;
  pl_cresta_iliaca: number | null;
  pl_supraespinal: number | null;
  pl_abdominal: number | null;
  pl_muslo: number | null;
  pl_pierna: number | null;
  sumatoria_pliegues: number | null;
  per_cintura: number | null;
  per_cadera: number | null;
  per_brazo: number | null;
  per_muslo: number | null;
  per_pierna: number | null;
  masa_grasa_kg: number | null;
  masa_grasa_pct: number | null;
  masa_muscular_kg: number | null;
  masa_osea_kg: number | null;
  datos_isak: Record<string, unknown>;
  creada_en: string;
}

/** Alta: fecha requerida; el resto, lo que se haya medido (números). */
export type MedicionCrear = { fecha: string; evaluador?: string | null; origen?: string } & Partial<
  Record<
    | "peso_kg" | "talla_cm" | "imc" | "talla_sentado_cm" | "envergadura_cm"
    | "pl_triceps" | "pl_subescapular" | "pl_biceps" | "pl_cresta_iliaca"
    | "pl_supraespinal" | "pl_abdominal" | "pl_muslo" | "pl_pierna" | "sumatoria_pliegues"
    | "per_cintura" | "per_cadera" | "per_brazo" | "per_muslo" | "per_pierna"
    | "masa_grasa_kg" | "masa_grasa_pct" | "masa_muscular_kg" | "masa_osea_kg",
    number | null
  >
>;

export function listarMediciones(clienteId: number): Promise<Medicion[]> {
  return api.get<Medicion[]>(`/pacientes/${clienteId}/mediciones`);
}
export function crearMedicion(clienteId: number, datos: MedicionCrear): Promise<Medicion> {
  return api.post<Medicion>(`/pacientes/${clienteId}/mediciones`, datos);
}
export function borrarMedicion(clienteId: number, medicionId: number): Promise<void> {
  return api.delete<void>(`/pacientes/${clienteId}/mediciones/${medicionId}`);
}

// ============================================================
// Adjuntos (PDF ISAK, estudios, planes) — por URL en esta etapa
// ============================================================

export interface Adjunto {
  id: number;
  empresa_id: number;
  cliente_id: number;
  nombre_archivo: string;
  ruta: string; // URL
  tipo: string | null; // pdf_isak / estudio / plan / otro
  entrada_clinica_id: number | null;
  fecha: string;
}

export interface AdjuntoCrear {
  nombre_archivo: string;
  ruta: string;
  tipo?: string | null;
}

export function listarAdjuntos(clienteId: number): Promise<Adjunto[]> {
  return api.get<Adjunto[]>(`/pacientes/${clienteId}/adjuntos`);
}
export function crearAdjunto(clienteId: number, datos: AdjuntoCrear): Promise<Adjunto> {
  return api.post<Adjunto>(`/pacientes/${clienteId}/adjuntos`, datos);
}
export function borrarAdjunto(clienteId: number, adjuntoId: number): Promise<void> {
  return api.delete<void>(`/pacientes/${clienteId}/adjuntos/${adjuntoId}`);
}
