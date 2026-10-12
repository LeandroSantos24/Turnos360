"use client";

/**
 * Layout del panel de super-administración (/admin/*).
 *
 * Antes eran dos links («Empresas» y «Cobranza») en un header de 1024 px y
 * todo lo demás apilado adentro. Ahora cada módulo tiene su ruta y el menú
 * va al costado (arriba, deslizable, en el celular). Tiene su propio guard
 * de sesión; el login queda afuera.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  Building2,
  CreditCard,
  Landmark,
  LayoutDashboard,
  Layers,
  LogOut,
  Plug,
  ScrollText,
  Users,
} from "lucide-react";

import { getAdminToken, clearAdminToken } from "@/lib/admin-api";
import { ConfirmarProvider } from "@/components/confirmar";

const NAV = [
  { href: "/admin", label: "Resumen", icon: LayoutDashboard, exacto: true },
  { href: "/admin/empresas", label: "Empresas", icon: Building2 },
  { href: "/admin/usuarios", label: "Usuarios y accesos", icon: Users },
  { href: "/admin/cobros", label: "Cobros y pagos", icon: CreditCard, tambien: ["/admin/cobranza"] },
  { href: "/admin/caja", label: "Caja y cierres", icon: Landmark },
  { href: "/admin/estadisticas", label: "Estadísticas", icon: BarChart3 },
  { href: "/admin/planes", label: "Suscripciones y planes", icon: Layers },
  { href: "/admin/integraciones", label: "Integraciones", icon: Plug },
  { href: "/admin/auditoria", label: "Auditoría y config.", icon: ScrollText, tambien: ["/admin/configuracion"] },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
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

  const activo = (n: (typeof NAV)[number]) =>
    n.exacto
      ? pathname === n.href
      : pathname.startsWith(n.href) || (n.tambien ?? []).some((t) => pathname.startsWith(t));

  return (
    <ConfirmarProvider>
      <div className="min-h-screen bg-background text-foreground lg:flex">
        <aside className="border-b bg-card lg:sticky lg:top-0 lg:h-screen lg:w-60 lg:shrink-0 lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between px-4 py-3 lg:block lg:px-5 lg:py-5">
            <div>
              <span className="text-lg font-bold" style={{ fontFamily: "var(--fuente-marca)" }}>
                Turnos360
              </span>
              <span className="ml-2 text-xs text-muted-foreground lg:ml-0 lg:block">Administración</span>
            </div>
            <button
              onClick={() => {
                clearAdminToken();
                router.replace("/admin/login");
              }}
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground lg:hidden"
            >
              <LogOut className="h-4 w-4" /> Salir
            </button>
          </div>
          <nav aria-label="Módulos" className="overflow-x-auto px-2 pb-2 lg:overflow-visible lg:px-3">
            <ul className="flex min-w-max gap-1 lg:min-w-0 lg:flex-col">
              {NAV.map((n) => {
                const a = activo(n);
                const Icono = n.icon;
                return (
                  <li key={n.href}>
                    <Link
                      href={n.href}
                      aria-current={a ? "page" : undefined}
                      className={`flex items-center gap-2.5 whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
                        a ? "bg-primary/10 text-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      }`}
                    >
                      <Icono className={`h-4 w-4 shrink-0 ${a ? "text-[hsl(170_85%_26%)] dark:text-primary" : ""}`} aria-hidden />
                      {n.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="hidden px-3 pt-4 lg:block">
            <button
              onClick={() => {
                clearAdminToken();
                router.replace("/admin/login");
              }}
              className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <LogOut className="h-4 w-4" /> Salir
            </button>
          </div>
        </aside>
        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
    </ConfirmarProvider>
  );
}
