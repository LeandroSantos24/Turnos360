"use client";

/**
 * Estadísticas de facturación (/estadisticas).
 * La plata real que entró en el período: total, neto de comisiones, ticket
 * promedio, evolución diaria, y desglose por método y por profesional.
 */

import { useEffect, useState, useCallback } from "react";
import {
  startOfDay,
  endOfDay,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  format,
} from "date-fns";
import { es } from "date-fns/locale";
import { toast } from "sonner";
import { Printer } from "lucide-react";

import {
  obtenerFacturacion,
  EstadisticasFacturacion,
} from "@/lib/estadisticas-api";
import { ApiError } from "@/lib/api";
import { RequiereDueno } from "@/components/requiere-rol";

type Periodo = "hoy" | "semana" | "mes";

const NUM = { fontVariantNumeric: "tabular-nums" } as const;
const SYNE = { fontFamily: "Syne, sans-serif" } as const;

function pesos(n: number): string {
  return `$${Math.round(n).toLocaleString("es-AR")}`;
}

function rango(p: Periodo): { desde: Date; hasta: Date } {
  const hoy = new Date();
  if (p === "hoy") return { desde: startOfDay(hoy), hasta: endOfDay(hoy) };
  if (p === "semana")
    return {
      desde: startOfWeek(hoy, { weekStartsOn: 1 }),
      hasta: endOfWeek(hoy, { weekStartsOn: 1 }),
    };
  return { desde: startOfMonth(hoy), hasta: endOfMonth(hoy) };
}

function KPI({
  label,
  valor,
  sub,
  destacado,
}: {
  label: string;
  valor: string;
  sub?: string;
  destacado?: boolean;
}) {
  return (
    <div className="rounded-2xl border bg-card p-5">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p
        className={`mt-2 text-2xl font-bold ${destacado ? "text-primary" : ""}`}
        style={{ ...NUM, ...SYNE }}
      >
        {valor}
      </p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

function Card({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border bg-card p-5">
      <h2 className="mb-4 text-lg font-bold" style={SYNE}>
        {titulo}
      </h2>
      {children}
    </div>
  );
}

function ContenidoEstadisticas() {
  const [periodo, setPeriodo] = useState<Periodo>("mes");
  const [datos, setDatos] = useState<EstadisticasFacturacion | null>(null);
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const { desde, hasta } = rango(periodo);
      const d = await obtenerFacturacion(desde.toISOString(), hasta.toISOString());
      setDatos(d);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, [periodo]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const maxMetodo = Math.max(1, ...(datos?.por_metodo.map((m) => m.total) ?? [1]));
  const maxProf = Math.max(
    1,
    ...(datos?.por_profesional.map((p) => p.total) ?? [1]),
  );
  const maxDia = Math.max(1, ...(datos?.por_dia.map((d) => d.total) ?? [1]));
  const sinDatos =
    datos &&
    datos.cantidad_pagos === 0 &&
    datos.por_dia.length === 0;

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={SYNE}>
            Estadísticas
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            La facturación real: lo que entró de verdad en el período.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center rounded-lg border p-0.5">
            {(["hoy", "semana", "mes"] as Periodo[]).map((p) => (
              <button
                key={p}
                onClick={() => setPeriodo(p)}
                className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                  periodo === p
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {p === "hoy" ? "Hoy" : p === "semana" ? "Semana" : "Mes"}
              </button>
            ))}
          </div>
          <a
            href={`/imprimir/estadisticas?periodo=${periodo}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted/50"
          >
            <Printer className="h-4 w-4" /> Imprimir
          </a>
        </div>
      </div>

      {cargando || !datos ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : sinDatos ? (
        <div className="rounded-2xl border bg-card p-10 text-center">
          <p className="text-sm text-muted-foreground">
            Todavía no hay cobros registrados en este período.
          </p>
        </div>
      ) : (
        <>
          {/* KPIs */}
          <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <KPI
              label="Facturado real"
              valor={pesos(datos.facturado_real)}
              destacado
            />
            <KPI label="Neto (− comisiones)" valor={pesos(datos.neto)} />
            <KPI label="Comisiones" valor={pesos(datos.comision_total)} />
            <KPI
              label="Ticket promedio"
              valor={pesos(datos.ticket_promedio)}
              sub={`${datos.cantidad_pagos} cobros`}
            />
          </div>

          {/* Evolución diaria */}
          {datos.por_dia.length > 1 && (
            <div className="mb-8">
              <Card titulo="Evolución diaria">
                <div className="flex h-44 items-end gap-1.5">
                  {datos.por_dia.map((d) => (
                    <div
                      key={d.fecha}
                      className="flex flex-1 flex-col items-center gap-1.5"
                      title={pesos(d.total)}
                    >
                      <div className="flex w-full flex-1 items-end">
                        <div
                          className="w-full rounded-t-md bg-primary/80 transition-all"
                          style={{
                            height: `${Math.max((d.total / maxDia) * 100, 2)}%`,
                          }}
                        />
                      </div>
                      <span className="text-[10px] text-muted-foreground">
                        {format(new Date(`${d.fecha}T12:00:00`), "d/M", {
                          locale: es,
                        })}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* Por método + por profesional */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Card titulo="Por método de pago">
              {datos.por_metodo.length === 0 ? (
                <p className="text-sm text-muted-foreground">Sin datos.</p>
              ) : (
                datos.por_metodo.map((m) => (
                  <div key={m.metodo} className="mb-3 last:mb-0">
                    <div className="mb-1 flex justify-between text-sm">
                      <span>{m.metodo}</span>
                      <span className="font-semibold tabular-nums" style={NUM}>
                        {pesos(m.total)}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${(m.total / maxMetodo) * 100}%` }}
                      />
                    </div>
                  </div>
                ))
              )}
            </Card>

            <Card titulo="Por profesional">
              {datos.por_profesional.length === 0 ? (
                <p className="text-sm text-muted-foreground">Sin datos.</p>
              ) : (
                datos.por_profesional.map((p) => (
                  <div key={p.recurso} className="mb-3 last:mb-0">
                    <div className="mb-1 flex justify-between text-sm">
                      <span>
                        {p.recurso}{" "}
                        <span className="text-muted-foreground">
                          · {p.turnos} turnos
                        </span>
                      </span>
                      <span className="font-semibold tabular-nums" style={NUM}>
                        {pesos(p.total)}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${(p.total / maxProf) * 100}%` }}
                      />
                    </div>
                  </div>
                ))
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

export default function EstadisticasPage() {
  return (
    <RequiereDueno>
      <ContenidoEstadisticas />
    </RequiereDueno>
  );
}
