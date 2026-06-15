/**
 * Utilidades visuales para los turnos en la agenda (estilo Google Calendar):
 * color sólido por estado (para la barra lateral y el avatar) + formato de hora.
 */

import { EstadoTurno } from "./turnos-api";

/** Color sólido (hex) según el estado. Se usa en la barra izquierda y el avatar. */
export function colorEstadoHex(estado: EstadoTurno): string {
  switch (estado) {
    case "pendiente":
      return "#f59e0b"; // ámbar
    case "confirmado":
      return "#3b82f6"; // azul
    case "en_curso":
      return "#8b5cf6"; // violeta
    case "finalizado":
      return "#22c55e"; // verde
    case "cancelado":
      return "#9ca3af"; // gris
    case "ausente":
      return "#ef4444"; // rojo
    default:
      return "#9ca3af";
  }
}

/** ¿Este estado se considera "inactivo"? (para tachar y atenuar) */
export function estaInactivo(estado: EstadoTurno): boolean {
  return estado === "cancelado" || estado === "ausente";
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

/** Extrae "HH:MM" de una fecha ISO, leyendo la hora tal cual se guardó. */
export function horaDe(fechaIso: string): string {
  const d = new Date(fechaIso);
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(
    d.getUTCMinutes(),
  ).padStart(2, "0")}`;
}

/** La inicial del nombre del cliente, para el avatar. */
export function inicialDe(nombre: string | null): string {
  if (!nombre) return "?";
  return nombre.trim().charAt(0).toUpperCase();
}