"use client";

/**
 * Mi página (/mi-pagina). El dueño edita el contenido de su landing pública:
 * sobre nosotros, dirección, contacto, logo, color, horarios (display) y redes.
 * Solo dueño (RequiereDueno + gate_dueno en el backend).
 */

import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Save,
  Instagram,
  Facebook,
  Linkedin,
  Globe,
  Music2,
  type LucideIcon,
} from "lucide-react";

import {
  obtenerLanding,
  guardarLanding,
  LandingConfig,
  HorariosAtencion,
  Franja,
  Redes,
} from "@/lib/empresa-api";
import { ApiError } from "@/lib/api";
import { RequiereDueno } from "@/components/requiere-rol";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const DIAS: { clave: string; label: string }[] = [
  { clave: "lun", label: "Lunes" },
  { clave: "mar", label: "Martes" },
  { clave: "mie", label: "Miércoles" },
  { clave: "jue", label: "Jueves" },
  { clave: "vie", label: "Viernes" },
  { clave: "sab", label: "Sábado" },
  { clave: "dom", label: "Domingo" },
];

const REDES: {
  clave: keyof Redes;
  label: string;
  placeholder: string;
  Icono: LucideIcon;
}[] = [
  { clave: "instagram", label: "Instagram", placeholder: "usuario o link", Icono: Instagram },
  { clave: "facebook", label: "Facebook", placeholder: "link a tu página", Icono: Facebook },
  { clave: "tiktok", label: "TikTok", placeholder: "@usuario", Icono: Music2 },
  { clave: "linkedin", label: "LinkedIn", placeholder: "link a tu perfil", Icono: Linkedin },
  { clave: "sitio_web", label: "Sitio web", placeholder: "https://…", Icono: Globe },
];

const VACIO: LandingConfig = {
  descripcion: null,
  direccion: null,
  telefono_publico: null,
  email_publico: null,
  logo_url: null,
  color_marca: null,
  horarios_atencion: null,
  redes: {},
};

