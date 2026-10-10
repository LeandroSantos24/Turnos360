/**
 * Cómo se presenta cada rubro en pantalla (foto, descripción, orden).
 *
 * El rubro en sí —su terminología, módulos y servicios sugeridos— vive en el
 * backend (app/presets.py). Acá solo lo visual, indexado por `codigo`. Un rubro
 * que no esté en este mapa se muestra igual, con ícono y sin foto.
 */

import {
  Briefcase,
  Car,
  Dumbbell,
  Flower2,
  Hand,
  HeartPulse,
  Leaf,
  type LucideIcon,
  MessageCircleHeart,
  Palette,
  Scissors,
  Sparkles,
  Stethoscope,
} from "lucide-react";

export interface InfoRubro {
  imagen: string | null;
  descripcion: string;
  icono: LucideIcon;
  orden: number;
}

export const RUBROS_INFO: Record<string, InfoRubro> = {
  barberia: { imagen: "/img/rubros/barberia.webp", descripcion: "Cortes, barba y color, con carriles en paralelo.", icono: Scissors, orden: 1 },
  peluqueria: { imagen: "/img/rubros/peluqueria.webp", descripcion: "Corte, color, mechas y tratamientos.", icono: Scissors, orden: 2 },
  estetica: { imagen: "/img/rubros/estetica.webp", descripcion: "Faciales, depilación, cejas y pestañas.", icono: Sparkles, orden: 3 },
  unas: { imagen: "/img/rubros/unas.webp", descripcion: "Semipermanente, esculpidas y pedicuría.", icono: Hand, orden: 4 },
  spa: { imagen: "/img/rubros/spa.webp", descripcion: "Masajes, drenaje y rituales.", icono: Flower2, orden: 5 },
  kinesiologia: { imagen: "/img/rubros/kinesiologia.webp", descripcion: "Sesiones, evaluaciones y bonos.", icono: HeartPulse, orden: 6 },
  medico: { imagen: "/img/rubros/medico.webp", descripcion: "Consultas con ficha clínica y obra social.", icono: Stethoscope, orden: 7 },
  nutricion: { imagen: "/img/rubros/nutricion.webp", descripcion: "Primera consulta, seguimiento y antropometría.", icono: Leaf, orden: 8 },
  psicologia: { imagen: "/img/rubros/psicologia.webp", descripcion: "Sesiones presenciales u online.", icono: MessageCircleHeart, orden: 9 },
  tatuajes: { imagen: "/img/rubros/tatuajes.webp", descripcion: "Sesiones largas con seña y retoques.", icono: Palette, orden: 10 },
  lavadero: { imagen: "/img/rubros/lavadero.webp", descripcion: "Lavados por box, con patente y vehículo.", icono: Car, orden: 11 },
  gimnasio: { imagen: "/img/rubros/gimnasio.webp", descripcion: "Entrenamiento personal y evaluaciones.", icono: Dumbbell, orden: 12 },
  otros: { imagen: "/img/rubros/otros.webp", descripcion: "Cualquier negocio que trabaje con turnos.", icono: Briefcase, orden: 99 },
};

export function infoRubro(codigo: string): InfoRubro {
  return RUBROS_INFO[codigo] ?? { imagen: null, descripcion: "", icono: Briefcase, orden: 50 };
}

/** Ordena una lista de rubros según la presentación (no alfabético). */
export function ordenarRubros<T extends { codigo: string }>(rubros: T[]): T[] {
  return [...rubros].sort((a, b) => infoRubro(a.codigo).orden - infoRubro(b.codigo).orden);
}
