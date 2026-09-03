/**
 * Los carriles de la agenda (las columnas de la grilla del día).
 *
 * Las columnas se generan a partir de los `grupo_agenda` de los servicios del
 * negocio: un turno cae en la columna de su grupo, y los servicios sin grupo
 * van a "General".
 *
 * POR QUÉ ESTE ARCHIVO YA NO NOMBRA NINGÚN SERVICIO
 * ─────────────────────────────────────────────────
 * Hasta acá el fallback —el que se usa cuando el negocio todavía no cargó
 * servicios, que es EXACTAMENTE el primer día de cualquiera— eran tres
 * columnas fijas: Corte, Tintura y Barba. A una barbería le quedaba bien de
 * casualidad; a una nutricionista, a un consultorio o a un spa les aparecía
 * una agenda con carriles de peluquería el día que entraban por primera vez,
 * sin haber cargado nada y sin ninguna forma de sacarlos.
 *
 * Turnos360 se vende a siete rubros. Cablear el vocabulario de uno solo en el
 * fallback del resto no es un detalle estético: es lo primero que ve alguien
 * que está decidiendo si el producto es para él.
 *
 * Ahora el fallback es una sola columna, "General", que no dice nada de ningún
 * rubro y es verdad para todos: mientras no haya servicios con grupo, todos los
 * turnos van a la misma columna. Los nombres lindos de los grupos conocidos
 * siguen existiendo (ver ETIQUETAS) pero solo se usan si el negocio de verdad
 * tiene un servicio en ese grupo.
 */

export interface Carril {
  id: string; // el grupo_agenda
  label: string; // lo que ve el usuario
}

/** Columna para los turnos sin grupo (servicios con grupo_agenda = null). */
export const GRUPO_GENERAL = "general";

/**
 * Nombres lindos para grupos que aparecen seguido, de cualquier rubro.
 *
 * Es un diccionario de cortesía, no una lista de columnas: un grupo que no
 * esté acá se muestra igual, con su nombre derivado del slug. Sirve para que
 * "unas" no se lea "Unas" y "kinesiologia" no pierda la tilde.
 */
const ETIQUETAS: Record<string, string> = {
  general: "General",
  // Barbería y peluquería
  corte: "Corte",
  tintura: "Tintura",
  barba: "Barba",
  color: "Color",
  // Uñas y estética
  unas: "Uñas",
  manos: "Manos",
  pies: "Pies",
  pestanas: "Pestañas",
  cejas: "Cejas",
  // Spa
  masajes: "Masajes",
  faciales: "Faciales",
  corporales: "Corporales",
  // Salud
  consulta: "Consulta",
  control: "Control",
  estudios: "Estudios",
  sesion: "Sesión",
};

/**
 * Carriles por defecto: UNA columna, mientras no haya servicios cargados.
 *
 * Sin esto la agenda del primer día no tendría dónde dibujar los turnos que se
 * carguen a mano antes de armar el catálogo de servicios.
 */
export const CARRILES: Carril[] = [
  { id: GRUPO_GENERAL, label: ETIQUETAS[GRUPO_GENERAL] },
];

/** Nombre legible de un grupo. "solo-lavado" → "Lavado". */
export function labelDeGrupo(grupo: string): string {
  if (ETIQUETAS[grupo]) return ETIQUETAS[grupo];
  const limpio = grupo.replace(/^solo-/, "").replace(/[-_]/g, " ").trim();
  return limpio.charAt(0).toUpperCase() + limpio.slice(1);
}

/**
 * Genera las columnas a partir de los grupos de los servicios del negocio.
 *
 * - Junta los grupos únicos de los servicios agendables.
 * - Si algún servicio no tiene grupo, agrega la columna "General".
 * - Ordena alfabético y deja "General" siempre al final: es el cajón de sastre,
 *   y un cajón de sastre en la primera columna empuja a la derecha las
 *   columnas que el dueño sí definió.
 * - Sin servicios (o sin ninguno agendable), cae a la columna única.
 *
 * Ya no hay orden privilegiado para corte/tintura/barba: el orden de las
 * columnas lo decide el catálogo del negocio, no el rubro con el que arrancó
 * el producto.
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
    if (a === GRUPO_GENERAL) return 1;
    if (b === GRUPO_GENERAL) return -1;
    return a.localeCompare(b, "es");
  });

  return ids.map((id) => ({ id, label: labelDeGrupo(id) }));
}

/**
 * En qué carril cae un turno según el grupo de su servicio.
 * Sin grupo (o grupo vacío) → columna "General".
 */
export function carrilDeTurno(servicioGrupo: string | null): string {
  return servicioGrupo ?? GRUPO_GENERAL;
}
