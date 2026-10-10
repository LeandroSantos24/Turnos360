"use client";

/**
 * «Mi suscripción» en apartados: resumen, planes, pagos, actividad y uso.
 *
 * Antes era UNA página con todo apilado. Ahora cada apartado es una ruta con
 * su pestaña y comparten una sola lectura de la API (ProveedorSuscripcion).
 * El circuito de pago (/suscripcion/cambiar/*) tiene su propio encabezado de
 * pasos y no lleva pestañas.
 */

import { usePathname } from "next/navigation";
import { Activity, BarChart3, LayoutGrid, Layers, Receipt } from "lucide-react";

import { SubNav } from "@/components/sub-nav";
import { ProveedorSuscripcion } from "./_suscripcion";

const PESTANAS = [
  { href: "/suscripcion", label: "Resumen", icon: LayoutGrid, exacto: true },
  { href: "/suscripcion/planes", label: "Planes", icon: Layers },
  { href: "/suscripcion/pagos", label: "Pagos", icon: Receipt },
  { href: "/suscripcion/actividad", label: "Actividad", icon: Activity },
  { href: "/suscripcion/uso", label: "Uso y límites", icon: BarChart3 },
];

export default function LayoutSuscripcion({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname.startsWith("/suscripcion/cambiar")) return <>{children}</>;

  return (
    <ProveedorSuscripcion>
      <div className="w-full space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="space-y-4">
          <div>
            <h1 className="titulo-pantalla">
              Mi <b>suscripción</b>.
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Tu plan, tus pagos y lo que estás usando.
            </p>
          </div>
          <SubNav items={PESTANAS} etiqueta="Apartados de la suscripción" />
        </header>
        {children}
      </div>
    </ProveedorSuscripcion>
  );
}
