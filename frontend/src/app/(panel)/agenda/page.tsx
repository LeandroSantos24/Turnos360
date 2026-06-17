"use client";

/**
 * Agenda visual (/agenda) — vista de lista (una fila por turno).
 *
 * Los turnos se muestran como filas ordenadas por horario, una debajo de la
 * otra. Clic en una fila abre el panel de detalle (TurnoDetalle) para
 * gestionar el turno y entrar a la ficha del cliente. El botón "Nuevo turno"
 * abre el diálogo de creación (que respeta los carriles del motor).
 */

import { useEffect, useState, useCallback } from "react";
import { addDays, format, startOfDay, endOfDay } from "date-fns";
import { isToday } from "date-fns/isToday";
import { es } from "date-fns/locale";
import { Plus } from "lucide-react";

import { listarRecursos, Recurso } from "@/lib/recursos-api";
import { listarTurnos, listarTurnosDelDia, Turno } from "@/lib/turnos-api";
import { MetricasDia } from "./metricas-dia";
import { TurnoDetalle } from "./turno-detalle";
import { NuevoTurnoDialog } from "./nuevo-turno-dialog";
import {
  colorEstadoHex,
  estaInactivo,
  labelEstado,
  horaDe,
  inicialDe,
} from "@/lib/turno-visual";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { GrillaCarriles } from "./grilla-carriles";

/** Ordena los turnos por hora de inicio. */
function ordenarPorHora(turnos: Turno[]): Turno[] {
  return [...turnos].sort((a, b) => {
    const ta = a.fecha_inicio ? new Date(a.fecha_inicio).getTime() : 0;
    const tb = b.fecha_inicio ? new Date(b.fecha_inicio).getTime() : 0;
    return ta - tb;
  });
}

