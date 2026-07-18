"use client";
 
/**
 * Vista de equipo: grilla horaria de un día con una columna por barbero.
 *
 * Misma lógica de posicionamiento que la grilla semanal, pero las columnas son
 * los barberos en vez de los días. Cada turno cae en la columna de su recurso.
 * Clic en un hueco crea un turno con ese barbero y esa hora ya elegidos.
 */
 
import { Turno } from "@/lib/turnos-api";
import { Recurso } from "@/lib/recursos-api";
import {
  colorEstadoHex,
  estaInactivo,
  labelEstado,
  horaDe,
  inicialDe,
} from "@/lib/turno-visual";
 
interface GrillaEquipoProps {
  turnos: Turno[];
  /** Barberos a mostrar (una columna cada uno). */
  recursos: Recurso[];
  /** Día mostrado (todos los turnos son de este día). */
  dia: Date;
  horaInicio?: number;
  horaFin?: number;
  onClickTurno?: (turno: Turno) => void;
  onClickHueco?: (recursoId: number, hora: Date) => void;
}
 
const ALTO_FRANJA = 48;
const MIN_POR_FRANJA = 30;
 
interface TurnoUbicado {
  turno: Turno;
  top: number;
  alto: number;
  columna: number;
  totalColumnas: number;
}
 
export function GrillaEquipo({
  turnos,
  recursos,
  dia,
  horaInicio = 9,
  horaFin = 19,
  onClickTurno,
  onClickHueco,
}: GrillaEquipoProps) {
  const franjas: { label: string; hora: number; minuto: number }[] = [];
  for (let h = horaInicio; h < horaFin; h++) {
    franjas.push({ label: `${String(h).padStart(2, "0")}:00`, hora: h, minuto: 0 });
    franjas.push({ label: `${String(h).padStart(2, "0")}:30`, hora: h, minuto: 30 });
  }
  const pxPorMin = ALTO_FRANJA / MIN_POR_FRANJA;
 
  function rango(turno: Turno): { ini: number; fin: number } | null {
    if (!turno.fecha_inicio || !turno.fecha_fin) return null;
    const i = new Date(turno.fecha_inicio);
    const f = new Date(turno.fecha_fin);
    const ini = (i.getUTCHours() - horaInicio) * 60 + i.getUTCMinutes();
    const fin = (f.getUTCHours() - horaInicio) * 60 + f.getUTCMinutes();
    if (ini < 0) return null;
    return { ini, fin };
  }
 
  /** Reparte en columnas los turnos que se solapan dentro de un barbero. */
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
        if (cluster.some((c) => item.r.ini < c.r.fin && c.r.ini < item.r.fin)) {
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
          // Alto proporcional a la duración, con un mínimo legible: aunque el
          // turno sea corto (o su duración venga mal calculada), la tarjeta
          // nunca es más fina que su texto.
          alto: Math.max((item.r.fin - item.r.ini) * pxPorMin, 40),
          columna: idx,
          totalColumnas,
        }),
      );
    }
    return res;
  }
 
  function turnosDeRecurso(recursoId: number): Turno[] {
    return turnos.filter((t) => t.recurso_id === recursoId);
  }
 
  function clickHueco(recursoId: number, hora: number, minuto: number) {
    if (!onClickHueco) return;
    const fecha = new Date(dia);
    fecha.setUTCHours(hora, minuto, 0, 0);
    onClickHueco(recursoId, fecha);
  }
 
  if (recursos.length === 0) {
    return (
      <div className="rounded-2xl border bg-card p-12 text-center text-sm text-muted-foreground">
        No hay barberos cargados.
      </div>
    );
  }
 
  return (
    <div className="overflow-x-auto rounded-2xl border bg-card">
      <div style={{ minWidth: 80 + recursos.length * 150 }}>
        {/* Encabezado: los barberos */}
        <div className="flex border-b bg-muted/30">
          <div className="w-16 shrink-0 border-r" />
          {recursos.map((r) => (
            <div
              key={r.id}
              className="flex flex-1 items-center justify-center gap-2 border-r px-2 py-2.5 text-center last:border-r-0"
            >
              <span
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: r.color ?? "#00d4aa" }}
              />
              <span className="truncate text-sm font-semibold">{r.nombre}</span>
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
                className="flex items-start justify-end border-b px-2 pt-1 last:border-b-0"
                style={{ height: ALTO_FRANJA }}
              >
                <span className="text-[10px] font-medium text-muted-foreground tabular-nums">
                  {f.label}
                </span>
              </div>
            ))}
          </div>
 
          {/* Una columna por barbero */}
          {recursos.map((r) => {
            const ubicados = ubicarTurnos(turnosDeRecurso(r.id));
            return (
              <div
                key={r.id}
                className="relative flex-1 border-r last:border-r-0"
              >
                {/* Celdas de fondo */}
                {franjas.map((f) => (
                  <div
                    key={f.label}
                    onClick={() => clickHueco(r.id, f.hora, f.minuto)}
                    className="cursor-pointer border-b transition-colors last:border-b-0 hover:bg-primary/5"
                    style={{ height: ALTO_FRANJA }}
                  />
                ))}
 
                {/* Turnos del barbero */}
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
                      <div className="flex h-full flex-col justify-center gap-0.5 px-1.5 py-1">
                        <div className="flex items-center gap-1.5">
                          <div
                            className="flex h-4 w-4 shrink-0 items-center justify-center rounded text-[9px] font-bold text-white"
                            style={{ backgroundColor: color, fontFamily: "Syne, sans-serif" }}
                          >
                            {inicialDe(turno.cliente_nombre)}
                          </div>
                          <span
                            className={`truncate text-[11px] font-semibold leading-tight ${
                              inactivo ? "line-through" : ""
                            }`}
                          >
                            {turno.cliente_nombre}
                          </span>
                        </div>
                        {alto > 34 && (
                          <span className="truncate text-[10px] leading-tight text-muted-foreground">
                            {turno.fecha_inicio && horaDe(turno.fecha_inicio)}
                            {turno.servicio_nombre ? ` · ${turno.servicio_nombre}` : ""}
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