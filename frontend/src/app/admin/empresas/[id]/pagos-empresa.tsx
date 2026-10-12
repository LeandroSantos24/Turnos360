"use client";

/**
 * Pestaña «Pagos» de la ficha: las operaciones de cobro de este negocio
 * (pagos, transferencias informadas, intentos de MP) con el detalle al
 * costado. Es la misma fuente que /admin/cobros, filtrada por empresa.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { ApiError } from "@/lib/api";
import { listarCobros, type ListaCobros } from "@/lib/admin-api";
import { Button } from "@/components/ui/button";
import { ChipEstado, METODOS, Vacio, fecha, pesos } from "../../_ui";
import { DetallePagoPanel } from "../../cobros/detalle-pago";

export function PagosEmpresa({ empresaId, onCambio }: { empresaId: number; onCambio?: () => void }) {
  const [d, setD] = useState<ListaCobros | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [abierto, setAbierto] = useState<number | null>(null);

  const cargar = useCallback(() => {
    listarCobros({ empresa_id: empresaId, limite: 100, pagina: 1 })
      .then(setD)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar los pagos."));
  }, [empresaId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  return (
    <section aria-labelledby="t-pagos-emp">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="t-pagos-emp" className="text-lg font-semibold">Pagos</h2>
        <Link href={`/admin/cobros?empresa_id=${empresaId}`} className="inline-flex items-center gap-1 text-sm font-medium underline-offset-4 hover:underline">
          Abrir en Cobros y pagos <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
      {error && <p role="alert" className="mb-3 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
      {!d ? (
        <div className="h-32 animate-pulse rounded-2xl bg-muted" />
      ) : d.filas.length === 0 ? (
        <Vacio>Este negocio todavía no tiene pagos ni intentos de pago.</Vacio>
      ) : (
        <>
          <dl className="mb-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            {([["Acreditado", d.sumas.acreditado], ["En revisión", d.sumas.en_revision], ["Pendiente", d.sumas.pendiente], ["Devuelto", d.sumas.devuelto]] as const).map(([k, v]) => (
              <div key={k} className="rounded-xl bg-muted/50 px-3 py-2">
                <dt className="text-xs text-muted-foreground">{k}</dt>
                <dd className="font-semibold tabular-nums">{pesos(v)}</dd>
              </div>
            ))}
          </dl>
          <ul className="divide-y rounded-2xl border bg-card">
            {d.filas.map((o) => (
              <li key={o.clave} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-sm">
                <span className="w-20 shrink-0 tabular-nums text-muted-foreground">{fecha(o.fecha)}</span>
                <span className="min-w-0 flex-1">
                  {o.concepto}
                  <span className="block text-xs text-muted-foreground">
                    {METODOS[o.metodo] ?? o.metodo}
                    {o.id_proveedor ? ` · MP ${o.id_proveedor}` : ""}
                    {o.devuelto > 0 ? ` · −${pesos(o.devuelto)} devuelto` : ""}
                  </span>
                </span>
                <span className="font-semibold tabular-nums">{pesos(o.monto)}</span>
                <ChipEstado estado={o.estado} etiqueta={o.estado_etiqueta} />
                {o.tipo === "pago" && <Button size="sm" variant="outline" onClick={() => setAbierto(o.id)}>Ver</Button>}
              </li>
            ))}
          </ul>
          {d.total > d.filas.length && (
            <p className="mt-2 text-xs text-muted-foreground">Se muestran las últimas {d.filas.length} de {d.total}. El resto, en Cobros y pagos.</p>
          )}
        </>
      )}
      <DetallePagoPanel
        pagoId={abierto}
        onCerrar={() => setAbierto(null)}
        onCambio={() => {
          cargar();
          onCambio?.();
        }}
      />
    </section>
  );
}
