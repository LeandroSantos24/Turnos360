"use client";

/**
 * Vidriera pública del negocio (turnos360.com.ar/<slug>). La página que ve el
 * cliente final: hero con estado de apertura, servicios reservables, equipo,
 * galería, horarios, ubicación y redes — y el wizard de reserva online.
 *
 * Diseño claro (fondo blanco) con el color_marca del negocio como acento.
 * Las secciones viven en vidriera-ui.tsx y el flujo de reserva en
 * reserva-wizard.tsx.
 */

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { obtenerVidriera, type Vidriera } from "@/lib/publico-api";
import { ApiError } from "@/lib/api";
import {
  TopBar,
  Hero,
  Servicios,
  Equipo,
  Galeria,
  Horarios,
  Ubicacion,
  Contacto,
  FooterVidriera,
  BarraMobile,
  acentoDe,
  TINTA,
  TINTA_SUAVE,
  ACENTO_DEFAULT,
} from "./vidriera-ui";
import { ReservaWizard } from "./reserva-wizard";

export default function VidrieraPage({ params }: { params: { slug: string } }) {
  const [vidriera, setVidriera] = useState<Vidriera | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<"no-existe" | "error" | null>(null);
  const [wizard, setWizard] = useState<{ abierto: boolean; servicio: number | null }>({
    abierto: false,
    servicio: null,
  });

  useEffect(() => {
    obtenerVidriera(params.slug)
      .then((v) => {
        setVidriera(v);
        document.title = `${v.nombre} · Reservá tu turno online`;
      })
      .catch((e) =>
        setError(e instanceof ApiError && e.status === 404 ? "no-existe" : "error"),
      )
      .finally(() => setCargando(false));
  }, [params.slug]);

  if (cargando) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <Loader2 className="h-6 w-6 animate-spin" style={{ color: ACENTO_DEFAULT }} />
      </div>
    );
  }

  if (error || !vidriera) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 bg-white px-6 text-center">
        <h1
          className="text-xl font-bold"
          style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
        >
          {error === "no-existe" ? "Este negocio no existe" : "No pudimos cargar la página"}
        </h1>
        <p className="text-sm" style={{ color: TINTA_SUAVE }}>
          {error === "no-existe"
            ? "Verificá el link e intentá de nuevo."
            : "Probá recargar en unos segundos."}
        </p>
      </div>
    );
  }

  const acento = acentoDe(vidriera);
  const abrir = (servicioId?: number) =>
    setWizard({ abierto: true, servicio: servicioId ?? null });
  const cerrar = () => setWizard({ abierto: false, servicio: null });

  return (
    <div className="min-h-screen bg-white antialiased" style={{ color: TINTA }}>
      <TopBar v={vidriera} acento={acento} onReservar={() => abrir()} />
      <Hero v={vidriera} acento={acento} onReservar={() => abrir()} />

      {vidriera.descripcion && (
        <section className="mx-auto max-w-3xl px-5 pb-4 text-center">
          <p
            className="whitespace-pre-line text-base leading-relaxed"
            style={{ color: TINTA_SUAVE }}
          >
            {vidriera.descripcion}
          </p>
        </section>
      )}

      <Servicios v={vidriera} acento={acento} onElegir={(id) => abrir(id)} />
      <Equipo v={vidriera} acento={acento} />
      <Galeria v={vidriera} acento={acento} />
      <Horarios v={vidriera} acento={acento} />
      <Ubicacion v={vidriera} acento={acento} />
      <Contacto v={vidriera} acento={acento} />
      <FooterVidriera />

      <BarraMobile acento={acento} onReservar={() => abrir()} />
      <ReservaWizard
        v={vidriera}
        slug={params.slug}
        acento={acento}
        abierto={wizard.abierto}
        servicioInicial={wizard.servicio}
        onCerrar={cerrar}
      />
    </div>
  );
}
