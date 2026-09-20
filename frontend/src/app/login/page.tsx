"use client";

/**
 * Pantalla de login (/login).
 *
 * Split-screen: a la izquierda la foto de un local real, oscurecida, con la
 * marca y lo que hace el producto; a la derecha el formulario. En móvil la
 * foto queda como una banda corta arriba y el formulario abajo.
 *
 * La lógica de auth no cambió: email + clave, llamada a la API, token y al panel.
 */

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, BarChart3, CalendarCheck, Eye, EyeOff, MessageCircle } from "lucide-react";

import { login } from "@/lib/auth-api";
import { INSTAGRAM, FACEBOOK, YOUTUBE } from "@/lib/contacto";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EASE } from "@/components/landing/movimiento";

const VENTAJAS = [
  {
    icono: <CalendarCheck className="h-[18px] w-[18px]" />,
    titulo: "Agenda con carriles paralelos",
    desc: "Varios profesionales atendiendo a la misma hora, sin turnos que se pisen.",
  },
  {
    icono: <MessageCircle className="h-[18px] w-[18px]" />,
    titulo: "Seña online y recordatorios",
    desc: "El que reserva paga y le llega el aviso. Menos ausentes, sin perseguir a nadie.",
  },
  {
    icono: <BarChart3 className="h-[18px] w-[18px]" />,
    titulo: "Caja, comisiones y clientes",
    desc: "Cuánto entró, cuánto le toca a cada uno y quién hace tres meses que no viene.",
  },
];

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [clave, setClave] = useState("");
  const [verClave, setVerClave] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  async function manejarSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setCargando(true);
    try {
      await login(email, clave);
      router.push("/inicio");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
      setCargando(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      {/* ═══ Panel de marca ═══
          En móvil es una banda de 200px arriba; en desktop, media pantalla. */}
      <div className="relative h-[200px] shrink-0 overflow-hidden bg-[#080d18] lg:h-auto lg:w-[52%] lg:shrink">
        <img
          src="/img/elfaro-portada.webp"
          alt=""
          aria-hidden
          className="absolute inset-0 h-full w-full object-cover opacity-60"
        />
        {/* El velo es DIRECCIONAL: casi opaco del lado del texto, mucho más
            liviano a la derecha, donde no hay nada escrito. Plano y parejo, o
            se comía la foto o dejaba el texto ilegible sobre el pelo claro. */}
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(760px 520px at 12% 10%, rgba(18,184,134,0.20), transparent 62%)," +
              "linear-gradient(104deg, rgba(8,13,24,0.96) 0%, rgba(8,13,24,0.90) 42%, rgba(8,13,24,0.58) 100%)",
          }}
        />

        <div className="relative flex h-full flex-col p-8 text-white lg:p-12 xl:p-16">
          <Link
            href="/"
            className="hidden items-center gap-2 text-sm text-white/55 transition-colors hover:text-white lg:inline-flex"
          >
            <ArrowLeft className="h-4 w-4" />
            Volver al inicio
          </Link>

          {/* Centrado y no repartido con justify-between: en una pantalla alta,
              el bloque de arriba y el de abajo se iban a los extremos y entre
              medio quedaba medio metro de nada. */}
          <div className="flex flex-1 flex-col justify-center gap-10 lg:gap-14">
            <div>
              <motion.h1
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: EASE }}
                className="text-3xl font-bold tracking-tight lg:text-[44px] lg:leading-[1.05]"
                style={{ fontFamily: "var(--fuente-marca)" }}
              >
                Turnos<span className="text-[#12b886]">360</span>
              </motion.h1>
              <motion.p
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: EASE, delay: 0.08 }}
                className="mt-3 max-w-md text-[15px] leading-relaxed text-white/60 lg:mt-5 lg:text-lg"
              >
                Tu agenda, tus cobros y tus números — todo en un solo lugar.
              </motion.p>
            </div>

            {/* Las ventajas solo en desktop: en la banda de 200px no entran y
                amontonarlas ahí hace que no se lea ninguna. */}
            <div className="hidden space-y-7 lg:block">
              {VENTAJAS.map((v, i) => (
                <motion.div
                  key={v.titulo}
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.55, ease: EASE, delay: 0.16 + i * 0.09 }}
                  className="flex gap-4"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#12b886]/25 bg-[#12b886]/[0.12] text-[#12b886]">
                    {v.icono}
                  </div>
                  <div>
                    <h3 className="font-semibold leading-snug">{v.titulo}</h3>
                    <p className="mt-1 max-w-sm text-sm leading-relaxed text-white/55">{v.desc}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Cada ícono aparece SOLO si hay URL en lib/contacto: antes los tres
              iban a href="#", que en producción es un link que no lleva a ningún
              lado. Mejor ausente que roto. */}
          <div className="hidden lg:block">
            <p className="mb-3 text-xs uppercase tracking-wide text-white/35">Seguinos</p>
            <div className="flex gap-3">
              <RedSocial href={INSTAGRAM} label="Instagram"><IconoInstagram /></RedSocial>
              {FACEBOOK && <RedSocial href={FACEBOOK} label="Facebook"><IconoFacebook /></RedSocial>}
              {YOUTUBE && <RedSocial href={YOUTUBE} label="YouTube"><IconoYoutube /></RedSocial>}
            </div>
          </div>
        </div>
      </div>

      {/* ═══ Formulario ═══ */}
      <div className="flex flex-1 items-center justify-center bg-background px-6 py-12 lg:py-6">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: EASE, delay: 0.1 }}
          className="w-full max-w-[380px]"
        >
          <Link
            href="/"
            className="mb-6 inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground lg:hidden"
          >
            <ArrowLeft className="h-4 w-4" />
            Volver al inicio
          </Link>

          <div className="mb-7">
            <h2
              className="text-[27px] font-bold leading-tight tracking-tight"
              style={{ fontFamily: "var(--fuente-titulos)" }}
            >
              Bienvenido de nuevo
            </h2>
            <p className="mt-1.5 text-[15px] text-muted-foreground">Ingresá a tu panel</p>
          </div>

          <form onSubmit={manejarSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder="dueno@lacueva.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                className="h-11"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="clave">Contraseña</Label>
                <Link
                  href="/olvide-password"
                  className="text-[13px] text-muted-foreground transition-colors hover:text-[#0e8371]"
                >
                  ¿La olvidaste?
                </Link>
              </div>
              {/* El ojo evita el error más común del login en el celular: la
                  clave bien tipeada pero con una letra de más que nadie ve. */}
              <div className="relative">
                <Input
                  id="clave"
                  type={verClave ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={clave}
                  onChange={(e) => setClave(e.target.value)}
                  required
                  className="h-11 pr-11"
                />
                <button
                  type="button"
                  onClick={() => setVerClave((v) => !v)}
                  aria-label={verClave ? "Ocultar contraseña" : "Mostrar contraseña"}
                  className="absolute right-1 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:text-foreground"
                >
                  {verClave ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, ease: EASE }}
                className="rounded-lg border border-destructive/25 bg-destructive/[0.07] px-3 py-2.5 text-sm text-destructive"
                role="alert"
              >
                {error}
              </motion.p>
            )}

            <Button type="submit" className="h-11 w-full text-[15px]" disabled={cargando}>
              {cargando ? "Ingresando…" : "Ingresar"}
            </Button>
          </form>

          <p className="mt-7 text-center text-sm text-muted-foreground">
            ¿Todavía no tenés cuenta?{" "}
            <Link href="/registro" className="font-semibold text-[#0e8371] hover:underline">
              Probalo gratis
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}

function RedSocial({
  href, label, children,
}: { href: string; label: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      aria-label={label}
      target="_blank"
      rel="noopener noreferrer"
      className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/[0.06] text-white/60 transition-colors hover:border-[#12b886]/30 hover:bg-[#12b886]/15 hover:text-[#12b886]"
    >
      {children}
    </a>
  );
}

/* ═══ Íconos de redes como SVG propios (no dependen de lucide) ═══ */

function IconoInstagram() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
    </svg>
  );
}

function IconoFacebook() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
      <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
    </svg>
  );
}

function IconoYoutube() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
      <path d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17" />
      <path d="m10 15 5-3-5-3z" />
    </svg>
  );
}
