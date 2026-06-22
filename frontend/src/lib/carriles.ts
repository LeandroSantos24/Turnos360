/**
 * Los carriles de la agenda (columnas de la grilla).
 *
 * Las columnas NO son fijas: se generan a partir de los grupos_agenda de los
 * servicios del negocio (ver carrilesDeGrupos). Un turno cae en la columna de
 * su grupo; los que no tienen grupo van a la columna "General".
 */
 
export interface Carril {
  id: string; // el grupo_agenda
  label: string; // lo que ve el usuario
}
 
/** Columna para los turnos sin grupo (servicios con grupo_agenda = null). */
export const GRUPO_GENERAL = "general";
 
/** Labels lindos para grupos conocidos. El resto se genera del slug. */
const LABELS: Record<string, string> = {
  corte: "Corte",
  tintura: "Tintura",
  barba: "Barba",
  general: "General",
};
 
/** Orden preferido: estos van primero, en este orden. */
const ORDEN_PREFERIDO = ["corte", "tintura", "barba"];
 
/** Carriles por defecto si todavía no hay servicios cargados. */
export const CARRILES: Carril[] = ORDEN_PREFERIDO.map((id) => ({
  id,
  label: LABELS[id] ?? id,
}));
 
/** Label legible para un grupo (conocido o nuevo). "solo-lavado" → "Lavado". */
export function labelDeGrupo(grupo: string): string {
  if (LABELS[grupo]) return LABELS[grupo];
  const limpio = grupo.replace(/^solo-/, "").replace(/[-_]/g, " ").trim();
  return limpio.charAt(0).toUpperCase() + limpio.slice(1);
}
 
/**
 * Genera las columnas a partir de los grupos de los servicios.
 * - Junta los grupos únicos.
 * - Si algún servicio no tiene grupo, agrega la columna "General".
 * - Ordena: los conocidos primero (corte, tintura, barba), después el resto
 *   alfabético, y "General" al final.
 * - Si no hay nada, cae a los carriles por defecto.
 */
export function carrilesDeGrupos(grupos: (string | null | undefined)[]): Carril[] {
  const set = new Set<string>();
  let haySinGrupo = false;
  for (const g of grupos) {
    if (g) set.add(g);
    else haySinGrupo = true;
  }
  if (haySinGrupo) set.add(GRUPO_GENERAL);
 
  if (set.size === 0) return CARRILES;
 
  const ids = Array.from(set).sort((a, b) => {
    const ia = ORDEN_PREFERIDO.indexOf(a);
    const ib = ORDEN_PREFERIDO.indexOf(b);
    if (ia !== -1 && ib !== -1) return ia - ib;
    if (ia !== -1) return -1;
    if (ib !== -1) return 1;
    if (a === GRUPO_GENERAL) return 1;
    if (b === GRUPO_GENERAL) return -1;
    return a.localeCompare(b);
  });
 
  return ids.map((id) => ({ id, label: labelDeGrupo(id) }));
}
 
/**
 * En qué carril cae un turno según su grupo.
 * Sin grupo (o grupo vacío) → columna "General".
 */
export function carrilDeTurno(servicioGrupo: string | null): string {
  return servicioGrupo ?? GRUPO_GENERAL;
}