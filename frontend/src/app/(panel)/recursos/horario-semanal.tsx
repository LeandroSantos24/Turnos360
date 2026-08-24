"use client";

/**
 * Horario semanal de UN recurso: una tarjeta por día, con sus franjas.
 *
 * Vive en su propio componente porque lo usan dos pantallas:
 *   · /recursos          — abajo de la lista, para el recurso seleccionado.
 *   · /recursos/[id]/horarios — la página suelta (links viejos, marcadores).
 *
 * Un día puede tener varias franjas (9–13 y 16–20 para el corte de mediodía).
 * Para "editar" una franja se borra y se crea de nuevo: son pocas y cambian
 * poco, y un editor in-situ costaba más de lo que resolvía.
 * Un día sin franjas queda cerrado.
 */

import { useCallback, useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import { toast } from "sonner";

import {
  agregarHorario,
  eliminarHorario,
  Horario,
  listarHorarios,
} from "@/lib/horarios-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/** Nombres de los días, índice 0=lunes … 6=domingo (igual que el backend). */
const DIAS = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
];

/** "09:00:00" → "09:00" para mostrar lindo. */
function horaCorta(s: string): string {
  return s.slice(0, 5);
}

/** Opciones de hora en formato 24h, cada 30 min: "00:00", "00:30" … "23:30". */
const HORAS: string[] = [];
for (let h = 0; h < 24; h++) {
  HORAS.push(`${String(h).padStart(2, "0")}:00`);
  HORAS.push(`${String(h).padStart(2, "0")}:30`);
}

export function HorarioSemanal({ recursoId }: { recursoId: number }) {
  const [horarios, setHorarios] = useState<Horario[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form "agregar franja" por día: { [dia]: { desde, hasta } }
  const [nuevos, setNuevos] = useState<
    Record<number, { desde: string; hasta: string }>
  >({});

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      setHorarios(await listarHorarios(recursoId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, [recursoId]);

  useEffect(() => {
    // Al cambiar de recurso se limpian los borradores del formulario: si no,
    // las horas tipeadas para un barbero aparecían en el siguiente.
    setNuevos({});
    cargar();
  }, [cargar]);

  function formDe(dia: number) {
    return nuevos[dia] ?? { desde: "09:00", hasta: "13:00" };
  }

  function setForm(dia: number, campo: "desde" | "hasta", valor: string) {
    setNuevos((prev) => ({ ...prev, [dia]: { ...formDe(dia), [campo]: valor } }));
  }

  async function agregar(dia: number) {
    const { desde, hasta } = formDe(dia);
    if (hasta <= desde) {
      toast.error("La hora de fin tiene que ser posterior a la de inicio");
      return;
    }
    try {
      await agregarHorario(recursoId, {
        dia_semana: dia,
        hora_desde: desde,
        hora_hasta: hasta,
      });
      toast.success(`Franja agregada al ${DIAS[dia].toLowerCase()}`);
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo agregar");
    }
  }

  async function quitar(h: Horario) {
    try {
      await eliminarHorario(recursoId, h.id);
      toast.success("Franja eliminada");
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo borrar");
    }
  }

  if (cargando) {
    return <p className="text-sm text-muted-foreground">Cargando horarios…</p>;
  }

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>;
  }

  return (
    <div className="grid gap-3">
      {DIAS.map((nombre, dia) => {
        const franjas = horarios
          .filter((h) => h.dia_semana === dia)
          .sort((a, b) => a.hora_desde.localeCompare(b.hora_desde));
        const form = formDe(dia);
        const cerrado = franjas.length === 0;

        return (
          <div
            key={dia}
            className={`rounded-2xl border p-4 ${cerrado ? "bg-muted/30" : "bg-card"}`}
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              {/* Día + franjas cargadas */}
              <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center">
                <span className="w-28 shrink-0 font-semibold">{nombre}</span>
                <div className="flex flex-wrap items-center gap-2">
                  {cerrado ? (
                    <span className="text-sm text-muted-foreground">Cerrado</span>
                  ) : (
                    franjas.map((h) => (
                      <span
                        key={h.id}
                        className="inline-flex items-center gap-1.5 rounded-full bg-muted px-3 py-1 text-sm tabular-nums"
                      >
                        {horaCorta(h.hora_desde)} – {horaCorta(h.hora_hasta)}
                        <button
                          type="button"
                          onClick={() => quitar(h)}
                          className="text-muted-foreground hover:text-destructive"
                          aria-label={`Quitar la franja de ${horaCorta(h.hora_desde)} a ${horaCorta(h.hora_hasta)} del ${nombre.toLowerCase()}`}
                        >
                          <X size={14} />
                        </button>
                      </span>
                    ))
                  )}
                </div>
              </div>

              {/* Agregar una franja. Los dos combos van rotulados a propósito:
                  sin "Desde" y "Hasta" arriba, son dos desplegables iguales y
                  hay que adivinar cuál es cuál. */}
              <div className="flex items-end gap-2">
                <div className="space-y-1">
                  <Label
                    htmlFor={`desde-${dia}`}
                    className="text-xs text-muted-foreground"
                  >
                    Desde
                  </Label>
                  <Select
                    value={form.desde}
                    onValueChange={(v) => v && setForm(dia, "desde", v)}
                  >
                    <SelectTrigger id={`desde-${dia}`} className="w-24 tabular-nums">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {HORAS.map((hh) => (
                        <SelectItem key={hh} value={hh} className="tabular-nums">
                          {hh}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label
                    htmlFor={`hasta-${dia}`}
                    className="text-xs text-muted-foreground"
                  >
                    Hasta
                  </Label>
                  <Select
                    value={form.hasta}
                    onValueChange={(v) => v && setForm(dia, "hasta", v)}
                  >
                    <SelectTrigger id={`hasta-${dia}`} className="w-24 tabular-nums">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {HORAS.map((hh) => (
                        <SelectItem key={hh} value={hh} className="tabular-nums">
                          {hh}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-9 shrink-0"
                  onClick={() => agregar(dia)}
                >
                  <Plus size={16} className="mr-1" />
                  Agregar
                </Button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