export default function AgendaPage() {
  const [recursos, setRecursos] = useState<Recurso[]>([]);
  const [recursoId, setRecursoId] = useState<number | null>(null);
  const [dia, setDia] = useState<Date>(startOfDay(new Date()));
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [turnosDia, setTurnosDia] = useState<Turno[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turnoSel, setTurnoSel] = useState<Turno | null>(null);
  const [dialogAbierto, setDialogAbierto] = useState(false);

  const hoyEs = isToday(dia);

  const cargarRecursos = useCallback(async () => {
    try {
      const data = await listarRecursos();
      const personas = data.items.filter((r) => r.tipo === "persona");
      setRecursos(personas);
      if (personas.length > 0) {
        setRecursoId((actual) => actual ?? personas[0].id);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    }
  }, []);

  useEffect(() => {
    cargarRecursos();
  }, [cargarRecursos]);

  const cargarTurnos = useCallback(async () => {
    if (recursoId === null) return;
    setCargando(true);
    setError(null);
    try {
      const desde = startOfDay(dia).toISOString();
      const hasta = endOfDay(dia).toISOString();
      const [delRecurso, delDia] = await Promise.all([
        listarTurnos(recursoId, desde, hasta),
        listarTurnosDelDia(desde, hasta),
      ]);
      setTurnos(ordenarPorHora(delRecurso.items));
      setTurnosDia(delDia.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar turnos");
    } finally {
      setCargando(false);
    }
  }, [recursoId, dia]);

  useEffect(() => {
    cargarTurnos();
  }, [cargarTurnos]);

  const recursoActual = recursos.find((r) => r.id === recursoId);

  return (
    <div className="p-8">
      {/* Encabezado */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Agenda</h1>

        <div className="flex items-center gap-3">
          {recursos.length > 0 && (
            <Select
              value={recursoId ? String(recursoId) : undefined}
              onValueChange={(v) => setRecursoId(Number(v))}
            >
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Elegí un recurso" />
              </SelectTrigger>
              <SelectContent>
                {recursos.map((r) => (
                  <SelectItem key={r.id} value={String(r.id)}>
                    {r.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              onClick={() => setDia((d) => addDays(d, -1))}
              aria-label="Día anterior"
            >
              ‹
            </Button>
            <Button
              variant={hoyEs ? "default" : "outline"}
              size="sm"
              onClick={() => setDia(startOfDay(new Date()))}
            >
              Hoy
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => setDia((d) => addDays(d, 1))}
              aria-label="Día siguiente"
            >
              ›
            </Button>
          </div>

          <Button onClick={() => setDialogAbierto(true)}>
            <Plus size={16} className="mr-1" />
            Nuevo turno
          </Button>
        </div>
      </div>

      <MetricasDia turnos={turnosDia} />

      <p className="mb-4 text-sm font-medium capitalize text-muted-foreground">
        {format(dia, "EEEE d 'de' MMMM", { locale: es })}
        {recursoActual && ` · ${recursoActual.nombre}`}
        {cargando && " · cargando…"}
      </p>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}
      {/* Grilla de carriles (nueva) */}
      <div className="mb-6">
        <GrillaCarriles
          turnos={turnos}
          dia={dia}
          onClickTurno={(t) => setTurnoSel(t)}
        />
      </div>
      {/* Lista de turnos: una fila por turno, en orden de horario */}
      {!cargando && turnos.length === 0 ? (
        <div className="rounded-2xl border bg-card p-12 text-center">
          <p className="text-sm text-muted-foreground">
            {recursoActual?.nombre ?? "Este recurso"} no tiene turnos este día.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border bg-card">
          {turnos.map((turno, i) => {
            const color = colorEstadoHex(turno.estado);
            const inactivo = estaInactivo(turno.estado);
            return (
              <div
                key={turno.id}
                onClick={() => setTurnoSel(turno)}
                className={`flex cursor-pointer items-stretch transition-colors hover:bg-muted/50 ${
                  i > 0 ? "border-t" : ""
                }`}
                style={{ opacity: inactivo ? 0.6 : 1 }}
              >
                {/* Hora a la izquierda */}
                <div className="flex w-24 shrink-0 flex-col items-end justify-center border-r px-4 py-4">
                  <span
                    className="text-sm font-bold"
                    style={{
                      fontFamily: "Syne, sans-serif",
                      fontVariantNumeric: "lining-nums tabular-nums",
                    }}
                  >
                    {turno.fecha_inicio && horaDe(turno.fecha_inicio)}
                  </span>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {turno.fecha_fin && horaDe(turno.fecha_fin)}
                  </span>
                </div>

                {/* Barra de color (estado) */}
                <div
                  className="w-1 shrink-0"
                  style={{ backgroundColor: color }}
                />

                {/* Contenido */}
                <div className="flex min-w-0 flex-1 items-center gap-3 px-4 py-4">
                  <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold text-white"
                    style={{
                      backgroundColor: color,
                      fontFamily: "Syne, sans-serif",
                    }}
                  >
                    {inicialDe(turno.cliente_nombre)}
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span
                      className={`truncate text-sm font-semibold ${
                        inactivo ? "line-through" : ""
                      }`}
                    >
                      {turno.cliente_nombre}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {turno.servicio_nombre ?? "Sin servicio"}
                      {turno.es_sobreturno && " · sobreturno"}
                    </span>
                  </div>
                  <span
                    className="shrink-0 rounded-full px-2.5 py-1 text-xs font-medium"
                    style={{ backgroundColor: `${color}22`, color: color }}
                  >
                    {labelEstado(turno.estado)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Leyenda */}
      <div className="mt-4 flex flex-wrap gap-4 text-xs text-muted-foreground">
        {(["pendiente", "confirmado", "en_curso", "finalizado", "cancelado"] as const).map(
          (e) => (
            <span key={e} className="flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: colorEstadoHex(e) }}
              />
              {labelEstado(e)}
            </span>
          ),
        )}
      </div>

      {/* Panel de detalle del turno */}
      <TurnoDetalle
        turno={turnoSel}
        abierto={turnoSel !== null}
        onCerrar={() => setTurnoSel(null)}
        onCambio={cargarTurnos}
      />

      {/* Diálogo de nuevo turno */}
      <NuevoTurnoDialog
        abierto={dialogAbierto}
        onCerrar={() => setDialogAbierto(false)}
        onCreado={cargarTurnos}
        recursoInicial={recursoId}
        fechaInicial={dia}
      />
    </div>
  );
}