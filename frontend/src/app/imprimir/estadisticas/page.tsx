"use client";

/**
 * Estadísticas imprimibles (/imprimir/estadisticas?periodo=hoy|semana|mes).
 * Documento en blanco y negro con la facturación real del período.
 */

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Printer } from "lucide-react";
import {
  startOfDay,
  endOfDay,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
} from "date-fns";

import {
  obtenerFacturacion,
  EstadisticasFacturacion,
} from "@/lib/estadisticas-api";

function pesos(n: number): string {
  return `$${Math.round(n).toLocaleString("es-AR")}`;
}

function rango(p: string): { desde: Date; hasta: Date } {
  const hoy = new Date();
  if (p === "hoy") return { desde: startOfDay(hoy), hasta: endOfDay(hoy) };
  if (p === "semana")
    return {
      desde: startOfWeek(hoy, { weekStartsOn: 1 }),
      hasta: endOfWeek(hoy, { weekStartsOn: 1 }),
    };
  return { desde: startOfMonth(hoy), hasta: endOfMonth(hoy) };
}

function etiqueta(p: string): string {
  if (p === "hoy") return "Hoy";
  if (p === "semana") return "Esta semana";
  return "Este mes";
}

function ContenidoImprimirEstadisticas() {
  const sp = useSearchParams();
  const periodo = sp.get("periodo") ?? "mes";
  const [datos, setDatos] = useState<EstadisticasFacturacion | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const { desde, hasta } = rango(periodo);
    obtenerFacturacion(desde.toISOString(), hasta.toISOString())
      .then(setDatos)
      .catch(() => setError(true));
  }, [periodo]);

  if (error) {
    return (
      <div className="min-h-screen bg-white p-10 text-black">
        No se pudieron cargar las estadísticas.
      </div>
    );
  }
  if (!datos) {
    return (
      <div className="min-h-screen bg-white p-10 text-black">Cargando…</div>
    );
  }

  return (
    <div className="min-h-screen bg-white text-black">
      <div className="mx-auto max-w-2xl p-10">
        {/* Acción (no se imprime) */}
        <div className="mb-6 print:hidden">
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 rounded-lg bg-black px-4 py-2 text-sm font-medium text-white"
          >
            <Printer className="h-4 w-4" /> Imprimir / Guardar PDF
          </button>
        </div>

        {/* Encabezado */}
        <div className="border-b-2 border-black pb-3">
          <h1 className="text-2xl font-bold">Estadísticas de facturación</h1>
          <p className="mt-1 text-sm">{etiqueta(periodo)}</p>
        </div>

        {/* Totales */}
        <table className="mt-6 w-full text-sm">
          <tbody>
            <tr className="border-b border-gray-300">
              <td className="py-2">Facturado real</td>
              <td className="py-2 text-right font-bold tabular-nums">
                {pesos(datos.facturado_real)}
              </td>
            </tr>
            <tr className="border-b border-gray-300">
              <td className="py-2">Comisiones</td>
              <td className="py-2 text-right tabular-nums">
                − {pesos(datos.comision_total)}
              </td>
            </tr>
            <tr className="border-b-2 border-black font-bold">
              <td className="py-2">Neto</td>
              <td className="py-2 text-right tabular-nums">
                {pesos(datos.neto)}
              </td>
            </tr>
            <tr className="border-b border-gray-300">
              <td className="py-2">Ticket promedio</td>
              <td className="py-2 text-right tabular-nums">
                {pesos(datos.ticket_promedio)}
              </td>
            </tr>
            <tr>
              <td className="py-2">Cantidad de cobros</td>
              <td className="py-2 text-right tabular-nums">
                {datos.cantidad_pagos}
              </td>
            </tr>
          </tbody>
        </table>

        {/* Por método */}
        {datos.por_metodo.length > 0 && (
          <>
            <h2 className="mt-8 text-lg font-bold">Por método de pago</h2>
            <table className="mt-1 w-full text-sm">
              <tbody>
                {datos.por_metodo.map((m) => (
                  <tr key={m.metodo} className="border-b border-gray-200">
                    <td className="py-1.5">{m.metodo}</td>
                    <td className="py-1.5 text-right tabular-nums">
                      {pesos(m.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {/* Por profesional */}
        {datos.por_profesional.length > 0 && (
          <>
            <h2 className="mt-8 text-lg font-bold">Por profesional</h2>
            <table className="mt-1 w-full text-sm">
              <thead>
                <tr className="border-b border-gray-400 text-left">
                  <th className="py-1.5">Profesional</th>
                  <th className="py-1.5 text-center">Turnos</th>
                  <th className="py-1.5 text-right">Facturado</th>
                </tr>
              </thead>
              <tbody>
                {datos.por_profesional.map((p) => (
                  <tr key={p.recurso} className="border-b border-gray-200">
                    <td className="py-1.5">{p.recurso}</td>
                    <td className="py-1.5 text-center tabular-nums">
                      {p.turnos}
                    </td>
                    <td className="py-1.5 text-right tabular-nums">
                      {pesos(p.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        <p className="mt-10 border-t border-gray-300 pt-3 text-xs text-gray-500">
          Generado por Turnos360
        </p>
      </div>
    </div>
  );
}
/** Next 14 exige un límite de Suspense alrededor de useSearchParams()
 *  para poder prerenderizar la página en el build de producción. */
export default function ImprimirEstadisticas() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-gray-500">Cargando…</div>}>
      <ContenidoImprimirEstadisticas />
    </Suspense>
  );
}
