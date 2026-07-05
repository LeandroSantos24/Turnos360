"use client";

/**
 * Secciones visuales de la vidriera pública (turnos360.com.ar/<slug>).
 * Diseño claro premium sobre fondo blanco: el color_marca del negocio tiñe
 * los acentos (botones, chips, detalles). Nada acá depende del tema del
 * panel (dark/light): todos los colores son explícitos a propósito.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  MapPin,
  Clock,
  MessageCircle,
  Globe,
  Mail,
  Phone,
  ChevronLeft,
  ChevronRight,
  X,
  CalendarCheck2,
  Sparkles,
} from "lucide-react";

import type { Vidriera } from "@/lib/publico-api";
import {
  IconoInstagram,
  IconoFacebook,
  IconoLinkedin,
  IconoTiktok,
  type IconoRed,
} from "@/components/iconos-redes";

/* ------------------------------------------------------------------ */
/* Tokens y helpers                                                    */
/* ------------------------------------------------------------------ */

export const TINTA = "#0c1015";
export const TINTA_SUAVE = "#4b5566";
export const BORDE = "#e9ecf1";
export const SUPERFICIE = "#f6f7f9";
export const ACENTO_DEFAULT = "#0ca88c";

/** Curva de easing compartida (tuple tipado: framer-motion 12 es estricto). */
const EASE: [number, number, number, number] = [0.21, 0.6, 0.35, 1];

/** #rrggbb -> rgba(r,g,b,a). Si el hex no es válido, cae al acento default. */
export function hexA(hex: string | null | undefined, alpha: number): string {
  const h = (hex ?? "").trim();
  const m = /^#?([0-9a-f]{6})$/i.exec(h);
  const v = m ? m[1] : ACENTO_DEFAULT.slice(1);
  const r = parseInt(v.slice(0, 2), 16);
  const g = parseInt(v.slice(2, 4), 16);
  const b = parseInt(v.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function acentoDe(v: Vidriera): string {
  const h = (v.color_marca ?? "").trim();
  return /^#[0-9a-f]{6}$/i.test(h) ? h : ACENTO_DEFAULT;
}

const DIAS_CLAVE = ["dom", "lun", "mar", "mie", "jue", "vie", "sab"] as const;
const DIAS_LABEL: Record<string, string> = {
  lun: "Lunes",
  mar: "Martes",
  mie: "Miércoles",
  jue: "Jueves",
  vie: "Viernes",
  sab: "Sábado",
  dom: "Domingo",
};

/** "Abierto ahora · hasta 19:00" / "Cerrado · abre mañana 09:00", desde
 *  horarios_atencion. Devuelve null si el negocio no cargó horarios. */
export function estadoApertura(
  horarios: Vidriera["horarios_atencion"],
): { abierto: boolean; texto: string } | null {
  if (!horarios) return null;
  const tiene = Object.values(horarios).some((f) => f && f.length > 0);
  if (!tiene) return null;

  const ahora = new Date();
  const hhmm = `${String(ahora.getHours()).padStart(2, "0")}:${String(
    ahora.getMinutes(),
  ).padStart(2, "0")}`;
  const hoyIdx = ahora.getDay();
  const franjasHoy = horarios[DIAS_CLAVE[hoyIdx]] ?? [];

  for (const [abre, cierra] of franjasHoy) {
    if (hhmm >= abre && hhmm < cierra) {
      return { abierto: true, texto: `Abierto ahora · hasta ${cierra}` };
    }
  }
  // Cerrado: ¿abre más tarde hoy?
  const proximaHoy = franjasHoy.find(([abre]) => abre > hhmm);
  if (proximaHoy) {
    return { abierto: false, texto: `Cerrado · abre hoy ${proximaHoy[0]}` };
  }
  // ¿Próximo día con franjas?
  for (let i = 1; i <= 7; i++) {
    const idx = (hoyIdx + i) % 7;
    const franjas = horarios[DIAS_CLAVE[idx]] ?? [];
    if (franjas.length > 0) {
      const cuando = i === 1 ? "mañana" : `el ${DIAS_LABEL[DIAS_CLAVE[idx]].toLowerCase()}`;
      return { abierto: false, texto: `Cerrado · abre ${cuando} ${franjas[0][0]}` };
    }
  }
  return { abierto: false, texto: "Cerrado" };
}

export function precioFmt(n: number | null): string {
  if (n == null) return "";
  return `$${n.toLocaleString("es-AR")}`;
}

export function linkWhatsApp(v: Vidriera): string | null {
  if (!v.telefono_publico) return null;
  const num = v.telefono_publico.replace(/\D/g, "");
  const texto = encodeURIComponent(`¡Hola ${v.nombre}! Quiero hacer una consulta.`);
  return `https://wa.me/${num}?text=${texto}`;
}

const REDES_META: Record<string, { label: string; Icono: IconoRed }> = {
  instagram: { label: "Instagram", Icono: IconoInstagram },
  facebook: { label: "Facebook", Icono: IconoFacebook },
  tiktok: { label: "TikTok", Icono: IconoTiktok },
  linkedin: { label: "LinkedIn", Icono: IconoLinkedin },
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

/* ------------------------------------------------------------------ */
/* Piezas chicas reutilizables                                         */
/* ------------------------------------------------------------------ */

/** Etiqueta de sección: puntito del acento + texto en mayúsculas. */
function Eyebrow({ acento, children }: { acento: string; children: React.ReactNode }) {
  return (
    <p
      className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em]"
      style={{ color: TINTA_SUAVE }}
    >
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: acento }}
      />
      {children}
    </p>
  );
}

