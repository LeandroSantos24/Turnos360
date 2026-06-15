"use client";

/**
 * Agenda visual (/agenda) — Etapa B: con los turnos pintados.
 *
 * Trae los turnos del recurso para el día elegido y los dibuja como bloques
 * posicionados sobre la grilla, según su hora de inicio y duración.
 */

import { useEffect, useState, useCallback } from "react";
import { addDays, format, startOfDay, endOfDay } from "date-fns";
import { es } from "date-fns/locale";

import { listarRecursos, Recurso } from "@/lib/recursos-api";
import { listarTurnos, Turno } from "@/lib/turnos-api";
import { colorEstado, labelEstado, horaDe } from "@/lib/turno-visual";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const HORA_INICIO = 9;
const HORA_FIN = 19;
const FRANJA_MIN = 30;
const ALTO_FRANJA = 48; // píxeles por franja de 30 min

function generarFranjas(): string[] {
  const franjas: string[] = [];
  for (let h = HORA_INICIO; h < HORA_FIN; h++) {
    for (let m = 0; m < 60; m += FRANJA_MIN) {
      franjas.push(
        `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`,
      );
    }
  }
  return franjas;
}

/**
 * Calcula la posición vertical (top) y la altura de un turno en píxeles,
 * según su hora de inicio y fin relativas al comienzo de la grilla.
 */
function posicionTurno(turno: Turno): { top: number; alto: number } | null {
  if (!turno.fecha_inicio || !turno.fecha_fin) return null;

  const ini = new Date(turno.fecha_inicio);
  const fin = new Date(turno.fecha_fin);

  // Minutos desde el inicio de la grilla (9:00)
  const minDesdeInicio =
    (ini.getHours() - HORA_INICIO) * 60 + ini.getMinutes();
  const duracionMin = (fin.getTime() - ini.getTime()) / 60000;

  // Si el turno cae fuera del rango visible, no lo mostramos
  if (minDesdeInicio < 0) return null;

  const pxPorMin = ALTO_FRANJA / FRANJA_MIN;
  return {
    top: minDesdeInicio * pxPorMin,
    alto: Math.max(duracionMin * pxPorMin, 24), // mínimo 24px para que se lea
  };
}

export default function AgendaPage() {
  const [recursos, setRecursos] = useState<Recurso[]>([]);
  const [recursoId, setRecursoId] = useState<number | null>(null);
  const [dia, setDia] = useState<Date>(startOfDay(new Date()));
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const franjas = generarFranjas();

  // Cargar recursos (selector de barbero)
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

  // Cargar turnos del día/recurso elegido
  const cargarTurnos = useCallback(async () => {
    if (recursoId === null) return;
    setCargando(true);
    setError(null);
    try {
      const desde = startOfDay(dia).toISOString();
      const hasta = endOfDay(dia).toISOString();
      const data = await listarTurnos(recursoId, desde, hasta);
      setTurnos(data.items);
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
            <Button variant="outline" size="sm" onClick={() => setDia((d) => addDays(d, -1))}>
              ◄
            </Button>
            <Button variant="outline" size="sm" onClick={() => setDia(startOfDay(new Date()))}>
              Hoy
            </Button>
            <Button variant="outline" size="sm" onClick={() => setDia((d) => addDays(d, 1))}>
              ►
            </Button>
          </div>
        </div>
      </div>

      <p className="mb-4 text-sm capitalize text-muted-foreground">
        {format(dia, "EEEE d 'de' MMMM yyyy", { locale: es })}
        {recursoActual && ` · ${recursoActual.nombre}`}
        {cargando && " · cargando…"}
      </p>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* La grilla, con los turnos posicionados encima */}
      <div className="overflow-hidden rounded-md border">
        <div className="relative flex">
          {/* Columna de horas */}
          <div className="w-20 shrink-0 border-r bg-muted/20">
            {franjas.map((hora) => (
              <div
                key={hora}
                className="px-3 text-sm text-muted-foreground"
                style={{ height: ALTO_FRANJA, lineHeight: `${ALTO_FRANJA}px` }}
              >
                {hora}
              </div>
            ))}
          </div>

          {/* Área de turnos */}
          <div className="relative flex-1">
            {/* Líneas de fondo (una por franja) */}
            {franjas.map((hora) => (
              <div
                key={hora}
                className="border-b last:border-b-0"
                style={{ height: ALTO_FRANJA }}
              />
            ))}

            {/* Los turnos, posicionados de forma absoluta */}
            {turnos.map((turno) => {
              const pos = posicionTurno(turno);
              if (!pos) return null;
              return (
                <div
                  key={turno.id}
                  className={`absolute left-1 right-1 overflow-hidden rounded border px-2 py-1 text-xs ${colorEstado(
                    turno.estado,
                  )}`}
                  style={{ top: pos.top + 1, height: pos.alto - 2 }}
                  title={`${turno.cliente_nombre} · ${labelEstado(turno.estado)}`}
                >
                  <div className="font-medium">
                    {turno.fecha_inicio && horaDe(turno.fecha_inicio)}{" "}
                    {turno.cliente_nombre}
                  </div>
                  {turno.servicio_nombre && (
                    <div className="truncate opacity-80">
                      {turno.servicio_nombre}
                      {turno.es_sobreturno && " · sobreturno"}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Leyenda de estados */}
      <div className="mt-4 flex flex-wrap gap-3 text-xs text-muted-foreground">
        {(["pendiente", "confirmado", "en_curso", "finalizado", "cancelado"] as const).map(
          (e) => (
            <span key={e} className="flex items-center gap-1.5">
              <span className={`inline-block h-3 w-3 rounded border ${colorEstado(e)}`} />
              {labelEstado(e)}
            </span>
          ),
        )}
      </div>
    </div>
  );
}