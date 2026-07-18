"use client";

/**
 * Tab "Mediciones" de la ficha: antropometría por fecha + evolución graficada.
 * IMC y sumatoria de pliegues los calcula el backend si no se cargan.
 * El detalle completo del informe ISAK vive en el PDF (tab Adjuntos);
 * acá van los valores que Giuliana quiere VER y COMPARAR en el tiempo.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import {
  listarMediciones,
  crearMedicion,
  borrarMedicion,
  Medicion,
  MedicionCrear,
} from "@/lib/ficha-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { GraficoLinea } from "@/components/graficos/linea";
import { Seccion, CampoNum, BotonBorrar, fechaLegible, hoyISO } from "./comunes";

/** Los campos numéricos del form, agrupados como se cargan en consulta. */
const GRUPOS_CAMPOS: { titulo: string; campos: [string, string, string?][] }[] = [
  {
    titulo: "Básicas",
    campos: [
      ["peso_kg", "Peso", "kg"],
      ["talla_cm", "Talla", "cm"],
      ["talla_sentado_cm", "Talla sentado", "cm"],
      ["envergadura_cm", "Envergadura", "cm"],
    ],
  },
  {
    titulo: "Pliegues (mm)",
    campos: [
      ["pl_triceps", "Tríceps"],
      ["pl_subescapular", "Subescapular"],
      ["pl_biceps", "Bíceps"],
      ["pl_cresta_iliaca", "Cresta ilíaca"],
      ["pl_supraespinal", "Supraespinal"],
      ["pl_abdominal", "Abdominal"],
      ["pl_muslo", "Muslo"],
      ["pl_pierna", "Pierna"],
    ],
  },
  {
    titulo: "Perímetros (cm)",
    campos: [
      ["per_cintura", "Cintura"],
      ["per_cadera", "Cadera"],
      ["per_brazo", "Brazo"],
      ["per_muslo", "Muslo"],
      ["per_pierna", "Pierna"],
    ],
  },
  {
    titulo: "Composición corporal",
    campos: [
      ["masa_grasa_kg", "Masa grasa", "kg"],
      ["masa_grasa_pct", "Masa grasa", "%"],
      ["masa_muscular_kg", "Masa muscular", "kg"],
      ["masa_osea_kg", "Masa ósea", "kg"],
    ],
  },
];

/** Métricas graficables (las que pidió ver comparadas en el tiempo). */
const METRICAS: { clave: keyof Medicion; label: string; unidad: string }[] = [
  { clave: "peso_kg", label: "Peso", unidad: " kg" },
  { clave: "imc", label: "IMC", unidad: "" },
  { clave: "per_cintura", label: "Cintura", unidad: " cm" },
  { clave: "sumatoria_pliegues", label: "Σ pliegues", unidad: " mm" },
  { clave: "masa_grasa_pct", label: "% grasa", unidad: " %" },
  { clave: "masa_muscular_kg", label: "Masa muscular", unidad: " kg" },
];

type FormNums = Record<string, string>;

