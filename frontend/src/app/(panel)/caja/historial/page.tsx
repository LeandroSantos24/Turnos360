"use client";

/**
 * Caja · Historial: las cajas abiertas y cerradas, con su arqueo e impresión.
 * Antes iba al pie de la caja del día, debajo de todos los movimientos.
 */

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { History, Printer } from "lucide-react";

import { listarCajas, type Caja } from "@/lib/finanzas-api";
import { ApiError } from "@/lib/api";
import { useSucursales } from "@/lib/use-sucursales";
import { getMe } from "@/lib/auth-api";
import { NUM } from "@/lib/numeros";
import { SubNav } from "@/components/sub-nav";
import { PESTANAS_CAJA } from "../pestanas";

function pesos(n: number): string {
  return `$${Number(n).toLocaleString("es-AR")}`;
}

function fechaHora(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function HistorialCajas() {
  const { abiertas, multi } = useSucursales();
  const [mirando, setMirando] = useState<number | null>(null);
  const [miSucursal, setMiSucursal] = useState<number | null>(null);
  const [cajas, setCajas] = useState<Caja[] | null>(null);

  useEffect(() => {
    getMe()
      .then((u) => setMiSucursal(u.sucursal_id))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    setCajas(null);
    listarCajas(mirando)
      .then(setCajas)
      .catch((err) => {
        toast.error(err instanceof ApiError ? err.message : "No se pudo cargar el historial");
        setCajas([]);
      });
  }, [mirando]);

  return (
    <div className="w-full px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="titulo-pantalla">
          Tu <b>caja</b>.
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">Cada apertura y cierre, con su arqueo.</p>
      </div>
      <div className="mb-6">
        <SubNav items={PESTANAS_CAJA} etiqueta="Apartados de la caja" />
      </div>

      {multi && (
        <div className="mb-5 flex flex-wrap items-center gap-1.5">
          {abiertas.map((suc) => {
            const propio = suc.id === miSucursal;
            const activo = mirando === suc.id || (mirando === null && propio);
            return (
              <button
                key={suc.id}
                type="button"
                aria-pressed={activo}
                onClick={() => setMirando(propio ? null : suc.id)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  activo ? "border-transparent bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                {suc.nombre}
                {propio && " · tu local"}
              </button>
            );
          })}
        </div>
      )}

      {cajas === null ? (
        <div className="h-40 animate-pulse rounded-2xl bg-muted" />
      ) : cajas.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-2xl border bg-card px-6 py-10 text-center">
          <History className="h-8 w-8 text-muted-foreground/60" aria-hidden />
          <p className="text-sm text-muted-foreground">Todavía no hay cajas. La primera aparece cuando abrís la caja del día.</p>
        </div>
      ) : (
        <ul className="divide-y overflow-hidden rounded-2xl border bg-card">
          {cajas.map((c) => {
            const abierta = c.estado === "abierta";
            return (
              <li key={c.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium tabular-nums" style={NUM}>
                    {fechaHora(c.fecha_apertura)}
                    {abierta ? " · en curso" : ` → ${fechaHora(c.fecha_cierre)}`}
                  </p>
                  <p className="text-xs text-muted-foreground tabular-nums" style={NUM}>
                    Inicial {pesos(c.saldo_inicial)}
                    {c.saldo_final != null && ` · Cierre ${pesos(c.saldo_final)}`}
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${
                    abierta ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400" : "bg-muted text-muted-foreground"
                  }`}
                >
                  {abierta ? "Abierta" : "Cerrada"}
                </span>
                <a
                  href={`/imprimir/caja/${c.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium hover:bg-muted/50"
                >
                  <Printer className="h-3.5 w-3.5" aria-hidden /> Ver e imprimir
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
