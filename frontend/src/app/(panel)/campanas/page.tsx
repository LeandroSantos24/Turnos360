"use client";

/**
 * Campañas · Resumen (/campanas).
 *
 * Las cinco campañas de un vistazo: si están prendidas, cómo están
 * configuradas y qué mandaron en los últimos 30 días (dato real de la tabla
 * Mensaje, sin contar las pruebas). Se pueden prender y apagar desde acá; el
 * detalle se ajusta en la pestaña de cada grupo.
 */

import Link from "next/link";
import { ArrowRight, Bell, Cake, Clock, HeartHandshake, Mail, Megaphone, Star } from "lucide-react";

import type { Automatizaciones } from "@/lib/empresa-api";
import { Switch } from "@/components/ui/switch";
import { AvisoPromos, CargandoCampanas, LineaActividad, textoAnticipacion, useCampanas } from "./_campanas";

type Fila = {
  clave: keyof Automatizaciones;
  titulo: string;
  Icono: typeof Bell;
  tono: string;
  href: string;
  detalle: (c: Automatizaciones) => string;
  falta?: (c: Automatizaciones) => string | null;
};

const FILAS: Fila[] = [
  {
    clave: "recordatorio_24h",
    titulo: "Primer recordatorio",
    Icono: Bell,
    tono: "var(--acento-cielo)",
    href: "/campanas/recordatorios",
    detalle: (c) => `Sale ${textoAnticipacion(c.recordatorio_24h.horas_antes)} del turno.`,
  },
  {
    clave: "recordatorio_2h",
    titulo: "Segundo recordatorio",
    Icono: Clock,
    tono: "var(--acento-cielo)",
    href: "/campanas/recordatorios",
    detalle: (c) => `Sale ${textoAnticipacion(c.recordatorio_2h.horas_antes)} del turno.`,
  },
  {
    clave: "cumple",
    titulo: "Saludo de cumpleaños",
    Icono: Cake,
    tono: "var(--acento-rosa)",
    href: "/campanas/fidelizacion",
    detalle: (c) =>
      c.cumple.dias_antes === 0 ? "Sale el día del cumpleaños." : `Sale ${c.cumple.dias_antes} día${c.cumple.dias_antes > 1 ? "s" : ""} antes del cumpleaños.`,
  },
  {
    clave: "inactivos",
    titulo: "Recuperar inactivos",
    Icono: HeartHandshake,
    tono: "var(--acento-rosa)",
    href: "/campanas/fidelizacion",
    detalle: (c) => `A quien lleva ${c.inactivos.dias} días sin venir${c.inactivos.min_visitas > 1 ? ` y vino ${c.inactivos.min_visitas}+ veces` : ""}.`,
  },
  {
    clave: "resena_google",
    titulo: "Reseña en Google",
    Icono: Star,
    tono: "var(--acento-ambar)",
    href: "/campanas/resenas",
    detalle: (c) => {
      const h = c.resena_google.horas_despues;
      return h === 0 ? "Sale al terminar el turno." : `Sale ${h >= 24 ? `${h / 24} día${h > 24 ? "s" : ""}` : `${h} h`} después del turno.`;
    },
    falta: (c) => (c.resena_google.activa && !c.resena_google.link.trim() ? "Falta el link de Google: no puede mandar nada." : null),
  },
];

export default function CampanasResumen() {
  const { cfg, set, actividad } = useCampanas();
  if (!cfg) return <CargandoCampanas />;

  const a = actividad?.alcance;
  const enviados = actividad
    ? Object.values(actividad.campanas).reduce((t, c) => t + c.enviados, 0)
    : null;

  return (
    <div className="space-y-6">
      {a && (
        <section aria-label="Alcance" className="grid gap-3 sm:grid-cols-3">
          <div className="tarjeta p-4">
            <p className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground">
              <Megaphone className="h-3.5 w-3.5" aria-hidden /> Enviados en {actividad!.dias} días
            </p>
            <p className="mt-1 text-2xl font-bold tabular-nums">{enviados}</p>
            <p className="text-xs text-muted-foreground">Emails reales, sin contar las pruebas.</p>
          </div>
          <div className="tarjeta p-4">
            <p className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground">
              <Mail className="h-3.5 w-3.5" aria-hidden /> Con email
            </p>
            <p className="mt-1 text-2xl font-bold tabular-nums">
              {a.con_email} <span className="text-sm font-medium text-muted-foreground">de {a.clientes}</span>
            </p>
            <p className="text-xs text-muted-foreground">Les llegan recordatorios y el pedido de reseña.</p>
          </div>
          <div className="tarjeta p-4">
            <p className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground">
              <HeartHandshake className="h-3.5 w-3.5" aria-hidden /> Aceptan promociones
            </p>
            <p className="mt-1 text-2xl font-bold tabular-nums">
              {a.aceptan_promos} <span className="text-sm font-medium text-muted-foreground">de {a.clientes}</span>
            </p>
            <p className="text-xs text-muted-foreground">Les llegan cumpleaños e inactivos.</p>
          </div>
        </section>
      )}

      <section aria-label="Campañas" className="tarjeta divide-y overflow-hidden">
        {FILAS.map(({ clave, titulo, Icono, tono, href, detalle, falta }) => {
          const activa = cfg[clave].activa;
          const aviso = falta?.(cfg) ?? null;
          return (
            <div key={clave} className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4 sm:flex-nowrap" style={{ "--tono": tono } as React.CSSProperties}>
              <span className="cajita">
                <Icono className="h-[18px] w-[18px]" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{titulo}</p>
                <p className="text-sm text-muted-foreground">{activa ? detalle(cfg) : "Apagada."}</p>
                {aviso && <p className="text-xs font-semibold text-amber-800 dark:text-amber-300">{aviso}</p>}
                <div className="mt-1">
                  <LineaActividad tipo={clave} />
                </div>
              </div>
              <Link href={href} className="enlace inline-flex shrink-0 items-center gap-1 text-sm">
                Configurar <ArrowRight className="h-3.5 w-3.5" aria-hidden />
              </Link>
              <Switch
                checked={activa}
                onCheckedChange={(v) => set(clave, { ...cfg[clave], activa: v } as Automatizaciones[typeof clave])}
                aria-label={`${activa ? "Apagar" : "Prender"} ${titulo}`}
              />
            </div>
          );
        })}
      </section>

      <AvisoPromos />

      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <Mail className="h-3.5 w-3.5 shrink-0" aria-hidden />
        Todo sale por email y el cliente necesita tener el suyo cargado. Probá cada una con «Enviarme una prueba» antes de dejarla andando.
      </p>
    </div>
  );
}
