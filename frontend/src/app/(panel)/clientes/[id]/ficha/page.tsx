"use client";
 
/**
 * Ficha clínica / anamnesis del paciente (/clientes/[id]/ficha).
 *
 * Formulario de la primera consulta del pack nutrición. Se completa de a poco:
 * carga lo que ya haya (GET) y guarda con upsert (PUT). Si el paciente todavía
 * no tiene ficha, arranca vacía. Estilo uniforme: títulos Syne, cards rounded-2xl.
 */
 
import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Save } from "lucide-react";
import { toast } from "sonner";
 
import { obtenerFicha, guardarFicha, Ficha, FichaGuardar } from "@/lib/ficha-api";
import { obtenerCliente, Cliente } from "@/lib/clientes-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
 
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
};
 
const VACIA: FormFicha = {
  motivo_consulta: "", objetivo: "", ocupacion: "", horario_trabajo: "", fum: "",
  actividad_fisica: "", enfermedades: "", operaciones: "", medicacion: "",
  antecedentes_familiares: "", consume_alcohol_drogas: "", fuma: "",
  sintomas_recurrentes: "", evacuacion: "", sueno: "",
  alimentos_no_consume: "", alimentos_no_tolera: "", alimentos_gustan: "", nutri_anterior: "",
  obra_social: "", plan_obra_social: "", nro_afiliado: "",
  horario_comidas: {}, frecuencia_consumo: {},
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
 
/** Convierte la ficha del backend (con nulls) al estado del form (strings). */
function aForm(f: Ficha): FormFicha {
  const t = (v: string | null) => v ?? "";
  return {
    motivo_consulta: t(f.motivo_consulta), objetivo: t(f.objetivo),
    ocupacion: t(f.ocupacion), horario_trabajo: t(f.horario_trabajo), fum: t(f.fum),
    actividad_fisica: t(f.actividad_fisica), enfermedades: t(f.enfermedades),
    operaciones: t(f.operaciones), medicacion: t(f.medicacion),
    antecedentes_familiares: t(f.antecedentes_familiares),
    consume_alcohol_drogas: t(f.consume_alcohol_drogas), fuma: t(f.fuma),
    sintomas_recurrentes: t(f.sintomas_recurrentes), evacuacion: t(f.evacuacion), sueno: t(f.sueno),
    alimentos_no_consume: t(f.alimentos_no_consume), alimentos_no_tolera: t(f.alimentos_no_tolera),
    alimentos_gustan: t(f.alimentos_gustan), nutri_anterior: t(f.nutri_anterior),
    obra_social: t(f.obra_social), plan_obra_social: t(f.plan_obra_social), nro_afiliado: t(f.nro_afiliado),
    horario_comidas: f.horario_comidas ?? {}, frecuencia_consumo: f.frecuencia_consumo ?? {},
  };
}
 
export default function FichaPage() {
  const params = useParams();
  const router = useRouter();
  const clienteId = Number(params.id);
 
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [form, setForm] = useState<FormFicha>(VACIA);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
 
  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const [c, f] = await Promise.all([obtenerCliente(clienteId), obtenerFicha(clienteId)]);
      setCliente(c);
      if (f) setForm(aForm(f));
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
 
  async function guardar() {
    setGuardando(true);
    try {
      const payload = { ...form, fum: form.fum || null } as FichaGuardar;
      await guardarFicha(clienteId, payload);
      toast.success("Ficha guardada");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }
 
  if (cargando) {
    return <div className="p-8 text-muted-foreground">Cargando ficha…</div>;
  }
 
  const nombre = cliente ? `${cliente.nombre} ${cliente.apellido ?? ""}`.trim() : "Paciente";
 
  return (
    <div className="mx-auto max-w-4xl p-6 space-y-6">
      {/* Encabezado */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="font-[family-name:var(--font-syne)] text-2xl font-bold">Ficha clínica</h1>
            <p className="text-sm text-muted-foreground">{nombre}</p>
          </div>
        </div>
        <Button onClick={guardar} disabled={guardando}>
          <Save className="mr-2 h-4 w-4" />
          {guardando ? "Guardando…" : "Guardar ficha"}
        </Button>
      </div>
 
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
        <div className="grid gap-3 sm:grid-cols-3">
          {GRUPOS.map(([clave, label]) => (
            <Campo key={clave} label={label} valor={form.frecuencia_consumo[clave] ?? ""} onChange={(v) => setGrupo(clave, v)} />
          ))}
        </div>
      </Seccion>
 
      {/* Salud general */}
      <Seccion titulo="Salud general">
        <CampoArea label="Actividad física" valor={form.actividad_fisica} onChange={(v) => set("actividad_fisica", v)} />
        <div className="grid gap-4 sm:grid-cols-2">
          <CampoArea label="Enfermedades" valor={form.enfermedades} onChange={(v) => set("enfermedades", v)} />
          <CampoArea label="Operaciones" valor={form.operaciones} onChange={(v) => set("operaciones", v)} />
          <CampoArea label="Medicación" valor={form.medicacion} onChange={(v) => set("medicacion", v)} />
          <CampoArea label="Antecedentes familiares" valor={form.antecedentes_familiares} onChange={(v) => set("antecedentes_familiares", v)} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo label="Alcohol / drogas" valor={form.consume_alcohol_drogas} onChange={(v) => set("consume_alcohol_drogas", v)} />
          <Campo label="Fuma" valor={form.fuma} onChange={(v) => set("fuma", v)} />
          <Campo label="Evacuación" valor={form.evacuacion} onChange={(v) => set("evacuacion", v)} />
          <Campo label="Sueño / descanso" valor={form.sueno} onChange={(v) => set("sueno", v)} />
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
 
/** Una sección con título Syne y card. */
function Seccion({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <Card className="space-y-4 rounded-2xl p-5">
      <h2 className="font-[family-name:var(--font-syne)] text-lg font-semibold">{titulo}</h2>
      {children}
    </Card>
  );
}
 
/** Un input corto con label. */
function Campo({
  label, valor, onChange, tipo = "text",
}: { label: string; valor: string; onChange: (v: string) => void; tipo?: string }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input type={tipo} value={valor} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
 
/** Un textarea con label, para texto largo. */
function CampoArea({
  label, valor, onChange,
}: { label: string; valor: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Textarea rows={2} value={valor} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}