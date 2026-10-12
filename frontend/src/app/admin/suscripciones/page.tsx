"use client";

/**
 * Evolución de las suscripciones (/admin/suscripciones).
 *
 * Sale de la foto diaria del estado de cada empresa (suscripcion_diaria). No
 * es «cuántas activas hay hoy»: es cuántas había al cierre de cada día,
 * semana o mes. Antes de la primera foto no hay datos y se dice claramente.
 */

import { useCallback, useEffect, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Camera, Info, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { tomarFotoSuscripciones, verEvolucion, type EvolucionSuscripciones } from "@/lib/admin-api";
import { Button } from "@/components/ui/button";
import { Columnas, Encabezado, Periodo, Tile, fecha, hoyISO } from "../_ui";
import { PestanasSuscripciones } from "../planes/pestanas";

const iso = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const GRANOS = [["dia", "Por día"], ["semana", "Por semana"], ["mes", "Por mes"]] as const;
type Grano = (typeof GRANOS)[number][0];

function etiqueta(p: string, g: Grano) {
  const d = new Date(`${p}T12:00:00`);
  return g === "mes"
    ? d.toLocaleDateString("es-AR", { month: "short", year: "2-digit" })
    : d.toLocaleDateString("es-AR", { day: "numeric", month: "short" });
}

function Var({ v }: { v: number | null | undefined }) {
  if (v === null || v === undefined) return <span>Sin período anterior comparable</span>;
  const Icono = v >= 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <span className="inline-flex items-center gap-0.5">
      <Icono className="h-3.5 w-3.5" aria-hidden /> {v >= 0 ? "+" : ""}{v}% vs. período anterior
    </span>
  );
}

