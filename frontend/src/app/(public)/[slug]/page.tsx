"use client";

/**
 * Vidriera pública del negocio (turnos360.com/<slug>). Página que ve el cliente
 * final: info del local, servicios, equipo, horarios, ubicación y redes.
 * Es solo lectura + contacto por WhatsApp. El wizard de reserva se suma aparte.
 */

import { useEffect, useState } from "react";
import {
  MapPin,
  Clock,
  MessageCircle,
  Instagram,
  Facebook,
  Linkedin,
  Music2,
  Globe,
  Scissors,
  Loader2,
  type LucideIcon,
} from "lucide-react";

import { obtenerVidriera, Vidriera } from "@/lib/publico-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

const DIAS: [string, string][] = [
  ["lun", "Lunes"],
  ["mar", "Martes"],
  ["mie", "Miércoles"],
  ["jue", "Jueves"],
  ["vie", "Viernes"],
  ["sab", "Sábado"],
  ["dom", "Domingo"],
];

const REDES_META: Record<string, { label: string; Icono: LucideIcon }> = {
  instagram: { label: "Instagram", Icono: Instagram },
  facebook: { label: "Facebook", Icono: Facebook },
  tiktok: { label: "TikTok", Icono: Music2 },
  linkedin: { label: "LinkedIn", Icono: Linkedin },
  sitio_web: { label: "Sitio web", Icono: Globe },
};

function hrefRed(clave: string, valor: string): string {
  const v = valor.trim();
  if (v.startsWith("http://") || v.startsWith("https://")) return v;
  const handle = v.replace(/^@/, "");
  switch (clave) {
    case "instagram":
      return `https://instagram.com/${handle}`;
    case "facebook":
      return `https://facebook.com/${handle}`;
    case "tiktok":
      return `https://tiktok.com/@${handle}`;
    case "linkedin":
      return `https://linkedin.com/in/${handle}`;
    default:
      return `https://${v}`;
  }
}

function precioFmt(n: number | null): string {
  if (n == null) return "";
  return `$${n.toLocaleString("es-AR")}`;
}

