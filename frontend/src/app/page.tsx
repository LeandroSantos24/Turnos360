"use client";

/**
 * Landing comercial de Turnos360 (https://turnos360.com.ar/). La página que
 * presenta el producto a los dueños de negocios: qué hace, cómo funciona y
 * cómo pedir una demo. El CTA es WhatsApp porque el onboarding es administrado
 * (no hay self-signup).
 *
 * Página pública: fondo blanco y colores explícitos (inmune al modo oscuro
 * del panel). Marca: teal + lima del logo, tipografías Syne + DM Sans.
 */

import { Fragment, useEffect, useState } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import {
  CalendarDays,
  Globe,
  Wallet,
  BadgeCheck,
  Users,
  BarChart3,
  MessageCircle,
  Check,
  ArrowRight,
  Sparkles,
  Scissors,
  Brush,
  Hand,
  Waves,
  Apple,
  Mail,
  Gift,
  Bell,
  CreditCard,
  X,
  ChevronDown,
} from "lucide-react";

/* ============================================================
   COMPLETAR ANTES DEL DEPLOY
   Número de WhatsApp para pedir demos, SIN "+" ni espacios.
   Ej: Argentina móvil → 549 + código de área + número.
   ============================================================ */
const WHATSAPP_NUMERO = "5492613456599";

const EMAIL_CONTACTO = "turnos360.contacto@gmail.com"; // ← CONFIRMAR dirección exacta
const MENSAJE_DEMO = "Hola! Quiero una demo de Turnos360 para mi negocio.";
const LINK_DEMO = `https://wa.me/${WHATSAPP_NUMERO}?text=${encodeURIComponent(MENSAJE_DEMO)}`;

/* Marca (tomada del logo) */
const TINTA = "#0c1015";
const TINTA_SUAVE = "#4b5566";
const BORDE = "#e9ecf1";
const SUPERFICIE = "#f6f7f9";
const TEAL = "#17a08a";
const TEAL_OSCURO = "#0e8371";
const LIMA = "#8bc540";

