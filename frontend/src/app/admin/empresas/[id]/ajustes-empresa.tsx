"use client";

/**
 * Resumen de los ajustes administrativos de una empresa (pestaña Resumen de
 * la ficha): los últimos cambios hechos a mano, con su tipo y motivo, y el
 * total de días dados sin cobrar. El detalle completo está en /admin/ajustes.
 */

import { useEffect, useState } from "react";
import Link from "next/link";

import { listarAjustesAdmin, type AjusteAdmin } from "@/lib/admin-api";
import { fecha } from "../../_ui";

export function AjustesEmpresa({ empresaId, version }: { empresaId: number; version: number }) {
  const [filas, setFilas] = useState<AjusteAdmin[] | null>(null);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    listarAjustesAdmin({ empresa_id: empresaId })
      .then((d) => {
        setFilas(d.filas);
        setTotal(d.total);
      })
      .catch(() => setFilas([]));
  }, [empresaId, version]);

  if (!filas) return <div className="h-24 animate-pulse rounded-2xl bg-muted" />;
  const regalados = filas
    .filter((a) => a.estado === "vigente" && (a.categoria === "cortesia" || a.categoria === "incidencia"))
    .reduce((s, a) => s + Math.max(0, a.dias ?? 0), 0);

  return (
    <section aria-labelledby="t-ajustes-emp" className="rounded-2xl border bg-card p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="t-ajustes-emp" className="font-semibold">Ajustes administrativos</h2>
        {total > 0 && (
          <Link href={`/admin/ajustes?empresa_id=${empresaId}`} className="text-sm font-medium underline-offset-4 hover:underline">
            Ver los {total}
          </Link>
        )}
      </div>
      {filas.length === 0 ? (
        <p className="mt-1 text-sm text-muted-foreground">No se le hizo ningún ajuste a mano.</p>
      ) : (
        <>
          <p className="mt-1 text-sm text-muted-foreground">
            {regalados > 0 ? `${regalados} día(s) dados sin cobrar entre los últimos ajustes. ` : ""}No es plata: no figura en la caja.
          </p>
          <ul className="mt-2 divide-y text-sm">
            {filas.slice(0, 5).map((a) => (
              <li key={a.id} className="py-2">
                <span className="font-medium">{a.tipo_etiqueta}</span>
                <span className="text-muted-foreground"> · {a.categoria_etiqueta} · {fecha(a.fecha)}</span>
                {a.dias ? <span className="tabular-nums"> · {a.dias > 0 ? "+" : ""}{a.dias} días</span> : null}
                {a.estado === "revertido" && <span className="text-muted-foreground"> · revertido</span>}
                {a.motivo && <span className="block text-muted-foreground">{a.motivo}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
