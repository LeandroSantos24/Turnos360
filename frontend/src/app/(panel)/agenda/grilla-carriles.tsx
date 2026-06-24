"use client";
 
/**
 * Grilla de carriles de la agenda.
 *
 * 3 columnas fijas (Corte / Tintura / Barba) × filas cada 30 min.
 * Cada turno se posiciona en su columna (según servicio_grupo) y a su hora,
 * con alto proporcional a la duración. Los turnos que se solapan en el tiempo
 * (ej. original + sobreturno) se reparten el ancho lado a lado.
 * Los huecos libres son clickeables para crear.
 */
 
import { useState } from "react";
import { Turno } from "@/lib/turnos-api";
import { Carril, carrilDeTurno } from "@/lib/carriles";
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
  /** Columnas a mostrar (generadas desde los grupos de los servicios). */
  carriles: Carril[];
  horaInicio?: number;
  horaFin?: number;
  /** Franjas de trabajo del barbero ese día (en minutos). Fuera de ellas, gris. */
  franjasTrabajo?: { desdeMin: number; hastaMin: number }[];
  onClickTurno?: (turno: Turno) => void;
  onClickHueco?: (carrilId: string, hora: Date) => void;
  /** Reprograma un turno al soltarlo en otra franja (drag & drop). */
  onMoverTurno?: (turno: Turno, nuevaFecha: Date) => void;
  dia: Date;
}
 
const ALTO_FRANJA = 60; // px por franja de 30 min (un poco más de aire)
const MIN_POR_FRANJA = 30;
 
/** Un turno con su posición calculada (para repartir solapados). */
interface TurnoUbicado {
  turno: Turno;
  top: number;
  alto: number;
  columna: number; // índice dentro del grupo de solapados
  totalColumnas: number; // cuántos solapados hay en su grupo
}
 
