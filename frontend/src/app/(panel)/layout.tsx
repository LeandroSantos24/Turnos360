"use client";

/**
 * Layout del panel: la barra lateral de navegación + la protección de sesión.
 *
 * Todo lo que viva dentro de (panel) hereda este marco. Dos responsabilidades:
 * 1. Proteger: si no hay sesión válida, redirige al login.
 * 2. Estructurar: barra lateral fija + área de contenido a la derecha.
 */

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { isLoggedIn, clearToken } from "@/lib/auth";
import { getMe, UsuarioMe } from "@/lib/auth-api";
import { Button } from "@/components/ui/button";

// Los ítems del menú. Cada uno es una pantalla del panel.
const NAV = [
  { href: "/", label: "Inicio" },
  { href: "/agenda", label: "Agenda" },
  { href: "/clientes", label: "Clientes" },
  { href: "/servicios", label: "Servicios" },
  { href: "/recursos", label: "Recursos" },
];

export default function PanelLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [usuario, setUsuario] = useState<UsuarioMe | null>(null);

  // Protección: al montar, verificamos sesión y traemos el usuario.
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

  // Mientras carga el usuario, no mostramos el panel (evita parpadeo).
  if (!usuario) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Cargando…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      {/* Barra lateral */}
      <aside className="flex w-60 flex-col border-r bg-muted/20">
        <div className="border-b p-4">
          <h1 className="text-lg font-semibold">Turnos360</h1>
          <p className="truncate text-xs text-muted-foreground">
            {usuario.nombre}
          </p>
        </div>

        <nav className="flex-1 space-y-1 p-2">
          {NAV.map((item) => {
            const activo =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-md px-3 py-2 text-sm transition-colors ${
                  activo
                    ? "bg-primary text-primary-foreground"
                    : "text-foreground hover:bg-muted"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t p-2">
          <Button
            variant="ghost"
            className="w-full justify-start"
            onClick={salir}
          >
            Cerrar sesión
          </Button>
        </div>
      </aside>

      {/* Área de contenido */}
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}