"use client";

/**
 * Cierre de caja imprimible (/imprimir/caja/[id]).
 * Documento en blanco y negro, pensado para imprimir o guardar como PDF.
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Printer } from "lucide-react";

import { detalleCaja, CajaDetalle } from "@/lib/finanzas-api";

function fechaHora(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function pesos(n: number): string {
  return `$${Number(n).toLocaleString("es-AR")}`;
}

export default function ImprimirCierreCaja() {
  const params = useParams();
  const cajaId = Number(params.id);
  const [data, setData] = useState<CajaDetalle | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    detalleCaja(cajaId)
      .then(setData)
      .catch(() => setError(true));
  }, [cajaId]);

  if (error) {
    return (
      <div className="min-h-screen bg-white p-10 text-black">
        No se pudo cargar la caja.
      </div>
    );
  }
  if (!data) {
    return (
      <div className="min-h-screen bg-white p-10 text-black">Cargando…</div>
    );
  }

  const { resumen, movimientos } = data;
  const ingresos = movimientos.filter((m) => m.tipo === "ingreso");
  const egresos = movimientos.filter((m) => m.tipo === "egreso");

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
          <h1 className="text-2xl font-bold">Cierre de caja</h1>
          <p className="mt-1 text-sm">
            Apertura: {fechaHora(resumen.caja.fecha_apertura)}
            <br />
            Cierre: {fechaHora(resumen.caja.fecha_cierre)}
          </p>
        </div>

        {/* Totales */}
        <table className="mt-6 w-full text-sm">
          <tbody>
            <tr className="border-b border-gray-300">
              <td className="py-2">Saldo inicial</td>
              <td className="py-2 text-right tabular-nums">
                {pesos(resumen.caja.saldo_inicial)}
              </td>
            </tr>
            <tr className="border-b border-gray-300">
              <td className="py-2">Ingresos</td>
              <td className="py-2 text-right tabular-nums">
                {pesos(resumen.total_ingresos)}
              </td>
            </tr>
            <tr className="border-b border-gray-300">
              <td className="py-2">Gastos</td>
              <td className="py-2 text-right tabular-nums">
                − {pesos(resumen.total_egresos)}
              </td>
            </tr>
            <tr className="border-b-2 border-black font-bold">
              <td className="py-2">Saldo esperado (todos los métodos)</td>
              <td className="py-2 text-right tabular-nums">
                {pesos(resumen.saldo_esperado)}
              </td>
            </tr>
            <tr className="border-b border-gray-300">
              <td className="py-2">Efectivo esperado en el cajón</td>
              <td className="py-2 text-right tabular-nums">
                {pesos(resumen.efectivo_esperado)}
              </td>
            </tr>
            {resumen.saldo_real != null && (
              <>
                <tr className="border-b border-gray-300">
                  <td className="py-2">Efectivo contado</td>
                  <td className="py-2 text-right tabular-nums">
                    {pesos(resumen.saldo_real)}
                  </td>
                </tr>
                <tr className="font-bold">
                  <td className="py-2">Diferencia del arqueo (contado − efectivo esperado)</td>
                  <td className="py-2 text-right tabular-nums">
                    {(resumen.diferencia ?? 0) >= 0 ? "+" : "−"}
                    {pesos(Math.abs(resumen.diferencia ?? 0))}
                  </td>
                </tr>
              </>
            )}
          </tbody>
        </table>

        {/* Desglose por método (arqueo) */}
        {resumen.por_metodo && resumen.por_metodo.length > 0 && (
          <>
            <h2 className="mt-8 text-lg font-bold">Ingresos por método</h2>
            <table className="mt-1 w-full text-sm">
              <thead>
                <tr className="border-b-2 border-black text-left text-xs uppercase">
                  <th className="py-1.5 font-semibold">Método</th>
                  <th className="py-1.5 text-right font-semibold">Cobros</th>
                  <th className="py-1.5 text-right font-semibold">Bruto</th>
                  <th className="py-1.5 text-right font-semibold">Comisión</th>
                  <th className="py-1.5 text-right font-semibold">Neto</th>
                </tr>
              </thead>
              <tbody>
                {resumen.por_metodo.map((pm) => (
                  <tr key={pm.metodo} className="border-b border-gray-200">
                    <td className="py-1.5">{pm.metodo}</td>
                    <td className="py-1.5 text-right tabular-nums">{pm.cantidad}</td>
                    <td className="py-1.5 text-right tabular-nums">
                      {pesos(pm.total)}
                    </td>
                    <td className="py-1.5 text-right tabular-nums">
                      {pm.comision > 0 ? `− ${pesos(pm.comision)}` : "—"}
                    </td>
                    <td className="py-1.5 text-right tabular-nums">
                      {pesos(pm.neto)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-black font-bold">
                  <td className="py-1.5">Total</td>
                  <td className="py-1.5 text-right tabular-nums">
                    {resumen.por_metodo.reduce((a, m) => a + m.cantidad, 0)}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {pesos(resumen.total_ingresos)}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {resumen.total_comisiones > 0
                      ? `− ${pesos(resumen.total_comisiones)}`
                      : "—"}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {pesos(resumen.total_neto)}
                  </td>
                </tr>
              </tfoot>
            </table>
            <p className="mt-1 text-xs text-gray-500">
              Neto = bruto menos la comisión del método de pago.
            </p>
          </>
        )}

        {resumen.egresos_por_metodo && resumen.egresos_por_metodo.length > 0 && (
          <>
            <h2 className="mt-8 text-lg font-bold">Gastos por método</h2>
            <table className="mt-1 w-full text-sm">
              <thead>
                <tr className="border-b-2 border-black text-left text-xs uppercase">
                  <th className="py-1.5 font-semibold">Método</th>
                  <th className="py-1.5 text-right font-semibold">Gastos</th>
                  <th className="py-1.5 text-right font-semibold">Total</th>
                </tr>
              </thead>
              <tbody>
                {resumen.egresos_por_metodo.map((em) => (
                  <tr key={em.metodo} className="border-b border-gray-200">
                    <td className="py-1.5">{em.metodo}</td>
                    <td className="py-1.5 text-right tabular-nums">{em.cantidad}</td>
                    <td className="py-1.5 text-right tabular-nums">{pesos(em.total)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-black font-bold">
                  <td className="py-1.5">Total</td>
                  <td className="py-1.5 text-right tabular-nums">
                    {resumen.egresos_por_metodo.reduce((a, m) => a + m.cantidad, 0)}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {pesos(resumen.total_egresos)}
                  </td>
                </tr>
              </tfoot>
            </table>
            <p className="mt-1 text-xs text-gray-500">
              Los gastos no tienen comisión: se paga el monto completo.
            </p>
          </>
        )}

        {/* Movimientos */}
        <h2 className="mt-8 text-lg font-bold">
          Movimientos ({movimientos.length})
        </h2>
        {ingresos.length > 0 && (
          <>
            <h3 className="mt-3 text-sm font-semibold uppercase">Ingresos</h3>
            <table className="mt-1 w-full text-sm">
              <tbody>
                {ingresos.map((m) => (
                  <tr key={m.id} className="border-b border-gray-200">
                    <td className="py-1.5">{fechaHora(m.fecha)}</td>
                    <td className="py-1.5">{m.concepto ?? "Ingreso"}</td>
                    <td className="py-1.5 text-right tabular-nums">
                      {pesos(m.monto)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {egresos.length > 0 && (
          <>
            <h3 className="mt-4 text-sm font-semibold uppercase">Gastos</h3>
            <table className="mt-1 w-full text-sm">
              <tbody>
                {egresos.map((m) => (
                  <tr key={m.id} className="border-b border-gray-200">
                    <td className="py-1.5">{fechaHora(m.fecha)}</td>
                    <td className="py-1.5">{m.concepto ?? "Gasto"}</td>
                    <td className="py-1.5 text-right tabular-nums">
                      − {pesos(m.monto)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        <p className="mt-10 border-t border-gray-300 pt-3 text-xs text-gray-500">
          Generado por Turnos360 · {fechaHora(new Date().toISOString())}
        </p>
      </div>
    </div>
  );
}