export function GrillaCarriles({
  turnos,
  carriles,
  horaInicio = 9,
  horaFin = 19,
  franjasTrabajo,
  onClickTurno,
  onClickHueco,
  onMoverTurno,
  dia,
}: GrillaCarrilesProps) {
  const [arrastrando, setArrastrando] = useState<Turno | null>(null);
  const [celdaActiva, setCeldaActiva] = useState<string | null>(null);
  const franjas: { label: string; hora: number; minuto: number }[] = [];
  for (let h = horaInicio; h < horaFin; h++) {
    franjas.push({ label: `${String(h).padStart(2, "0")}:00`, hora: h, minuto: 0 });
    franjas.push({ label: `${String(h).padStart(2, "0")}:30`, hora: h, minuto: 30 });
  }
 
  const pxPorMin = ALTO_FRANJA / MIN_POR_FRANJA;
 
  /** ¿La franja de 30 min que arranca a esta hora cae dentro del horario de trabajo? */
  function dentroDeHorario(hora: number, minuto: number): boolean {
    if (franjasTrabajo === undefined) return true; // sin info → todo habilitado
    const min = hora * 60 + minuto;
    return franjasTrabajo.some((f) => min >= f.desdeMin && min < f.hastaMin);
  }
 
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
 
  /**
   * Ubica los turnos de un carril, repartiendo en columnas los que se solapan.
   * Algoritmo: agrupa turnos que se pisan en el tiempo, y dentro de cada grupo
   * les asigna una columna (0, 1, 2…) para que se dibujen lado a lado.
   */
  function ubicarTurnos(turnosCarril: Turno[]): TurnoUbicado[] {
    const conRango = turnosCarril
      .map((t) => ({ turno: t, r: rango(t) }))
      .filter((x) => x.r !== null) as { turno: Turno; r: { ini: number; fin: number } }[];
 
    // Ordenar por inicio
    conRango.sort((a, b) => a.r.ini - b.r.ini);
 
    // Agrupar en "clusters" de turnos que se solapan entre sí
    const clusters: (typeof conRango)[] = [];
    for (const item of conRango) {
      // ¿Entra en algún cluster existente? (se pisa con alguno de sus miembros)
      let metido = false;
      for (const cluster of clusters) {
        const seSolapa = cluster.some(
          (c) => item.r.ini < c.r.fin && c.r.ini < item.r.fin,
        );
        if (seSolapa) {
          cluster.push(item);
          metido = true;
          break;
        }
      }
      if (!metido) clusters.push([item]);
    }
 
    // Para cada cluster, asignar columnas
    const resultado: TurnoUbicado[] = [];
    for (const cluster of clusters) {
      const totalColumnas = cluster.length;
      cluster.forEach((item, idx) => {
        resultado.push({
          turno: item.turno,
          top: item.r.ini * pxPorMin,
          alto: Math.max((item.r.fin - item.r.ini) * pxPorMin, 26),
          columna: idx,
          totalColumnas,
        });
      });
    }
    return resultado;
  }
 
  function turnosDeCarril(carrilId: string): Turno[] {
    return turnos.filter((t) => carrilDeTurno(t.servicio_grupo) === carrilId);
  }
 
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
        <div className="w-14 shrink-0 border-r" />
        {carriles.map((carril) => (
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
        <div className="w-14 shrink-0 border-r">
          {franjas.map((f) => (
            <div
              key={f.label}
              className="flex items-start justify-end border-b px-2 pt-1 last:border-b-0"
              style={{ height: ALTO_FRANJA }}
            >
              <span className="text-[11px] font-medium text-muted-foreground tabular-nums">
                {f.label}
              </span>
            </div>
          ))}
        </div>
 
        {/* Las 3 columnas de carriles */}
        {carriles.map((carril) => {
          const ubicados = ubicarTurnos(turnosDeCarril(carril.id));
          return (
            <div
              key={carril.id}
              className="relative flex-1 border-r last:border-r-0"
            >
              {/* Celdas de fondo (clickeables; zona de drop para mover turnos) */}
              {franjas.map((f) => {
                const dentro = dentroDeHorario(f.hora, f.minuto);
                const idCelda = `${carril.id}-${f.label}`;
                const activa = celdaActiva === idCelda;
                return (
                  <div
                    key={f.label}
                    onClick={() => clickHueco(carril.id, f.hora, f.minuto)}
                    onDragOver={(e) => {
                      if (!arrastrando) return;
                      e.preventDefault();
                      setCeldaActiva(idCelda);
                    }}
                    onDragLeave={() => {
                      if (celdaActiva === idCelda) setCeldaActiva(null);
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (arrastrando) {
                        const nueva = new Date(dia);
                        nueva.setUTCHours(f.hora, f.minuto, 0, 0);
                        onMoverTurno?.(arrastrando, nueva);
                      }
                      setArrastrando(null);
                      setCeldaActiva(null);
                    }}
                    className={`cursor-pointer border-b transition-colors last:border-b-0 ${
                      activa
                        ? "bg-primary/20 ring-1 ring-inset ring-primary"
                        : dentro
                          ? "hover:bg-primary/5"
                          : "bg-muted/40 hover:bg-muted/60"
                    }`}
                    style={{ height: ALTO_FRANJA }}
                  />
                );
              })}
 
              {/* Turnos ubicados (con reparto lado a lado) */}
              {ubicados.map(({ turno, top, alto, columna, totalColumnas }) => {
                const color = colorEstadoHex(turno.estado);
                const inactivo = estaInactivo(turno.estado);
                // Ancho y posición horizontal según la columna del cluster
                const gap = 3; // separación entre solapados
                const anchoPct = 100 / totalColumnas;
                const left = `calc(${columna * anchoPct}% + ${columna === 0 ? 3 : gap}px)`;
                const width = `calc(${anchoPct}% - ${totalColumnas === 1 ? 6 : gap + 3}px)`;
                const compacto = alto < 44 || totalColumnas > 1;
 
                return (
                  <div
                    key={turno.id}
                    draggable={!inactivo}
                    onDragStart={() => setArrastrando(turno)}
                    onDragEnd={() => {
                      setArrastrando(null);
                      setCeldaActiva(null);
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      onClickTurno?.(turno);
                    }}
                    className={`absolute overflow-hidden rounded-lg shadow-sm transition-all hover:z-10 hover:shadow-md ${
                      inactivo ? "" : "cursor-grab active:cursor-grabbing"
                    }`}
                    style={{
                      top: top + 2,
                      height: alto - 4,
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
                    <div className="flex h-full flex-col gap-0.5 px-2 py-1.5">
                      {/* Línea 1: avatar + nombre */}
                      <div className="flex items-center gap-1.5">
                        <div
                          className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[10px] font-bold text-white"
                          style={{
                            backgroundColor: color,
                            fontFamily: "Syne, sans-serif",
                          }}
                        >
                          {inicialDe(turno.cliente_nombre)}
                        </div>
                        <span
                          className={`truncate text-xs font-semibold leading-none ${
                            inactivo ? "line-through" : ""
                          }`}
                        >
                          {turno.cliente_nombre}
                        </span>
                        {turno.es_sobreturno && (
                          <Zap
                            size={11}
                            className="ml-auto shrink-0"
                            style={{ color }}
                          />
                        )}
                      </div>
                      {/* Línea 2: hora + servicio (si hay espacio) */}
                      {!compacto && (
                        <p className="truncate pl-6 text-[11px] leading-tight text-muted-foreground">
                          {turno.fecha_inicio && horaDe(turno.fecha_inicio)}
                          {turno.servicio_nombre && ` · ${turno.servicio_nombre}`}
                        </p>
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
  );
}