/** Editor de horarios visibles (display). Por día: abierto/cerrado + 1-2 franjas. */
function HorariosEditor({
  value,
  onChange,
}: {
  value: HorariosAtencion;
  onChange: (h: HorariosAtencion) => void;
}) {
  const franjasDe = (clave: string): Franja[] => value[clave] ?? [];
  const abierto = (clave: string) => franjasDe(clave).length > 0;

  function toggle(clave: string, on: boolean) {
    onChange({ ...value, [clave]: on ? [["09:00", "19:00"]] : [] });
  }
  function setHora(clave: string, i: number, extremo: 0 | 1, hora: string) {
    const franjas = franjasDe(clave).map((f, j) => {
      if (j !== i) return f;
      const copia: Franja = [f[0], f[1]];
      copia[extremo] = hora;
      return copia;
    });
    onChange({ ...value, [clave]: franjas });
  }
  function agregarFranja(clave: string) {
    onChange({ ...value, [clave]: [...franjasDe(clave), ["16:00", "20:00"]] });
  }
  function quitarFranja(clave: string, i: number) {
    onChange({ ...value, [clave]: franjasDe(clave).filter((_, j) => j !== i) });
  }

  return (
    <div className="space-y-2">
      {DIAS.map((d) => {
        const franjas = franjasDe(d.clave);
        return (
          <div key={d.clave} className="rounded-xl border p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{d.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  {abierto(d.clave) ? "Abierto" : "Cerrado"}
                </span>
                <Switch
                  checked={abierto(d.clave)}
                  onCheckedChange={(on) => toggle(d.clave, on)}
                />
              </div>
            </div>

            {abierto(d.clave) && (
              <div className="mt-3 space-y-2">
                {franjas.map((f, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input
                      type="time"
                      value={f[0]}
                      onChange={(e) => setHora(d.clave, i, 0, e.target.value)}
                      className="w-32"
                    />
                    <span className="text-sm text-muted-foreground">a</span>
                    <Input
                      type="time"
                      value={f[1]}
                      onChange={(e) => setHora(d.clave, i, 1, e.target.value)}
                      className="w-32"
                    />
                    {franjas.length > 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => quitarFranja(d.clave, i)}
                      >
                        Quitar
                      </Button>
                    )}
                  </div>
                ))}
                {franjas.length < 2 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => agregarFranja(d.clave)}
                  >
                    + Agregar franja (ej. tarde/siesta)
                  </Button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ContenidoMiPagina() {
  const [form, setForm] = useState<LandingConfig | null>(null);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    obtenerLanding()
      .then((data) => setForm({ ...VACIO, ...data, redes: data.redes ?? {} }))
      .catch((err) =>
        toast.error(err instanceof ApiError ? err.message : "Error al cargar"),
      )
      .finally(() => setCargando(false));
  }, []);

  function set<K extends keyof LandingConfig>(clave: K, valor: LandingConfig[K]) {
    setForm((f) => (f ? { ...f, [clave]: valor } : f));
  }
  function setRed(clave: keyof Redes, valor: string) {
    setForm((f) => (f ? { ...f, redes: { ...f.redes, [clave]: valor } } : f));
  }

  async function guardar() {
    if (!form) return;
    setGuardando(true);
    const limpio = (s: string | null) => {
      const t = (s ?? "").trim();
      return t === "" ? null : t;
    };
    const redesLimpias: Redes = {};
    for (const [k, v] of Object.entries(form.redes)) {
      if ((v ?? "").trim() !== "") redesLimpias[k] = (v as string).trim();
    }
    const tieneHorarios =
      !!form.horarios_atencion &&
      Object.values(form.horarios_atencion).some((f) => f.length > 0);

    const payload: LandingConfig = {
      descripcion: limpio(form.descripcion),
      direccion: limpio(form.direccion),
      telefono_publico: limpio(form.telefono_publico),
      email_publico: limpio(form.email_publico),
      logo_url: limpio(form.logo_url),
      color_marca: limpio(form.color_marca),
      horarios_atencion: tieneHorarios ? form.horarios_atencion : null,
      redes: redesLimpias,
    };

    try {
      const guardado = await guardarLanding(payload);
      setForm({ ...VACIO, ...guardado, redes: guardado.redes ?? {} });
      toast.success("Página actualizada");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  if (cargando || !form) {
    return <div className="p-8 text-sm text-muted-foreground">Cargando…</div>;
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: "Syne, sans-serif" }}>
            Mi página
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Lo que ven tus clientes en tu página pública. Se comparte con el link de tu negocio.
          </p>
        </div>
        <Button onClick={guardar} disabled={guardando}>
          <Save className="mr-1.5 h-4 w-4" />
          {guardando ? "Guardando…" : "Guardar cambios"}
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Información del negocio */}
        <Card className="rounded-2xl">
          <CardHeader>
            <CardTitle style={{ fontFamily: "Syne, sans-serif" }}>
              Información del negocio
            </CardTitle>
            <CardDescription>Lo básico que ve el cliente al entrar.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="descripcion">Sobre nosotros</Label>
              <Textarea
                id="descripcion"
                rows={4}
                placeholder="Contá qué hace especial a tu negocio…"
                value={form.descripcion ?? ""}
                onChange={(e) => set("descripcion", e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="direccion">Dirección</Label>
              <Input
                id="direccion"
                placeholder="San Martín 1234, Mendoza"
                value={form.direccion ?? ""}
                onChange={(e) => set("direccion", e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                De acá sale el botón “Ver en Google Maps”.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="tel">Teléfono / WhatsApp</Label>
                <Input
                  id="tel"
                  placeholder="+54 9 261 123 4567"
                  value={form.telefono_publico ?? ""}
                  onChange={(e) => set("telefono_publico", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="hola@tunegocio.com"
                  value={form.email_publico ?? ""}
                  onChange={(e) => set("email_publico", e.target.value)}
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="logo">URL del logo</Label>
                <Input
                  id="logo"
                  placeholder="https://…/logo.png"
                  value={form.logo_url ?? ""}
                  onChange={(e) => set("logo_url", e.target.value)}
                />
                <p className="text-xs text-muted-foreground">Por ahora, pegá la URL.</p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="color">Color de marca</Label>
                <div className="flex items-center gap-2">
                  <input
                    id="color"
                    type="color"
                    className="h-9 w-12 cursor-pointer rounded-md border bg-transparent"
                    value={form.color_marca ?? "#00d4aa"}
                    onChange={(e) => set("color_marca", e.target.value)}
                  />
                  <Input
                    value={form.color_marca ?? ""}
                    placeholder="#00d4aa"
                    onChange={(e) => set("color_marca", e.target.value)}
                    className="w-32"
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Redes y links */}
        <Card className="rounded-2xl">
          <CardHeader>
            <CardTitle style={{ fontFamily: "Syne, sans-serif" }}>Redes y links</CardTitle>
            <CardDescription>Dejá vacío lo que no uses.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {REDES.map(({ clave, label, placeholder, Icono }) => (
              <div key={String(clave)} className="space-y-1.5">
                <Label htmlFor={String(clave)} className="flex items-center gap-2">
                  <Icono className="h-4 w-4 text-muted-foreground" />
                  {label}
                </Label>
                <Input
                  id={String(clave)}
                  placeholder={placeholder}
                  value={form.redes[clave] ?? ""}
                  onChange={(e) => setRed(clave, e.target.value)}
                />
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Horarios */}
        <Card className="rounded-2xl lg:col-span-2">
          <CardHeader>
            <CardTitle style={{ fontFamily: "Syne, sans-serif" }}>
              Horarios de atención
            </CardTitle>
            <CardDescription>
              Solo para mostrar en tu página. Los turnos reservables salen de la agenda de cada
              profesional.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <HorariosEditor
              value={form.horarios_atencion ?? {}}
              onChange={(h) => set("horarios_atencion", h)}
            />
          </CardContent>
        </Card>
      </div>

      <div className="mt-6 flex justify-end">
        <Button onClick={guardar} disabled={guardando}>
          <Save className="mr-1.5 h-4 w-4" />
          {guardando ? "Guardando…" : "Guardar cambios"}
        </Button>
      </div>
    </div>
  );
}

export default function MiPaginaPage() {
  return (
    <RequiereDueno>
      <ContenidoMiPagina />
    </RequiereDueno>
  );
}