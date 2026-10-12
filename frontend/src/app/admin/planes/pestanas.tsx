"use client";

import { History, Layers, LineChart } from "lucide-react";

import { PestanasAdmin } from "../_ui";

/** Suscripciones y planes: catálogo, evolución en el tiempo y ajustes a mano. */
export function PestanasSuscripciones() {
  return (
    <PestanasAdmin
      items={[
        { href: "/admin/planes", label: "Planes", icon: Layers },
        { href: "/admin/suscripciones", label: "Evolución", icon: LineChart },
        { href: "/admin/ajustes", label: "Ajustes administrativos", icon: History },
      ]}
    />
  );
}
