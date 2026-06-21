"use client";

/**
 * Vista semanal de la agenda: grilla horaria (horas a la izquierda × 7 días).
 *
 * Reutiliza la misma lógica de posicionamiento de la grilla diaria (cada turno
 * arriba/alto según hora y duración), pero las columnas son los días de la
 * semana en vez de los carriles. Los solapados de un mismo día se reparten lado
 * a lado. Las franjas fuera del horario del barbero se ven grisadas (por día),
 * pero siguen clickeables.
 */

import { Turno } from "@/lib/turnos-api";
import { Horario } from "@/lib/horarios-api";
import {
  colorEstadoHex,
  estaInactivo,
  labelEstado,
  horaDe,
} from "@/lib/turno-visual";
import {
  startOfWeek,
  addDays,
  startOfDay,
  endOfDay,
  isSameDay,
  format,
} from "date-fns";
import { es } from "date-fns/locale";

interface GrillaSemanaProps {
  turnos: Turno[];
  /** Cualquier día de la semana a mostrar. */
  dia: Date;
  horaInicio?: number;
  horaFin?: number;
  /** Horarios del barbero, para grisar las franjas fuera de horario por día. */
  horarios?: Horario[];
  onClickTurno?: (turno: Turno) => void;
  onClickHueco?: (hora: Date) => void;
}

const ALTO_FRANJA = 48; // px por franja de 30 min (compacto: hay 7 columnas)
const MIN_POR_FRANJA = 30;

interface TurnoUbicado {
  turno: Turno;
  top: number;
  alto: number;
  columna: number;
  totalColumnas: number;
}

