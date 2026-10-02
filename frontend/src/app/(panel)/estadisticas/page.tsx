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
import { BarChart3, Printer, TrendingUp, TrendingDown } from "lucide-react";

import {
  obtenerFacturacion,
  EstadisticasFacturacion,
} from "@/lib/estadisticas-api";
import { ApiError } from "@/lib/api";
import { useSucursales } from "@/lib/use-sucursales";
import {
  SelectorPeriodo,
  rangoDe,
  rangoInicial,
  type Periodo,
} from "@/components/selector-periodo";
import { listarRecursos } from "@/lib/recursos-api";
import { RequiereDueno } from "@/components/requiere-rol";


// lining-nums es lo que faltaba.
//
// Syne trae por defecto cifras de estilo geométrico: el 2 y el 4 salen con
// formas raras y de alturas distintas, que es lo que se veía en las tarjetas
// de Estadísticas. Inicio usa la MISMA fuente y se ve normal porque pide
// lining-nums, que fuerza las cifras alineadas de altura uniforme.
// tabular-nums, aparte, les da a todas el mismo ancho para que las columnas
// de plata queden alineadas.
const NUM = { fontVariantNumeric: "lining-nums tabular-nums" } as const;
const SYNE = { fontFamily: "var(--fuente-titulos)" } as const;

