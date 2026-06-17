"use client";

/**
 * Grilla de carriles de la agenda.
 *
 * 3 columnas fijas (Corte / Tintura / Barba) × filas cada 30 min.
 * Cada turno se posiciona en su columna (según servicio_grupo) y a su hora,
 * con alto proporcional a la duración. Los huecos libres son clickeables.
 */

import { Turno } from "@/lib/turnos-api";
import { CARRILES, carrilDeTurno } from "@/lib/carriles";
import {
  colorEstadoHex,
  estaInactivo,
  labelEstado,
  horaDe,
  inicialDe,
} from "@/lib/turno-visual";
import { Zap } from "lucide-react";

interface GrillaCarrilesProps {
  turnos: Turno[];
  horaInicio?: number;
  horaFin?: number;
  onClickTurno?: (turno: Turno) => void;
  onClickHueco?: (carrilId: string, hora: Date) => void;
  dia: Date;
}

const ALTO_FRANJA = 56; // px por franja de 30 min
const MIN_POR_FRANJA = 30;

export function GrillaCarriles({
  turnos,
  horaInicio = 9,
  horaFin = 19,
  onClickTurno,
  onClickHueco,
  dia,
}: GrillaCarrilesProps) {
  // Generar las franjas de 30 min (las filas)
  const franjas: { label: string; hora: number; minuto: number }[] = [];
  for (let h = horaInicio; h < horaFin; h++) {
    franjas.push({ label: `${String(h).padStart(2, "0")}:00`, hora: h, minuto: 0 });
    franjas.push({ label: `${String(h).padStart(2, "0")}:30`, hora: h, minuto: 30 });
  }

  const pxPorMin = ALTO_FRANJA / MIN_POR_FRANJA;

  /** Posición (top) y alto de un turno en píxeles, dentro de su columna. */
  function posicion(turno: Turno): { top: number; alto: number } | null {
    if (!turno.fecha_inicio || !turno.fecha_fin) return null;
    const ini = new Date(turno.fecha_inicio);
    const fin = new Date(turno.fecha_fin);
    const minDesdeInicio =
      (ini.getUTCHours() - horaInicio) * 60 + ini.getUTCMinutes();
    if (minDesdeInicio < 0) return null;
    const duracionMin = (fin.getTime() - ini.getTime()) / 60000;
    return {
      top: minDesdeInicio * pxPorMin,
      alto: Math.max(duracionMin * pxPorMin, 24),
    };
  }

  /** Turnos que van en una columna (carril) dada. */
  function turnosDeCarril(carrilId: string): Turno[] {
    return turnos.filter((t) => carrilDeTurno(t.servicio_grupo) === carrilId);
  }

  /** Maneja el clic en una celda vacía. */
  function clickHueco(carrilId: string, hora: number, minuto: number) {
    if (!onClickHueco) return;
    const fecha = new Date(dia);
    fecha.setUTCHours(hora, minuto, 0, 0);
    onClickHueco(carrilId, fecha);
  }

  return (
    <div className="overflow-hidden rounded-2xl border bg-card">
      {/* Encabezado: las 3 columnas */}
      <div className="flex border-b bg-muted/30">
        <div className="w-16 shrink-0 border-r" />
        {CARRILES.map((carril) => (
          <div
            key={carril.id}
            className="flex-1 border-r px-4 py-3 text-center text-sm font-bold last:border-r-0"
            style={{ fontFamily: "Syne, sans-serif" }}
          >
            {carril.label}
          </div>
        ))}
      </div>

      {/* Cuerpo */}
      <div className="flex">
        {/* Columna de horas */}
        <div className="w-16 shrink-0 border-r">
          {franjas.map((f) => (
            <div
              key={f.label}
              className="flex items-start justify-end border-b px-2 py-1 last:border-b-0"
              style={{ height: ALTO_FRANJA }}
            >
              <span className="text-xs font-medium text-muted-foreground tabular-nums">
                {f.label}
              </span>
            </div>
          ))}
        </div>

        {/* Las 3 columnas de carriles */}
        {CARRILES.map((carril) => {
          const turnosCarril = turnosDeCarril(carril.id);
          return (
            <div
              key={carril.id}
              className="relative flex-1 border-r last:border-r-0"
            >
              {/* Celdas de fondo (clickeables para crear) */}
              {franjas.map((f) => (
                <div
                  key={f.label}
                  onClick={() => clickHueco(carril.id, f.hora, f.minuto)}
                  className="cursor-pointer border-b transition-colors last:border-b-0 hover:bg-primary/5"
                  style={{ height: ALTO_FRANJA }}
                />
              ))}

              {/* Turnos posicionados encima */}
              {turnosCarril.map((turno) => {
                const pos = posicion(turno);
                if (!pos) return null;
                const color = colorEstadoHex(turno.estado);
                const inactivo = estaInactivo(turno.estado);
                return (
                  <div
                    key={turno.id}
                    onClick={() => onClickTurno?.(turno)}
                    className="absolute left-1 right-1 cursor-pointer overflow-hidden rounded-lg border-l-4 px-2 py-1 shadow-sm transition-shadow hover:shadow-md"
                    style={{
                      top: pos.top + 1,
                      height: pos.alto - 2,
                      borderLeftColor: color,
                      backgroundColor: `${color}18`,
                      opacity: inactivo ? 0.55 : 1,
                      // borde extra para sobreturnos
                      outline: turno.es_sobreturno
                        ? `2px dashed ${color}`
                        : "none",
                      outlineOffset: "-2px",
                    }}
                    title={`${turno.cliente_nombre} · ${labelEstado(turno.estado)}`}
                  >
                    <div className="flex items-center gap-1.5">
                      <div
                        className="flex h-5 w-5 shrink-0 items-center justify-center rounded text-[10px] font-bold text-white"
                        style={{ backgroundColor: color }}
                      >
                        {inicialDe(turno.cliente_nombre)}
                      </div>
                      <span
                        className={`truncate text-xs font-semibold ${
                          inactivo ? "line-through" : ""
                        }`}
                        style={{ color }}
                      >
                        {turno.cliente_nombre}
                      </span>
                      {turno.es_sobreturno && (
                        <Zap size={11} style={{ color }} className="shrink-0" />
                      )}
                    </div>
                    {pos.alto > 38 && (
                      <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
                        {turno.fecha_inicio && horaDe(turno.fecha_inicio)} ·{" "}
                        {turno.servicio_nombre}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}