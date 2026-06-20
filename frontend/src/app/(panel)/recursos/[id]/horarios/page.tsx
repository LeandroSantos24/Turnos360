"use client";

/**
 * Configuración del horario de atención de un recurso (/recursos/[id]/horarios).
 *
 * Una tarjeta por día (lunes a domingo). Cada día puede tener varias franjas
 * (ej. 9–13 y 16–20 para el corte de mediodía). Se agregan y se quitan franjas;
 * para "editar" una, se borra y se crea de nuevo. Un día sin franjas = cerrado.
 */

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Plus, X } from "lucide-react";
import { toast } from "sonner";

import { obtenerRecurso, Recurso } from "@/lib/recursos-api";
import {
  listarHorarios,
  agregarHorario,
  eliminarHorario,
  Horario,
} from "@/lib/horarios-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
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

export default function HorariosRecursoPage() {
  const params = useParams();
  const router = useRouter();
  const recursoId = Number(params.id);

  const [recurso, setRecurso] = useState<Recurso | null>(null);
  const [horarios, setHorarios] = useState<Horario[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form "agregar franja" por día: { [dia]: { desde, hasta } }
  const [nuevos, setNuevos] = useState<Record<number, { desde: string; hasta: string }>>({});

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const [r, h] = await Promise.all([
        obtenerRecurso(recursoId),
        listarHorarios(recursoId),
      ]);
      setRecurso(r);
      setHorarios(h);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, [recursoId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  /** Lee el form de un día, con valores por defecto si está vacío. */
  function formDe(dia: number) {
    return nuevos[dia] ?? { desde: "09:00", hasta: "13:00" };
  }

  function setForm(dia: number, campo: "desde" | "hasta", valor: string) {
    setNuevos((prev) => ({
      ...prev,
      [dia]: { ...formDe(dia), [campo]: valor },
    }));
  }

  async function agregar(dia: number) {
    const { desde, hasta } = formDe(dia);
    if (hasta <= desde) {
      toast.error("La hora de fin debe ser posterior a la de inicio");
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
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">Cargando horarios…</p>
      </div>
    );
  }

  if (error || !recurso) {
    return (
      <div className="p-8">
        <Button variant="outline" size="sm" onClick={() => router.back()}>
          <ArrowLeft size={16} className="mr-1" /> Volver
        </Button>
        <p className="mt-4 text-sm text-destructive">
          {error ?? "Recurso no encontrado"}
        </p>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Barra superior */}
      <div className="mb-4">
        <Button
          variant="ghost"
          size="sm"
          className="-ml-2"
          onClick={() => router.back()}
        >
          <ArrowLeft size={16} className="mr-1" /> Volver
        </Button>
      </div>

      {/* Cabecera */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Horarios de atención</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {recurso.nombre} · agregá una o varias franjas por día. Un día sin
          franjas queda cerrado.
        </p>
      </div>

      {/* Una tarjeta por día */}
      <div className="grid gap-3">
        {DIAS.map((nombre, dia) => {
          const franjas = horarios
            .filter((h) => h.dia_semana === dia)
            .sort((a, b) => a.hora_desde.localeCompare(b.hora_desde));
          const form = formDe(dia);

          return (
            <div key={dia} className="rounded-2xl border bg-card p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <span className="w-28 font-semibold">{nombre}</span>

                {/* Franjas existentes */}
                <div className="flex flex-1 flex-wrap items-center gap-2">
                  {franjas.length === 0 ? (
                    <span className="text-sm text-muted-foreground">
                      Cerrado
                    </span>
                  ) : (
                    franjas.map((h) => (
                      <span
                        key={h.id}
                        className="inline-flex items-center gap-1.5 rounded-full bg-muted px-3 py-1 text-sm tabular-nums"
                      >
                        {horaCorta(h.hora_desde)} – {horaCorta(h.hora_hasta)}
                        <button
                          onClick={() => quitar(h)}
                          className="text-muted-foreground hover:text-destructive"
                          aria-label="Quitar franja"
                        >
                          <X size={14} />
                        </button>
                      </span>
                    ))
                  )}
                </div>

                {/* Form para agregar */}
                <div className="flex items-center gap-2">
                  <Select
                    value={form.desde}
                    onValueChange={(v) => setForm(dia, "desde", v)}
                  >
                    <SelectTrigger className="w-24 tabular-nums">
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
                  <span className="text-muted-foreground">–</span>
                  <Select
                    value={form.hasta}
                    onValueChange={(v) => setForm(dia, "hasta", v)}
                  >
                    <SelectTrigger className="w-24 tabular-nums">
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
                  <Button
                    size="icon"
                    variant="outline"
                    className="h-9 w-9 shrink-0"
                    onClick={() => agregar(dia)}
                    aria-label="Agregar franja"
                  >
                    <Plus size={16} />
                  </Button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}