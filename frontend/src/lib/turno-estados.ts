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
  // Reapertura flexible (para corregir errores).
  finalizado: ["en_curso", "confirmado"],
  cancelado: ["confirmado", "pendiente"],
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

// Estados terminales: desde ellos, cualquier transición es una "reapertura".
const ESTADOS_TERMINALES: EstadoTurno[] = ["finalizado", "cancelado", "ausente"];

/**
 * Etiqueta del botón según el estado ORIGEN y DESTINO.
 * Si venimos de un estado terminal (finalizado/cancelado), el texto deja claro
 * que es una reapertura, en vez del label normal.
 */
export function labelAccion(origen: EstadoTurno, destino: EstadoTurno): string {
  if (ESTADOS_TERMINALES.includes(origen)) {
    // Reapertura: el texto indica que se está reabriendo
    const labelDestino: Record<EstadoTurno, string> = {
      confirmado: "Reabrir como confirmado",
      en_curso: "Reabrir y seguir atendiendo",
      pendiente: "Reabrir como pendiente",
      finalizado: "Reabrir",
      cancelado: "Reabrir",
      ausente: "Reabrir",
    };
    return labelDestino[destino];
  }
  return ACCION_LABEL[destino];
}

/** ¿Esta transición es una reapertura (viene de un estado terminal)? */
export function esReapertura(origen: EstadoTurno): boolean {
  return ESTADOS_TERMINALES.includes(origen);
}