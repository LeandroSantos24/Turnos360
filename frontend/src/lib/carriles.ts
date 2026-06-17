/**
 * Los carriles de la agenda (columnas de la grilla).
 *
 * Cada carril agrupa los servicios de un mismo grupo_agenda. Un turno cae en
 * la columna de su servicio_grupo. Los servicios "en paralelo" (grupo que
 * empieza con "solo-") van a la columna que mejor matchee, o a una genérica.
 */

export interface Carril {
  id: string; // el grupo_agenda que matchea
  label: string; // lo que ve el usuario
}

// Las 3 columnas fijas de la barbería.
export const CARRILES: Carril[] = [
  { id: "corte", label: "Corte" },
  { id: "tintura", label: "Tintura" },
  { id: "barba", label: "Barba" },
];

/**
 * Decide en qué carril cae un turno según su grupo.
 * Si el grupo coincide con un carril, va ahí. Si no (ej. "solo-lavado"),
 * devuelve null (no se muestra en estas 3 columnas, o lo manejamos aparte).
 */
export function carrilDeTurno(servicioGrupo: string | null): string | null {
  if (!servicioGrupo) return null;
  // Match directo con un carril conocido
  const directo = CARRILES.find((c) => c.id === servicioGrupo);
  if (directo) return directo.id;
  // Los "solo-X" (en paralelo) no entran en las 3 columnas fijas por ahora
  return null;
}