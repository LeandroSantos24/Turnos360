/**
 * Duraciones en lenguaje humano.
 *
 * "120 min" es correcto pero nadie piensa así: un cliente que ve una tintura
 * de 120 minutos tiene que hacer la cuenta para saber que se le va la mañana.
 * "2 horas" se entiende sin pensar.
 *
 * Se usa tanto en la vidriera (donde el cliente decide) como en el panel
 * (donde el dueño carga y revisa), para que el mismo servicio no se lea de dos
 * formas distintas según la pantalla.
 */

/**
 * 15 -> "15 min" · 60 -> "1 hora" · 90 -> "1 h 30 min" · 120 -> "2 horas"
 *
 * Por debajo de una hora se dejan los minutos: "45 min" es más claro que
 * "3/4 de hora". A partir de ahí manda la hora, y los minutos sueltos se
 * escriben en formato corto para que no quede un renglón entero dentro de una
 * tarjeta de servicio.
 */
export function duracionLegible(min: number | null | undefined): string {
  const m = Math.max(0, Math.round(Number(min) || 0));
  if (m === 0) return "—";
  if (m < 60) return `${m} min`;

  const horas = Math.floor(m / 60);
  const resto = m % 60;
  const txtHoras = horas === 1 ? "1 hora" : `${horas} horas`;
  if (resto === 0) return txtHoras;
  // Con minutos sueltos se abrevia: "1 h 30 min" entra donde
  // "1 hora y 30 minutos" rompe el renglón.
  return `${horas} h ${resto} min`;
}
