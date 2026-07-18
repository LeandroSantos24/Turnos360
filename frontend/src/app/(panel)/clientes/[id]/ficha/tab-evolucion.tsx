"use client";

/**
 * Tab "Evolución" de la ficha: los controles/consultas de seguimiento.
 * Es el registro de cómo viene el paciente: cómo se sintió, apetito,
 * entrenamiento, descanso, y la prescripción de la consulta.
 */

import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import {
  listarEntradas,
  crearEntrada,
  borrarEntrada,
  Entrada,
} from "@/lib/ficha-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Seccion, CampoArea, BotonBorrar, fechaLegible, hoyISO } from "./comunes";

const TIPOS: [string, string][] = [
  ["primera_consulta", "Primera consulta"],
  ["control", "Control"],
  ["antropometria", "Antropometría"],
];

const CAMPOS_TEXTO: [keyof FormEntrada, string][] = [
  ["como_se_sintio", "¿Cómo se sintió?"],
  ["noto_diferencia", "¿Notó diferencias?"],
  ["apetito", "Apetito"],
  ["entrenamiento", "Entrenamiento"],
  ["descanso", "Descanso / sueño"],
  ["estres", "Estrés"],
  ["resumen_antropometria", "Resumen antropometría"],
  ["prescripcion", "Prescripción / indicaciones"],
];

type FormEntrada = {
  fecha: string;
  tipo: string;
  como_se_sintio: string;
  noto_diferencia: string;
  apetito: string;
  entrenamiento: string;
  descanso: string;
  estres: string;
  resumen_antropometria: string;
  prescripcion: string;
  proximo_turno: string;
};

const VACIA = (): FormEntrada => ({
  fecha: hoyISO(),
  tipo: "control",
  como_se_sintio: "",
  noto_diferencia: "",
  apetito: "",
  entrenamiento: "",
  descanso: "",
  estres: "",
  resumen_antropometria: "",
  prescripcion: "",
  proximo_turno: "",
});

function etiquetaTipo(tipo: string): string {
  return TIPOS.find(([v]) => v === tipo)?.[1] ?? tipo;
}

export function TabEvolucion({ clienteId }: { clienteId: number }) {
  const [entradas, setEntradas] = useState<Entrada[]>([]);
  const [cargando, setCargando] = useState(true);
  const [mostrarForm, setMostrarForm] = useState(false);
  const [form, setForm] = useState<FormEntrada>(VACIA());
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setEntradas(await listarEntradas(clienteId));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudieron cargar los controles");
    } finally {
      setCargando(false);
    }
  }, [clienteId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const set = (campo: keyof FormEntrada, valor: string) =>
    setForm((f) => ({ ...f, [campo]: valor }));

  async function guardar() {
    if (!form.fecha) {
      toast.error("Poné la fecha del control");
      return;
    }
    setGuardando(true);
    try {
      const limpio = (s: string) => (s.trim() === "" ? null : s.trim());
      await crearEntrada(clienteId, {
        fecha: form.fecha,
        tipo: form.tipo,
        como_se_sintio: limpio(form.como_se_sintio),
        noto_diferencia: limpio(form.noto_diferencia),
        apetito: limpio(form.apetito),
        entrenamiento: limpio(form.entrenamiento),
        descanso: limpio(form.descanso),
        estres: limpio(form.estres),
        resumen_antropometria: limpio(form.resumen_antropometria),
        prescripcion: limpio(form.prescripcion),
        proximo_turno: form.proximo_turno || null,
      });
      toast.success("Control registrado");
      setForm(VACIA());
      setMostrarForm(false);
      cargar();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  async function borrar(id: number) {
    try {
      await borrarEntrada(clienteId, id);
      setEntradas((lista) => lista.filter((e) => e.id !== id));
      toast.success("Control borrado");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo borrar");
    }
  }

  return (
    <div className="space-y-6">
      {/* Alta */}
      {!mostrarForm ? (
        <Button onClick={() => setMostrarForm(true)}>
          <Plus className="mr-1.5 h-4 w-4" /> Nuevo control
        </Button>
      ) : (
        <Seccion titulo="Nuevo control">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Fecha</Label>
              <Input type="date" value={form.fecha} onChange={(e) => set("fecha", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Tipo</Label>
              <select
                value={form.tipo}
                onChange={(e) => set("tipo", e.target.value)}
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
              >
                {TIPOS.map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Próximo turno (sugerido)</Label>
              <Input type="date" value={form.proximo_turno} onChange={(e) => set("proximo_turno", e.target.value)} />
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {CAMPOS_TEXTO.map(([clave, label]) => (
              <CampoArea
                key={clave}
                label={label}
                valor={form[clave]}
                onChange={(v) => set(clave, v)}
              />
            ))}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => { setMostrarForm(false); setForm(VACIA()); }}>
              Cancelar
            </Button>
            <Button onClick={guardar} disabled={guardando}>
              {guardando ? "Guardando…" : "Guardar control"}
            </Button>
          </div>
        </Seccion>
      )}

      {/* Lista */}
      {cargando ? (
        <p className="text-sm text-muted-foreground">Cargando controles…</p>
      ) : entradas.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Todavía no hay controles. El primero suele ser la primera consulta.
        </p>
      ) : (
        <div className="space-y-3">
          {entradas.map((e) => (
            <div key={e.id} className="rounded-2xl border bg-card p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-semibold tabular-nums">{fechaLegible(e.fecha)}</span>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    {etiquetaTipo(e.tipo)}
                  </span>
                  {e.proximo_turno && (
                    <span className="text-xs text-muted-foreground">
                      Próximo: {fechaLegible(e.proximo_turno)}
                    </span>
                  )}
                </div>
                <BotonBorrar onConfirm={() => borrar(e.id)} />
              </div>
              <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2">
                {CAMPOS_TEXTO.map(([clave, label]) => {
                  const valor = e[clave as keyof Entrada] as string | null;
                  if (!valor) return null;
                  return (
                    <div key={clave}>
                      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                        {label}
                      </dt>
                      <dd className="whitespace-pre-line text-sm">{valor}</dd>
                    </div>
                  );
                })}
              </dl>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