export default function EvolucionAdmin() {
  const [g, setG] = useState<Grano>("dia");
  const [[desde, hasta], setRango] = useState<[string, string]>(() => [iso(new Date(Date.now() - 29 * 86400000)), hoyISO()]);
  const [d, setD] = useState<EvolucionSuscripciones | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tomando, setTomando] = useState(false);

  const cargar = useCallback(() => {
    setError(null);
    verEvolucion(g, desde, hasta)
      .then(setD)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo calcular la evolución."));
  }, [g, desde, hasta]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function tomarFoto() {
    setTomando(true);
    try {
      const r = await tomarFotoSuscripciones();
      toast.success(r.fotos || r.reconstruidas ? `Foto tomada: ${r.fotos} empresa(s)` : "La foto de hoy ya estaba tomada");
      cargar();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo tomar la foto.");
    } finally {
      setTomando(false);
    }
  }

  const conDatos = d?.serie.filter((p) => p.activas_al_cierre !== null) ?? [];

  return (
    <div>
      <Encabezado
        titulo="Suscripciones y planes"
        bajada="Cómo evolucionó la base de clientes, día a día. Sale de una foto diaria del estado de cada empresa, no del estado de hoy."
        acciones={
          <Button size="sm" variant="outline" onClick={tomarFoto} disabled={tomando}>
            {tomando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" aria-hidden />} Tomar la foto de hoy
          </Button>
        }
      />
      <PestanasSuscripciones />
      <div className="mb-6 flex flex-wrap items-end gap-4">
        <div role="radiogroup" aria-label="Agrupar por" className="inline-flex rounded-lg border p-0.5">
          {GRANOS.map(([v, t]) => (
            <button key={v} role="radio" aria-checked={g === v} onClick={() => setG(v)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${g === v ? "bg-primary/15 text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
              {t}
            </button>
          ))}
        </div>
        <Periodo desde={desde} hasta={hasta} onCambio={(a, b) => setRango([a, b])} />
      </div>

      {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
      {!d ? (
        <div className="h-40 animate-pulse rounded-2xl bg-muted" />
      ) : (
        <div className="space-y-6">
          <p className="flex items-start gap-2 rounded-xl border bg-card px-3 py-2 text-sm">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            {d.confiable_desde
              ? <span>Datos diarios fiables desde el <b>{fecha(d.confiable_desde)}</b>. Antes de esa fecha no hay historia y no se estima.</span>
              : <span>Todavía no hay fotos diarias: la primera se toma esta noche (o ahora, con el botón de arriba).</span>}
          </p>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile etiqueta="Activas al cierre" valor={d.total.activas_al_cierre ?? "—"} nota={<Var v={d.variacion.activas_al_cierre} />} />
            <Tile etiqueta="Nuevas" valor={d.total.nuevas ?? 0} nota={<Var v={d.variacion.nuevas} />} />
            <Tile etiqueta="Vencimientos" valor={d.total.vencimientos ?? 0} nota={<Var v={d.variacion.vencimientos} />} tono={d.total.vencimientos ? "aviso" : "neutro"} />
            <Tile etiqueta="Cancelaciones" valor={d.total.cancelaciones ?? 0} nota={<Var v={d.variacion.cancelaciones} />} tono={d.total.cancelaciones ? "error" : "neutro"} />
          </div>

          {conDatos.length > 0 && (
            <section className="rounded-2xl border bg-card p-4">
              <h2 className="text-sm font-semibold">Suscripciones activas al cierre de cada {g === "dia" ? "día" : g}</h2>
              <Columnas
                etiqueta="Activas al cierre"
                formato={(n) => String(n)}
                datos={conDatos.map((p) => ({ clave: p.periodo, etiqueta: etiqueta(p.periodo, g), valor: p.activas_al_cierre ?? 0 }))}
              />
            </section>
          )}

          <section aria-labelledby="t-tabla" className="rounded-2xl border bg-card">
            <h2 id="t-tabla" className="border-b px-4 py-3 text-sm font-semibold">Detalle</h2>
            <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label="Detalle por período (deslizable)">
              <table className="w-full min-w-[680px] text-sm">
                <thead className="text-xs text-muted-foreground">
                  <tr className="border-b">
                    {["Período", "Activas al cierre", "Nuevas", "Reactivadas", "Vencimientos", "Cancelaciones", "Pruebas vencidas", "Cambios de plan", "Datos"].map((h, i) => (
                      <th key={h} scope="col" className={`px-3 py-2 font-medium ${i ? "text-right" : "text-left"}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {d.serie.map((p) => (
                    <tr key={p.periodo} className="border-b last:border-0">
                      <th scope="row" className="px-3 py-2 text-left font-medium">{etiqueta(p.periodo, g)}</th>
                      <td className="px-3 py-2 text-right">{p.activas_al_cierre ?? "—"}</td>
                      <td className="px-3 py-2 text-right">{p.nuevas}</td>
                      <td className="px-3 py-2 text-right">{p.reactivadas}</td>
                      <td className="px-3 py-2 text-right">{p.vencimientos}</td>
                      <td className="px-3 py-2 text-right">{p.cancelaciones}</td>
                      <td className="px-3 py-2 text-right">{p.pruebas_vencidas}</td>
                      <td className="px-3 py-2 text-right">{p.cambios_de_plan}</td>
                      <td className="px-3 py-2 text-right text-xs text-muted-foreground">
                        {p.dias_con_datos === 0 ? "sin datos" : p.dias_con_datos < p.dias ? `${p.dias_con_datos}/${p.dias} días` : "completo"}
                        {p.dias_reconstruidos ? ` · ${p.dias_reconstruidos} reconstr.` : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {d.cambios_de_plan.length > 0 && (
            <section className="rounded-2xl border bg-card p-4 text-sm">
              <h2 className="font-semibold">Cambios de plan del período</h2>
              <ul className="mt-2 space-y-1">
                {d.cambios_de_plan.map((c) => <li key={c.cambio}>{c.cambio}: <b>{c.cantidad}</b></li>)}
              </ul>
            </section>
          )}

          <details className="rounded-2xl border bg-card p-4 text-sm">
            <summary className="cursor-pointer font-semibold">Qué cuenta cada número</summary>
            <dl className="mt-3 space-y-2">
              {Object.entries(d.definiciones).map(([k, v]) => (
                <div key={k}><dt className="font-medium capitalize">{k.replace(/_/g, " ")}</dt><dd className="text-muted-foreground">{v}</dd></div>
              ))}
            </dl>
          </details>
        </div>
      )}
    </div>
  );
}
