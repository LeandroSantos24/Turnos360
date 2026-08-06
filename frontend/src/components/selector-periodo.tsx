"use client";

/**
 * Selector de período, compartido por Inicio y Estadísticas.
 *
 * Existía en dos versiones distintas: Inicio usaba un desplegable y
 * Estadísticas un grupo de botones, con "personalizado" solo en la primera.
 * Dos controles para lo mismo obligan a aprender la pantalla dos veces, y
 * Estadísticas se quedaba sin poder mirar historial más viejo que el mes en
 * curso.
 *
 * Toda la aritmética de fechas vive acá, incluida la tolerancia a los valores
 * intermedios que emite un input type="date" mientras se tipea (un format()
 * sobre eso tira RangeError y voltea la pantalla entera).
 */

import {
  startOfDay,
  endOfDay,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  subMonths,
  format,
  parseISO,
  isValid,
} from "date-fns";
import { es } from "date-fns/locale";

export type Periodo = "hoy" | "semana" | "mes" | "mes_pasado" | "personalizado";

export const PERIODOS: { valor: Periodo; label: string }[] = [
  { valor: "hoy", label: "Hoy" },
  { valor: "semana", label: "Semana" },
  { valor: "mes", label: "Mes" },
  { valor: "mes_pasado", label: "Mes pasado" },
  { valor: "personalizado", label: "Personalizado" },
];

/**
 * "yyyy-MM-dd" -> Date, o null si todavía no es una fecha completa.
 *
 * El input type="date" emite valores intermedios mientras se tipea: "" con la
 * fecha incompleta, o un año de un dígito ("0007-08-01"). parseISO("")
 * devuelve Invalid Date y format() sobre eso TIRA RangeError, que sin atajar
 * se convierte en el "Application error" de Next.
 */
export function fechaDeInput(valor: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(valor)) return null;
  const d = parseISO(valor);
  if (!isValid(d)) return null;
  if (d.getFullYear() < 1900 || d.getFullYear() > 2200) return null;
  return d;
}

/** Rango del período. null = rango personalizado todavía incompleto o invertido. */
export function rangoDe(
  periodo: Periodo,
  desde: string,
  hasta: string,
): { desde: Date; hasta: Date } | null {
  const hoy = new Date();
  if (periodo === "semana") {
    return {
      desde: startOfWeek(hoy, { weekStartsOn: 1 }),
      hasta: endOfWeek(hoy, { weekStartsOn: 1 }),
    };
  }
  if (periodo === "mes") {
    return { desde: startOfMonth(hoy), hasta: endOfMonth(hoy) };
  }
  if (periodo === "mes_pasado") {
    const m = subMonths(hoy, 1);
    return { desde: startOfMonth(m), hasta: endOfMonth(m) };
  }
  if (periodo === "personalizado") {
    const d = fechaDeInput(desde);
    const h = fechaDeInput(hasta);
    if (!d || !h) return null;
    if (d > h) return null;
    return { desde: startOfDay(d), hasta: endOfDay(h) };
  }
  return { desde: startOfDay(hoy), hasta: endOfDay(hoy) };
}

/** Texto del subtítulo. Nunca formatea una fecha sin validar. */
export function textoPeriodo(
  periodo: Periodo,
  desde: string,
  hasta: string,
): string {
  const r = rangoDe(periodo, desde, hasta);
  if (periodo !== "personalizado") {
    return PERIODOS.find((p) => p.valor === periodo)?.label.toLowerCase() ?? "";
  }
  if (!r) return "completá las dos fechas";
  return `${format(r.desde, "d MMM", { locale: es })} al ${format(r.hasta, "d MMM yyyy", { locale: es })}`;
}

/** Valor inicial de los inputs: el mes en curso, para que nunca arranquen vacíos. */
export function rangoInicial(): { desde: string; hasta: string } {
  const hoy = new Date();
  return {
    desde: format(startOfMonth(hoy), "yyyy-MM-dd"),
    hasta: format(hoy, "yyyy-MM-dd"),
  };
}

export function SelectorPeriodo({
  periodo,
  onPeriodo,
  desde,
  hasta,
  onDesde,
  onHasta,
}: {
  periodo: Periodo;
  onPeriodo: (p: Periodo) => void;
  desde: string;
  hasta: string;
  onDesde: (v: string) => void;
  onHasta: (v: string) => void;
}) {
  const rangoOk = periodo !== "personalizado" || rangoDe(periodo, desde, hasta) !== null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap items-center rounded-lg border p-0.5">
        {PERIODOS.map((p) => (
          <button
            key={p.valor}
            type="button"
            onClick={() => onPeriodo(p.valor)}
            className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
              periodo === p.valor
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {periodo === "personalizado" && (
        <div className="flex flex-wrap items-center gap-1.5">
          <input
            type="date"
            value={desde}
            max={hasta || undefined}
            onChange={(e) => onDesde(e.target.value)}
            className={`rounded-lg border bg-background px-2.5 py-1.5 text-sm ${
              rangoOk ? "" : "border-amber-500"
            }`}
          />
          <span className="text-sm text-muted-foreground">a</span>
          <input
            type="date"
            value={hasta}
            min={desde || undefined}
            onChange={(e) => onHasta(e.target.value)}
            className={`rounded-lg border bg-background px-2.5 py-1.5 text-sm ${
              rangoOk ? "" : "border-amber-500"
            }`}
          />
        </div>
      )}
    </div>
  );
}
