/**
 * Utilidades visuales para los turnos en la agenda:
 * colores por estado y formato de hora.
 */

import { EstadoTurno } from "./turnos-api";

/**
 * Color de fondo y texto según el estado del turno.
 * Devuelve clases de Tailwind. Los estados "muertos" (cancelado, ausente)
 * se ven apagados; los activos, con color.
 */
export function colorEstado(estado: EstadoTurno): string {
  switch (estado) {
    case "pendiente":
      return "bg-amber-100 text-amber-900 border-amber-300";
    case "confirmado":
      return "bg-blue-100 text-blue-900 border-blue-300";
    case "en_curso":
      return "bg-purple-100 text-purple-900 border-purple-300";
    case "finalizado":
      return "bg-green-100 text-green-900 border-green-300";
    case "cancelado":
      return "bg-gray-100 text-gray-500 border-gray-300 line-through";
    case "ausente":
      return "bg-red-50 text-red-700 border-red-200 line-through";
    default:
      return "bg-gray-100 text-gray-900 border-gray-300";
  }
}

/** Etiqueta legible del estado. */
export function labelEstado(estado: EstadoTurno): string {
  const labels: Record<EstadoTurno, string> = {
    pendiente: "Pendiente",
    confirmado: "Confirmado",
    en_curso: "En curso",
    finalizado: "Finalizado",
    cancelado: "Cancelado",
    ausente: "Ausente",
  };
  return labels[estado] ?? estado;
}

/** Extrae "HH:MM" de una fecha ISO. */
export function horaDe(fechaIso: string): string {
  const d = new Date(fechaIso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(
    d.getMinutes(),
  ).padStart(2, "0")}`;
}