export function GrillaSemana({
  turnos,
  dia,
  horaInicio = 9,
  horaFin = 19,
  horarios,
  onClickTurno,
  onClickHueco,
}: GrillaSemanaProps) {
  const inicioSemana = startOfWeek(dia, { weekStartsOn: 1 });
  const dias = Array.from({ length: 7 }, (_, i) => addDays(inicioSemana, i));

  const franjas: { label: string; hora: number; minuto: number }[] = [];
  for (let h = horaInicio; h < horaFin; h++) {
    franjas.push({ label: `${String(h).padStart(2, "0")}:00`, hora: h, minuto: 0 });
    franjas.push({ label: `${String(h).padStart(2, "0")}:30`, hora: h, minuto: 30 });
  }
  const pxPorMin = ALTO_FRANJA / MIN_POR_FRANJA;

  /** Minutos desde el inicio de la grilla y duración de un turno. */
  function rango(turno: Turno): { ini: number; fin: number } | null {
    if (!turno.fecha_inicio || !turno.fecha_fin) return null;
    const i = new Date(turno.fecha_inicio);
    const f = new Date(turno.fecha_fin);
    const ini = (i.getUTCHours() - horaInicio) * 60 + i.getUTCMinutes();
    const fin = (f.getUTCHours() - horaInicio) * 60 + f.getUTCMinutes();
    if (ini < 0) return null;
    return { ini, fin };
  }

  /** Reparte en columnas los turnos que se solapan dentro de un día. */
  function ubicarTurnos(lista: Turno[]): TurnoUbicado[] {
    const conRango = lista
      .map((t) => ({ turno: t, r: rango(t) }))
      .filter((x) => x.r !== null) as {
      turno: Turno;
      r: { ini: number; fin: number };
    }[];
    conRango.sort((a, b) => a.r.ini - b.r.ini);

    const clusters: (typeof conRango)[] = [];
    for (const item of conRango) {
      let metido = false;
      for (const cluster of clusters) {
        if (
          cluster.some((c) => item.r.ini < c.r.fin && c.r.ini < item.r.fin)
        ) {
          cluster.push(item);
          metido = true;
          break;
        }
      }
      if (!metido) clusters.push([item]);
    }

    const res: TurnoUbicado[] = [];
    for (const cluster of clusters) {
      const totalColumnas = cluster.length;
      cluster.forEach((item, idx) =>
        res.push({
          turno: item.turno,
          top: item.r.ini * pxPorMin,
          alto: Math.max((item.r.fin - item.r.ini) * pxPorMin, 22),
          columna: idx,
          totalColumnas,
        }),
      );
    }
    return res;
  }

  /** Turnos que caen en un día (mismo criterio que la vista diaria). */
  function turnosDelDia(d: Date): Turno[] {
    const ini = startOfDay(d);
    const fin = endOfDay(d);
    return turnos.filter((t) => {
      if (!t.fecha_inicio) return false;
      const ti = new Date(t.fecha_inicio);
      return ti >= ini && ti <= fin;
    });
  }

  /** Franjas de trabajo del barbero para un día (backend 0=lun…6=dom). */
  function franjasDeDia(d: Date): { desdeMin: number; hastaMin: number }[] | undefined {
    if (!horarios) return undefined;
    const ds = (d.getDay() + 6) % 7;
    return horarios
      .filter((h) => h.dia_semana === ds)
      .map((h) => {
        const [h1, m1] = h.hora_desde.split(":");
        const [h2, m2] = h.hora_hasta.split(":");
        return {
          desdeMin: Number(h1) * 60 + Number(m1),
          hastaMin: Number(h2) * 60 + Number(m2),
        };
      });
  }

  function dentro(
    fr: { desdeMin: number; hastaMin: number }[] | undefined,
    hora: number,
    minuto: number,
  ): boolean {
    if (fr === undefined) return true;
    const min = hora * 60 + minuto;
    return fr.some((f) => min >= f.desdeMin && min < f.hastaMin);
  }

  function clickHueco(d: Date, hora: number, minuto: number) {
    if (!onClickHueco) return;
    const fecha = new Date(d);
    fecha.setUTCHours(hora, minuto, 0, 0);
    onClickHueco(fecha);
  }

  const hoy = new Date();

  return (
    <div className="overflow-x-auto rounded-2xl border bg-card">
      <div className="min-w-[760px]">
        {/* Encabezado: los 7 días */}
        <div className="flex border-b bg-muted/30">
          <div className="w-14 shrink-0 border-r" />
          {dias.map((d) => {
            const esHoy = isSameDay(d, hoy);
            return (
              <div
                key={d.toISOString()}
                className={`flex-1 border-r px-2 py-2 text-center last:border-r-0 ${
                  esHoy ? "bg-primary/10" : ""
                }`}
              >
                <p className="text-[11px] uppercase text-muted-foreground">
                  {format(d, "EEE", { locale: es })}
                </p>
                <p
                  className={`text-sm font-bold tabular-nums ${
                    esHoy ? "text-primary" : ""
                  }`}
                  style={{ fontFamily: "Syne, sans-serif" }}
                >
                  {format(d, "d")}
                </p>
              </div>
            );
          })}
        </div>

        {/* Cuerpo */}
        <div className="flex">
          {/* Columna de horas */}
          <div className="w-14 shrink-0 border-r">
            {franjas.map((f) => (
              <div
                key={f.label}
                className="flex items-start justify-end border-b px-2 pt-1 last:border-b-0"
                style={{ height: ALTO_FRANJA }}
              >
                <span className="text-[10px] font-medium text-muted-foreground tabular-nums">
                  {f.label}
                </span>
              </div>
            ))}
          </div>

          {/* 7 columnas de días */}
          {dias.map((d) => {
            const ftrabajo = franjasDeDia(d);
            const ubicados = ubicarTurnos(turnosDelDia(d));
            return (
              <div
                key={d.toISOString()}
                className="relative flex-1 border-r last:border-r-0"
              >
                {/* Celdas de fondo */}
                {franjas.map((f) => {
                  const ok = dentro(ftrabajo, f.hora, f.minuto);
                  return (
                    <div
                      key={f.label}
                      onClick={() => clickHueco(d, f.hora, f.minuto)}
                      className={`cursor-pointer border-b transition-colors last:border-b-0 ${
                        ok ? "hover:bg-primary/5" : "bg-muted/40 hover:bg-muted/60"
                      }`}
                      style={{ height: ALTO_FRANJA }}
                    />
                  );
                })}

                {/* Turnos */}
                {ubicados.map(({ turno, top, alto, columna, totalColumnas }) => {
                  const color = colorEstadoHex(turno.estado);
                  const inactivo = estaInactivo(turno.estado);
                  const gap = 2;
                  const anchoPct = 100 / totalColumnas;
                  const left = `calc(${columna * anchoPct}% + ${columna === 0 ? 2 : gap}px)`;
                  const width = `calc(${anchoPct}% - ${totalColumnas === 1 ? 4 : gap + 2}px)`;
                  return (
                    <div
                      key={turno.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onClickTurno?.(turno);
                      }}
                      className="absolute overflow-hidden rounded-md shadow-sm transition-all hover:z-10 hover:shadow-md"
                      style={{
                        top: top + 1,
                        height: alto - 2,
                        left,
                        width,
                        backgroundColor: inactivo ? `${color}12` : `${color}1f`,
                        borderLeft: `3px solid ${color}`,
                        opacity: inactivo ? 0.6 : 1,
                        outline: turno.es_sobreturno ? `2px dashed ${color}` : "none",
                        outlineOffset: "-2px",
                      }}
                      title={`${turno.cliente_nombre} · ${turno.servicio_nombre ?? ""} · ${labelEstado(turno.estado)}${turno.es_sobreturno ? " · sobreturno" : ""}`}
                    >
                      <div className="flex h-full flex-col px-1 py-0.5">
                        <span
                          className={`truncate text-[11px] font-semibold leading-tight ${
                            inactivo ? "line-through" : ""
                          }`}
                        >
                          {turno.fecha_inicio && horaDe(turno.fecha_inicio)}{" "}
                          {turno.cliente_nombre}
                        </span>
                        {alto > 30 && (
                          <span className="truncate text-[10px] leading-tight text-muted-foreground">
                            {turno.servicio_nombre}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}