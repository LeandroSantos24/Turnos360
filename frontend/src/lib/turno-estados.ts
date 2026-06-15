/**
 * Transiciones de estado válidas (espejo de TRANSICIONES del backend).
 * Define qué acciones se pueden hacer desde cada estado.
 */

import { EstadoTurno } from "./turnos-api";

/** Desde cada estado, a qué estados se puede pasar. */
export const TRANSICIONES: Record<EstadoTurno, EstadoTurno[]> = {
  pendiente: ["confirmado", "cancelado", "ausente"],
  confirmado: ["en_curso", "cancelado", "ausente"],
  en_curso: ["finalizado", "cancelado"],
  finalizado: [],
  cancelado: [],
  ausente: [],
};

/** Texto del botón para cada acción (estado destino). */
export const ACCION_LABEL: Record<EstadoTurno, string> = {
  confirmado: "Confirmar",
  en_curso: "Iniciar atención",
  finalizado: "Finalizar",
  cancelado: "Cancelar",
  ausente: "Marcar ausente",
  pendiente: "Volver a pendiente",
};