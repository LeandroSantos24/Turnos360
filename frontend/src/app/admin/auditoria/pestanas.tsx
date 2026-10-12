"use client";

import { ScrollText, Settings } from "lucide-react";

import { PestanasAdmin } from "../_ui";

/** Auditoría y configuración: el registro de acciones y la marca de Turnos360. */
export function PestanasAuditoria() {
  return (
    <PestanasAdmin
      items={[
        { href: "/admin/auditoria", label: "Auditoría", icon: ScrollText },
        { href: "/admin/configuracion", label: "Configuración", icon: Settings },
      ]}
    />
  );
}
