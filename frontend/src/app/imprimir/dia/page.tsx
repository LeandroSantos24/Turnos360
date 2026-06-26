"use client";

/**
 * Parte del día imprimible (/imprimir/dia).
 * Lista de turnos de una fecha: hora, cliente, servicio, quién atendió,
 * monto, estado y si se cobró. Pensado para imprimir o guardar como PDF.
 */

import { useEffect, useState } from "react";
import { Printer } from "lucide-react";

import { listarTurnosDelDia, Turno } from "@/lib/turnos-api";
import { labelEstado, horaDe } from "@/lib/turno-visual";

function pesos(n: number): string {
  return `$${Number(n).toLocaleString("es-AR")}`;
}

export default function ImprimirParteDia() {
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10));
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    setCargando(true);
    listarTurnosDelDia(`${fecha}T00:00:00`, `${fecha}T23:59:59`)
      .then((r) => setTurnos(r.items))
      .catch(() => setTurnos([]))
      .finally(() => setCargando(false));
  }, [fecha]);

  const ordenados = [...turnos].sort((a, b) =>
    (a.fecha_inicio ?? "").localeCompare(b.fecha_inicio ?? ""),
  );
  const totalFacturado = turnos.reduce(
    (acc, t) => acc + Number(t.total ?? 0),
    0,
  );
  const cobrados = turnos.filter((t) => t.cobrado).length;
  const fechaLarga = new Date(`${fecha}T12:00:00`).toLocaleDateString("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="min-h-screen bg-white text-black">
      <div className="mx-auto max-w-3xl p-10">
        {/* Controles (no se imprimen) */}
        <div className="mb-6 flex items-center gap-3 print:hidden">
          <input
            type="date"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 rounded-lg bg-black px-4 py-2 text-sm font-medium text-white"
          >
            <Printer className="h-4 w-4" /> Imprimir / Guardar PDF
          </button>
        </div>

        <div className="border-b-2 border-black pb-3">
          <h1 className="text-2xl font-bold">Parte del día</h1>
          <p className="mt-1 text-sm capitalize">{fechaLarga}</p>
        </div>

        {cargando ? (
          <p className="mt-6 text-sm">Cargando…</p>
        ) : (
          <>
            <table className="mt-6 w-full text-sm">
              <thead>
                <tr className="border-b-2 border-black text-left">
                  <th className="py-2 pr-2">Hora</th>
                  <th className="pr-2">Cliente</th>
                  <th className="pr-2">Servicio</th>
                  <th className="pr-2">Atendió</th>
                  <th className="pr-2 text-right">Monto</th>
                  <th className="pr-2">Estado</th>
                  <th>Cobro</th>
                </tr>
              </thead>
              <tbody>
                {ordenados.map((t) => (
                  <tr key={t.id} className="border-b border-gray-200 align-top">
                    <td className="py-1.5 pr-2 tabular-nums">
                      {t.fecha_inicio && horaDe(t.fecha_inicio)}
                    </td>
                    <td className="pr-2">{t.cliente_nombre}</td>
                    <td className="pr-2">{t.servicio_nombre ?? "—"}</td>
                    <td className="pr-2">{t.recurso_nombre ?? "—"}</td>
                    <td className="pr-2 text-right tabular-nums">
                      {pesos(Number(t.total ?? 0))}
                    </td>
                    <td className="pr-2">{labelEstado(t.estado)}</td>
                    <td>{t.cobrado ? "Cobrado" : "Pendiente"}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {turnos.length === 0 && (
              <p className="mt-4 text-sm text-gray-500">Sin turnos este día.</p>
            )}

            <div className="mt-6 border-t-2 border-black pt-3 text-sm">
              <div className="flex justify-between">
                <span>Turnos</span>
                <span className="tabular-nums">
                  {turnos.length} ({cobrados} cobrados)
                </span>
              </div>
              <div className="flex justify-between font-bold">
                <span>Total facturado</span>
                <span className="tabular-nums">{pesos(totalFacturado)}</span>
              </div>
            </div>
          </>
        )}

        <p className="mt-10 border-t border-gray-300 pt-3 text-xs text-gray-500">
          Generado por Turnos360
        </p>
      </div>
    </div>
  );
}