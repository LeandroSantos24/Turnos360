"use client";

/**
 * Resumen general del super-admin (/admin).
 *
 * Todo sale de /admin/resumen. Lo acreditado, lo pendiente, lo en revisión
 * y lo devuelto van separados: ninguno se suma a otro, y nada de lo que se
 * espera cobrar aparece como cobrado.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Info, XCircle } from "lucide-react";

import { ApiError } from "@/lib/api";
import { resumenGeneral, type ResumenGeneral } from "@/lib/admin-api";
import { Columnas, Encabezado, Periodo, Tile, hoyISO, pesos } from "./_ui";

const ESTADOS: Record<string, string> = {
  activa: "Activas",
  prueba: "En prueba",
  prueba_vencida: "Prueba vencida",
  pendiente_pago: "Pago pendiente",
  en_revision: "Pago en revisión",
  prorroga: "En prórroga",
  vencida: "Vencidas",
  cancelacion_programada: "Cancelación programada",
  cancelada: "Canceladas",
  suspendida: "Suspendidas",
  sin_vencimiento: "Sin vencimiento",
};

export default function ResumenAdmin() {
  const [desde, setDesde] = useState(() => `${hoyISO().slice(0, 8)}01`);
  const [hasta, setHasta] = useState(hoyISO);
  const [d, setD] = useState<ResumenGeneral | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(() => {
    setError(null);
    resumenGeneral(desde, hasta)
      .then(setD)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo cargar el resumen."));
  }, [desde, hasta]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  return (
    <div>
      <Encabezado
        titulo="Resumen"
        bajada="Lo cobrado, lo que falta cobrar y lo que hay que mirar hoy. Lo acreditado y lo pendiente nunca se suman."
      />
      <div className="mb-6">
        <Periodo desde={desde} hasta={hasta} onCambio={(a, b) => { setDesde(a); setHasta(b); }} />
      </div>

      {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
      {!d ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-24 animate-pulse rounded-2xl bg-muted" />)}
        </div>
      ) : (
        <div className="space-y-6">
          {d.alertas.length > 0 && (
            <section aria-label="Alertas" className="space-y-2">
              {d.alertas.map((a) => {
                const Icono = a.tipo === "error" ? XCircle : a.tipo === "aviso" ? AlertTriangle : Info;
                const color = a.tipo === "error" ? "border-red-300 bg-red-50 text-red-900 dark:bg-red-950/40 dark:text-red-200"
                  : a.tipo === "aviso" ? "border-amber-300 bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
                  : "border-sky-300 bg-sky-50 text-sky-900 dark:bg-sky-950/40 dark:text-sky-200";
                return (
                  <Link key={a.texto} href={a.href} className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm ${color}`}>
                    <Icono className="h-4 w-4 shrink-0" aria-hidden />
                    <span className="flex-1">{a.texto}</span>
                    <ArrowRight className="h-4 w-4" aria-hidden />
                  </Link>
                );
              })}
            </section>
          )}

          <section aria-labelledby="t-plata">
            <h2 id="t-plata" className="mb-3 text-sm font-semibold text-muted-foreground">Plata del período</h2>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Tile etiqueta="Acreditado" valor={pesos(d.periodo.acreditado)} nota={`${d.periodo.cantidad_cobros} cobro(s)`} tono="ok" />
              <Tile etiqueta="Devoluciones" valor={pesos(d.periodo.devoluciones)} nota="Solo las confirmadas" />
              <Tile etiqueta="Comisiones" valor={pesos(d.periodo.comisiones)} nota="Las que informó Mercado Pago" />
              <Tile etiqueta="Neto calculado" valor={pesos(d.periodo.neto)} nota="No es el saldo del banco" />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Tile etiqueta="En revisión" valor={pesos(d.periodo.en_revision)} nota="Transferencias informadas, sin verificar" tono={d.periodo.en_revision ? "aviso" : "neutro"} />
              <Tile etiqueta="Pendiente" valor={pesos(d.periodo.pendiente)} nota="Pagos de Mercado Pago sin terminar" />
              <Tile etiqueta="Rechazado" valor={pesos(d.periodo.rechazado)} tono={d.periodo.rechazado ? "error" : "neutro"} />
            </div>
          </section>

          <section aria-labelledby="t-negocios" className="grid gap-3 lg:grid-cols-[1fr_1fr]">
            <div className="rounded-2xl border bg-card p-4">
              <h2 id="t-negocios" className="text-sm font-semibold">Negocios y suscripciones</h2>
              <div className="mt-3 grid grid-cols-3 gap-3 text-center">
                <div><p className="text-2xl font-bold tabular-nums">{d.empresas.total}</p><p className="text-xs text-muted-foreground">Registrados</p></div>
                <div><p className="text-2xl font-bold tabular-nums">{d.suscripciones.activas}</p><p className="text-xs text-muted-foreground">Suscripciones activas</p></div>
                <div><p className="text-2xl font-bold tabular-nums">{d.suscripciones.por_vencer_7d}</p><p className="text-xs text-muted-foreground">Vencen en 7 días</p></div>
              </div>
              <ul className="mt-4 flex flex-wrap gap-1.5 text-xs">
                {Object.entries(d.suscripciones.por_estado).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                  <li key={k} className="rounded-full bg-muted px-2.5 py-1">{ESTADOS[k] ?? k}: <b>{v}</b></li>
                ))}
                {d.empresas.inactivas > 0 && <li className="rounded-full bg-muted px-2.5 py-1">Pausadas: <b>{d.empresas.inactivas}</b></li>}
              </ul>
            </div>
            <div className="rounded-2xl border bg-card p-4">
              <h2 className="text-sm font-semibold">Neto por semana</h2>
              <p className="text-xs text-muted-foreground">Últimas 12 semanas del período elegido.</p>
              <Columnas
                etiqueta="Neto por semana"
                datos={d.serie_semanal.map((s) => ({
                  clave: s.periodo,
                  etiqueta: new Date(`${s.periodo}T12:00:00`).toLocaleDateString("es-AR", { day: "numeric", month: "short" }),
                  valor: s.neto,
                }))}
              />
            </div>
          </section>

          <section className="grid gap-3 sm:grid-cols-2">
            <Link href="/admin/cobranza" className="rounded-2xl border bg-card p-4 hover:bg-muted/50">
              <p className="font-semibold">{d.transferencias_en_revision} transferencia(s) por revisar</p>
              <p className="text-sm text-muted-foreground">Verificar en el banco y aprobar o rechazar.</p>
            </Link>
            <Link href="/admin/cobros?estado=reembolso_solicitado" className="rounded-2xl border bg-card p-4 hover:bg-muted/50">
              <p className="font-semibold">{d.devoluciones_pendientes.cantidad} devolución(es) sin confirmar</p>
              <p className="text-sm text-muted-foreground">{pesos(d.devoluciones_pendientes.monto)} pedidos, todavía no devueltos.</p>
            </Link>
          </section>
        </div>
      )}
    </div>
  );
}
