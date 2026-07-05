"use client";

/**
 * Pantalla de login (/login).
 *
 * Split-screen: a la izquierda un panel de marca (qué es Turnos360 + features
 * + redes), a la derecha el formulario. En móvil se muestra solo el formulario.
 * La lógica de auth es la de siempre: captura email + clave, llama a la API,
 * guarda el token y redirige al panel.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarCheck, MessageCircle, BarChart3 } from "lucide-react";

import { login } from "@/lib/auth-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [clave, setClave] = useState("");
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
    <div className="flex min-h-screen">
      {/* ===== Panel de marca (solo desktop) ===== */}
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-[#0a0f1e] p-12 text-white lg:flex">
        {/* Halo decorativo teal */}
        <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-[#00d4aa]/15 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 -left-20 h-80 w-80 rounded-full bg-[#00d4aa]/10 blur-3xl" />

        {/* Marca + tagline */}
        <div className="relative">
          <h1
            className="text-4xl font-bold tracking-tight"
            style={{ fontFamily: "Syne, sans-serif" }}
          >
            Turnos<span className="text-[#00d4aa]">360</span>
          </h1>
          <p className="mt-3 max-w-sm text-lg text-white/70">
            La forma simple de gestionar tus turnos, clientes y facturación — todo en un solo lugar.
          </p>
        </div>

        {/* Features */}
        <div className="relative space-y-6">
          <Feature
            icon={<CalendarCheck className="h-5 w-5" />}
            titulo="Agenda inteligente"
            desc="Toda tu agenda organizada, con sobreturnos y vistas por día, semana o equipo."
          />
          <Feature
            icon={<MessageCircle className="h-5 w-5" />}
            titulo="Recordatorios por WhatsApp"
            desc="Menos ausentes con avisos automáticos a tus clientes. (próximamente)"
          />
          <Feature
            icon={<BarChart3 className="h-5 w-5" />}
            titulo="Clientes y métricas"
            desc="CRM, membresías y números claros para entender tu negocio."
          />
        </div>

        {/* Redes (a futuro: poné acá tus links reales) */}
        <div className="relative">
          <p className="mb-3 text-xs uppercase tracking-wide text-white/40">Seguinos</p>
          <div className="flex gap-3">
            <RedSocial href="#" label="Instagram"><IconoInstagram /></RedSocial>
            <RedSocial href="#" label="Facebook"><IconoFacebook /></RedSocial>
            <RedSocial href="#" label="YouTube"><IconoYoutube /></RedSocial>
          </div>
        </div>
      </div>

      {/* ===== Panel del formulario ===== */}
      <div className="flex w-full items-center justify-center bg-background p-6 lg:w-1/2">
        <div className="w-full max-w-sm">
          {/* Marca chica (solo móvil, donde no se ve el panel de la izquierda) */}
          <h1
            className="mb-8 text-center text-3xl font-bold lg:hidden"
            style={{ fontFamily: "Syne, sans-serif" }}
          >
            Turnos<span className="text-[#00d4aa]">360</span>
          </h1>

          <div className="mb-6">
            <h2 className="text-2xl font-bold" style={{ fontFamily: "Syne, sans-serif" }}>
              Bienvenido de nuevo
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">Ingresá a tu panel</p>
          </div>

          <form onSubmit={manejarSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="dueno@lacueva.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="clave">Contraseña</Label>
              <Input
                id="clave"
                type="password"
                placeholder="••••••••"
                value={clave}
                onChange={(e) => setClave(e.target.value)}
                required
              />
            </div>

            {error && (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={cargando}>
              {cargando ? "Ingresando…" : "Ingresar"}
            </Button>
          </form>

          <p className="mt-8 text-center text-xs text-muted-foreground">
            Turnos360 — automatización de turnos para tu negocio
          </p>
        </div>
      </div>
    </div>
  );
}

/** Una feature del panel de marca: ícono en círculo teal + título + descripción. */
function Feature({
  icon, titulo, desc,
}: { icon: React.ReactNode; titulo: string; desc: string }) {
  return (
    <div className="flex gap-4">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#00d4aa]/15 text-[#00d4aa]">
        {icon}
      </div>
      <div>
        <h3 className="font-semibold">{titulo}</h3>
        <p className="mt-0.5 text-sm text-white/60">{desc}</p>
      </div>
    </div>
  );
}

/** Botón redondo de red social. A futuro, reemplazá href="#" por tu link real. */
function RedSocial({
  href, label, children,
}: { href: string; label: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      aria-label={label}
      target="_blank"
      rel="noopener noreferrer"
      className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-white/70 transition-colors hover:bg-[#00d4aa]/20 hover:text-[#00d4aa]"
    >
      {children}
    </a>
  );
}


/* ===== Íconos de redes como SVG propios (no dependen de lucide) ===== */

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