"use client";

/**
 * Tarjetas de métricas del día (estilo dashboard): total de turnos,
 * confirmados, pendientes e ingresos previstos. Se nutre de todos los
 * turnos del local en el día (no de un recurso puntual).
 */

import { Turno } from "@/lib/turnos-api";

interface MetricasProps {
  turnos: Turno[];
}

export function MetricasDia({ turnos }: MetricasProps) {
  const activos = turnos.filter(
    (t) => t.estado !== "cancelado" && t.estado !== "ausente",
  );
  const confirmados = turnos.filter((t) => t.estado === "confirmado").length;
  const pendientes = turnos.filter((t) => t.estado === "pendiente").length;

  const ingresos = activos.reduce(
    (acc, t) => acc + (t.importe_previsto ? Number(t.importe_previsto) : 0),
    0,
  );

  const tarjetas = [
    { label: "Turnos hoy", valor: String(activos.length), color: "text-foreground" },
    { label: "Confirmados", valor: String(confirmados), color: "text-blue-600" },
    { label: "Pendientes", valor: String(pendientes), color: "text-amber-600" },
    {
      label: "Ingresos previstos",
      valor: `$${ingresos.toLocaleString("es-AR")}`,
      color: "text-green-600",
    },
  ];

  return (
    <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tarjetas.map((t) => (
        <div key={t.label} className="rounded-lg border bg-background p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            {t.label}
          </p>
          <p className={`mt-1 text-2xl font-semibold ${t.color}`}>{t.valor}</p>
        </div>
      ))}
    </div>
  );
}