function hexA(hex: string, alpha: number) {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

const EASE: [number, number, number, number] = [0.21, 0.6, 0.35, 1];

/** Aparece al entrar en viewport (una sola vez). */
function Reveal({
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
      initial={reduce ? false : { opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, delay, ease: EASE }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

function BotonDemo({ grande = false }: { grande?: boolean }) {
  return (
    <a
      href={LINK_DEMO}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center justify-center gap-2 rounded-full font-semibold text-white shadow-lg transition-transform hover:scale-[1.02] active:scale-[0.98] ${
        grande ? "px-7 py-3.5 text-base" : "px-5 py-2.5 text-sm"
      }`}
      style={{
        background: `linear-gradient(135deg, ${TEAL}, ${TEAL_OSCURO})`,
        boxShadow: `0 10px 30px -10px ${hexA(TEAL, 0.55)}`,
      }}
    >
      <MessageCircle className={grande ? "h-5 w-5" : "h-4 w-4"} />
      Pedí una demo
    </a>
  );
}

/* ============ Mock del producto (CSS puro) ============ */

function TurnoMock({
  hora,
  nombre,
  servicio,
  color,
  alto,
}: {
  hora: string;
  nombre: string;
  servicio: string;
  color: string;
  alto: string;
}) {
  return (
    <div
      className={`rounded-lg border-l-[3px] px-2 py-1.5 ${alto}`}
      style={{ borderLeftColor: color, background: hexA(color, 0.09) }}
    >
      <p className="text-[9px] font-semibold leading-tight" style={{ color: TINTA }}>
        {hora} · {nombre}
      </p>
      <p className="text-[8px] leading-tight" style={{ color: TINTA_SUAVE }}>
        {servicio}
      </p>
    </div>
  );
}

function MockProducto() {
  return (
    <div className="relative mx-auto w-full max-w-2xl">
      {/* Ventana del panel */}
      <div
        className="overflow-hidden rounded-2xl border bg-white"
        style={{ borderColor: BORDE, boxShadow: "0 30px 80px -30px rgba(12,16,21,0.28)" }}
      >
        {/* Barra tipo ventana */}
        <div
          className="flex items-center gap-2 border-b px-4 py-2.5"
          style={{ borderColor: BORDE, background: SUPERFICIE }}
        >
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
          <p className="ml-2 text-[11px] font-medium" style={{ color: TINTA_SUAVE }}>
            Agenda · Hoy
          </p>
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-[9px] font-semibold"
            style={{ background: hexA(TEAL, 0.12), color: TEAL_OSCURO }}
          >
            12 turnos · $184.500 previstos
          </span>
        </div>

        {/* Grilla de carriles */}
        <div className="grid grid-cols-3 gap-2 p-3">
          {[
            {
              titulo: "Corte",
              color: TEAL,
              turnos: [
                { hora: "10:00", nombre: "Juan P.", servicio: "Corte fade", alto: "h-12" },
                { hora: "10:45", nombre: "Marcos L.", servicio: "Corte + lavado", alto: "h-12" },
                { hora: "11:30", nombre: "Tomás R.", servicio: "Corte clásico", alto: "h-10" },
              ],
            },
            {
              titulo: "Tintura",
              color: "#8b5cf6",
              turnos: [
                { hora: "10:00", nombre: "Sofía M.", servicio: "Color completo", alto: "h-[104px]" },
                { hora: "12:00", nombre: "Carla D.", servicio: "Mechas", alto: "h-16" },
              ],
            },
            {
              titulo: "Barba",
              color: "#f59e0b",
              turnos: [
                { hora: "10:15", nombre: "Diego F.", servicio: "Perfilado", alto: "h-10" },
                { hora: "11:00", nombre: "Lucas B.", servicio: "Barba + toalla", alto: "h-12" },
                { hora: "12:00", nombre: "Nico S.", servicio: "Perfilado", alto: "h-10" },
              ],
            },
          ].map((carril) => (
            <div key={carril.titulo}>
              <p
                className="mb-1.5 text-center text-[9px] font-bold uppercase tracking-wider"
                style={{ color: carril.color }}
              >
                {carril.titulo}
              </p>
              <div className="space-y-1.5">
                {carril.turnos.map((t) => (
                  <TurnoMock key={t.hora + t.nombre} {...t} color={carril.color} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tarjeta flotante: caja */}
      <div
        className="absolute -bottom-6 -right-3 hidden w-52 rotate-1 rounded-xl border bg-white p-3.5 md:block"
        style={{ borderColor: BORDE, boxShadow: "0 20px 50px -20px rgba(12,16,21,0.3)" }}
      >
        <p className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: TINTA_SUAVE }}>
          Caja del día
        </p>
        <p
          className="mt-0.5 text-xl font-bold tabular-nums"
          style={{ color: TINTA, fontFamily: "Syne, sans-serif" }}
        >
          $184.500
        </p>
        <div className="mt-2 space-y-1 text-[10px] tabular-nums" style={{ color: TINTA_SUAVE }}>
          {[
            ["Efectivo", "$92.000"],
            ["Mercado Pago", "$61.500"],
            ["Débito", "$31.000"],
          ].map(([m, v]) => (
            <div key={m} className="flex justify-between">
              <span>{m}</span>
              <span className="font-semibold" style={{ color: TINTA }}>
                {v}
              </span>
            </div>
          ))}
        </div>
        <div
          className="mt-2 flex items-center gap-1 rounded-md px-1.5 py-1 text-[9px] font-semibold"
          style={{ background: hexA(LIMA, 0.16), color: "#4f7317" }}
        >
          <Check className="h-3 w-3" />
          Arqueo sin diferencias
        </div>
      </div>

      {/* Tarjeta flotante: reserva online */}
      <div
        className="absolute -left-4 -top-5 hidden -rotate-2 items-center gap-2 rounded-xl border bg-white px-3 py-2.5 md:flex"
        style={{ borderColor: BORDE, boxShadow: "0 16px 40px -18px rgba(12,16,21,0.3)" }}
      >
        <span
          className="flex h-7 w-7 items-center justify-center rounded-full"
          style={{ background: hexA(TEAL, 0.12) }}
        >
          <Globe className="h-3.5 w-3.5" style={{ color: TEAL_OSCURO }} />
        </span>
        <div>
          <p className="text-[10px] font-bold leading-tight" style={{ color: TINTA }}>
            Nueva reserva online
          </p>
          <p className="text-[9px] leading-tight" style={{ color: TINTA_SUAVE }}>
            Martina · Corte · mañana 16:30
          </p>
        </div>
      </div>
    </div>
  );
}

/* ============ Secciones ============ */

function Navbar() {
  const [conFondo, setConFondo] = useState(false);
  useEffect(() => {
    const f = () => setConFondo(window.scrollY > 10);
    f();
    window.addEventListener("scroll", f, { passive: true });
    return () => window.removeEventListener("scroll", f);
  }, []);

  return (
    <header
      className="fixed inset-x-0 top-0 z-40 transition-all"
      style={{
        background: conFondo ? "rgba(255,255,255,0.86)" : "transparent",
        backdropFilter: conFondo ? "blur(12px)" : undefined,
        WebkitBackdropFilter: conFondo ? "blur(12px)" : undefined,
        borderBottom: conFondo ? `1px solid ${BORDE}` : "1px solid transparent",
      }}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <a href="#" className="flex items-center gap-2.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/marca/isotipo.png" alt="" className="h-10 w-auto" />
          <span
            className="text-[19px] font-bold tracking-tight"
            style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
          >
            Turnos<span style={{ color: TEAL }}>360</span>
          </span>
        </a>
        <nav className="hidden items-center gap-7 text-sm font-medium md:flex" style={{ color: TINTA_SUAVE }}>
          <a href="#funciones" className="transition-colors hover:text-black">
            Funciones
          </a>
          <a href="#como-funciona" className="transition-colors hover:text-black">
            Cómo funciona
          </a>
          <a href="#rubros" className="transition-colors hover:text-black">
            Rubros
          </a>
          <a href="#precios" className="transition-colors hover:text-black">
            Precios
          </a>
          <a href="#faq" className="transition-colors hover:text-black">
            Preguntas
          </a>
        </nav>
        <div className="flex items-center gap-2 sm:gap-4">
          <Link
            href="/login"
            className="text-sm font-semibold transition-colors hover:text-black"
            style={{ color: TINTA_SUAVE }}
          >
            <span className="sm:hidden">Entrar</span>
            <span className="hidden sm:inline">Iniciar sesión</span>
          </Link>
          <BotonDemo />
        </div>
      </div>
    </header>
  );
}

function Hero() {
  const reduce = useReducedMotion();
  const contenedor = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.1 } },
  };
  const item = {
    hidden: { opacity: 0, y: 24 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE } },
  };

  return (
    <section className="relative overflow-hidden pb-24 pt-32 md:pt-40">
      {/* Veladuras de marca */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: `radial-gradient(700px 380px at 18% -5%, ${hexA(TEAL, 0.1)}, transparent 65%), radial-gradient(600px 340px at 88% 8%, ${hexA(LIMA, 0.1)}, transparent 65%)`,
        }}
      />
      <motion.div
        variants={contenedor}
        initial={reduce ? "visible" : "hidden"}
        animate="visible"
        className="relative mx-auto max-w-6xl px-5"
      >
        <div className="mx-auto max-w-3xl text-center">
          <motion.div variants={item}>
            <span
              className="inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-semibold"
              style={{ borderColor: hexA(TEAL, 0.35), color: TEAL_OSCURO, background: hexA(TEAL, 0.07) }}
            >
              <Sparkles className="h-3.5 w-3.5" />
              Gestión integral de turnos y clientes
            </span>
          </motion.div>

          <motion.h1
            variants={item}
            className="mt-5 text-4xl font-bold leading-[1.08] tracking-tight md:text-6xl"
            style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
          >
            Tu negocio ordenado.
            <br />
            <span
              style={{
                background: `linear-gradient(90deg, ${TEAL}, ${LIMA})`,
                WebkitBackgroundClip: "text",
                backgroundClip: "text",
                color: "transparent",
              }}
            >
              Tus clientes reservan solos.
            </span>
          </motion.h1>

          <motion.p
            variants={item}
            className="mx-auto mt-5 max-w-xl text-base leading-relaxed md:text-lg"
            style={{ color: TINTA_SUAVE }}
          >
            Agenda inteligente, reservas online 24/7, caja, membresías y CRM en un solo
            sistema. Pensado para barberías, peluquerías, uñas y estética.
          </motion.p>

          <motion.div variants={item} className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <BotonDemo grande />
            <a
              href="#funciones"
              className="inline-flex items-center gap-1.5 rounded-full border px-6 py-3 text-sm font-semibold transition-colors"
              style={{ borderColor: BORDE, color: TINTA }}
            >
              Ver funciones
              <ArrowRight className="h-4 w-4" />
            </a>
          </motion.div>

          <motion.div
            variants={item}
            className="mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs font-medium"
            style={{ color: TINTA_SUAVE }}
          >
            {[
              "Sin comisión por reserva",
              "Te lo configuramos nosotros",
              "Cancelás cuando quieras",
            ].map((g) => (
              <span key={g} className="inline-flex items-center gap-1.5">
                <Check className="h-3.5 w-3.5" strokeWidth={3} style={{ color: TEAL }} />
                {g}
              </span>
            ))}
          </motion.div>
        </div>

        <motion.div variants={item} className="mt-14 md:mt-16">
          <MockProducto />
        </motion.div>
      </motion.div>
    </section>
  );
}

const FUNCIONES: { Icono: typeof CalendarDays; titulo: string; texto: string; badgeMP?: boolean }[] = [
  {
    Icono: CalendarDays,
    titulo: "Agenda con carriles paralelos",
    texto:
      "Corte, tintura y barba conviven a la misma hora sin pisarse. La grilla refleja cómo trabaja tu equipo de verdad, con sobreturnos controlados.",
  },
  {
    Icono: CreditCard,
    titulo: "Cobro online al reservar",
    texto:
      "Vos elegís: una seña o el total del servicio. El que paga, aparece — y la plata va directo a TU cuenta de Mercado Pago, sin pasar por nadie.",
    badgeMP: true,
  },
  {
    Icono: Globe,
    titulo: "Reservas online 24/7",
    texto:
      "Tu página pública con servicios, equipo, galería y reserva en 4 pasos. El turno cae directo en tu agenda, hasta cuando el local está cerrado.",
  },
  {
    Icono: Bell,
    titulo: "Recordatorios automáticos",
    texto:
      "Confirmación por email al reservar y recordatorio 24 horas antes, solos. El cliente se olvida menos y vos no perseguís a nadie.",
  },
  {
    Icono: Wallet,
    titulo: "Caja y arqueo de verdad",
    texto:
      "Apertura, cierre, pago dividido y comisión por método. Sabés cuánto entró por efectivo, Mercado Pago o tarjeta, y si la caja cierra sin diferencias.",
  },
  {
    Icono: BadgeCheck,
    titulo: "Membresías y abonos",
    texto:
      "La promo \"pagás el mes y venís siempre\" administrada sola: qué cubre cada plan, quién lo tiene activo y cuánto te rinde cada abono.",
  },
  {
    Icono: Gift,
    titulo: "Gift cards con QR",
    texto:
      "Generás la tarjeta con código único, la imprimís o la mandás por WhatsApp, y se canjea una sola vez. Imposible de falsificar.",
  },
  {
    Icono: Users,
    titulo: "Clientes con historial",
    texto:
      "Cada cliente con su ficha: visitas, gasto real, servicio favorito y observaciones. Reconocés al frecuente y detectás al que dejó de venir.",
  },
  {
    Icono: BarChart3,
    titulo: "Números para decidir",
    texto:
      "Facturación cobrada por día, semana y mes, ticket promedio y desglose por profesional. Lo previsto y lo real, separados.",
  },
  {
    Icono: MessageCircle,
    titulo: "WhatsApp a un toque",
    texto:
      "El teléfono de cada cliente abre el chat directo para confirmar o avisar. Sin copiar números ni salir del sistema.",
  },
];

function Funciones() {
  return (
    <section id="funciones" className="scroll-mt-20 py-20" style={{ background: SUPERFICIE }}>
      <div className="mx-auto max-w-6xl px-5">
        <Reveal className="mx-auto max-w-2xl text-center">
          <h2
            className="text-3xl font-bold tracking-tight md:text-4xl"
            style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
          >
            Todo lo que tu negocio usa, en un solo lugar
          </h2>
          <p className="mt-3 text-base" style={{ color: TINTA_SUAVE }}>
            Sin agenda de papel, sin planillas sueltas, sin cuentas a mano al final del día.
          </p>
        </Reveal>

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FUNCIONES.map((f, i) => (
            <Reveal key={f.titulo} delay={Math.min(i * 0.05, 0.25)}>
              <div
                className="h-full rounded-2xl border bg-white p-6 transition-shadow hover:shadow-lg"
                style={{ borderColor: BORDE }}
              >
                <span
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl"
                  style={{ background: hexA(TEAL, 0.11) }}
                >
                  <f.Icono className="h-5 w-5" style={{ color: TEAL_OSCURO }} />
                </span>
                <h3
                  className="mt-4 text-lg font-bold"
                  style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
                >
                  {f.titulo}
                </h3>
                <p className="mt-2 text-sm leading-relaxed" style={{ color: TINTA_SUAVE }}>
                  {f.texto}
                </p>
                {f.badgeMP && (
                  <span
                    className="mt-3 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1"
                    style={{ borderColor: BORDE, background: "#fff" }}
                    title="Integrado con Mercado Pago"
                  >
                    {/* Isotipo simplificado de Mercado Pago (uso nominativo: indica la integración) */}
                    <svg viewBox="0 0 32 22" className="h-4 w-6" aria-hidden>
                      <ellipse cx="16" cy="11" rx="15" ry="10" fill="#00B1EA" />
                      <path
                        d="M8 10c2.5-2.6 5-3.8 7-2.2 1 .8 2.4 1 3.5.4 1.8-1 3.7-1.4 5.5-.4"
                        fill="none"
                        stroke="#fff"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                      />
                      <path
                        d="M11 13.5c1.6 1.4 3.4 1.6 5 .6M17.5 14.8c1.4.9 3 .9 4.3.1"
                        fill="none"
                        stroke="#fff"
                        strokeWidth="1.4"
                        strokeLinecap="round"
                      />
                    </svg>
                    <span className="text-xs font-semibold" style={{ color: "#2D3277" }}>
                      Mercado Pago
                    </span>
                  </span>
                )}
              </div>
            </Reveal>
          ))}

          {/* Tarjeta CTA que completa la grilla */}
          <Reveal delay={0.3}>
            <div
              className="flex h-full flex-col items-start justify-between rounded-2xl p-6 text-white"
              style={{ background: `linear-gradient(150deg, ${TEAL}, ${TEAL_OSCURO})` }}
            >
              <div>
                <h3 className="text-lg font-bold" style={{ fontFamily: "Syne, sans-serif" }}>
                  ¿Querés verlo con tus servicios y tu equipo?
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-white/85">
                  Te lo mostramos andando con datos como los tuyos, sin compromiso.
                </p>
              </div>
              <a
                href={LINK_DEMO}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-white px-5 py-2.5 text-sm font-semibold transition-transform hover:scale-[1.02]"
                style={{ color: TEAL_OSCURO }}
              >
                <MessageCircle className="h-4 w-4" />
                Hablemos
              </a>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function Integraciones() {
  // Cada logo tiene una proporción distinta, así que fijar la misma altura los
  // deja desparejos. Damos a cada uno su altura para que pesen visualmente igual.
  const logos = [
    { src: "/marca/integraciones/mercado-pago.png", alt: "Mercado Pago", cls: "h-11" },
    { src: "/marca/integraciones/google-calendar.png", alt: "Google Calendar", cls: "h-8" },
    { src: "/marca/integraciones/google-maps.png", alt: "Google Maps", cls: "h-6" },
    { src: "/marca/integraciones/whatsapp.png", alt: "WhatsApp", cls: "h-7" },
  ];
  return (
    <section className="relative overflow-hidden py-20">
      {/* Fondo con un halo suave de marca */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 0%, rgba(23,160,138,0.06), transparent 70%)",
        }}
      />
      <div className="relative mx-auto max-w-5xl px-5">
        <Reveal>
          <div className="text-center">
            <span
              className="text-xs font-bold uppercase tracking-[0.2em]"
              style={{ color: TEAL_OSCURO }}
            >
              Integraciones
            </span>
            <h2
              className="mx-auto mt-3 max-w-2xl text-3xl font-bold tracking-tight md:text-4xl"
              style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
            >
              Se conecta con las apps que{" "}
              <span style={{ color: TEAL_OSCURO }}>ya usás</span>
            </h2>
            <p
              className="mx-auto mt-4 max-w-xl text-base leading-relaxed"
              style={{ color: TINTA_SUAVE }}
            >
              Cobrás las señas con Mercado Pago, tus clientes suman el turno a su
              Google Calendar, te encuentran por Google Maps y les avisás por
              WhatsApp. Todo desde el mismo lugar.
            </p>
          </div>
        </Reveal>

        <Reveal delay={0.1}>
          <div
            className="mt-12 grid grid-cols-2 gap-px overflow-hidden rounded-3xl border md:grid-cols-4"
            style={{
              borderColor: BORDE,
              background: BORDE,
              boxShadow: "0 24px 60px -32px rgba(12,16,21,0.22)",
            }}
          >
            {logos.map((l) => (
              <div
                key={l.alt}
                className="flex items-center justify-center bg-white px-6 py-10 transition-colors hover:bg-[#f6f7f9]"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={l.src}
                  alt={l.alt}
                  className={`${l.cls} w-auto max-w-[75%] object-contain`}
                />
              </div>
            ))}
          </div>
        </Reveal>

        <Reveal delay={0.16}>
          <p className="mt-5 text-center text-sm" style={{ color: TINTA_SUAVE }}>
            <span className="font-semibold" style={{ color: TINTA }}>
              Sin comisión por reserva.
            </span>{" "}
            La plata de las señas va directo a tu cuenta de Mercado Pago.
          </p>
        </Reveal>
      </div>
    </section>
  );
}

function Diferenciador() {
  const puntos = [
    "Caja diaria con arqueo, pago dividido y comisión por método de pago",
    "Membresías y abonos con rentabilidad calculada sola",
    "Historial y gasto real por cliente, no solo una lista de nombres",
    "Estadísticas de lo cobrado de verdad, separado de lo agendado",
    "Carriles paralelos: tu agenda modela cómo trabaja tu equipo",
  ];
  return (
    <section className="py-20">
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 lg:grid-cols-2">
        <Reveal>
          <h2
            className="text-3xl font-bold tracking-tight md:text-4xl"
            style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
          >
            No es solo una agenda:
            <br />
            es el <span style={{ color: TEAL_OSCURO }}>back-office completo</span>
          </h2>
          <p className="mt-4 text-base leading-relaxed" style={{ color: TINTA_SUAVE }}>
            Cualquier app te da un calendario. Turnos360 además te dice cuánta plata entró,
            por dónde entró, qué clientes valen oro y si el abono que vendés te conviene.
            La parte del negocio que las agendas simples no tocan.
          </p>
          <ul className="mt-6 space-y-3">
            {puntos.map((p) => (
              <li key={p} className="flex items-start gap-2.5 text-sm" style={{ color: TINTA }}>
                <span
                  className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full"
                  style={{ background: hexA(LIMA, 0.22) }}
                >
                  <Check className="h-3 w-3" style={{ color: "#4f7317" }} />
                </span>
                {p}
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal delay={0.12}>
          {/* Mini mock: rentabilidad de membresía */}
          <div
            className="rounded-2xl border bg-white p-5"
            style={{ borderColor: BORDE, boxShadow: "0 24px 60px -28px rgba(12,16,21,0.25)" }}
          >
            <div className="flex items-center justify-between">
              <p className="text-sm font-bold" style={{ fontFamily: "Syne, sans-serif", color: TINTA }}>
                Membresía · Cortes del mes
              </p>
              <span
                className="rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide"
                style={{ background: "#fef3c7", color: "#92400e" }}
              >
                PRO
              </span>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-3 text-center">
              {[
                ["Precio", "$50.000"],
                ["Cortes usados", "6"],
                ["Precio efectivo", "$8.333"],
              ].map(([k, v]) => (
                <div key={k} className="rounded-xl p-3" style={{ background: SUPERFICIE }}>
                  <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: TINTA_SUAVE }}>
                    {k}
                  </p>
                  <p
                    className="mt-1 text-base font-bold tabular-nums"
                    style={{ color: TINTA, fontFamily: "Syne, sans-serif" }}
                  >
                    {v}
                  </p>
                </div>
              ))}
            </div>
            <div className="mt-4 space-y-2">
              {[
                ["12 jun · Corte fade", "Cubierto por abono"],
                ["19 jun · Corte + lavado", "Cubierto por abono"],
                ["26 jun · Corte clásico", "Cubierto por abono"],
              ].map(([t, e]) => (
                <div
                  key={t}
                  className="flex items-center justify-between rounded-lg border px-3 py-2 text-xs"
                  style={{ borderColor: BORDE }}
                >
                  <span style={{ color: TINTA }}>{t}</span>
                  <span className="font-semibold" style={{ color: TEAL_OSCURO }}>
                    {e}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[11px]" style={{ color: TINTA_SUAVE }}>
              El sistema calcula solo cuánto te rinde cada plan. El barbero cobra su comisión
              aunque el corte esté cubierto.
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function ComoFunciona() {
  const pasos = [
    {
      n: "1",
      titulo: "Nos contás de tu negocio",
      texto: "Servicios, equipo y horarios. Una charla corta por WhatsApp alcanza para empezar.",
    },
    {
      n: "2",
      titulo: "Te lo dejamos andando",
      texto:
        "Configuramos todo nosotros y te entregamos el sistema listo, con tu página pública y tu equipo cargado.",
    },
    {
      n: "3",
      titulo: "Tus clientes reservan solos",
      texto:
        "Compartís tu link, las reservas caen en la agenda y vos ves la caja y los números todos los días.",
    },
  ];
  return (
    <section id="como-funciona" className="scroll-mt-20 py-20" style={{ background: SUPERFICIE }}>
      <div className="mx-auto max-w-6xl px-5">
        <Reveal className="mx-auto max-w-2xl text-center">
          <h2
            className="text-3xl font-bold tracking-tight md:text-4xl"
            style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
          >
            Arrancar es fácil: te acompañamos nosotros
          </h2>
          <p className="mt-3 text-base" style={{ color: TINTA_SUAVE }}>
            Nada de configurar solo un sistema que no conocés.
          </p>
        </Reveal>

        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {pasos.map((p, i) => (
            <Reveal key={p.n} delay={i * 0.08}>
              <div className="h-full rounded-2xl border bg-white p-6" style={{ borderColor: BORDE }}>
                <span
                  className="flex h-10 w-10 items-center justify-center rounded-full text-base font-bold text-white"
                  style={{ background: `linear-gradient(135deg, ${TEAL}, ${TEAL_OSCURO})`, fontFamily: "Syne, sans-serif" }}
                >
                  {p.n}
                </span>
                <h3
                  className="mt-4 text-lg font-bold"
                  style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
                >
                  {p.titulo}
                </h3>
                <p className="mt-2 text-sm leading-relaxed" style={{ color: TINTA_SUAVE }}>
                  {p.texto}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

function Rubros() {
  const rubros: { Icono: typeof Scissors; nombre: string; texto: string; color: string }[] = [
    { Icono: Scissors, nombre: "Barberías", texto: "Carriles por servicio: corte, tintura y barba a la vez.", color: TEAL },
    { Icono: Brush, nombre: "Peluquerías", texto: "Agenda por estilista, membresías y caja diaria.", color: "#8b5cf6" },
    { Icono: Hand, nombre: "Salones de uñas", texto: "Servicios con duración real y reservas online 24/7.", color: "#ec4899" },
    { Icono: Sparkles, nombre: "Centros de estética", texto: "Tratamientos, paquetes y ficha de cada clienta.", color: LIMA },
    { Icono: Waves, nombre: "Masajes y spa", texto: "Turnos por cabina o profesional, sin superponerse.", color: "#3b82f6" },
    { Icono: Apple, nombre: "Nutricionistas", texto: "Ficha clínica, mediciones y evolución del paciente.", color: "#f59e0b" },
  ];
  return (
    <section id="rubros" className="scroll-mt-20 py-20">
      <div className="mx-auto max-w-5xl px-5">
        <Reveal>
          <h2
            className="text-center text-3xl font-bold tracking-tight md:text-4xl"
            style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
          >
            Hecho para negocios que viven de sus turnos
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-center text-sm leading-relaxed" style={{ color: TINTA_SUAVE }}>
            El sistema se adapta al rubro: los nombres, los campos del cliente y la forma de
            agendar cambian según tu negocio, sin configurar nada raro.
          </p>
        </Reveal>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rubros.map(({ Icono, nombre, texto, color }, i) => (
            <Reveal key={nombre} delay={i * 0.05}>
              <div
                className="h-full rounded-2xl border p-5 transition-transform hover:-translate-y-0.5"
                style={{
                  borderColor: BORDE,
                  background: `linear-gradient(160deg, ${hexA(color, 0.07)}, #ffffff 55%)`,
                }}
              >
                <span
                  className="inline-flex h-11 w-11 items-center justify-center rounded-xl"
                  style={{ background: hexA(color, 0.14), color }}
                >
                  <Icono className="h-5 w-5" strokeWidth={2.2} />
                </span>
                <p className="mt-3 text-base font-bold" style={{ fontFamily: "Syne, sans-serif", color: TINTA }}>
                  {nombre}
                </p>
                <p className="mt-1 text-sm leading-relaxed" style={{ color: TINTA_SUAVE }}>
                  {texto}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
        <Reveal delay={0.2}>
          <p className="mt-8 text-center text-sm" style={{ color: TINTA_SUAVE }}>
            ¿Tenés otro rubro con turnos?{" "}
            <a href={LINK_DEMO} target="_blank" rel="noopener noreferrer" className="font-semibold" style={{ color: TEAL_OSCURO }}>
              Escribinos
            </a>{" "}
            y lo vemos juntos.
          </p>
        </Reveal>
      </div>
    </section>
  );
}

function AppEnLaptop() {
  // Mockup FIEL al panel real: sidebar con grupos, header de la agenda con
  // selector y tabs, métricas del día y la grilla horaria con carriles.
  const gruposMenu: { label: string; items: [string, boolean][] }[] = [
    { label: "Principal", items: [["Inicio", false], ["Agenda", true], ["Clientes", false]] },
    { label: "Negocio", items: [["Servicios", false], ["Recursos", false], ["Membresías", false], ["Gift cards", false], ["Campañas", false], ["Mi página", false]] },
    { label: "Finanzas", items: [["Estadísticas", false], ["Caja", false]] },
  ];
  const metricas: { valor: string; label: string; color: string }[] = [
    { valor: "5", label: "Turnos hoy", color: TEAL },
    { valor: "3", label: "Confirmados", color: "#3b82f6" },
    { valor: "1", label: "Pendientes", color: "#f59e0b" },
    { valor: "$74.000", label: "Ingresos previstos", color: "#10b981" },
  ];
  const horas = ["09:00", "09:30", "10:00", "10:30"];
  // turnos[hora][columna] — columnas: Corte / Barba / Color
  const turnos: Record<string, Record<number, { n: string; s: string; pend?: boolean }>> = {
    "09:00": { 0: { n: "Julián", s: "Corte fade" }, 1: { n: "Diego", s: "Barba + perfilado" } },
    "09:30": { 0: { n: "Marcos", s: "Corte clásico" }, 2: { n: "Sofía", s: "Color global" } },
    "10:00": { 0: { n: "Tomás", s: "Corte + lavado", pend: true } },
    "10:30": { 1: { n: "Lucas", s: "Barba" } },
  };

  function Celda({ turno }: { turno?: { n: string; s: string; pend?: boolean } }) {
    if (!turno) return <div className="border-b border-l" style={{ borderColor: "#eef1f5" }} />;
    const col = turno.pend ? "#f59e0b" : "#10b981";
    return (
      <div className="border-b border-l p-[3px]" style={{ borderColor: "#eef1f5" }}>
        <div
          className="flex h-full items-center gap-1 rounded-[4px] border-l-2 px-1 py-[3px]"
          style={{ background: hexA(col, 0.1), borderColor: col }}
        >
          <span
            className="flex h-2.5 w-2.5 shrink-0 items-center justify-center rounded-full text-[5px] font-bold text-white"
            style={{ background: col }}
          >
            {turno.n[0]}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-[6.5px] font-bold leading-tight" style={{ color: TINTA }}>
              {turno.n}
            </span>
            <span className="block truncate text-[5.5px] leading-tight" style={{ color: TINTA_SUAVE }}>
              {turno.s}
            </span>
          </span>
        </div>
      </div>
    );
  }

  return (
    <section className="overflow-hidden py-20" style={{ background: SUPERFICIE }}>
      <div className="mx-auto max-w-5xl px-5">
        <Reveal>
          <h2
            className="text-center text-3xl font-bold tracking-tight md:text-4xl"
            style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
          >
            Así se ve por dentro
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-center text-sm leading-relaxed" style={{ color: TINTA_SUAVE }}>
            El panel completo del negocio: agenda en carriles, clientes, caja y estadísticas.
            Pensado para usarse todo el día sin manual.
          </p>
        </Reveal>
        <Reveal delay={0.1}>
          <div className="mx-auto mt-12 w-full max-w-3xl">
            {/* Pantalla de la notebook */}
            <div
              className="relative overflow-hidden rounded-t-2xl border-[10px] border-b-0"
              style={{ borderColor: "#1c222c", background: "#1c222c", boxShadow: "0 40px 90px -35px rgba(12,16,21,0.45)" }}
            >
              <span className="absolute left-1/2 top-1 z-10 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-black/60" />
              <div className="flex overflow-hidden rounded-lg bg-white" style={{ aspectRatio: "16/9.6" }}>
                {/* Sidebar del panel (fiel: grupos + item activo con pill) */}
                <div className="flex w-[24%] flex-col p-2.5" style={{ background: "#0a0f1e" }}>
                  <div className="mb-0.5 flex items-center gap-1.5">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src="/marca/isotipo.png" alt="" className="h-3.5 w-auto" />
                    <span className="text-[8.5px] font-bold text-white" style={{ fontFamily: "Syne, sans-serif" }}>
                      Turnos<span style={{ color: TEAL }}>360</span>
                    </span>
                  </div>
                  <p className="mb-1 text-[6px] font-semibold" style={{ color: TEAL }}>
                    dueño
                  </p>
                  {gruposMenu.map((g) => (
                    <div key={g.label} className="mb-1">
                      <p className="px-1 py-0.5 text-[5.5px] font-bold uppercase tracking-[0.14em]" style={{ color: "#5d6578" }}>
                        {g.label}
                      </p>
                      {g.items.map(([it, activo]) => (
                        <div
                          key={it}
                          className="rounded px-1.5 py-[2.5px] text-[7px] font-medium"
                          style={
                            activo
                              ? { background: hexA("#00d4aa", 0.16), color: "#00f5c4" }
                              : { color: "#8b93a7" }
                          }
                        >
                          {it}
                        </div>
                      ))}
                    </div>
                  ))}
                  <div className="mt-auto text-[6px]" style={{ color: "#8b93a7" }}>
                    La Cueva · Dueño
                  </div>
                </div>

                {/* Panel principal: la agenda real */}
                <div className="flex-1 overflow-hidden p-2.5" style={{ background: "#f6f7f9" }}>
                  {/* Header: título + selector + tabs + CTA */}
                  <div className="flex items-center gap-1.5">
                    <p className="text-[10px] font-bold" style={{ fontFamily: "Syne, sans-serif", color: TINTA }}>
                      Agenda
                    </p>
                    <span className="rounded border bg-white px-1.5 py-[2px] text-[6px]" style={{ borderColor: BORDE, color: TINTA }}>
                      Lucas Estrella ⌄
                    </span>
                    <span className="ml-0.5 flex overflow-hidden rounded border text-[6px]" style={{ borderColor: BORDE }}>
                      <span className="px-1.5 py-[2px] font-bold text-white" style={{ background: TEAL }}>Día</span>
                      <span className="bg-white px-1.5 py-[2px]" style={{ color: TINTA_SUAVE }}>Semana</span>
                      <span className="bg-white px-1.5 py-[2px]" style={{ color: TINTA_SUAVE }}>Mes</span>
                      <span className="bg-white px-1.5 py-[2px]" style={{ color: TINTA_SUAVE }}>Equipo</span>
                    </span>
                    <span className="ml-auto rounded-full px-2 py-[3px] text-[6.5px] font-bold text-white" style={{ background: "#12b886" }}>
                      + Nuevo turno
                    </span>
                  </div>

                  {/* Métricas del día */}
                  <div className="mt-1.5 grid grid-cols-4 gap-1.5">
                    {metricas.map((m) => (
                      <div key={m.label} className="rounded-md border bg-white p-1.5" style={{ borderColor: "#e9ecf1" }}>
                        <span
                          className="inline-block rounded px-1 py-[1px] text-[6px] font-bold"
                          style={{ background: hexA(m.color, 0.14), color: m.color }}
                        >
                          ●
                        </span>
                        <p className="mt-0.5 text-[9px] font-extrabold tabular-nums" style={{ color: TINTA }}>
                          {m.valor}
                        </p>
                        <p className="text-[5.5px]" style={{ color: TINTA_SUAVE }}>
                          {m.label}
                        </p>
                      </div>
                    ))}
                  </div>

                  <p className="mt-1.5 text-[6px] font-medium" style={{ color: TINTA_SUAVE }}>
                    Lunes 13 de julio · Lucas Estrella
                  </p>

                  {/* Grilla horaria con carriles (como la real) */}
                  <div className="mt-1 overflow-hidden rounded-md border bg-white" style={{ borderColor: "#e9ecf1" }}>
                    <div className="grid" style={{ gridTemplateColumns: "24px 1fr 1fr 1fr" }}>
                      {/* Header de columnas */}
                      <div className="border-b" style={{ borderColor: "#eef1f5", background: "#f8f9fb" }} />
                      {["Corte", "Barba", "Color"].map((c) => (
                        <p
                          key={c}
                          className="border-b border-l py-[3px] text-center text-[6.5px] font-bold"
                          style={{ borderColor: "#eef1f5", background: "#f8f9fb", color: TINTA }}
                        >
                          {c}
                        </p>
                      ))}
                      {/* Filas por hora */}
                      {horas.map((h) => (
                        <Fragment key={h}>
                          <p className="border-b py-[7px] pr-1 text-right text-[5.5px] tabular-nums" style={{ borderColor: "#eef1f5", color: TINTA_SUAVE }}>
                            {h}
                          </p>
                          <Celda turno={turnos[h]?.[0]} />
                          <Celda turno={turnos[h]?.[1]} />
                          <Celda turno={turnos[h]?.[2]} />
                        </Fragment>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            {/* Base de la notebook */}
            <div
              className="relative mx-auto h-3.5 rounded-b-xl"
              style={{ width: "112%", marginLeft: "-6%", background: "linear-gradient(#dfe3e9, #b9bfc9)" }}
            >
              <span className="absolute left-1/2 top-0 h-1.5 w-16 -translate-x-1/2 rounded-b-md bg-[#a7adb8]" />
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function Precios() {
  const incluye = [
    "0% de comisión por reserva — el precio es todo lo que pagás",
    "Agenda y turnos ilimitados",
    "Tu página de reservas online 24/7",
    "Caja, gastos y estadísticas reales",
    "Membresías y CRM de clientes",
    "Usuarios y profesionales ilimitados",
    "Onboarding acompañado: tu página queda lista con vos",
  ];
  return (
    <section id="precios" className="scroll-mt-20 py-20">
      <div className="mx-auto max-w-3xl px-5">
        <Reveal>
          <h2
            className="text-center text-3xl font-bold tracking-tight md:text-4xl"
            style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
          >
            Precio simple, sin sorpresas
          </h2>
          <p className="mx-auto mt-4 max-w-md text-center text-sm leading-relaxed" style={{ color: TINTA_SUAVE }}>
            Un solo plan con todo incluido. Sin límites de turnos, sin funciones
            bloqueadas, sin comisiones por reserva, sin letra chica.
          </p>
        </Reveal>
        <Reveal delay={0.1}>
          <div
            className="mt-10 rounded-3xl border bg-white p-8 md:p-10"
            style={{ borderColor: BORDE, boxShadow: "0 30px 80px -35px rgba(12,16,21,0.25)" }}
          >
            <div className="flex flex-wrap items-end justify-center gap-2 text-center">
              <p
                className="text-5xl font-bold tabular-nums tracking-tight md:text-6xl"
                style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
              >
                $16.990
              </p>
              <p className="pb-1.5 text-sm font-medium" style={{ color: TINTA_SUAVE }}>
                /mes por local
              </p>
            </div>
            <ul className="mx-auto mt-8 grid max-w-xl gap-3 sm:grid-cols-2">
              {incluye.map((item) => (
                <li key={item} className="flex items-start gap-2.5 text-sm" style={{ color: TINTA }}>
                  <span
                    className="mt-0.5 flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full"
                    style={{ background: hexA(TEAL, 0.14) }}
                  >
                    <Check className="h-3 w-3" style={{ color: TEAL_OSCURO }} strokeWidth={3} />
                  </span>
                  {item}
                </li>
              ))}
            </ul>
            <div className="mt-9 flex flex-col items-center gap-3">
              <BotonDemo grande />
              <p className="text-xs" style={{ color: TINTA_SUAVE }}>
                Sin permanencia · Pedí una demo y probalo antes de pagar
              </p>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}


/* ============================================================
   COMPARATIVA — la sección firma.
   Las seis apps de turnos del mercado venden lo mismo: agenda,
   señas y recordatorios. Ninguna administra la plata del local.
   Ser honestos en lo que empatamos hace creíble lo que sigue.
   ============================================================ */
const COMPARACION: { fila: string; ellos: boolean; detalle?: string }[] = [
  { fila: "Agenda y reservas online 24/7", ellos: true },
  { fila: "Recordatorios automáticos", ellos: true },
  { fila: "Cobro al reservar (seña o total)", ellos: true },
  { fila: "Página propia del negocio", ellos: true },
  { fila: "Caja diaria con arqueo y cierre", ellos: false, detalle: "Cuánto entró por cada método y si el cajón cuadra" },
  { fila: "Comisiones por profesional", ellos: false, detalle: "Cuánto le toca a cada barbero, calculado solo" },
  { fila: "Membresías y abonos", ellos: false, detalle: "El plan mensual, con su rentabilidad real" },
  { fila: "Gift cards con QR", ellos: false, detalle: "Se canjean una sola vez, imposibles de falsificar" },
  { fila: "Agenda en carriles paralelos", ellos: false, detalle: "Corte, color y barba a la misma hora sin pisarse" },
  { fila: "0% de comisión por reserva", ellos: false, detalle: "Lo que cobrás es tuyo. Pagás la cuota y nada más" },
];


/* ============================================================
   EL CAMBIO — antes / después. El competidor real de Turnos360
   no es otra app: es la libreta y el WhatsApp suelto. Mostrar
   los dos mundos lado a lado hace tangible el salto.
   ============================================================ */
const SIN_SISTEMA: string[] = [
  "Turnos anotados en la libreta o en chats de WhatsApp",
  "Clientes que reservan y no aparecen",
  "El teléfono suena mientras estás cortando",
  "A fin de día no sabés cuánto entró ni cuánto le toca a cada uno",
];
const CON_SISTEMA: string[] = [
  "Agenda en carriles, ordenada y accesible desde cualquier lado",
  "Seña o cobro anticipado: el que paga, aparece",
  "Tus clientes reservan solos desde tu página, 24/7",
  "Caja cerrada con arqueo y la comisión de cada barbero calculada",
];

function ElCambio() {
  return (
    <section className="px-5 py-20">
      <div className="mx-auto max-w-4xl">
        <Reveal>
          <div className="text-center">
            <p className="text-xs font-bold uppercase tracking-[0.2em]" style={{ color: TEAL }}>
              El cambio
            </p>
            <h2
              className="mt-3 text-3xl font-bold tracking-tight md:text-4xl"
              style={{ fontFamily: "Syne, sans-serif" }}
            >
              De la libreta al negocio en números
            </h2>
          </div>
        </Reveal>
        <div className="mt-10 grid gap-4 md:grid-cols-2">
          <Reveal delay={0.05}>
            <div className="h-full rounded-2xl border p-6" style={{ borderColor: BORDE, background: SUPERFICIE }}>
              <p className="text-sm font-bold" style={{ color: TINTA_SUAVE }}>
                Sin sistema
              </p>
              <ul className="mt-4 space-y-3">
                {SIN_SISTEMA.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm leading-relaxed" style={{ color: TINTA_SUAVE }}>
                    <X className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2.5} style={{ color: "#cfd5de" }} />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
          <Reveal delay={0.12}>
            <div
              className="h-full rounded-2xl border p-6"
              style={{ borderColor: hexA(TEAL, 0.35), background: hexA(TEAL, 0.05) }}
            >
              <p className="text-sm font-bold" style={{ color: TEAL_OSCURO }}>
                Con Turnos360
              </p>
              <ul className="mt-4 space-y-3">
                {CON_SISTEMA.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm font-medium leading-relaxed" style={{ color: TINTA }}>
                    <span
                      className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full"
                      style={{ background: hexA(TEAL, 0.15) }}
                    >
                      <Check className="h-3 w-3" strokeWidth={3} style={{ color: TEAL }} />
                    </span>
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function Comparativa() {
  return (
    <section className="px-5 py-20" style={{ background: SUPERFICIE }}>
      <div className="mx-auto max-w-4xl">
        <Reveal>
          <div className="text-center">
            <p
              className="text-xs font-bold uppercase tracking-[0.2em]"
              style={{ color: TEAL }}
            >
              La diferencia
            </p>
            <h2
              className="mt-3 text-3xl font-bold tracking-tight md:text-4xl"
              style={{ fontFamily: "Syne, sans-serif" }}
            >
              Las demás te llenan la agenda.
              <br />
              Turnos360 además te administra el negocio.
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-sm" style={{ color: TINTA_SUAVE }}>
              Reservar turnos lo resuelve cualquiera, y nosotros también. La
              pregunta es qué pasa después: la plata, las comisiones, los abonos.
            </p>
          </div>
        </Reveal>

        <Reveal delay={0.1}>
          <div
            className="mt-10 overflow-hidden rounded-2xl border bg-white"
            style={{ borderColor: BORDE }}
          >
            {/* Encabezado */}
            <div
              className="grid grid-cols-[1fr_auto_auto] items-center gap-3 border-b px-5 py-3.5 text-xs font-semibold uppercase tracking-wide sm:gap-6 sm:px-6"
              style={{ borderColor: BORDE, color: TINTA_SUAVE }}
            >
              <span>Función</span>
              <span className="w-16 text-center sm:w-24">Las demás</span>
              <span
                className="w-16 rounded-full px-2 py-1 text-center sm:w-24"
                style={{ background: hexA(TEAL, 0.12), color: TEAL_OSCURO }}
              >
                Turnos360
              </span>
            </div>

            {COMPARACION.map((c, i) => (
              <div
                key={c.fila}
                className="grid grid-cols-[1fr_auto_auto] items-center gap-3 px-5 py-3.5 sm:gap-6 sm:px-6"
                style={{
                  borderTop: i === 0 ? "none" : `1px solid ${BORDE}`,
                  background: c.ellos ? "transparent" : hexA(TEAL, 0.03),
                }}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">{c.fila}</p>
                  {c.detalle && (
                    <p className="mt-0.5 text-xs" style={{ color: TINTA_SUAVE }}>
                      {c.detalle}
                    </p>
                  )}
                </div>
                <span className="flex w-16 justify-center sm:w-24">
                  {c.ellos ? (
                    <Check className="h-4 w-4" strokeWidth={3} style={{ color: "#9aa3b2" }} />
                  ) : (
                    <X className="h-4 w-4" strokeWidth={2.5} style={{ color: "#cfd5de" }} />
                  )}
                </span>
                <span className="flex w-16 justify-center sm:w-24">
                  <span
                    className="flex h-6 w-6 items-center justify-center rounded-full"
                    style={{ background: hexA(TEAL, 0.12) }}
                  >
                    <Check className="h-3.5 w-3.5" strokeWidth={3} style={{ color: TEAL }} />
                  </span>
                </span>
              </div>
            ))}
          </div>
        </Reveal>

        <Reveal delay={0.15}>
          <p className="mt-5 text-center text-xs" style={{ color: TINTA_SUAVE }}>
            Comparado con las apps de turnos más usadas en Argentina, a julio de 2026.
          </p>
        </Reveal>
      </div>
    </section>
  );
}

/* ============================================================
   PREGUNTAS FRECUENTES — las objeciones reales de la venta,
   contestadas antes de la reunión.
   ============================================================ */
const FAQS: { p: string; r: string }[] = [
  {
    p: "¿Tengo que saber de computación?",
    r: "No. Nosotros damos de alta tu negocio, cargamos tus servicios, tu equipo y tu página. Vos entrás y ya está andando. Si algo no se entiende, nos escribís por WhatsApp y lo resolvemos.",
  },
  {
    p: "¿Mis clientes tienen que descargar una app?",
    r: "No. Reservan desde el link de tu página, en el navegador del celular. Compartís ese link en tu Instagram o tu estado de WhatsApp y listo.",
  },
  {
    p: "¿Me cobran comisión por cada turno?",
    r: "Cero. Pagás la cuota mensual y nada más. Si cobrás la seña con Mercado Pago, la plata va directo a tu cuenta y la única comisión es la de Mercado Pago, que no tocamos.",
  },
  {
    p: "¿Sirve si tengo varios barberos trabajando a la vez?",
    r: "Es para lo que está hecho. La agenda muestra carriles paralelos: mientras uno corta, otro puede estar haciendo color y otro barba, sin que los turnos se pisen. Y cada uno tiene su comisión calculada.",
  },
  {
    p: "¿Qué pasa con los que reservan y no vienen?",
    r: "Dos frenos: el cobro anticipado con Mercado Pago —elegís si pedís una seña o el total— y los recordatorios automáticos por email 24 horas y 2 horas antes.",
  },
  {
    p: "¿Puedo probarlo antes de pagar?",
    r: "Sí. Te hacemos una demo con tu negocio cargado de verdad — tus servicios, tu equipo, tu página — para que veas cómo te quedaría. Sin compromiso.",
  },
];

function FAQ() {
  const [abierta, setAbierta] = useState<number | null>(0);

  return (
    <section id="faq" className="px-5 py-20">
      <div className="mx-auto max-w-3xl">
        <Reveal>
          <div className="text-center">
            <p
              className="text-xs font-bold uppercase tracking-[0.2em]"
              style={{ color: TEAL }}
            >
              Preguntas frecuentes
            </p>
            <h2
              className="mt-3 text-3xl font-bold tracking-tight md:text-4xl"
              style={{ fontFamily: "Syne, sans-serif" }}
            >
              Lo que todos preguntan
            </h2>
          </div>
        </Reveal>

        <div className="mt-10 space-y-3">
          {FAQS.map((f, i) => {
            const activa = abierta === i;
            return (
              <Reveal key={f.p} delay={i * 0.04}>
                <div
                  className="overflow-hidden rounded-2xl border bg-white"
                  style={{ borderColor: activa ? hexA(TEAL, 0.4) : BORDE }}
                >
                  <button
                    type="button"
                    onClick={() => setAbierta(activa ? null : i)}
                    aria-expanded={activa}
                    className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
                  >
                    <span className="text-sm font-semibold sm:text-base">{f.p}</span>
                    <ChevronDown
                      className="h-4 w-4 shrink-0 transition-transform duration-300"
                      style={{
                        color: activa ? TEAL : TINTA_SUAVE,
                        transform: activa ? "rotate(180deg)" : "none",
                      }}
                    />
                  </button>
                  <div
                    className="grid transition-all duration-300"
                    style={{ gridTemplateRows: activa ? "1fr" : "0fr" }}
                  >
                    <div className="overflow-hidden">
                      <p
                        className="px-5 pb-4 text-sm leading-relaxed"
                        style={{ color: TINTA_SUAVE }}
                      >
                        {f.r}
                      </p>
                    </div>
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function CTAFinal() {
  return (
    <section className="px-5 pb-20">
      <Reveal className="mx-auto max-w-5xl">
        <div
          className="relative overflow-hidden rounded-3xl px-6 py-14 text-center text-white md:py-16"
          style={{ background: `linear-gradient(140deg, ${TINTA} 30%, ${TEAL_OSCURO})` }}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{
              background: `radial-gradient(500px 260px at 85% 15%, ${hexA(LIMA, 0.22)}, transparent 60%)`,
            }}
          />
          <div className="relative">
            <h2
              className="mx-auto max-w-2xl text-3xl font-bold tracking-tight md:text-4xl"
              style={{ fontFamily: "Syne, sans-serif" }}
            >
              Dejá la libreta. Empezá a ver tu negocio en números.
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm text-white/75 md:text-base">
              Escribinos y coordinamos una demo con tus servicios y tu equipo. Sin compromiso.
            </p>
            <div className="mt-7 flex justify-center">
              <BotonDemo grande />
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t py-10" style={{ borderColor: BORDE }}>
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-5 sm:flex-row">
        <div className="flex items-center gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/marca/isotipo.png" alt="" className="h-8 w-auto" />
          <span className="text-base font-bold tracking-tight" style={{ fontFamily: "Syne, sans-serif", color: TINTA }}>
            Turnos<span style={{ color: TEAL }}>360</span>
          </span>
        </div>
        <div className="text-center">
          <p className="text-xs" style={{ color: TINTA_SUAVE }}>
            © {new Date().getFullYear()} Turnos360 · Hecho en Mendoza, Argentina
          </p>
          <p className="mt-1 text-xs" style={{ color: TINTA_SUAVE }}>
            <Link href="/terminos" className="underline underline-offset-2">
              Términos y condiciones
            </Link>
            {" · "}
            <Link href="/privacidad" className="underline underline-offset-2">
              Política de privacidad
            </Link>
          </p>
          <a
            href={`mailto:${EMAIL_CONTACTO}`}
            className="mt-1 inline-flex items-center gap-1.5 text-xs font-semibold"
            style={{ color: TEAL_OSCURO }}
          >
            <Mail className="h-3.5 w-3.5" />
            {EMAIL_CONTACTO}
          </a>
        </div>
        <div className="flex items-center gap-5">
          <Link href="/login" className="text-xs font-semibold" style={{ color: TINTA_SUAVE }}>
            Iniciar sesión
          </Link>
          <a
            href={LINK_DEMO}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-semibold"
            style={{ color: TEAL_OSCURO }}
          >
            Contacto por WhatsApp
          </a>
        </div>
      </div>
    </footer>
  );
}

export default function LandingComercial() {
  return (
    <div className="min-h-screen bg-white antialiased" style={{ color: TINTA }}>
      <Navbar />
      <main>
        <Hero />
        <Funciones />
        <Integraciones />
        <ElCambio />
        <Diferenciador />
        <Comparativa />
        <ComoFunciona />
        <AppEnLaptop />
        <Rubros />
        <Precios />
        <FAQ />
      </main>
      <Footer />
    </div>
  );
}
