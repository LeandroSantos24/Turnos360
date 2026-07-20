"use client";

/**
 * Layout del panel de super-administración (/admin/*).
 * Tiene su propio guard de sesión y un header simple, sin el sidebar del negocio.
 * La página de login queda fuera del guard.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut } from "lucide-react";

import { getAdminToken, clearAdminToken } from "@/lib/admin-api";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [listo, setListo] = useState(false);

  useEffect(() => {
    if (pathname === "/admin/login") {
      setListo(true);
      return;
    }
    if (!getAdminToken()) {
      router.replace("/admin/login");
      return;
    }
    setListo(true);
  }, [pathname, router]);

  if (!listo) return null;
  if (pathname === "/admin/login") return <>{children}</>;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div>
            <span
              className="text-lg font-bold"
              style={{ fontFamily: "Syne, sans-serif" }}
            >
              Turnos360
            </span>
            <span className="ml-2 text-sm text-muted-foreground">
              · Administración
            </span>
          </div>
          <nav className="flex items-center gap-1">
            <Link
              href="/admin"
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                pathname === "/admin"
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Empresas
            </Link>
            <Link
              href="/admin/cobranza"
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                pathname.startsWith("/admin/cobranza")
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Cobranza
            </Link>
          </nav>
          <button
            onClick={() => {
              clearAdminToken();
              router.replace("/admin/login");
            }}
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <LogOut className="h-4 w-4" /> Salir
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
    </div>
  );
}