export function TabMediciones({ clienteId }: { clienteId: number }) {
  const [mediciones, setMediciones] = useState<Medicion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [mostrarForm, setMostrarForm] = useState(false);
  const [fecha, setFecha] = useState(hoyISO());
  const [evaluador, setEvaluador] = useState("");
  const [origen, setOrigen] = useState("manual");
  const [nums, setNums] = useState<FormNums>({});
  const [guardando, setGuardando] = useState(false);
  const [metrica, setMetrica] = useState<(typeof METRICAS)[number]>(METRICAS[0]);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setMediciones(await listarMediciones(clienteId));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudieron cargar las mediciones");
    } finally {
      setCargando(false);
    }
  }, [clienteId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const setNum = (clave: string, valor: string) =>
    setNums((n) => ({ ...n, [clave]: valor }));

  // Vista previa del IMC mientras se carga (el backend recalcula igual).
  const imcPreview = useMemo(() => {
    const peso = parseFloat(nums.peso_kg ?? "");
    const talla =
      parseFloat(nums.talla_cm ?? "") ||
      [...mediciones].reverse().find((m) => m.talla_cm != null)?.talla_cm ||
      NaN;
    if (!peso || !talla) return null;
    const metros = Number(talla) / 100;
    return (peso / (metros * metros)).toFixed(2);
  }, [nums.peso_kg, nums.talla_cm, mediciones]);

  async function guardar() {
    if (!fecha) {
      toast.error("Poné la fecha de la medición");
      return;
    }
    const payload: MedicionCrear = { fecha, origen };
    if (evaluador.trim()) payload.evaluador = evaluador.trim();
    let alguno = false;
    for (const grupo of GRUPOS_CAMPOS) {
      for (const [clave] of grupo.campos) {
        const v = (nums[clave] ?? "").trim();
        if (v !== "" && !Number.isNaN(Number(v))) {
          (payload as Record<string, unknown>)[clave] = Number(v);
          alguno = true;
        }
      }
    }
    if (!alguno) {
      toast.error("Cargá al menos una medición");
      return;
    }
    setGuardando(true);
    try {
      await crearMedicion(clienteId, payload);
      toast.success("Medición guardada");
      setNums({});
      setEvaluador("");
      setFecha(hoyISO());
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
      await borrarMedicion(clienteId, id);
      setMediciones((lista) => lista.filter((m) => m.id !== id));
      toast.success("Medición borrada");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo borrar");
    }
  }

  const datosGrafico = mediciones
    .filter((m) => m[metrica.clave] != null)
    .map((m) => ({ fecha: m.fecha, valor: Number(m[metrica.clave]) }));

  const tabla = [...mediciones].reverse(); // más reciente arriba

  return (
    <div className="space-y-6">
      {/* Alta */}
      {!mostrarForm ? (
        <Button onClick={() => setMostrarForm(true)}>
          <Plus className="mr-1.5 h-4 w-4" /> Nueva medición
        </Button>
      ) : (
        <Seccion titulo="Nueva medición">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Fecha</Label>
              <Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Evaluador</Label>
              <Input value={evaluador} onChange={(e) => setEvaluador(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Origen</Label>
              <select
                value={origen}
                onChange={(e) => setOrigen(e.target.value)}
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
              >
                <option value="manual">Manual</option>
                <option value="isakmetry">Informe ISAK</option>
              </select>
            </div>
          </div>

          {GRUPOS_CAMPOS.map((grupo) => (
            <div key={grupo.titulo}>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {grupo.titulo}
              </p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {grupo.campos.map(([clave, label, sufijo]) => (
                  <CampoNum
                    key={clave}
                    label={label}
                    sufijo={sufijo}
                    valor={nums[clave] ?? ""}
                    onChange={(v) => setNum(clave, v)}
                  />
                ))}
              </div>
            </div>
          ))}

          <p className="text-xs text-muted-foreground">
            {imcPreview
              ? `IMC calculado: ${imcPreview} (el sistema lo guarda solo).`
              : "El IMC y la sumatoria de pliegues se calculan solos al guardar."}
          </p>

          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => { setMostrarForm(false); setNums({}); }}>
              Cancelar
            </Button>
            <Button onClick={guardar} disabled={guardando}>
              {guardando ? "Guardando…" : "Guardar medición"}
            </Button>
          </div>
        </Seccion>
      )}

      {/* Evolución graficada */}
      {mediciones.length > 0 && (
        <Seccion titulo="Evolución">
          <div className="flex flex-wrap gap-2">
            {METRICAS.map((m) => (
              <button
                key={m.clave}
                type="button"
                onClick={() => setMetrica(m)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  metrica.clave === m.clave
                    ? "border-primary bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <GraficoLinea datos={datosGrafico} unidad={metrica.unidad} />
        </Seccion>
      )}

      {/* Tabla resumen */}
      {cargando ? (
        <p className="text-sm text-muted-foreground">Cargando mediciones…</p>
      ) : mediciones.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Todavía no hay mediciones. Cargá la primera toma para empezar a ver la evolución.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border bg-card">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2.5">Fecha</th>
                <th className="px-4 py-2.5">Peso</th>
                <th className="px-4 py-2.5">IMC</th>
                <th className="px-4 py-2.5">Cintura</th>
                <th className="px-4 py-2.5">Σ pliegues</th>
                <th className="px-4 py-2.5">% grasa</th>
                <th className="px-4 py-2.5">Origen</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {tabla.map((m) => (
                <tr key={m.id} className="border-b last:border-0">
                  <td className="px-4 py-2.5 font-medium">{fechaLegible(m.fecha)}</td>
                  <td className="px-4 py-2.5">{m.peso_kg != null ? `${m.peso_kg} kg` : "—"}</td>
                  <td className="px-4 py-2.5">{m.imc ?? "—"}</td>
                  <td className="px-4 py-2.5">{m.per_cintura != null ? `${m.per_cintura} cm` : "—"}</td>
                  <td className="px-4 py-2.5">{m.sumatoria_pliegues != null ? `${m.sumatoria_pliegues} mm` : "—"}</td>
                  <td className="px-4 py-2.5">{m.masa_grasa_pct != null ? `${m.masa_grasa_pct} %` : "—"}</td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground">
                    {m.origen === "isakmetry" ? "ISAK" : "Manual"}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <BotonBorrar onConfirm={() => borrar(m.id)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
