"use client";

/**
 * Layout del panel: sidebar navy estilo TurnosPro + protección de sesión.
 *
 * - Ítems agrupados (Principal / Negocio / Sistema), íconos lucide-react.
 * - "Pill" teal animado que se desliza al ítem activo (framer-motion).
 * - Toggle de tema claro/oscuro integrado.
 * - Sidebar navy oscuro siempre; el contenido respeta el tema.
 */

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Calendar,
  Users,
  Scissors,
  UserCog,
  LogOut,
  ChevronRight,
} from "lucide-react";

import { isLoggedIn, clearToken } from "@/lib/auth";
import { getMe, UsuarioMe } from "@/lib/auth-api";
import { ThemeToggle } from "@/components/theme-toggle";

// Ítems del menú, agrupados como en TurnosPro.
const NAV = [
  { href: "/", label: "Inicio", icon: LayoutDashboard, grupo: "principal" },
  { href: "/agenda", label: "Agenda", icon: Calendar, grupo: "principal" },
  { href: "/clientes", label: "Clientes", icon: Users, grupo: "principal" },
  { href: "/servicios", label: "Servicios", icon: Scissors, grupo: "negocio" },
  { href: "/recursos", label: "Recursos", icon: UserCog, grupo: "negocio" },
];

const GRUPOS = [
  { id: "principal", label: "Principal" },
  { id: "negocio", label: "Negocio" },
];

export default function PanelLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [usuario, setUsuario] = useState<UsuarioMe | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.push("/login");
      return;
    }
    getMe()
      .then(setUsuario)
      .catch(() => router.push("/login"));
  }, [router]);

  function salir() {
    clearToken();
    router.push("/login");
  }

  if (!usuario) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Cargando…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar navy */}
      <aside
        className="flex w-60 shrink-0 flex-col"
        style={{
          background: "hsl(222 47% 8%)",
          borderRight: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        {/* Logo */}
        <div
          className="px-5 pb-5 pt-6"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
        >
          <Link href="/" className="group flex items-center gap-3">
            <div
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-base font-bold transition-transform group-hover:scale-105"
              style={{
                background: "hsl(168 100% 42%)",
                color: "hsl(222 47% 8%)",
                fontFamily: "Syne, sans-serif",
              }}
            >
              T
            </div>
            <div>
              <div
                className="font-semibold leading-none text-white"
                style={{ fontFamily: "Syne, sans-serif", fontSize: "16px" }}
              >
                Turnos360
              </div>
              <div
                className="mt-1 text-xs font-medium"
                style={{ color: "hsl(168 100% 42%)" }}
              >
                {usuario.rol}
              </div>
            </div>
          </Link>
        </div>

        {/* Navegación agrupada */}
        <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
          {GRUPOS.map((grupo) => {
            const items = NAV.filter((n) => n.grupo === grupo.id);
            return (
              <div key={grupo.id}>
                <p
                  className="mb-1.5 px-2 text-xs font-semibold uppercase tracking-widest"
                  style={{ color: "rgba(255,255,255,0.25)" }}
                >
                  {grupo.label}
                </p>
                <div className="space-y-0.5">
                  {items.map((item) => {
                    const activo =
                      item.href === "/"
                        ? pathname === "/"
                        : pathname.startsWith(item.href);
                    const Icono = item.icon;
                    return (
                      <Link key={item.href} href={item.href}>
                        <div
                          className="group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-150"
                          style={{
                            color: activo
                              ? "hsl(168 100% 42%)"
                              : "rgba(255,255,255,0.55)",
                          }}
                        >
                          {activo && (
                            <motion.div
                              layoutId="active-pill"
                              className="absolute inset-0 rounded-xl"
                              style={{
                                background: "rgba(0,212,170,0.08)",
                                border: "1px solid rgba(0,212,170,0.2)",
                              }}
                              transition={{
                                type: "spring",
                                bounce: 0.2,
                                duration: 0.4,
                              }}
                            />
                          )}
                          <Icono
                            size={17}
                            className="relative z-10 shrink-0"
                            style={{
                              color: activo
                                ? "hsl(168 100% 42%)"
                                : "rgba(255,255,255,0.4)",
                            }}
                          />
                          <span className="relative z-10">{item.label}</span>
                          {activo && (
                            <ChevronRight
                              size={14}
                              className="relative z-10 ml-auto"
                              style={{ color: "hsl(168 100% 42%)" }}
                            />
                          )}
                        </div>
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>

        {/* Usuario + acciones */}
        <div
          className="px-3 pb-4"
          style={{
            borderTop: "1px solid rgba(255,255,255,0.06)",
            paddingTop: "12px",
          }}
        >
          <div className="flex items-center gap-3 px-2 py-2">
            <div
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-semibold"
              style={{
                background: "hsl(217 35% 19%)",
                color: "hsl(168 100% 42%)",
                border: "1px solid rgba(0,212,170,0.2)",
                fontFamily: "Syne, sans-serif",
              }}
            >
              {usuario.nombre?.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">
                {usuario.nombre}
              </p>
              <p
                className="truncate text-xs"
                style={{ color: "rgba(255,255,255,0.35)" }}
              >
                {usuario.email}
              </p>
            </div>
          </div>

          {/* Fila de acciones: tema + cerrar sesión */}
          <div className="mt-2 flex items-center gap-1 px-1">
            <div className="[&_button]:text-white/60 [&_button:hover]:bg-white/10">
              <ThemeToggle />
            </div>
            <button
              onClick={salir}
              className="flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-white/10"
              style={{ color: "rgba(255,255,255,0.55)" }}
            >
              <LogOut size={16} />
              Cerrar sesión
            </button>
          </div>
        </div>
      </aside>

      {/* Contenido */}
      <main className="flex-1 overflow-auto bg-background">{children}</main>
    </div>
  );
}