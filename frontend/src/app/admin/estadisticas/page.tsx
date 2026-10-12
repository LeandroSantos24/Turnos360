"use client";

/**
 * Estadísticas y reportes (/admin/estadisticas).
 *
 * Serie por semana o por mes con lo cobrado, lo devuelto y el neto, la
 * variación contra el período anterior del mismo largo y la tabla con todos
 * los números. Cada métrica tiene su definición a la vista: el número no
 * dice nada si no se sabe qué cuenta.
 */

import { useCallback, useEffect, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { exportarEstadisticas, verEstadisticas, type Estadisticas } from "@/lib/admin-api";
import { Button } from "@/components/ui/button";
import { Columnas, Encabezado, Periodo, Tile, hoyISO, pesos } from "../_ui";

const iso = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);

function etiquetaPeriodo(p: string, g: "semana" | "mes") {
  const d = new Date(`${p}T12:00:00`);
  return g === "mes"
    ? d.toLocaleDateString("es-AR", { month: "short", year: "2-digit" })
    : d.toLocaleDateString("es-AR", { day: "numeric", month: "short" });
}

function Variacion({ v }: { v: number | null | undefined }) {
  if (v === null || v === undefined) return <span>Sin período anterior para comparar</span>;
  const sube = v >= 0;
  const Icono = sube ? ArrowUpRight : ArrowDownRight;
  return (
    <span className="inline-flex items-center gap-0.5">
      <Icono className="h-3.5 w-3.5" aria-hidden />
      {sube ? "+" : ""}{Math.round(v * 10) / 10}% vs. período anterior
    </span>
  );
}

const SERIES: { clave: "bruto" | "neto" | "devoluciones"; titulo: string }[] = [
  { clave: "bruto", titulo: "Cobrado (bruto)" },
  { clave: "neto", titulo: "Neto calculado" },
  { clave: "devoluciones", titulo: "Devoluciones" },
];

