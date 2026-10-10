import { Banknote, History } from "lucide-react";

import type { ItemSubNav } from "@/components/sub-nav";

export const PESTANAS_CAJA: ItemSubNav[] = [
  { href: "/caja", label: "Caja del día", icon: Banknote, exacto: true },
  { href: "/caja/historial", label: "Historial", icon: History },
];
