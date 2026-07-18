"use client";

/**
 * Tab "Anamnesis" de la ficha: la entrevista de primera consulta.
 *
 * Mejoras sobre la versión original, pedidas en la entrevista con Giuliana:
 * - "Notas de entrevista" arriba de todo: el borrador libre para cuando el
 *   paciente cuenta todo de corrido y no se puede ir llenando casilleros.
 * - Frecuencia de consumo con RANGOS seleccionables (nunca → todos los días).
 * - Preguntas de salud con patrón Sí/No: el detalle se despliega solo si es Sí.
 * - Tabaco con cigarrillos/día y años → IPA calculado automáticamente.
 *
 * Notas, cigarrillos y años viven en datos_extra (JSONB): cero migraciones.
 */

import { useCallback, useEffect, useState } from "react";
import { Save } from "lucide-react";
import { toast } from "sonner";

import { obtenerFicha, guardarFicha, Ficha, FichaGuardar } from "@/lib/ficha-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Seccion, Campo, CampoArea } from "./comunes";

/** Estado del formulario: todos los campos como string + los dos mapas. */
type FormFicha = {
  motivo_consulta: string;
  objetivo: string;
  ocupacion: string;
  horario_trabajo: string;
  fum: string;
  actividad_fisica: string;
  enfermedades: string;
  operaciones: string;
  medicacion: string;
  antecedentes_familiares: string;
  consume_alcohol_drogas: string;
  fuma: string;
  sintomas_recurrentes: string;
  evacuacion: string;
  sueno: string;
  alimentos_no_consume: string;
  alimentos_no_tolera: string;
  alimentos_gustan: string;
  nutri_anterior: string;
  obra_social: string;
  plan_obra_social: string;
  nro_afiliado: string;
  horario_comidas: Record<string, string>;
  frecuencia_consumo: Record<string, string>;
  // En datos_extra (JSONB):
  notas_entrevista: string;
  fuma_cig_dia: string;
  fuma_anios: string;
};

const VACIA: FormFicha = {
  motivo_consulta: "", objetivo: "", ocupacion: "", horario_trabajo: "", fum: "",
  actividad_fisica: "", enfermedades: "", operaciones: "", medicacion: "",
  antecedentes_familiares: "", consume_alcohol_drogas: "", fuma: "",
  sintomas_recurrentes: "", evacuacion: "", sueno: "",
  alimentos_no_consume: "", alimentos_no_tolera: "", alimentos_gustan: "", nutri_anterior: "",
  obra_social: "", plan_obra_social: "", nro_afiliado: "",
  horario_comidas: {}, frecuencia_consumo: {},
  notas_entrevista: "", fuma_cig_dia: "", fuma_anios: "",
};

// Las comidas del día y los grupos de alimentos (para las dos "tablas").
const COMIDAS = [
  ["desayuno", "Desayuno"], ["colacion_manana", "Colación mañana"],
  ["almuerzo", "Almuerzo"], ["merienda", "Merienda"],
  ["colacion_tarde", "Colación tarde"], ["cena", "Cena"],
];

const GRUPOS = [
  ["lacteos", "Lácteos"], ["huevo", "Huevo"], ["carnes", "Carnes"],
  ["hc", "Hidratos"], ["legumbres", "Legumbres"], ["verduras", "Verduras"],
  ["frutas", "Frutas"], ["pescado", "Pescado"], ["procesados", "Procesados"],
  ["azucar", "Azúcar / edulc."], ["sal", "Sal"],
];

/** La escala de frecuencia acordada con Giuliana (rango, no texto libre). */
const RANGOS = [
  "nunca",
  "1-2 por semana",
  "3-4 por semana",
  "5-6 por semana",
  "todos los días",
];