export default function EstadisticasAdmin() {
  const [g, setG] = useState<"semana" | "mes">("mes");
  const [[desde, hasta], setRango] = useState<[string, string]>(() => {
    const h = new Date(`${hoyISO()}T12:00:00`);
    return [iso(new Date(h.getFullYear(), h.getMonth() - 5, 1)), hoyISO()];
  });
  const [d, setD] = useState<Estadisticas | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportando, setExportando] = useState(false);

  const cargar = useCallback(() => {
    setError(null);
    verEstadisticas(g, desde, hasta)
      .then(setD)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron calcular las estadísticas."));
  }, [g, desde, hasta]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function exportar() {
    setExportando(true);
    try {
      await exportarEstadisticas(g, desde, hasta);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo exportar.");
    } finally {
      setExportando(false);
    }
  }

  return (
    <div>
      <Encabezado
        titulo="Estadísticas y reportes"
        bajada="Cobros, devoluciones y neto por semana o por mes. Lo pendiente nunca se suma a lo cobrado."
        acciones={
          <Button variant="outline" size="sm" onClick={exportar} disabled={exportando}>
            {exportando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} Exportar CSV
          </Button>
        }
      />
      <div className="mb-6 flex flex-wrap items-end gap-4">
        <div role="radiogroup" aria-label="Agrupar por" className="inline-flex rounded-lg border p-0.5">
          {(["semana", "mes"] as const).map((x) => (
            <button key={x} role="radio" aria-checked={g === x} onClick={() => setG(x)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${g === x ? "bg-primary/15 text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
              {x === "semana" ? "Por semana" : "Por mes"}
            </button>
          ))}
        </div>
        <Periodo desde={desde} hasta={hasta} onCambio={(a, b) => setRango([a, b])} />
      </div>

      {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
      {!d ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-24 animate-pulse rounded-2xl bg-muted" />)}
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile etiqueta="Cobrado" valor={pesos(d.total.bruto)} nota={<Variacion v={d.variacion.bruto} />} />
            <Tile etiqueta="Devoluciones" valor={pesos(d.total.devoluciones)} nota={<Variacion v={d.variacion.devoluciones} />} />
            <Tile etiqueta="Neto calculado" valor={pesos(d.total.neto)} nota={<Variacion v={d.variacion.neto} />} />
            <Tile etiqueta="Suscripciones activas" valor={d.suscripciones_activas_hoy} nota="Hoy (no hay historia por día)" />
          </div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile etiqueta="Cobros" valor={d.total.cobros} nota={`${d.total.altas} alta(s) · ${d.total.renovaciones} renovación(es)`} />
            <Tile etiqueta="Comisiones" valor={pesos(d.total.comisiones)} />
            <Tile etiqueta="Pendientes" valor={d.total.pendientes} nota={`${d.total.rechazados} rechazado(s) · no es plata cobrada`} />
            <Tile etiqueta="Cancelaciones" valor={d.total.cancelaciones} />
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            {SERIES.map((s) => (
              <section key={s.clave} className="rounded-2xl border bg-card p-4">
                <h2 className="text-sm font-semibold">{s.titulo}</h2>
                <Columnas
                  etiqueta={`${s.titulo} por ${g}`}
                  datos={d.serie.map((p) => ({ clave: p.periodo, etiqueta: etiquetaPeriodo(p.periodo, g), valor: p[s.clave] }))}
                />
              </section>
            ))}
          </div>

          <section aria-labelledby="t-tabla" className="rounded-2xl border bg-card">
            <h2 id="t-tabla" className="border-b px-4 py-3 text-sm font-semibold">Detalle por {g}</h2>
            <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label="Tabla por período (deslizable)">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="text-xs text-muted-foreground">
                  <tr className="border-b">
                    {["Período", "Cobrado", "Devoluciones", "Comisiones", "Neto", "Cobros", "Altas", "Renov.", "Pendiente", "Cancel."].map((h, i) => (
                      <th key={h} scope="col" className={`px-3 py-2 font-medium ${i ? "text-right" : "text-left"}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {d.serie.map((p) => (
                    <tr key={p.periodo} className="border-b last:border-0">
                      <th scope="row" className="px-3 py-2 text-left font-medium">{etiquetaPeriodo(p.periodo, g)}</th>
                      <td className="px-3 py-2 text-right">{pesos(p.bruto)}</td>
                      <td className="px-3 py-2 text-right">{pesos(p.devoluciones)}</td>
                      <td className="px-3 py-2 text-right">{pesos(p.comisiones)}</td>
                      <td className="px-3 py-2 text-right font-semibold">{pesos(p.neto)}</td>
                      <td className="px-3 py-2 text-right">{p.cobros}</td>
                      <td className="px-3 py-2 text-right">{p.altas}</td>
                      <td className="px-3 py-2 text-right">{p.renovaciones}</td>
                      <td className="px-3 py-2 text-right">{p.pendientes}</td>
                      <td className="px-3 py-2 text-right">{p.cancelaciones}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {d.beneficios && (
            <section aria-labelledby="t-benef" className="rounded-2xl border border-dashed bg-card p-4">
              <h2 id="t-benef" className="text-sm font-semibold">Beneficios comerciales (días, no plata)</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">{d.beneficios.nota}</p>
              <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                {([
                  ["Días de cortesía", d.beneficios.total.dias_cortesia],
                  ["Días por incidencias", d.beneficios.total.dias_incidencia],
                  ["Sin clasificar", d.beneficios.total.dias_sin_clasificar],
                  ["Empresas", d.beneficios.total.empresas],
                ] as const).map(([k, v]) => (
                  <div key={k} className="rounded-xl bg-muted/50 px-3 py-2">
                    <dt className="text-xs text-muted-foreground">{k}</dt>
                    <dd className="font-semibold tabular-nums">{v}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-2 text-xs">
                <a href="/admin/ajustes" className="font-medium underline underline-offset-4">Ver los ajustes uno por uno</a>
              </p>
            </section>
          )}

          <details className="rounded-2xl border bg-card p-4 text-sm">
            <summary className="cursor-pointer font-semibold">Qué cuenta cada número</summary>
            <dl className="mt-3 space-y-2">
              {Object.entries(d.definiciones).map(([k, v]) => (
                <div key={k}>
                  <dt className="font-medium capitalize">{k.replace(/_/g, " ")}</dt>
                  <dd className="text-muted-foreground">{v}</dd>
                </div>
              ))}
            </dl>
          </details>
        </div>
      )}
    </div>
  );
}
