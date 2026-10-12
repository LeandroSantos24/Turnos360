"use client";

import { ClipboardCheck, ListOrdered } from "lucide-react";

import { PestanasAdmin } from "../_ui";

/** Cobros y pagos: la lista de operaciones y la bandeja de cobranza. */
export function PestanasCobros() {
  return (
    <PestanasAdmin
      items={[
        { href: "/admin/cobros", label: "Operaciones", icon: ListOrdered },
        { href: "/admin/cobranza", label: "Transferencias y cobranza", icon: ClipboardCheck },
      ]}
    />
  );
}