export default function VidrieraPage({ params }: { params: { slug: string } }) {
  const [vidriera, setVidriera] = useState<Vidriera | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<"no-existe" | "error" | null>(null);

  useEffect(() => {
    obtenerVidriera(params.slug)
      .then(setVidriera)
      .catch((e) =>
        setError(e instanceof ApiError && e.status === 404 ? "no-existe" : "error"),
      )
      .finally(() => setCargando(false));
  }, [params.slug]);

  if (cargando) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !vidriera) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 bg-background px-6 text-center">
        <h1 className="text-xl font-bold" style={{ fontFamily: "Syne, sans-serif" }}>
          {error === "no-existe" ? "Este negocio no existe" : "No pudimos cargar la página"}
        </h1>
        <p className="text-sm text-muted-foreground">
          {error === "no-existe"
            ? "Verificá el link e intentá de nuevo."
            : "Probá recargar en unos segundos."}
        </p>
      </div>
    );
  }

  const acento = vidriera.color_marca || "#00d4aa";
  const wa = vidriera.telefono_publico
    ? `https://wa.me/${vidriera.telefono_publico.replace(/\D/g, "")}?text=${encodeURIComponent(
        `¡Hola ${vidriera.nombre}! Quiero reservar un turno.`,
      )}`
    : null;
  const maps = vidriera.direccion
    ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(vidriera.direccion)}`
    : null;
  const redes = Object.entries(vidriera.redes || {}).filter(
    ([, v]) => v && v.trim() !== "",
  );
  const tieneHorarios =
    vidriera.horarios_atencion &&
    Object.values(vidriera.horarios_atencion).some((f) => f.length > 0);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-3xl px-5 py-10">
        {/* Hero */}
        <header className="flex flex-col items-center text-center">
          {vidriera.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={vidriera.logo_url}
              alt={vidriera.nombre}
              className="h-20 w-20 rounded-2xl object-cover"
            />
          ) : (
            <div
              className="flex h-20 w-20 items-center justify-center rounded-2xl text-3xl font-bold"
              style={{ background: acento, color: "#0a0f1e", fontFamily: "Syne, sans-serif" }}
            >
              {vidriera.nombre.charAt(0).toUpperCase()}
            </div>
          )}
          <h1
            className="mt-4 text-3xl font-bold"
            style={{ fontFamily: "Syne, sans-serif" }}
          >
            {vidriera.nombre}
          </h1>
          {wa && (
            <a href={wa} target="_blank" rel="noopener noreferrer" className="mt-5">
              <Button style={{ background: acento, color: "#0a0f1e" }}>
                <MessageCircle className="mr-1.5 h-4 w-4" />
                Escribinos por WhatsApp
              </Button>
            </a>
          )}
        </header>

        {/* Sobre nosotros */}
        {vidriera.descripcion && (
          <section className="mt-10">
            <h2 className="mb-2 text-lg font-semibold" style={{ fontFamily: "Syne, sans-serif" }}>
              Sobre nosotros
            </h2>
            <p className="whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
              {vidriera.descripcion}
            </p>
          </section>
        )}

        {/* Servicios */}
        {vidriera.servicios.length > 0 && (
          <section className="mt-10">
            <h2 className="mb-3 text-lg font-semibold" style={{ fontFamily: "Syne, sans-serif" }}>
              Servicios
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {vidriera.servicios.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between rounded-2xl border bg-card p-4"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium">{s.nombre}</p>
                    <p className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      {s.duracion_min} min
                    </p>
                  </div>
                  {s.precio != null && (
                    <span
                      className="shrink-0 font-semibold"
                      style={{
                        color: acento,
                        fontVariantNumeric: "lining-nums tabular-nums",
                      }}
                    >
                      {precioFmt(s.precio)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Equipo */}
        {vidriera.recursos.length > 0 && (
          <section className="mt-10">
            <h2 className="mb-3 text-lg font-semibold" style={{ fontFamily: "Syne, sans-serif" }}>
              Nuestro equipo
            </h2>
            <div className="flex flex-wrap gap-2">
              {vidriera.recursos.map((r) => (
                <span
                  key={r.id}
                  className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-sm"
                >
                  <Scissors className="h-3.5 w-3.5" style={{ color: acento }} />
                  {r.nombre}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Horarios */}
        {tieneHorarios && (
          <section className="mt-10">
            <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold" style={{ fontFamily: "Syne, sans-serif" }}>
              <Clock className="h-4 w-4" style={{ color: acento }} />
              Horarios
            </h2>
            <div className="overflow-hidden rounded-2xl border">
              {DIAS.map(([clave, label], i) => {
                const franjas = vidriera.horarios_atencion?.[clave] ?? [];
                return (
                  <div
                    key={clave}
                    className={`flex items-center justify-between px-4 py-2.5 text-sm ${
                      i % 2 === 0 ? "bg-card" : "bg-background"
                    }`}
                  >
                    <span className="font-medium">{label}</span>
                    <span className="text-muted-foreground">
                      {franjas.length > 0
                        ? franjas.map((f) => `${f[0]} a ${f[1]}`).join(" · ")
                        : "Cerrado"}
                    </span>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Ubicación */}
        {vidriera.direccion && (
          <section className="mt-10">
            <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold" style={{ fontFamily: "Syne, sans-serif" }}>
              <MapPin className="h-4 w-4" style={{ color: acento }} />
              Dónde estamos
            </h2>
            <p className="text-sm text-muted-foreground">{vidriera.direccion}</p>
            {maps && (
              <a
                href={maps}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-block text-sm font-medium"
                style={{ color: acento }}
              >
                Ver en Google Maps →
              </a>
            )}
          </section>
        )}

        {/* Redes */}
        {redes.length > 0 && (
          <section className="mt-10">
            <div className="flex flex-wrap gap-2">
              {redes.map(([clave, valor]) => {
                const meta = REDES_META[clave] ?? { label: clave, Icono: Globe };
                const Icono = meta.Icono;
                return (
                  <a
                    key={clave}
                    href={hrefRed(clave, valor)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <Icono className="h-4 w-4" />
                    {meta.label}
                  </a>
                );
              })}
            </div>
          </section>
        )}

        {/* Footer */}
        <footer className="mt-14 border-t pt-6 text-center text-xs text-muted-foreground">
          Reservá online con{" "}
          <span className="font-semibold" style={{ fontFamily: "Syne, sans-serif" }}>
            Turnos360
          </span>
        </footer>
      </div>
    </div>
  );
}