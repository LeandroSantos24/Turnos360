"use client";

/**
 * Agenda visual (/agenda) — vista de lista (una fila por turno).
 *
 * En vez de posicionar bloques por hora (frágil y se solapan), mostramos los
 * turnos como filas ordenadas por horario, una debajo de la otra. Cada fila:
 * hora a la izquierda + barra de color + avatar + cliente y servicio.
 * Imposible que se descuadre: es flujo natural, no posición absoluta.
 */

import { useEffect, useState, useCallback } from "react";
import { addDays, format, startOfDay, endOfDay } from "date-fns";
import { isToday } from "date-fns/isToday";
import { es } from "date-fns/locale";

import { listarRecursos, Recurso } from "@/lib/recursos-api";
import { listarTurnos, listarTurnosDelDia, Turno } from "@/lib/turnos-api";
import { MetricasDia } from "./metricas-dia";
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
        <h1 className="text-2xl font-semibold">Agenda</h1>

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

      {/* Lista de turnos: una fila por turno, en orden de horario */}
      {!cargando && turnos.length === 0 ? (
        <p className="rounded-lg border bg-background p-8 text-center text-sm text-muted-foreground">
          {recursoActual?.nombre ?? "Este recurso"} no tiene turnos este día.
        </p>
      ) : (
        <div className="overflow-hidden rounded-lg border bg-background">
          {turnos.map((turno, i) => {
            const color = colorEstadoHex(turno.estado);
            const inactivo = estaInactivo(turno.estado);
            return (
              <div
                key={turno.id}
                className={`flex cursor-pointer items-stretch transition-colors hover:bg-muted/40 ${
                  i > 0 ? "border-t" : ""
                }`}
                style={{ opacity: inactivo ? 0.6 : 1 }}
              >
                {/* Hora a la izquierda */}
                <div className="flex w-24 shrink-0 flex-col items-end justify-center border-r px-3 py-3">
                  <span className="text-sm font-semibold">
                    {turno.fecha_inicio && horaDe(turno.fecha_inicio)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {turno.fecha_fin && horaDe(turno.fecha_fin)}
                  </span>
                </div>

                {/* Barra de color (estado) */}
                <div
                  className="w-1.5 shrink-0"
                  style={{ backgroundColor: color }}
                />

                {/* Contenido */}
                <div className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3">
                  {/* Avatar */}
                  <div
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white"
                    style={{ backgroundColor: color }}
                  >
                    {inicialDe(turno.cliente_nombre)}
                  </div>
                  {/* Cliente + servicio */}
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
                  {/* Estado (etiqueta a la derecha) */}
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
    </div>
  );
}