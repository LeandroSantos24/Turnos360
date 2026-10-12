"use client";

/**
 * Piezas chicas que comparten las pantallas del super-admin: encabezado,
 * tiles de números, chip de estado de un cobro, selector de período y
 * formatos. Nada de lógica de negocio: los números vienen del backend.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";

import type { EstadoOperacion } from "@/lib/admin-api";

export const SYNE = { fontFamily: "var(--fuente-titulos)" } as const;

export function pesos(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `$${Math.round(n).toLocaleString("es-AR")}`;
}

export function fecha(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = iso.length === 10 ? new Date(`${iso}T12:00:00`) : new Date(iso);
  return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function fechaHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export const hoyISO = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

export function Encabezado({
  titulo,
  bajada,
  acciones,
}: {
  titulo: string;
  bajada?: string;
  acciones?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold" style={SYNE}>
          {titulo}
        </h1>
        {bajada && <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{bajada}</p>}
      </div>
      {acciones && <div className="flex flex-wrap gap-2">{acciones}</div>}
    </div>
  );
}

export function Tile({
  etiqueta,
  valor,
  nota,
  tono = "neutro",
}: {
  etiqueta: string;
  valor: React.ReactNode;
  nota?: React.ReactNode;
  tono?: "neutro" | "ok" | "aviso" | "error";
}) {
  const borde = {
    neutro: "",
    ok: "border-l-4 border-l-emerald-500",
    aviso: "border-l-4 border-l-amber-500",
    error: "border-l-4 border-l-red-500",
  }[tono];
  return (
    <div className={`min-w-0 rounded-2xl border bg-card p-3 sm:p-4 ${borde}`}>
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground sm:text-xs">{etiqueta}</p>
      <p className="mt-1 text-xl font-bold tabular-nums sm:text-2xl">{valor}</p>
      {nota && <p className="mt-0.5 text-xs text-muted-foreground">{nota}</p>}
    </div>
  );
}

const ESTILO_ESTADO: Record<EstadoOperacion, string> = {
  acreditado: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  en_revision: "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200",
  pendiente: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  rechazado: "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200",
  cancelado: "bg-muted text-muted-foreground",
  anulado: "bg-muted text-muted-foreground line-through",
  reembolso_solicitado: "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-200",
  reembolso_parcial: "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-200",
  reembolso_total: "bg-violet-200 text-violet-950 dark:bg-violet-900 dark:text-violet-100",
};

export function ChipEstado({ estado, etiqueta }: { estado: EstadoOperacion; etiqueta: string }) {
  return (
    <span className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${ESTILO_ESTADO[estado] ?? "bg-muted"}`}>
      {etiqueta}
    </span>
  );
}

export const METODOS: Record<string, string> = {
  transferencia: "Transferencia",
  mercadopago: "Mercado Pago",
  debito_automatico: "Débito automático",
  efectivo: "Efectivo",
  manual: "Manual",
};

/** Desde / hasta con atajos. Las fechas son de calendario (Argentina). */
export function Periodo({
  desde,
  hasta,
  onCambio,
}: {
  desde: string;
  hasta: string;
  onCambio: (desde: string, hasta: string) => void;
}) {
  const hoy = new Date(`${hoyISO()}T12:00:00`);
  const iso = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const atajos: [string, () => [string, string]][] = [
    ["Este mes", () => [iso(new Date(hoy.getFullYear(), hoy.getMonth(), 1)), iso(hoy)]],
    ["Mes pasado", () => [iso(new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1)), iso(new Date(hoy.getFullYear(), hoy.getMonth(), 0))]],
    ["Últimos 7 días", () => [iso(new Date(hoy.getTime() - 6 * 86400000)), iso(hoy)]],
    ["Semana pasada", () => {
      const lunes = new Date(hoy.getTime() - ((hoy.getDay() + 6) % 7) * 86400000 - 7 * 86400000);
      return [iso(lunes), iso(new Date(lunes.getTime() + 6 * 86400000))];
    }],
  ];
  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="text-xs text-muted-foreground">
        Desde
        <input type="date" value={desde} max={hasta} onChange={(e) => onCambio(e.target.value, hasta)}
          className="mt-1 block rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground" />
      </label>
      <label className="text-xs text-muted-foreground">
        Hasta
        <input type="date" value={hasta} min={desde} onChange={(e) => onCambio(desde, e.target.value)}
          className="mt-1 block rounded-lg border bg-background px-2 py-1.5 text-sm text-foreground" />
      </label>
      <div className="flex flex-wrap gap-1">
        {atajos.map(([t, f]) => (
          <button key={t} type="button" onClick={() => onCambio(...f())}
            className="rounded-full border px-3 py-1.5 text-xs font-medium hover:bg-muted">
            {t}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Pestañas como links, dentro de un módulo del admin. */
export function PestanasAdmin({ items }: { items: { href: string; label: string; icon?: LucideIcon; exacto?: boolean }[] }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Secciones" className="-mx-1 mb-6 overflow-x-auto px-1">
      <ul className="flex min-w-max gap-1 border-b">
        {items.map(({ href, label, icon: Icono, exacto }) => {
          const activo = exacto ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
          return (
            <li key={href}>
              <Link href={href} aria-current={activo ? "page" : undefined}
                className={`-mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
                  activo ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
                }`}>
                {Icono && <Icono className="h-4 w-4" aria-hidden />}
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/**
 * Columnas de un período (una serie). Un solo color: el título dice qué es,
 * no hace falta leyenda. Cada barra tiene su tooltip y abajo hay tabla.
 */
export function Columnas({
  datos,
  formato = pesos,
  etiqueta,
}: {
  datos: { clave: string; etiqueta: string; valor: number }[];
  formato?: (n: number) => string;
  etiqueta: string;
}) {
  const max = Math.max(1, ...datos.map((d) => Math.abs(d.valor)));
  const hayNegativos = datos.some((d) => d.valor < 0);
  return (
    <figure aria-label={etiqueta}>
      <div className="flex h-40 items-end gap-1.5 border-b border-border/70 pt-4">
        {datos.map((d) => {
          const alto = `${Math.max(2, (Math.abs(d.valor) / max) * 100)}%`;
          return (
            <div key={d.clave} className="group relative flex h-full flex-1 items-end justify-center">
              <div
                className={`w-full max-w-[44px] rounded-t ${d.valor < 0 ? "bg-red-400/80" : "bg-primary/80"} transition-opacity group-hover:opacity-100`}
                style={{ height: alto }}
                tabIndex={0}
                role="img"
                aria-label={`${d.etiqueta}: ${formato(d.valor)}`}
              />
              <div className="pointer-events-none absolute -top-2 z-10 hidden -translate-y-full whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-xs text-background group-hover:block group-focus-within:block">
                {d.etiqueta}: {formato(d.valor)}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-1 flex gap-1.5">
        {datos.map((d, i) => (
          <span key={d.clave} className="flex-1 truncate text-center text-[10px] text-muted-foreground">
            {datos.length > 8 && i % 2 === 1 ? "" : d.etiqueta}
          </span>
        ))}
      </div>
      {hayNegativos && <figcaption className="mt-1 text-xs text-muted-foreground">En rojo, los períodos con neto negativo.</figcaption>}
    </figure>
  );
}

export function Vacio({ children }: { children: React.ReactNode }) {
  return <div className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">{children}</div>;
}