function pesos(n: number): string {
  return `$${Math.round(n).toLocaleString("es-AR")}`;
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

function MiniDato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="rounded-xl border bg-muted/30 p-3">
      <p className="text-xs text-muted-foreground">{etiqueta}</p>
      <p className="mt-0.5 text-lg font-bold tabular-nums" style={SYNE}>
        {valor}
      </p>
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
  const inicial = rangoInicial();
  const [desdeCustom, setDesdeCustom] = useState(inicial.desde);
  const [hastaCustom, setHastaCustom] = useState(inicial.hasta);
  const [recursoId, setRecursoId] = useState<number | null>(null);
  // Local que se está mirando. null = todos, que con varios locales es la
  // vista que el dueño quiere por defecto: primero el total, después el
  // desglose.
  const { multi } = useSucursales();
  const [sucursalId, setSucursalId] = useState<number | null>(null);
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
      const r = rangoDe(periodo, desdeCustom, hastaCustom);
      // Rango a medio escribir: dejamos los datos anteriores y esperamos.
      if (!r) {
        setCargando(false);
        return;
      }
      const { desde, hasta } = r;
      const d = await obtenerFacturacion(
        desde.toISOString(),
        hasta.toISOString(),
        recursoId,
        sucursalId,
      );
      setDatos(d);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, [periodo, recursoId, sucursalId, desdeCustom, hastaCustom]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const maxMetodo = Math.max(1, ...(datos?.por_metodo.map((m) => m.total) ?? [1]));
  const maxProf = Math.max(
    1,
    ...(datos?.por_profesional.map((p) => p.total) ?? [1]),
  );
  const maxSucursal = Math.max(
    1,
    ...(datos?.por_sucursal.map((s) => s.total) ?? [1]),
  );
  const sinDatos =
    datos &&
    datos.cantidad_pagos === 0 &&
    datos.por_dia.length === 0;

  return (
    <div className="w-full px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="titulo-pantalla">
            Tus <b>estadísticas</b>.
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            La facturación real: lo que entró de verdad en el período.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SelectorPeriodo
            periodo={periodo}
            onPeriodo={setPeriodo}
            desde={desdeCustom}
            hasta={hastaCustom}
            onDesde={setDesdeCustom}
            onHasta={setHastaCustom}
          />
          <a
            href={`/imprimir/estadisticas?periodo=${periodo}`
              + (periodo === "personalizado"
                  ? `&desde=${desdeCustom}&hasta=${hastaCustom}`
                  : "")
              + (recursoId != null ? `&recurso_id=${recursoId}` : "")}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted/50"
          >
            <Printer className="h-4 w-4" /> Imprimir
          </a>
        </div>
      </div>

      {/* Selector de local. Solo con más de uno. */}
      {multi && (datos?.por_sucursal.length ?? 0) > 1 && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">Local:</span>
          <button
            onClick={() => setSucursalId(null)}
            className={`rounded-full border px-3 py-1 text-sm transition-colors ${
              sucursalId === null
                ? "border-primary bg-primary/10 text-primary"
                : "hover:border-muted-foreground/40"
            }`}
          >
            Todos
          </button>
          {(datos?.por_sucursal ?? []).map((suc) => (
            <button
              key={suc.sucursal_id}
              onClick={() => setSucursalId(suc.sucursal_id)}
              className={`rounded-full border px-3 py-1 text-sm transition-colors ${
                sucursalId === suc.sucursal_id
                  ? "border-primary bg-primary/10 text-primary"
                  : "hover:border-muted-foreground/40"
              }`}
            >
              {suc.sucursal}
            </button>
          ))}
        </div>
      )}

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
        <div
          className="tarjeta vacio"
          style={{ "--tono": "var(--acento-violeta)" } as React.CSSProperties}
        >
          <span className="vacio-icono">
            <BarChart3 className="h-7 w-7" />
          </span>
          <p className="text-lg font-semibold">
            Sin cobros en este período
          </p>
          <p className="max-w-md text-sm text-muted-foreground">
            Acá se mide la facturación real, no los turnos agendados. Probá con
            un período más largo desde el selector de arriba.
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
                          {p.prepago > 0 && ` · ${pesos(p.prepago)} con gift card`}
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

          {/* Comparación entre locales. Se muestra ENTERA aunque el panel
              esté filtrado a uno: un gráfico de comparación con una sola
              barra no compara nada. */}
          {datos.por_sucursal.length > 1 && (
            <div className="mt-4">
              <Card titulo="Comparación entre locales">
                {datos.por_sucursal.map((suc) => (
                  <div key={suc.sucursal_id} className="mb-3 last:mb-0">
                    <div className="mb-1 flex justify-between text-sm">
                      <span>
                        {suc.sucursal}{" "}
                        <span className="text-muted-foreground">
                          · {suc.turnos} turnos · ticket {pesos(suc.ticket)}
                        </span>
                      </span>
                      <span className="font-semibold tabular-nums" style={NUM}>
                        {pesos(suc.total)}{" "}
                        <span className="text-xs font-normal text-muted-foreground">
                          {suc.pct}%
                        </span>
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${(suc.total / maxSucursal) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </Card>
            </div>
          )}

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

          {/* De dónde salió la plata: la facturación ya no es solo la
              atención. Vender un abono o una gift card también entra, y
              mezclarlo todo en un número hacía que el ticket promedio
              mintiera. */}
          {datos.por_origen.length > 1 && (
            <div className="mt-4">
              <Card titulo="De dónde salió la facturación">
                <div className="space-y-2.5">
                  {datos.por_origen.map((o) => (
                    <div key={o.origen} className="flex items-center justify-between gap-3">
                      <span className="text-sm">{o.etiqueta}</span>
                      <span className="text-right text-sm">
                        <span className="font-semibold tabular-nums">{pesos(o.total)}</span>
                        <span className="ml-2 text-xs text-muted-foreground">
                          {o.cantidad} {o.cantidad === 1 ? "operación" : "operaciones"}
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
                <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">
                  El ticket promedio se calcula solo sobre la atención
                  ({pesos(datos.facturado_turnos)}): una venta de abono no es
                  una visita y desvirtuaría el número.
                  {datos.prepago_consumido > 0 &&
                    ` Además se usaron ${pesos(datos.prepago_consumido)} de gift cards: no suman acá porque esa plata ya entró cuando se vendieron.`}
                </p>
              </Card>
            </div>
          )}

          {/* Rendimiento de los cupones: la pregunta que decide si una promo
              sirvió o fue regalar plata. */}
          {datos.por_cupon.length > 0 && (
            <div className="mt-4">
              <Card titulo="Cupones de descuento">
                <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <MiniDato etiqueta="Usos" valor={String(datos.cupones_resumen.usos)} />
                  <MiniDato
                    etiqueta="Personas distintas"
                    valor={String(datos.cupones_resumen.personas)}
                  />
                  <MiniDato
                    etiqueta="Facturado"
                    valor={pesos(datos.cupones_resumen.facturado)}
                  />
                  <MiniDato
                    etiqueta="Descuento otorgado"
                    valor={pesos(datos.cupones_resumen.descuento_otorgado)}
                  />
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-xs text-muted-foreground">
                        <th className="pb-2 pr-3 font-medium">Código</th>
                        <th className="pb-2 pr-3 text-right font-medium">Usos</th>
                        <th className="pb-2 pr-3 text-right font-medium">Personas</th>
                        <th className="pb-2 pr-3 text-right font-medium">Facturó</th>
                        <th className="pb-2 pr-3 text-right font-medium">Descuento</th>
                        <th className="pb-2 text-right font-medium">Se concretó</th>
                      </tr>
                    </thead>
                    <tbody>
                      {datos.por_cupon.map((c) => (
                        <tr key={c.codigo} className="border-b last:border-0">
                          <td className="py-2.5 pr-3">
                            <span className="font-medium">{c.codigo}</span>
                            <span className="ml-2 text-xs text-muted-foreground">
                              {c.tipo === "porcentaje" ? `${c.valor}%` : pesos(c.valor)}
                            </span>
                            {!c.activo && (
                              <span className="ml-2 text-xs text-muted-foreground">
                                · inactivo
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 pr-3 text-right tabular-nums">
                            {c.usos}
                            {c.max_usos != null && (
                              <span className="text-xs text-muted-foreground">
                                /{c.max_usos}
                              </span>
                            )}
                          </td>
                          <td className="py-2.5 pr-3 text-right tabular-nums">
                            {c.personas}
                          </td>
                          <td className="py-2.5 pr-3 text-right tabular-nums">
                            {pesos(c.facturado)}
                          </td>
                          <td className="py-2.5 pr-3 text-right tabular-nums text-muted-foreground">
                            −{pesos(c.descuento_otorgado)}
                          </td>
                          <td className="py-2.5 text-right">
                            <span
                              className={
                                c.tasa_concrecion >= 70
                                  ? "font-medium text-emerald-600"
                                  : c.tasa_concrecion >= 40
                                    ? "font-medium text-amber-600"
                                    : "font-medium text-red-600"
                              }
                            >
                              {c.tasa_concrecion}%
                            </span>
                            <span className="ml-1.5 text-xs text-muted-foreground">
                              {c.finalizados}/{c.usos}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                  &quot;Se concretó&quot; es cuántos de los turnos que usaron el
                  código terminaron atendidos. Un código con muchos usos y poca
                  concreción está atrayendo gente que después no viene.
                </p>
              </Card>
            </div>
          )}

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
      <p className="text-2xl font-bold tabular-nums" style={{ fontVariantNumeric: "lining-nums tabular-nums", color }}>
        {valor}
      </p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

/* ── Barras de horarios más demandados ── */
/** Tope del eje. Siempre par, para que la marca del medio sea un entero:
 *  un eje que dice 7,5 se lee como un número roto. */
function topeEje(max: number): number {
  return 2 * Math.ceil(max / 2);
}

function HorariosBar({ horas }: { horas: { hora: number; cantidad: number }[] }) {
  const mapa = new Map(horas.map((h) => [h.hora, h.cantidad]));

  /* EL RANGO ES EL DÍA, NO LOS DATOS.
     Del mínimo al máximo de lo que hubiera, dos turnos a dos horas distintas
     daban dos columnas de media pantalla cada una — se leían como dos bloques
     de color y daban a entender que el negocio abre dos horas. Con una jornada
     de referencia (9 a 20, que se amplía sola si hay turnos afuera), esos dos
     turnos se ven como lo que son: dos picos en un día casi vacío. */
  const desde = Math.min(9, ...horas.map((h) => h.hora));
  const hasta = Math.max(20, ...horas.map((h) => h.hora));
  const rango: number[] = [];
  for (let h = desde; h <= hasta; h++) rango.push(h);

  const max = Math.max(1, ...horas.map((h) => h.cantidad));
  const tope = topeEje(max);
  const pico = horas.reduce((a, b) => (b.cantidad > a.cantidad ? b : a), horas[0]);
  const total = horas.reduce((a, b) => a + b.cantidad, 0);

  return (
    <div>
      {/* El titular dice el dato; el gráfico muestra la forma del día. Sin esta
          línea hay que leer el gráfico para sacar la conclusión más obvia. */}
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>
          Tu hora más pedida es las{" "}
          <b className="tabular-nums text-foreground">{pico.hora}:00</b> con{" "}
          <b className="tabular-nums text-foreground">{pico.cantidad}</b>{" "}
          {pico.cantidad === 1 ? "turno" : "turnos"}
        </span>
        <span className="tabular-nums">{total} en total</span>
      </div>

      <div className="flex gap-2.5">
        {/* El eje. Sin escala, una barra llena puede ser 1 turno o 50. */}
        <div className="flex h-44 w-7 flex-none flex-col items-end justify-between text-[10px] tabular-nums text-muted-foreground/70">
          <span>{tope}</span>
          <span>{tope / 2}</span>
          <span>0</span>
        </div>
        <div className="relative h-44 flex-1">
          <div className="absolute inset-x-0 top-0 border-t border-dashed border-border/70" />
          <div className="absolute inset-x-0 top-1/2 border-t border-dashed border-border/70" />
          <div className="absolute inset-x-0 bottom-0 border-t border-border" />
          {/* Las barras llenan su columna con 4px de aire. Antes tenían un ancho
              máximo de 38px y flotaban perdidas en una tarjeta de 1600px. */}
          <div className="absolute inset-0 flex items-end gap-1">
            {rango.map((h) => {
              const c = mapa.get(h) ?? 0;
              const esPico = c === max && c > 0;
              return (
                <div key={h} className="group relative flex h-full flex-1 items-end">
                  <div
                    className={`w-full rounded-t-md transition-colors group-hover:bg-primary ${
                      esPico ? "bg-primary" : "bg-primary/40"
                    }`}
                    style={{ height: c > 0 ? `${Math.max((c / tope) * 100, 3)}%` : "0%" }}
                  />
                  <span className="pointer-events-none absolute bottom-full left-1/2 mb-1.5 -translate-x-1/2 rounded-md bg-foreground px-1.5 py-0.5 text-[10px] font-semibold tabular-nums text-background opacity-0 transition-opacity group-hover:opacity-100">
                    {c}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="flex gap-2.5">
        <div className="w-7 flex-none" />
        <div className="mt-1.5 flex flex-1 gap-1">
          {rango.map((h) => {
            const c = mapa.get(h) ?? 0;
            const esPico = c === max && c > 0;
            return (
              <span
                key={h}
                className={`flex-1 text-center text-[10px] tabular-nums ${
                  esPico ? "font-semibold text-foreground" : "text-muted-foreground/70"
                }`}
              >
                {h}
              </span>
            );
          })}
        </div>
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        Turnos por hora de inicio. Para decidir a qué hora conviene tener más
        gente — y qué horas muertas llenar con una promo.
      </p>
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
