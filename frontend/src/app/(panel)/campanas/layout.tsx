"use client";

/**
 * «Campañas» en apartados: resumen, que no falten, que vuelvan y reseñas.
 *
 * Antes eran cinco tarjetas apiladas en una sola página larga. Ahora el
 * resumen muestra de un vistazo qué está prendido y qué mandó cada una en los
 * últimos 30 días, y cada grupo tiene su pestaña con la configuración.
 */

import { HeartHandshake, LayoutGrid, Star, Bell } from "lucide-react";

import { SubNav } from "@/components/sub-nav";
import { EstadoCampanas, ProveedorCampanas } from "./_campanas";

const PESTANAS = [
  { href: "/campanas", label: "Resumen", icon: LayoutGrid, exacto: true },
  { href: "/campanas/recordatorios", label: "Que no falten", icon: Bell },
  { href: "/campanas/fidelizacion", label: "Que vuelvan", icon: HeartHandshake },
  { href: "/campanas/resenas", label: "Reseñas", icon: Star },
];

export default function LayoutCampanas({ children }: { children: React.ReactNode }) {
  return (
    <ProveedorCampanas>
      <div className="w-full space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="titulo-pantalla">
                Tus <b>campañas</b>.
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Mensajes que salen solos. Prendés lo que quieras usar y el sistema se encarga.
              </p>
            </div>
            <EstadoCampanas />
          </div>
          <SubNav items={PESTANAS} etiqueta="Apartados de campañas" />
        </header>
        {children}
      </div>
    </ProveedorCampanas>
  );
}
