"use client";

/**
 * Tarjetas de métricas del día, estilo TurnosPro:
 * ícono en cajita de color, valor grande en Syne, etiqueta debajo.
 * Respeta modo claro/oscuro (usa variables de shadcn).
 */

import { Turno } from "@/lib/turnos-api";
import { Calendar, CheckCircle2, Clock, Banknote } from "lucide-react";

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
    {
      label: "Turnos hoy",
      valor: String(activos.length),
      icon: Calendar,
      color: "#00d4aa", // teal
    },
    {
      label: "Confirmados",
      valor: String(confirmados),
      icon: CheckCircle2,
      color: "#3b82f6", // azul
    },
    {
      label: "Pendientes",
      valor: String(pendientes),
      icon: Clock,
      color: "#f59e0b", // ámbar
    },
    {
      label: "Ingresos previstos",
      valor: `$${ingresos.toLocaleString("es-AR")}`,
      icon: Banknote,
      color: "#10b981", // verde
    },
  ];

  return (
    <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
      {tarjetas.map((t) => {
        const Icono = t.icon;
        return (
          <div
            key={t.label}
            className="rounded-2xl border bg-card p-5 transition-shadow hover:shadow-sm"
          >
            <div
              className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl"
              style={{
                background: `${t.color}18`,
                border: `1px solid ${t.color}30`,
              }}
            >
              <Icono size={18} style={{ color: t.color }} />
            </div>
            <p
              className="mb-1 text-2xl font-bold tabular-nums"
              style={{
                fontFamily: "Syne, sans-serif",
                fontVariantNumeric: "lining-nums tabular-nums",
              }}
            >
              {t.valor}
            </p>
            <p className="text-sm font-medium text-muted-foreground">
              {t.label}
            </p>
          </div>
        );
      })}
    </div>
  );
}