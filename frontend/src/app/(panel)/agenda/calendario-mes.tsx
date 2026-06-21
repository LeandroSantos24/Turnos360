"use client";

/**
 * Vista mensual de la agenda: calendario clásico (semanas × 7 días).
 *
 * Cada celda es un día y muestra un resumen de sus turnos (hasta 3, con punto de
 * color por estado, y "+N más" si hay más). Al hacer clic en un día se abre la
 * vista diaria de esa fecha. Los días de otros meses se ven atenuados.
 */

import { Turno } from "@/lib/turnos-api";
import { colorEstadoHex, horaDe } from "@/lib/turno-visual";
import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  addDays,
  isSameMonth,
  isSameDay,
  startOfDay,
  endOfDay,
  format,
} from "date-fns";

interface CalendarioMesProps {
  turnos: Turno[];
  /** Cualquier día del mes a mostrar. */
  dia: Date;
  onClickDia?: (dia: Date) => void;
}

const DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

export function CalendarioMes({ turnos, dia, onClickDia }: CalendarioMesProps) {
  const inicio = startOfWeek(startOfMonth(dia), { weekStartsOn: 1 });
  const fin = endOfWeek(endOfMonth(dia), { weekStartsOn: 1 });
  const dias: Date[] = [];
  for (let d = inicio; d <= fin; d = addDays(d, 1)) dias.push(d);

  const hoy = new Date();

  function turnosDelDia(d: Date): Turno[] {
    const ini = startOfDay(d);
    const f = endOfDay(d);
    return turnos
      .filter((t) => {
        if (!t.fecha_inicio) return false;
        const ti = new Date(t.fecha_inicio);
        return ti >= ini && ti <= f;
      })
      .sort(
        (a, b) =>
          new Date(a.fecha_inicio!).getTime() -
          new Date(b.fecha_inicio!).getTime(),
      );
  }

  return (
    <div className="overflow-hidden rounded-2xl border bg-card">
      {/* Encabezado: días de la semana */}
      <div className="grid grid-cols-7 border-b bg-muted/30">
        {DIAS_SEMANA.map((d) => (
          <div
            key={d}
            className="px-2 py-2 text-center text-xs font-bold text-muted-foreground"
          >
            {d}
          </div>
        ))}
      </div>

      {/* Celdas del calendario */}
      <div className="grid grid-cols-7">
        {dias.map((d, i) => {
          const delMes = isSameMonth(d, dia);
          const esHoy = isSameDay(d, hoy);
          const ts = turnosDelDia(d);
          return (
            <button
              key={i}
              onClick={() => onClickDia?.(d)}
              className={`flex min-h-[100px] flex-col gap-1 border-b border-r p-1.5 text-left align-top transition-colors hover:bg-primary/5 [&:nth-child(7n)]:border-r-0 ${
                delMes ? "" : "bg-muted/20"
              }`}
            >
              <span
                className={`text-xs font-semibold tabular-nums ${
                  esHoy
                    ? "flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground"
                    : delMes
                      ? ""
                      : "text-muted-foreground"
                }`}
                style={{ fontFamily: "Syne, sans-serif" }}
              >
                {format(d, "d")}
              </span>

              <div className="flex flex-col gap-0.5 overflow-hidden">
                {ts.slice(0, 3).map((t) => (
                  <span
                    key={t.id}
                    className="flex items-center gap-1 truncate text-[10px] leading-tight"
                  >
                    <span
                      className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ backgroundColor: colorEstadoHex(t.estado) }}
                    />
                    <span className="truncate text-muted-foreground">
                      {t.fecha_inicio && horaDe(t.fecha_inicio)} {t.cliente_nombre}
                    </span>
                  </span>
                ))}
                {ts.length > 3 && (
                  <span className="text-[10px] font-medium text-muted-foreground">
                    +{ts.length - 3} más
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}