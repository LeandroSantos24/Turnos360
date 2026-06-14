"use client";

/**
 * Agenda visual (/agenda) — Etapa A: la grilla.
 *
 * Selector de día + selector de barbero, y una grilla de horarios de 9 a 19
 * en franjas de 30 min. Los turnos se pintan en la Etapa B.
 */

import { useEffect, useState, useCallback } from "react";
import { addDays, format, startOfDay } from "date-fns";
import { es } from "date-fns/locale";

import { listarRecursos, Recurso } from "@/lib/recursos-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// La grilla va de 9 a 19 hs, en franjas de 30 minutos.
const HORA_INICIO = 9;
const HORA_FIN = 19;
const FRANJA_MIN = 30;

/** Genera las etiquetas de hora: "09:00", "09:30", … "18:30". */
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

export default function AgendaPage() {
  const [recursos, setRecursos] = useState<Recurso[]>([]);
  const [recursoId, setRecursoId] = useState<number | null>(null);
  const [dia, setDia] = useState<Date>(startOfDay(new Date()));
  const [error, setError] = useState<string | null>(null);

  const franjas = generarFranjas();

  // Cargar los recursos (para el selector de barbero).
  const cargarRecursos = useCallback(async () => {
    setError(null);
    try {
      const data = await listarRecursos();
      const personas = data.items.filter((r) => r.tipo === "persona");
      setRecursos(personas);
      // Seleccionar el primero por defecto
      if (personas.length > 0 && recursoId === null) {
        setRecursoId(personas[0].id);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    cargarRecursos();
  }, [cargarRecursos]);

  const recursoActual = recursos.find((r) => r.id === recursoId);

  return (
    <div className="p-8">
      {/* Encabezado con los controles */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Agenda</h1>

        <div className="flex items-center gap-3">
          {/* Selector de barbero */}
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

          {/* Navegación de día */}
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDia((d) => addDays(d, -1))}
            >
              ◄
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDia(startOfDay(new Date()))}
            >
              Hoy
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDia((d) => addDays(d, 1))}
            >
              ►
            </Button>
          </div>
        </div>
      </div>

      {/* Fecha seleccionada, legible */}
      <p className="mb-4 text-sm capitalize text-muted-foreground">
        {format(dia, "EEEE d 'de' MMMM yyyy", { locale: es })}
        {recursoActual && ` · ${recursoActual.nombre}`}
      </p>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* La grilla de horarios */}
      <div className="overflow-hidden rounded-md border">
        {franjas.map((hora) => (
          <div
            key={hora}
            className="flex items-stretch border-b last:border-b-0"
          >
            {/* Columna de hora */}
            <div className="w-20 shrink-0 border-r bg-muted/20 px-3 py-3 text-sm text-muted-foreground">
              {hora}
            </div>
            {/* Celda del turno (vacía por ahora) */}
            <div className="min-h-[3rem] flex-1 px-3 py-2 hover:bg-muted/10">
              {/* Etapa B: acá van los turnos */}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}