/** Convierte la ficha del backend (con nulls) al estado del form (strings). */
function aForm(f: Ficha): FormFicha {
  const t = (v: string | null) => v ?? "";
  const extra = (f.datos_extra ?? {}) as Record<string, unknown>;
  const ex = (clave: string) => {
    const v = extra[clave];
    return v == null ? "" : String(v);
  };
  return {
    motivo_consulta: t(f.motivo_consulta), objetivo: t(f.objetivo),
    ocupacion: t(f.ocupacion), horario_trabajo: t(f.horario_trabajo), fum: t(f.fum),
    actividad_fisica: t(f.actividad_fisica), enfermedades: t(f.enfermedades),
    operaciones: t(f.operaciones), medicacion: t(f.medicacion),
    antecedentes_familiares: t(f.antecedentes_familiares),
    consume_alcohol_drogas: t(f.consume_alcohol_drogas), fuma: t(f.fuma),
    sintomas_recurrentes: t(f.sintomas_recurrentes), evacuacion: t(f.evacuacion),
    sueno: t(f.sueno),
    alimentos_no_consume: t(f.alimentos_no_consume), alimentos_no_tolera: t(f.alimentos_no_tolera),
    alimentos_gustan: t(f.alimentos_gustan), nutri_anterior: t(f.nutri_anterior),
    obra_social: t(f.obra_social), plan_obra_social: t(f.plan_obra_social),
    nro_afiliado: t(f.nro_afiliado),
    horario_comidas: f.horario_comidas ?? {}, frecuencia_consumo: f.frecuencia_consumo ?? {},
    notas_entrevista: ex("notas_entrevista"),
    fuma_cig_dia: ex("fuma_cig_dia"),
    fuma_anios: ex("fuma_anios"),
  };
}

/** Pregunta con switch Sí/No: el detalle se despliega solo cuando es Sí. */
function CampoSiNo({
  label, valor, onChange, children,
}: {
  label: string;
  valor: string;
  onChange: (v: string) => void;
  children?: React.ReactNode; // contenido extra bajo el textarea (ej. IPA)
}) {
  const [abierto, setAbierto] = useState(valor.trim() !== "");

  // Si la carga async trae contenido, abrimos.
  useEffect(() => {
    if (valor.trim() !== "") setAbierto(true);
  }, [valor]);

  function toggle(on: boolean) {
    setAbierto(on);
    if (!on) onChange(""); // apagar = "No" → se limpia el detalle
  }

  return (
    <div className="rounded-xl border p-3">
      <div className="flex items-center justify-between gap-3">
        <Label className="text-sm">{label}</Label>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{abierto ? "Sí" : "No"}</span>
          <Switch checked={abierto} onCheckedChange={toggle} />
        </div>
      </div>
      {abierto && (
        <div className="mt-2.5 space-y-2">
          <Textarea
            rows={2}
            value={valor}
            placeholder="Detalle…"
            onChange={(e) => onChange(e.target.value)}
          />
          {children}
        </div>
      )}
    </div>
  );
}

