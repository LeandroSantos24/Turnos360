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
import { Printer, TrendingUp, TrendingDown } from "lucide-react";

import {
  obtenerFacturacion,
  EstadisticasFacturacion,
} from "@/lib/estadisticas-api";
import { ApiError } from "@/lib/api";
import { listarRecursos } from "@/lib/recursos-api";
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
  const [recursoId, setRecursoId] = useState<number | null>(null);
  const [recursos, setRecursos] = useState<{ id: number; nombre: string }[]>([]);
  const [datos, setDatos] = useState<EstadisticasFacturacion | null>(null);
  const [cargando, setCargando] = useState(true);

  // Lista de profesionales para el selector (una sola vez).
  useEffect(() => {
    listarRecursos()
      .then((r) =>
        setRecursos(
          r.items
            .filter((x) => x.tipo === "persona")
            .map((x) => ({ id: x.id, nombre: x.nombre })),
        ),
      )
      .catch(() => setRecursos([]));
  }, []);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const { desde, hasta } = rango(periodo);
      const d = await obtenerFacturacion(
        desde.toISOString(),
        hasta.toISOString(),
        recursoId,
      );
      setDatos(d);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, [periodo, recursoId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const maxMetodo = Math.max(1, ...(datos?.por_metodo.map((m) => m.total) ?? [1]));
  const maxProf = Math.max(
    1,
    ...(datos?.por_profesional.map((p) => p.total) ?? [1]),
  );
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
            href={`/imprimir/estadisticas?periodo=${periodo}`
              + (recursoId != null ? `&recurso_id=${recursoId}` : "")}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted/50"
          >
            <Printer className="h-4 w-4" /> Imprimir
          </a>
        </div>
      </div>

      {/* Selector de profesional: "Todos" o filtrar el panel a uno */}
      {recursos.length > 0 && (
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">
            Profesional:
          </span>
          <button
            onClick={() => setRecursoId(null)}
            className={`rounded-full border px-3 py-1 text-sm transition-colors ${
              recursoId === null
                ? "border-primary bg-primary/10 text-primary"
                : "hover:border-muted-foreground/40"
            }`}
          >
            Todos
          </button>
          {recursos.map((r) => (
            <button
              key={r.id}
              onClick={() => setRecursoId(r.id)}
              className={`rounded-full border px-3 py-1 text-sm transition-colors ${
                recursoId === r.id
                  ? "border-primary bg-primary/10 text-primary"
                  : "hover:border-muted-foreground/40"
              }`}
            >
              {r.nombre}
            </button>
          ))}
        </div>
      )}

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

          {/* Evolución diaria — gráfico lineal (resalta los picos) */}
          {datos.por_dia.length > 1 && (
            <div className="mb-8">
              <Card titulo="Evolución de la facturación">
                <GraficoLineal
                  dias={datos.por_dia}
                  total={datos.facturado_real}
                  variacion={datos.variacion_pct}
                />
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

            <Card titulo={recursoId === null ? "Por profesional" : "Este profesional"}>
              {datos.por_profesional.length === 0 ? (
                <p className="text-sm text-muted-foreground">Sin datos.</p>
              ) : (
                datos.por_profesional.map((p) => (
                  <div key={p.recurso} className="mb-3 last:mb-0">
                    <div className="mb-1 flex justify-between text-sm">
                      <span>
                        {p.recurso}{" "}
                        <span className="text-muted-foreground">
                          · {p.turnos} turnos · ticket {pesos(p.ticket)}
                        </span>
                      </span>
                      <span className="font-semibold tabular-nums" style={NUM}>
                        {pesos(p.total)}{" "}
                        <span className="text-xs font-normal text-muted-foreground">
                          {p.pct}%
                        </span>
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

          {/* Ausentismo + servicios + horarios */}
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <Card titulo="Turnos por estado">
              <div className="grid grid-cols-3 gap-3 text-center">
                <EstadoBox
                  label="Finalizados"
                  valor={datos.estados.finalizados}
                  color="#10b981"
                />
                <EstadoBox
                  label="Cancelados"
                  valor={datos.estados.cancelados}
                  color="#f59e0b"
                />
                <EstadoBox
                  label="Ausentes"
                  valor={datos.estados.ausentes}
                  color="#ef4444"
                />
              </div>
              <div className="mt-4 rounded-xl bg-muted/50 p-3 text-center">
                <p className="text-xs text-muted-foreground">Tasa de ausentismo</p>
                <p
                  className="text-2xl font-bold tabular-nums"
                  style={{
                    ...NUM,
                    color:
                      datos.estados.tasa_ausentismo > 15
                        ? "#ef4444"
                        : datos.estados.tasa_ausentismo > 8
                          ? "#f59e0b"
                          : "#10b981",
                  }}
                >
                  {datos.estados.tasa_ausentismo}%
                </p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  De cada 100 turnos que debían atenderse, faltaron{" "}
                  {Math.round(datos.estados.tasa_ausentismo)}.
                </p>
              </div>
            </Card>

            <Card titulo="Servicios más pedidos">
              {datos.por_servicio.length === 0 ? (
                <p className="text-sm text-muted-foreground">Sin datos.</p>
              ) : (
                datos.por_servicio.slice(0, 6).map((s) => {
                  const maxServ = Math.max(
                    1,
                    ...datos.por_servicio.map((x) => x.total),
                  );
                  return (
                    <div key={s.servicio} className="mb-3 last:mb-0">
                      <div className="mb-1 flex justify-between text-sm">
                        <span>
                          {s.servicio}{" "}
                          <span className="text-muted-foreground">
                            · {s.cantidad}
                          </span>
                        </span>
                        <span className="font-semibold tabular-nums" style={NUM}>
                          {pesos(s.total)}
                        </span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{ width: `${(s.total / maxServ) * 100}%` }}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </Card>
          </div>

          {/* Horarios más demandados */}
          {datos.por_hora.length > 0 && (
            <div className="mt-4">
              <Card titulo="Horarios más demandados">
                <HorariosBar horas={datos.por_hora} />
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ── Gráfico lineal de facturación (SVG, sin dependencias) ── */
function GraficoLineal({
  dias,
  total,
  variacion,
}: {
  dias: { fecha: string; total: number }[];
  total: number;
  variacion: number | null;
}) {
  const [hover, setHover] = useState<number | null>(null);

  const W = 720;
  const H = 210;
  const PL = 54;
  const PR = 18;
  const PT = 24;
  const PB = 30;
  const max = Math.max(1, ...dias.map((d) => d.total));
  const n = dias.length;
  const x = (i: number) => PL + (i * (W - PL - PR)) / Math.max(1, n - 1);
  const y = (v: number) => H - PB - (v / max) * (H - PT - PB);
  const puntos = dias.map((d, i) => [x(i), y(d.total)] as const);
  const linea = puntos.map(([px, py], i) => `${i === 0 ? "M" : "L"}${px},${py}`).join(" ");
  const area = `${linea} L${x(n - 1)},${H - PB} L${x(0)},${H - PB} Z`;
  const idxPico = dias.reduce((mi, d, i) => (d.total > dias[mi].total ? i : mi), 0);

  const refs = [0, max / 2, max];
  const fmtK = (v: number) =>
    v >= 1000 ? `$${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k` : `$${Math.round(v)}`;
  const fmtDia = (f: string) =>
    format(new Date(`${f}T12:00:00`), "d/M", { locale: es });

  // Cuántas etiquetas de fecha mostrar sin amontonar.
  const paso = n <= 12 ? 1 : Math.ceil(n / 10);

  return (
    <div>
      {/* Encabezado: total del período + variación vs anterior */}
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-xs text-muted-foreground">Total del período</p>
          <p className="text-3xl font-bold tabular-nums" style={NUM}>
            {pesos(total)}
          </p>
        </div>
        {variacion !== null && (
          <div
            className="flex items-center gap-1 rounded-full px-2.5 py-1 text-sm font-semibold"
            style={{
              background: variacion >= 0 ? "#10b98118" : "#ef444418",
              color: variacion >= 0 ? "#10b981" : "#ef4444",
            }}
          >
            {variacion >= 0 ? (
              <TrendingUp className="h-4 w-4" />
            ) : (
              <TrendingDown className="h-4 w-4" />
            )}
            {variacion >= 0 ? "+" : ""}
            {variacion}% vs período anterior
          </div>
        )}
      </div>

      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-56 w-full min-w-[560px]"
          onMouseLeave={() => setHover(null)}
        >
          <defs>
            <linearGradient id="areaFact" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.32" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Referencias horizontales + eje Y */}
          {refs.map((v) => (
            <g key={v}>
              <line
                x1={PL}
                y1={y(v)}
                x2={W - PR}
                y2={y(v)}
                stroke="currentColor"
                strokeWidth="1"
                className="opacity-10"
              />
              <text
                x={PL - 8}
                y={y(v) + 3}
                textAnchor="end"
                className="fill-current text-[9px] opacity-50"
              >
                {fmtK(v)}
              </text>
            </g>
          ))}

          <path d={area} fill="url(#areaFact)" />
          <path
            d={linea}
            fill="none"
            stroke="#10b981"
            strokeWidth="3"
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {/* Guía vertical del punto activo */}
          {hover !== null && (
            <line
              x1={x(hover)}
              y1={PT}
              x2={x(hover)}
              y2={H - PB}
              stroke="#10b981"
              strokeWidth="1"
              strokeDasharray="3 3"
              className="opacity-40"
            />
          )}

          {puntos.map(([px, py], i) => {
            const activo = hover === i;
            const esPico = i === idxPico && n > 2;
            const mostrarMonto = activo || esPico;
            return (
              <g key={dias[i].fecha}>
                {/* Zona de hover ancha e invisible para captar el mouse */}
                <rect
                  x={px - (W - PL - PR) / (2 * Math.max(1, n - 1))}
                  y={PT}
                  width={(W - PL - PR) / Math.max(1, n - 1)}
                  height={H - PT - PB}
                  fill="transparent"
                  onMouseEnter={() => setHover(i)}
                />
                <circle
                  cx={px}
                  cy={py}
                  r={activo ? 5.5 : esPico ? 4.5 : 3}
                  fill="#10b981"
                  stroke="#fff"
                  strokeWidth={activo ? 2 : 0}
                />
                {mostrarMonto && (
                  <text
                    x={px}
                    y={py - 12}
                    textAnchor="middle"
                    className="fill-current text-[10px] font-bold"
                  >
                    {fmtK(dias[i].total)}
                  </text>
                )}
                {i % paso === 0 && (
                  <text
                    x={px}
                    y={H - 8}
                    textAnchor="middle"
                    className={`fill-current text-[9px] ${activo ? "font-bold opacity-90" : "opacity-55"}`}
                  >
                    {fmtDia(dias[i].fecha)}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

/* ── Cajita de un estado de turno ── */
function EstadoBox({ label, valor, color }: { label: string; valor: number; color: string }) {
  return (
    <div className="rounded-xl border p-3">
      <p className="text-2xl font-bold tabular-nums" style={{ fontVariantNumeric: "tabular-nums", color }}>
        {valor}
      </p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

/* ── Barras de horarios más demandados ── */
function HorariosBar({ horas }: { horas: { hora: number; cantidad: number }[] }) {
  const mapa = new Map(horas.map((h) => [h.hora, h.cantidad]));
  const desde = Math.min(...horas.map((h) => h.hora));
  const hasta = Math.max(...horas.map((h) => h.hora));
  const rango: number[] = [];
  for (let h = desde; h <= hasta; h++) rango.push(h);
  const max = Math.max(1, ...horas.map((h) => h.cantidad));
  return (
    <div className="flex h-40 items-end gap-1">
      {rango.map((h) => {
        const c = mapa.get(h) ?? 0;
        return (
          <div key={h} className="flex flex-1 flex-col items-center gap-1" title={`${c} turnos`}>
            <div className="flex w-full flex-1 items-end">
              <div
                className="w-full rounded-t bg-primary/80"
                style={{ height: `${Math.max((c / max) * 100, c > 0 ? 4 : 0)}%` }}
              />
            </div>
            <span className="text-[9px] text-muted-foreground">{h}h</span>
          </div>
        );
      })}
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
