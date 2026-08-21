"use client";

/**
 * Seguimiento publicitario (/seguimiento).
 *
 * El dueño conecta SU Meta Pixel y/o SU Google Tag para medir las visitas y
 * las reservas de su vidriera en sus propias campañas. Los IDs se validan en
 * el backend contra una lista blanca cerrada antes de llegar a un <script>.
 */

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { LineChart, Save, CheckCircle2, Circle } from "lucide-react";

import {
  leerSeguimiento,
  guardarSeguimiento,
  type SeguimientoConfig,
} from "@/lib/empresa-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const SYNE = { fontFamily: "Syne, sans-serif" } as const;

function Tarjeta({
  titulo,
  subtitulo,
  conectado,
  children,
}: {
  titulo: string;
  subtitulo: string;
  conectado: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border bg-card p-5 md:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-bold" style={SYNE}>
            {titulo}
          </h2>
          <p className="mt-0.5 text-sm text-muted-foreground">{subtitulo}</p>
        </div>
        <span
          className={`flex shrink-0 items-center gap-1.5 text-xs font-medium ${
            conectado ? "text-emerald-600" : "text-muted-foreground"
          }`}
        >
          {conectado ? (
            <CheckCircle2 className="h-3.5 w-3.5" />
          ) : (
            <Circle className="h-3.5 w-3.5" />
          )}
          {conectado ? "Conectado" : "Sin conectar"}
        </span>
      </div>
      <div className="mt-5 space-y-2">{children}</div>
    </section>
  );
}

export default function SeguimientoPage() {
  const [form, setForm] = useState<SeguimientoConfig | null>(null);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setForm(await leerSeguimiento());
    } catch {
      toast.error("No se pudo cargar la configuración");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function guardar() {
    if (!form) return;
    setGuardando(true);
    try {
      setForm(
        await guardarSeguimiento({
          meta_pixel_id: form.meta_pixel_id?.trim() || null,
          google_tag_id: form.google_tag_id?.trim() || null,
          google_conversion_label:
            form.google_conversion_label?.trim() || null,
        }),
      );
      toast.success("Guardado");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) {
    return <p className="p-6 text-sm text-muted-foreground">Cargando…</p>;
  }
  if (!form) {
    return <p className="p-6 text-sm text-muted-foreground">No se pudo cargar.</p>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold" style={SYNE}>
            <LineChart className="h-6 w-6" />
            Seguimiento
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Conectá tu píxel y medí las visitas y reservas de tu página en tus
            campañas.
          </p>
        </div>
        <Button onClick={guardar} disabled={guardando}>
          <Save className="mr-2 h-4 w-4" />
          {guardando ? "Guardando…" : "Guardar"}
        </Button>
      </header>

      <Tarjeta
        titulo="Meta Pixel"
        subtitulo="Para tus anuncios de Instagram y Facebook."
        conectado={Boolean(form.meta_pixel_id)}
      >
        <Label htmlFor="meta">Pixel ID</Label>
        <Input
          id="meta"
          inputMode="numeric"
          placeholder="1234567890123456"
          value={form.meta_pixel_id ?? ""}
          onChange={(e) =>
            setForm({ ...form, meta_pixel_id: e.target.value || null })
          }
        />
        <p className="text-xs text-muted-foreground">
          Son solo números. Lo encontrás en Meta Business Suite → Administrador
          de eventos → Orígenes de datos. Dejalo vacío para desconectarlo.
        </p>
      </Tarjeta>

      <Tarjeta
        titulo="Google Tag"
        subtitulo="Para Google Analytics o Google Ads."
        conectado={Boolean(form.google_tag_id)}
      >
        <Label htmlFor="google">ID de medición</Label>
        <Input
          id="google"
          placeholder="G-XXXXXXXXXX"
          value={form.google_tag_id ?? ""}
          onChange={(e) =>
            setForm({ ...form, google_tag_id: e.target.value || null })
          }
        />
        <p className="text-xs text-muted-foreground">
          Tiene la forma G-XXXXXXX (Analytics) o AW-XXXXXXXXX (Ads).
        </p>

        {/* La etiqueta SOLO tiene sentido con un tag de Ads, y sin ella Ads
            no cuenta ni una conversión: necesita el par AW-XXXX/etiqueta.
            Aparece sola cuando hace falta para no confundir a nadie que use
            Analytics. */}
        {(form.google_tag_id ?? "").toUpperCase().startsWith("AW-") && (
          <div className="mt-4 space-y-1.5 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
            <Label htmlFor="label">Etiqueta de conversión</Label>
            <Input
              id="label"
              placeholder="AbC-D_efG-h12_34-567"
              value={form.google_conversion_label ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  google_conversion_label: e.target.value || null,
                })
              }
            />
            <p className="text-xs text-muted-foreground">
              <strong>Sin esto, Google Ads no cuenta ni una conversión</strong>{" "}
              — vas a ver visitas y cero reservas, y no es cierto. La sacás de
              Google Ads → Objetivos → tu conversión → «Configurar con la
              etiqueta»: es la parte que va después de la barra.
            </p>
          </div>
        )}
      </Tarjeta>

      <section className="rounded-2xl border bg-muted/40 p-5 text-sm">
        <p className="font-medium">Qué se mide</p>
        <ul className="mt-2 space-y-1.5 text-muted-foreground">
          <li>
            <strong>Visitas</strong> a tu página pública, apenas alguien la
            abre.
          </li>
          <li>
            <strong>Reservas confirmadas</strong>, que es el dato que te dice si
            la publicidad rinde: no alcanza con saber cuánta gente entró, sino
            cuántos terminaron sacando turno.
          </li>
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">
          Los datos van directo a tu cuenta de Meta o Google. Turnos360 no los
          guarda ni los ve.
        </p>
      </section>
    </div>
  );
}
