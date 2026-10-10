"use client";

/**
 * Pestañas de una sección del panel, como rutas.
 *
 * Son links y no un estado de React: cada apartado tiene su URL (se puede
 * compartir, el «atrás» del navegador funciona y un F5 no te devuelve al
 * principio). En el celular la fila se desplaza de costado en vez de partirse.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";

export interface ItemSubNav {
  href: string;
  label: string;
  icon?: LucideIcon;
  /** Marca activa solo con la ruta exacta (para la pestaña «principal»). */
  exacto?: boolean;
}

export function SubNav({ items, etiqueta }: { items: ItemSubNav[]; etiqueta: string }) {
  const pathname = usePathname();
  return (
    <nav aria-label={etiqueta} className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <ul className="flex min-w-max gap-1 border-b">
        {items.map((it) => {
          const activo = it.exacto
            ? pathname === it.href
            : pathname === it.href || pathname.startsWith(`${it.href}/`);
          const Icono = it.icon;
          return (
            <li key={it.href}>
              <Link
                href={it.href}
                aria-current={activo ? "page" : undefined}
                className={`relative flex items-center gap-1.5 whitespace-nowrap px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-t-lg ${
                  activo
                    ? "text-foreground after:absolute after:inset-x-2 after:-bottom-px after:h-0.5 after:rounded-full after:bg-primary"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {Icono && <Icono className="h-4 w-4" aria-hidden />}
                {it.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