export function TabAnamnesis({ clienteId }: { clienteId: number }) {
  const [form, setForm] = useState<FormFicha>(VACIA);
  const [extraPrevio, setExtraPrevio] = useState<Record<string, unknown>>({});
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const f = await obtenerFicha(clienteId);
      if (f) {
        setForm(aForm(f));
        setExtraPrevio((f.datos_extra ?? {}) as Record<string, unknown>);
      }
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo cargar la ficha");
    } finally {
      setCargando(false);
    }
  }, [clienteId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const set = (campo: keyof FormFicha, valor: string) =>
    setForm((f) => ({ ...f, [campo]: valor }));
  const setComida = (clave: string, valor: string) =>
    setForm((f) => ({ ...f, horario_comidas: { ...f.horario_comidas, [clave]: valor } }));
  const setGrupo = (clave: string, valor: string) =>
    setForm((f) => ({ ...f, frecuencia_consumo: { ...f.frecuencia_consumo, [clave]: valor } }));

  // IPA = (cigarrillos por día ÷ 20) × años fumando
  const cig = parseFloat(form.fuma_cig_dia);
  const anios = parseFloat(form.fuma_anios);
  const ipa = cig > 0 && anios > 0 ? ((cig / 20) * anios).toFixed(1) : null;

  async function guardar() {
    setGuardando(true);
    try {
      // datos_extra: preservamos claves ajenas y actualizamos las nuestras.
      const extra: Record<string, unknown> = { ...extraPrevio };
      const setExtra = (clave: string, v: string) => {
        if (v.trim() === "") delete extra[clave];
        else extra[clave] = v.trim();
      };
      setExtra("notas_entrevista", form.notas_entrevista);
      setExtra("fuma_cig_dia", form.fuma_cig_dia);
      setExtra("fuma_anios", form.fuma_anios);

      const { notas_entrevista, fuma_cig_dia, fuma_anios, ...campos } = form;
      const payload = { ...campos, fum: form.fum || null, datos_extra: extra } as FichaGuardar;
      await guardarFicha(clienteId, payload);
      setExtraPrevio(extra);
      toast.success("Ficha guardada");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) {
    return <p className="text-sm text-muted-foreground">Cargando ficha…</p>;
  }

  return (
    <div className="space-y-6">
      {/* Notas de entrevista: el borrador libre, siempre arriba de todo */}
      <Seccion titulo="Notas de entrevista">
        <p className="-mt-2 text-xs text-muted-foreground">
          Para cuando el paciente cuenta todo de corrido: anotá acá y después distribuí en los
          campos. Se guarda con la ficha.
        </p>
        <Textarea
          rows={5}
          value={form.notas_entrevista}
          placeholder="Escribí libremente lo que va contando el paciente…"
          onChange={(e) => set("notas_entrevista", e.target.value)}
        />
      </Seccion>

      {/* Motivo y contexto */}
      <Seccion titulo="Motivo y contexto">
        <CampoArea label="Motivo de consulta" valor={form.motivo_consulta} onChange={(v) => set("motivo_consulta", v)} />
        <CampoArea label="Objetivo" valor={form.objetivo} onChange={(v) => set("objetivo", v)} />
        <div className="grid gap-4 sm:grid-cols-3">
          <Campo label="Ocupación" valor={form.ocupacion} onChange={(v) => set("ocupacion", v)} />
          <Campo label="Horario de trabajo/estudio" valor={form.horario_trabajo} onChange={(v) => set("horario_trabajo", v)} />
          <Campo label="FUM" tipo="date" valor={form.fum} onChange={(v) => set("fum", v)} />
        </div>
      </Seccion>

      {/* Alimentación */}
      <Seccion titulo="Alimentación">
        <Label className="text-sm font-medium">Horario de comidas</Label>
        <div className="grid gap-3 sm:grid-cols-3">
          {COMIDAS.map(([clave, label]) => (
            <Campo key={clave} label={label} valor={form.horario_comidas[clave] ?? ""} onChange={(v) => setComida(clave, v)} />
          ))}
        </div>
        <Label className="mt-4 text-sm font-medium">Frecuencia de consumo</Label>
        <p className="-mt-2 text-xs text-muted-foreground">
          Por rango, para comparar entre pacientes sin escribir.
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          {GRUPOS.map(([clave, label]) => {
            const actual = form.frecuencia_consumo[clave] ?? "";
            const esLegacy = actual !== "" && !RANGOS.includes(actual);
            return (
              <div key={clave} className="space-y-1">
                <Label className="text-xs text-muted-foreground">{label}</Label>
                <select
                  value={actual}
                  onChange={(e) => setGrupo(clave, e.target.value)}
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                >
                  <option value="">—</option>
                  {RANGOS.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                  {esLegacy && <option value={actual}>{actual} (anterior)</option>}
                </select>
              </div>
            );
          })}
        </div>
      </Seccion>

      {/* Salud general */}
      <Seccion titulo="Salud general">
        <CampoArea label="Actividad física (qué hace, frecuencia, dónde juega, posición, si come antes/después)" valor={form.actividad_fisica} onChange={(v) => set("actividad_fisica", v)} rows={3} />
        <div className="grid gap-3 sm:grid-cols-2">
          <CampoSiNo label="¿Tiene enfermedades / patologías?" valor={form.enfermedades} onChange={(v) => set("enfermedades", v)} />
          <CampoSiNo label="¿Toma medicación?" valor={form.medicacion} onChange={(v) => set("medicacion", v)} />
          <CampoSiNo label="¿Operaciones previas?" valor={form.operaciones} onChange={(v) => set("operaciones", v)} />
          <CampoSiNo label="¿Antecedentes familiares?" valor={form.antecedentes_familiares} onChange={(v) => set("antecedentes_familiares", v)} />
          <CampoSiNo label="¿Consume alcohol / otras sustancias?" valor={form.consume_alcohol_drogas} onChange={(v) => set("consume_alcohol_drogas", v)} />
          <CampoSiNo label="¿Fuma?" valor={form.fuma} onChange={(v) => set("fuma", v)}>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-[11px] text-muted-foreground">Cigarrillos / día</Label>
                <input
                  type="number" inputMode="numeric" min={0}
                  value={form.fuma_cig_dia}
                  onChange={(e) => set("fuma_cig_dia", e.target.value)}
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-[11px] text-muted-foreground">Años fumando</Label>
                <input
                  type="number" inputMode="numeric" min={0}
                  value={form.fuma_anios}
                  onChange={(e) => set("fuma_anios", e.target.value)}
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                />
              </div>
            </div>
            {ipa && (
              <p className="text-xs text-muted-foreground">
                IPA: <span className="font-semibold text-foreground">{ipa}</span> paquetes/año
              </p>
            )}
          </CampoSiNo>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo label="Evacuación" valor={form.evacuacion} onChange={(v) => set("evacuacion", v)} placeholder="normal / diarrea / constipación…" />
          <Campo label="Sueño / descanso" valor={form.sueno} onChange={(v) => set("sueno", v)} placeholder="horas, cómo se levanta…" />
        </div>
        <CampoArea label="Síntomas recurrentes" valor={form.sintomas_recurrentes} onChange={(v) => set("sintomas_recurrentes", v)} />
      </Seccion>

      {/* Preferencias */}
      <Seccion titulo="Preferencias alimentarias">
        <div className="grid gap-4 sm:grid-cols-2">
          <CampoArea label="Alimentos que no consume" valor={form.alimentos_no_consume} onChange={(v) => set("alimentos_no_consume", v)} />
          <CampoArea label="Alimentos que no tolera" valor={form.alimentos_no_tolera} onChange={(v) => set("alimentos_no_tolera", v)} />
          <CampoArea label="Alimentos que le gustan" valor={form.alimentos_gustan} onChange={(v) => set("alimentos_gustan", v)} />
          <CampoArea label="Experiencia con nutri anterior" valor={form.nutri_anterior} onChange={(v) => set("nutri_anterior", v)} />
        </div>
      </Seccion>

      {/* Cobertura */}
      <Seccion titulo="Cobertura">
        <div className="grid gap-4 sm:grid-cols-3">
          <Campo label="Obra social" valor={form.obra_social} onChange={(v) => set("obra_social", v)} />
          <Campo label="Plan" valor={form.plan_obra_social} onChange={(v) => set("plan_obra_social", v)} />
          <Campo label="N.º de afiliado" valor={form.nro_afiliado} onChange={(v) => set("nro_afiliado", v)} />
        </div>
      </Seccion>

      <div className="flex justify-end">
        <Button onClick={guardar} disabled={guardando}>
          <Save className="mr-2 h-4 w-4" />
          {guardando ? "Guardando…" : "Guardar ficha"}
        </Button>
      </div>
    </div>
  );
}