function TituloSeccion({ children }: { children: React.ReactNode }) {
  return (
    <h2
      className="text-2xl font-bold tracking-tight md:text-3xl"
      style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
    >
      {children}
    </h2>
  );
}

/** Wrapper de aparición al scroll (respeta prefers-reduced-motion). */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 26 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-70px" }}
      transition={{ duration: 0.55, delay, ease: EASE }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/** Botón primario teñido con el acento del negocio. */
export function BotonAcento({
  acento,
  onClick,
  href,
  children,
  grande = false,
}: {
  acento: string;
  onClick?: () => void;
  href?: string;
  children: React.ReactNode;
  grande?: boolean;
}) {
  const clase = `inline-flex items-center justify-center gap-2 rounded-full font-semibold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${
    grande ? "px-7 py-3.5 text-base" : "px-5 py-2.5 text-sm"
  }`;
  const estilo = {
    background: acento,
    outlineColor: acento,
    boxShadow: `0 8px 24px -10px ${hexA(acento, 0.55)}`,
  };
  if (href) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={clase} style={estilo}>
        {children}
      </a>
    );
  }
  return (
    <button type="button" onClick={onClick} className={clase} style={estilo}>
      {children}
    </button>
  );
}

function Monograma({ v, acento, tam }: { v: Vidriera; acento: string; tam: string }) {
  if (v.logo_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={v.logo_url}
        alt={v.nombre}
        className={`${tam} rounded-2xl border object-cover`}
        style={{ borderColor: BORDE }}
      />
    );
  }
  return (
    <div
      className={`${tam} flex items-center justify-center rounded-2xl text-white`}
      style={{
        background: `linear-gradient(135deg, ${acento}, ${hexA(acento, 0.72)})`,
        fontFamily: "Syne, sans-serif",
      }}
    >
      <span className="text-[1.6em] font-bold">{v.nombre.charAt(0).toUpperCase()}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Topbar sticky                                                       */
/* ------------------------------------------------------------------ */

export function TopBar({ v, acento, onReservar }: { v: Vidriera; acento: string; onReservar: () => void }) {
  const [conFondo, setConFondo] = useState(false);
  useEffect(() => {
    const f = () => setConFondo(window.scrollY > 24);
    f();
    window.addEventListener("scroll", f, { passive: true });
    return () => window.removeEventListener("scroll", f);
  }, []);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-40 transition-all ${
        conFondo ? "backdrop-blur-md" : ""
      }`}
      style={{
        background: conFondo ? "rgba(255,255,255,0.82)" : "transparent",
        borderBottom: conFondo ? `1px solid ${BORDE}` : "1px solid transparent",
      }}
    >
      <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-5">
        <div className="flex min-w-0 items-center gap-3">
          <Monograma v={v} acento={acento} tam="h-9 w-9 text-xs" />
          <span
            className="truncate text-base font-bold"
            style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
          >
            {v.nombre}
          </span>
        </div>
        <BotonAcento acento={acento} onClick={onReservar}>
          <CalendarCheck2 className="h-4 w-4" />
          Reservar
        </BotonAcento>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/* Hero                                                                */
/* ------------------------------------------------------------------ */

export function Hero({ v, acento, onReservar }: { v: Vidriera; acento: string; onReservar: () => void }) {
  const reduce = useReducedMotion();
  const estado = useMemo(() => estadoApertura(v.horarios_atencion), [v.horarios_atencion]);
  const wa = linkWhatsApp(v);

  const contenedor = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.09 } },
  };
  const item = {
    hidden: { opacity: 0, y: 22 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE } },
  };

  return (
    <section className="relative overflow-hidden pt-28 pb-16 md:pt-36 md:pb-24">
      {/* Veladura sutil del acento arriba: vida sin dejar de ser fondo blanco */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -top-40 h-[420px]"
        style={{
          background: `radial-gradient(60% 60% at 50% 0%, ${hexA(acento, 0.1)} 0%, transparent 70%)`,
        }}
      />
      <motion.div
        variants={contenedor}
        initial={reduce ? "visible" : "hidden"}
        animate="visible"
        className="relative mx-auto flex max-w-3xl flex-col items-center px-5 text-center"
      >
        <motion.div variants={item}>
          <Monograma v={v} acento={acento} tam="h-24 w-24 text-2xl md:h-28 md:w-28" />
        </motion.div>

        <motion.h1
          variants={item}
          className="mt-6 text-[2.6rem] font-extrabold leading-[1.05] tracking-tight md:text-6xl"
          style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
        >
          {v.nombre}
        </motion.h1>

        {estado && (
          <motion.div
            variants={item}
            className="mt-4 inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-sm font-medium"
            style={{
              borderColor: estado.abierto ? hexA(acento, 0.35) : BORDE,
              background: estado.abierto ? hexA(acento, 0.08) : SUPERFICIE,
              color: estado.abierto ? acento : TINTA_SUAVE,
            }}
          >
            <span className="relative flex h-2 w-2">
              {estado.abierto && (
                <span
                  className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
                  style={{ background: acento }}
                />
              )}
              <span
                className="relative inline-flex h-2 w-2 rounded-full"
                style={{ background: estado.abierto ? acento : "#9aa3b2" }}
              />
            </span>
            {estado.texto}
          </motion.div>
        )}

        {v.direccion && (
          <motion.p
            variants={item}
            className="mt-3 flex items-center gap-1.5 text-sm"
            style={{ color: TINTA_SUAVE }}
          >
            <MapPin className="h-4 w-4" />
            {v.direccion}
          </motion.p>
        )}

        <motion.div variants={item} className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <BotonAcento acento={acento} onClick={onReservar} grande>
            <CalendarCheck2 className="h-5 w-5" />
            Reservar turno
          </BotonAcento>
          {wa && (
            <a
              href={wa}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-full border px-6 py-3.5 text-base font-semibold transition-colors hover:bg-[#f6f7f9]"
              style={{ borderColor: BORDE, color: TINTA }}
            >
              <MessageCircle className="h-5 w-5" style={{ color: acento }} />
              WhatsApp
            </a>
          )}
        </motion.div>
      </motion.div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Servicios                                                           */
/* ------------------------------------------------------------------ */

export function Servicios({
  v,
  acento,
  onElegir,
}: {
  v: Vidriera;
  acento: string;
  onElegir: (servicioId: number) => void;
}) {
  if (v.servicios.length === 0) return null;
  return (
    <section id="servicios" className="mx-auto max-w-5xl px-5 py-12 md:py-16">
      <Reveal>
        <Eyebrow acento={acento}>Servicios</Eyebrow>
        <TituloSeccion>Elegí tu servicio</TituloSeccion>
        <p className="mt-2 text-sm" style={{ color: TINTA_SUAVE }}>
          Tocá un servicio para reservarlo online.
        </p>
      </Reveal>
      <div className="mt-7 grid gap-3.5 sm:grid-cols-2">
        {v.servicios.map((s, i) => (
          <Reveal key={s.id} delay={Math.min(i * 0.05, 0.3)}>
            <button
              type="button"
              onClick={() => onElegir(s.id)}
              className="group flex w-full items-center justify-between gap-4 rounded-2xl border bg-white p-5 text-left transition-all hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
              style={{ borderColor: BORDE, outlineColor: acento }}
            >
              <div className="min-w-0">
                <p className="truncate text-base font-semibold" style={{ color: TINTA }}>
                  {s.nombre}
                </p>
                <p className="mt-1 flex items-center gap-1.5 text-sm" style={{ color: TINTA_SUAVE }}>
                  <Clock className="h-3.5 w-3.5" />
                  {s.duracion_min} min
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                {s.precio != null && (
                  <span
                    className="text-lg font-bold"
                    style={{ color: TINTA, fontVariantNumeric: "lining-nums tabular-nums" }}
                  >
                    {precioFmt(s.precio)}
                  </span>
                )}
                <span
                  className="flex h-9 w-9 items-center justify-center rounded-full transition-all group-hover:text-white"
                  style={{ background: hexA(acento, 0.1), color: acento }}
                >
                  <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </span>
              </div>
            </button>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Equipo (carrusel horizontal con snap)                               */
/* ------------------------------------------------------------------ */

export function Equipo({ v, acento }: { v: Vidriera; acento: string }) {
  const ref = useRef<HTMLDivElement>(null);
  if (v.recursos.length === 0) return null;

  const mover = (dir: 1 | -1) => {
    ref.current?.scrollBy({ left: dir * 220, behavior: "smooth" });
  };

  return (
    <section className="py-12 md:py-16" style={{ background: SUPERFICIE }}>
      <div className="mx-auto max-w-5xl px-5">
        <Reveal className="flex items-end justify-between gap-4">
          <div>
            <Eyebrow acento={acento}>Equipo</Eyebrow>
            <TituloSeccion>Quiénes te atienden</TituloSeccion>
          </div>
          {v.recursos.length > 3 && (
            <div className="hidden gap-2 md:flex">
              {[
                { Icono: ChevronLeft, dir: -1 as const, label: "Anterior" },
                { Icono: ChevronRight, dir: 1 as const, label: "Siguiente" },
              ].map(({ Icono, dir, label }) => (
                <button
                  key={label}
                  type="button"
                  aria-label={label}
                  onClick={() => mover(dir)}
                  className="flex h-10 w-10 items-center justify-center rounded-full border bg-white transition-colors hover:bg-[#eef0f4]"
                  style={{ borderColor: BORDE, color: TINTA }}
                >
                  <Icono className="h-4 w-4" />
                </button>
              ))}
            </div>
          )}
        </Reveal>

        <Reveal delay={0.08}>
          <div
            ref={ref}
            className="mt-7 flex snap-x snap-mandatory gap-4 overflow-x-auto pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            {v.recursos.map((r) => (
              <figure key={r.id} className="w-[160px] shrink-0 snap-start md:w-[190px]">
                <div
                  className="group relative aspect-[4/5] overflow-hidden rounded-2xl border bg-white"
                  style={{ borderColor: BORDE }}
                >
                  {r.foto_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={r.foto_url}
                      alt={r.nombre}
                      loading="lazy"
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
                    />
                  ) : (
                    <div
                      className="flex h-full w-full items-center justify-center text-4xl font-bold text-white"
                      style={{
                        background: `linear-gradient(150deg, ${hexA(acento, 0.9)}, ${hexA(acento, 0.55)})`,
                        fontFamily: "Syne, sans-serif",
                      }}
                    >
                      {r.nombre.charAt(0).toUpperCase()}
                    </div>
                  )}
                </div>
                <figcaption className="mt-2.5 text-center text-sm font-semibold" style={{ color: TINTA }}>
                  {r.nombre}
                </figcaption>
              </figure>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Galería con lightbox                                                */
/* ------------------------------------------------------------------ */

export function Galeria({ v, acento }: { v: Vidriera; acento: string }) {
  const [abierta, setAbierta] = useState<number | null>(null);
  const fotos = v.galeria ?? [];

  useEffect(() => {
    if (abierta === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAbierta(null);
      if (e.key === "ArrowRight") setAbierta((i) => (i === null ? i : (i + 1) % fotos.length));
      if (e.key === "ArrowLeft")
        setAbierta((i) => (i === null ? i : (i - 1 + fotos.length) % fotos.length));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [abierta, fotos.length]);

  if (fotos.length === 0) return null;

  return (
    <section className="mx-auto max-w-5xl px-5 py-12 md:py-16">
      <Reveal>
        <Eyebrow acento={acento}>Galería</Eyebrow>
        <TituloSeccion>Un vistazo al lugar</TituloSeccion>
      </Reveal>
      <div className="mt-7 grid auto-rows-[150px] grid-cols-2 gap-3 md:auto-rows-[190px] md:grid-cols-3">
        {fotos.map((url, i) => (
          <Reveal key={`${url}-${i}`} delay={Math.min(i * 0.04, 0.25)} className={i % 6 === 0 ? "row-span-2" : ""}>
            <button
              type="button"
              onClick={() => setAbierta(i)}
              className="group block h-full w-full overflow-hidden rounded-2xl border focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
              style={{ borderColor: BORDE, outlineColor: acento }}
              aria-label={`Ver foto ${i + 1}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={url}
                alt=""
                loading="lazy"
                className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.05]"
              />
            </button>
          </Reveal>
        ))}
      </div>

      <AnimatePresence>
        {abierta !== null && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
            onClick={() => setAbierta(null)}
            role="dialog"
            aria-modal="true"
            aria-label="Foto ampliada"
          >
            <button
              type="button"
              aria-label="Cerrar"
              className="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/20"
              onClick={() => setAbierta(null)}
            >
              <X className="h-5 w-5" />
            </button>
            {fotos.length > 1 && (
              <>
                <button
                  type="button"
                  aria-label="Anterior"
                  className="absolute left-3 flex h-11 w-11 items-center justify-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/20 md:left-6"
                  onClick={(e) => {
                    e.stopPropagation();
                    setAbierta((i) => (i === null ? i : (i - 1 + fotos.length) % fotos.length));
                  }}
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
                <button
                  type="button"
                  aria-label="Siguiente"
                  className="absolute right-3 flex h-11 w-11 items-center justify-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/20 md:right-6"
                  onClick={(e) => {
                    e.stopPropagation();
                    setAbierta((i) => (i === null ? i : (i + 1) % fotos.length));
                  }}
                >
                  <ChevronRight className="h-5 w-5" />
                </button>
              </>
            )}
            <motion.img
              key={abierta}
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              src={fotos[abierta]}
              alt={`Foto ${abierta + 1} de ${fotos.length}`}
              className="max-h-[86vh] max-w-full rounded-xl object-contain"
              onClick={(e) => e.stopPropagation()}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Horarios (resalta el día actual)                                    */
/* ------------------------------------------------------------------ */

export function Horarios({ v, acento }: { v: Vidriera; acento: string }) {
  const tiene =
    v.horarios_atencion && Object.values(v.horarios_atencion).some((f) => f.length > 0);
  if (!tiene) return null;
  const hoy = DIAS_CLAVE[new Date().getDay()];

  return (
    <section className="mx-auto max-w-5xl px-5 py-12 md:py-16">
      <div className="grid gap-8 md:grid-cols-[1fr_1.2fr] md:items-start">
        <Reveal>
          <Eyebrow acento={acento}>Horarios</Eyebrow>
          <TituloSeccion>Cuándo encontrarnos</TituloSeccion>
          <p className="mt-2 text-sm" style={{ color: TINTA_SUAVE }}>
            También podés reservar online a cualquier hora: la agenda queda
            confirmada al instante.
          </p>
        </Reveal>
        <Reveal delay={0.08}>
          <div className="overflow-hidden rounded-2xl border bg-white" style={{ borderColor: BORDE }}>
            {(["lun", "mar", "mie", "jue", "vie", "sab", "dom"] as const).map((clave) => {
              const franjas = v.horarios_atencion?.[clave] ?? [];
              const esHoy = clave === hoy;
              return (
                <div
                  key={clave}
                  className="flex items-center justify-between border-b px-4 py-3 text-sm last:border-b-0"
                  style={{
                    borderColor: BORDE,
                    background: esHoy ? hexA(acento, 0.07) : "transparent",
                  }}
                >
                  <span className="flex items-center gap-2 font-semibold" style={{ color: TINTA }}>
                    {esHoy && (
                      <span className="h-1.5 w-1.5 rounded-full" style={{ background: acento }} />
                    )}
                    {DIAS_LABEL[clave]}
                    {esHoy && (
                      <span className="text-xs font-medium" style={{ color: acento }}>
                        Hoy
                      </span>
                    )}
                  </span>
                  <span
                    style={{
                      color: franjas.length ? TINTA_SUAVE : "#9aa3b2",
                      fontVariantNumeric: "lining-nums tabular-nums",
                    }}
                  >
                    {franjas.length > 0
                      ? franjas.map((f) => `${f[0]} a ${f[1]}`).join(" · ")
                      : "Cerrado"}
                  </span>
                </div>
              );
            })}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Ubicación con mapa embebido                                         */
/* ------------------------------------------------------------------ */

export function Ubicacion({ v, acento }: { v: Vidriera; acento: string }) {
  if (!v.direccion) return null;
  const q = encodeURIComponent(v.direccion);
  return (
    <section className="mx-auto max-w-5xl px-5 py-12 md:py-16">
      <Reveal>
        <Eyebrow acento={acento}>Ubicación</Eyebrow>
        <TituloSeccion>Dónde estamos</TituloSeccion>
        <p className="mt-2 flex items-center gap-1.5 text-sm" style={{ color: TINTA_SUAVE }}>
          <MapPin className="h-4 w-4" style={{ color: acento }} />
          {v.direccion}
          <a
            href={`https://www.google.com/maps/search/?api=1&query=${q}`}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-2 font-semibold underline-offset-2 hover:underline"
            style={{ color: acento }}
          >
            Cómo llegar
          </a>
        </p>
      </Reveal>
      <Reveal delay={0.08}>
        <div className="mt-6 overflow-hidden rounded-3xl border" style={{ borderColor: BORDE }}>
          <iframe
            title={`Mapa de ${v.nombre}`}
            src={`https://www.google.com/maps?q=${q}&output=embed`}
            className="h-[300px] w-full md:h-[360px]"
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
          />
        </div>
      </Reveal>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Contacto y redes                                                    */
/* ------------------------------------------------------------------ */

export function Contacto({ v, acento }: { v: Vidriera; acento: string }) {
  const redes = Object.entries(v.redes || {}).filter(([, val]) => val && val.trim() !== "");
  const tieneAlgo = redes.length > 0 || v.telefono_publico || v.email_publico;
  if (!tieneAlgo) return null;

  return (
    <section className="mx-auto max-w-5xl px-5 pb-14 pt-4 md:pb-20">
      <Reveal className="flex flex-wrap items-center gap-2.5">
        {v.telefono_publico && (
          <a
            href={`tel:${v.telefono_publico.replace(/\s/g, "")}`}
            className="flex items-center gap-1.5 rounded-full border bg-white px-3.5 py-2 text-sm font-medium transition-colors hover:bg-[#f6f7f9]"
            style={{ borderColor: BORDE, color: TINTA }}
          >
            <Phone className="h-4 w-4" style={{ color: acento }} />
            {v.telefono_publico}
          </a>
        )}
        {v.email_publico && (
          <a
            href={`mailto:${v.email_publico}`}
            className="flex items-center gap-1.5 rounded-full border bg-white px-3.5 py-2 text-sm font-medium transition-colors hover:bg-[#f6f7f9]"
            style={{ borderColor: BORDE, color: TINTA }}
          >
            <Mail className="h-4 w-4" style={{ color: acento }} />
            {v.email_publico}
          </a>
        )}
        {redes.map(([clave, valor]) => {
          const meta = REDES_META[clave] ?? { label: clave, Icono: Globe };
          const Icono = meta.Icono;
          return (
            <a
              key={clave}
              href={hrefRed(clave, valor)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-full border bg-white px-3.5 py-2 text-sm font-medium transition-colors hover:bg-[#f6f7f9]"
              style={{ borderColor: BORDE, color: TINTA }}
            >
              <Icono className="h-4 w-4" style={{ color: acento }} />
              {meta.label}
            </a>
          );
        })}
      </Reveal>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Footer + barra mobile                                               */
/* ------------------------------------------------------------------ */

export function FooterVidriera() {
  return (
    <footer className="border-t py-8 pb-24 text-center md:pb-8" style={{ borderColor: BORDE }}>
      <a
        href="/"
        className="inline-flex items-center gap-1.5 text-xs font-medium transition-colors hover:text-[#0c1015]"
        style={{ color: TINTA_SUAVE }}
      >
        <Sparkles className="h-3.5 w-3.5" />
        Reservas online con{" "}
        <span className="font-bold" style={{ fontFamily: "Syne, sans-serif", color: TINTA }}>
          Turnos360
        </span>
      </a>
    </footer>
  );
}

/** CTA fija abajo, solo mobile: la conversión vive acá. */
export function BarraMobile({ acento, onReservar }: { acento: string; onReservar: () => void }) {
  return (
    <div
      className="fixed inset-x-0 bottom-0 z-40 border-t bg-white/90 px-5 py-3 backdrop-blur-md md:hidden"
      style={{ borderColor: BORDE, paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}
    >
      <button
        type="button"
        onClick={onReservar}
        className="flex w-full items-center justify-center gap-2 rounded-full py-3.5 text-base font-bold text-white shadow-md"
        style={{ background: acento, boxShadow: `0 8px 24px -10px ${hexA(acento, 0.6)}` }}
      >
        <CalendarCheck2 className="h-5 w-5" />
        Reservar turno
      </button>
    </div>
  );
}
