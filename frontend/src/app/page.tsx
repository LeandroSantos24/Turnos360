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

import { useEffect, useState } from "react";
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
} from "lucide-react";

/* ============================================================
   COMPLETAR ANTES DEL DEPLOY
   Número de WhatsApp para pedir demos, SIN "+" ni espacios.
   Ej: Argentina móvil → 549 + código de área + número.
   ============================================================ */
const WHATSAPP_NUMERO = "5492610000000"; // ← COMPLETAR con tu número real

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
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/marca/logo-horizontal.png" alt="Turnos360" className="h-8 w-auto" />
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

          <motion.p variants={item} className="mt-5 text-xs" style={{ color: TINTA_SUAVE }}>
            Demo sin compromiso · Onboarding acompañado · Hecho en Argentina
          </motion.p>
        </div>

        <motion.div variants={item} className="mt-14 md:mt-16">
          <MockProducto />
        </motion.div>
      </motion.div>
    </section>
  );
}

const FUNCIONES: { Icono: typeof CalendarDays; titulo: string; texto: string }[] = [
  {
    Icono: CalendarDays,
    titulo: "Agenda con carriles paralelos",
    texto:
      "Corte, tintura y barba conviven a la misma hora sin pisarse. La grilla refleja cómo trabaja tu equipo de verdad, con sobreturnos controlados.",
  },
  {
    Icono: Globe,
    titulo: "Reservas online 24/7",
    texto:
      "Tu página pública con servicios, equipo, galería y reserva en 4 pasos. El turno cae directo en tu agenda, hasta cuando el local está cerrado.",
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
  const rubros = ["Barberías", "Peluquerías", "Salones de uñas", "Centros de estética"];
  return (
    <section id="rubros" className="scroll-mt-20 py-20">
      <div className="mx-auto max-w-4xl px-5 text-center">
        <Reveal>
          <h2
            className="text-3xl font-bold tracking-tight md:text-4xl"
            style={{ fontFamily: "Syne, sans-serif", color: TINTA }}
          >
            Hecho para negocios que viven de sus turnos
          </h2>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            {rubros.map((r) => (
              <span
                key={r}
                className="rounded-full border px-5 py-2.5 text-sm font-semibold"
                style={{ borderColor: BORDE, color: TINTA, background: "#fff" }}
              >
                {r}
              </span>
            ))}
            <span
              className="rounded-full border border-dashed px-5 py-2.5 text-sm font-semibold"
              style={{ borderColor: hexA(TEAL, 0.5), color: TEAL_OSCURO, background: hexA(TEAL, 0.05) }}
            >
              Salud y consultorios · próximamente
            </span>
          </div>
          <p className="mx-auto mt-6 max-w-xl text-sm leading-relaxed" style={{ color: TINTA_SUAVE }}>
            El sistema se adapta al rubro: los nombres, los campos del cliente y la forma de
            agendar cambian según tu negocio, sin que tengas que configurar nada raro.
          </p>
        </Reveal>
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
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/marca/logo-horizontal.png" alt="Turnos360" className="h-7 w-auto" />
        <p className="text-xs" style={{ color: TINTA_SUAVE }}>
          © {new Date().getFullYear()} Turnos360 · Hecho en Mendoza, Argentina
        </p>
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
        <Diferenciador />
        <ComoFunciona />
        <Rubros />
        <CTAFinal />
      </main>
      <Footer />
    </div>
  );
}
