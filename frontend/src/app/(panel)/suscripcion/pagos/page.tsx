"use client";

/**
 * Mi suscripción · Historial de pagos.
 *
 * Solo lista pagos ACREDITADOS (los anulados no aparecen). Lo que todavía no
 * se acreditó —una transferencia en revisión, un pago pendiente o rechazado en
 * Mercado Pago— va aparte, rotulado, y nunca se mezcla con lo cobrado.
 * No hay comprobante fiscal: el detalle muestra la referencia real del cobro
 * cuando existe (id de Mercado Pago) y nada más.
 */

import { useMemo, useState } from "react";
import { Clock, Receipt, XCircle } from "lucide-react";

import type { PagoSuscripcion } from "@/lib/empresa-api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Cargando, fechaCorta, fechaLarga, pesos, useSuscripcion } from "../_suscripcion";

const PERIODOS = [
  { valor: "todo", texto: "Todo" },
  { valor: "3", texto: "Últimos 3 meses" },
  { valor: "12", texto: "Últimos 12 meses" },
] as const;

export default function SuscripcionPagos() {
  const { datos, cargando } = useSuscripcion();
  const [periodo, setPeriodo] = useState<string>("todo");
  const [metodo, setMetodo] = useState<string>("todos");
  const [abierto, setAbierto] = useState<PagoSuscripcion | null>(null);

  const metodos = useMemo(
    () => Array.from(new Set((datos?.pagos ?? []).map((p) => p.metodo))),
    [datos],
  );

  const filtrados = useMemo(() => {
    const pagos = datos?.pagos ?? [];
    const desde =
      periodo === "todo" ? null : new Date(new Date().setMonth(new Date().getMonth() - Number(periodo)));
    return pagos.filter(
      (p) =>
        (metodo === "todos" || p.metodo === metodo) &&
        (!desde || (p.fecha && new Date(`${p.fecha}T00:00:00`) >= desde)),
    );
  }, [datos, periodo, metodo]);

  if (cargando || !datos) return <Cargando />;

  const total = filtrados.reduce((s, p) => s + p.monto, 0);
  const enCurso: { icono: React.ReactNode; texto: string; detalle: string; clase: string }[] = [];
  if (datos.aviso) {
    enCurso.push({
      icono: <Clock className="h-4 w-4" />,
      texto: datos.aviso.estado === "info_solicitada" ? "Transferencia: falta un dato" : "Transferencia en revisión",
      detalle: [
        datos.aviso.monto ? pesos(datos.aviso.monto) : null,
        datos.aviso.plan_etiqueta,
        datos.aviso.creado_en ? `informada el ${fechaCorta(datos.aviso.creado_en)}` : null,
      ]
        .filter(Boolean)
        .join(" · "),
      clase: "text-sky-700 dark:text-sky-400",
    });
  }
  if (datos.ultimo_intento && !datos.aviso) {
    const rech = datos.ultimo_intento.estado === "rechazado";
    enCurso.push({
      icono: rech ? <XCircle className="h-4 w-4" /> : <Clock className="h-4 w-4" />,
      texto: rech ? "Mercado Pago rechazó el pago (no se cobró)" : "Pago pendiente en Mercado Pago",
      detalle: [pesos(datos.ultimo_intento.monto), datos.ultimo_intento.plan_etiqueta, fechaCorta(datos.ultimo_intento.fecha)]
        .filter(Boolean)
        .join(" · "),
      clase: rech ? "text-red-700 dark:text-red-400" : "text-amber-700 dark:text-amber-400",
    });
  }

  return (
    <div className="space-y-5">
      {enCurso.length > 0 && (
        <section className="rounded-2xl border bg-card p-5">
          <h2 className="text-sm font-semibold">Todavía no acreditado</h2>
          <ul className="mt-3 space-y-2">
            {enCurso.map((e) => (
              <li key={e.texto} className="flex items-start gap-2 text-sm">
                <span className={`mt-0.5 ${e.clase}`}>{e.icono}</span>
                <span>
                  <span className="font-medium">{e.texto}</span>
                  {e.detalle && <span className="text-muted-foreground"> · {e.detalle}</span>}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-2xl border bg-card p-5 md:p-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-base font-bold">Pagos acreditados</h2>
            <p className="text-sm text-muted-foreground">
              {filtrados.length} pago{filtrados.length === 1 ? "" : "s"} · {pesos(total)}
            </p>
          </div>
          {datos.pagos.length > 0 && (
            <div className="flex flex-wrap gap-2">
              <Filtro etiqueta="Período" valor={periodo} onCambio={setPeriodo} opciones={PERIODOS.map((p) => ({ valor: p.valor, texto: p.texto }))} />
              {metodos.length > 1 && (
                <Filtro
                  etiqueta="Método"
                  valor={metodo}
                  onCambio={setMetodo}
                  opciones={[{ valor: "todos", texto: "Todos" }, ...metodos.map((m) => ({ valor: m, texto: m }))]}
                />
              )}
            </div>
          )}
        </div>

        {datos.pagos.length === 0 ? (
          <div className="mt-6 flex flex-col items-center gap-2 py-6 text-center">
            <Receipt className="h-8 w-8 text-muted-foreground/60" aria-hidden />
            <p className="text-sm text-muted-foreground">
              Todavía no hay pagos registrados. Cuando se acredite el primero, aparece acá.
            </p>
          </div>
        ) : filtrados.length === 0 ? (
          <p className="mt-6 text-sm text-muted-foreground">No hay pagos con esos filtros.</p>
        ) : (
          <>
            <ul className="mt-4 divide-y sm:hidden">
              {filtrados.map((p, i) => (
                <li key={p.id ?? `${p.fecha}-${i}`}>
                  <button
                    type="button"
                    onClick={() => setAbierto(p)}
                    className="flex w-full items-start justify-between gap-3 py-3 text-left"
                  >
                    <span className="min-w-0">
                      <span className="block text-sm font-medium">
                        {p.tipo_etiqueta ?? "Pago"}
                        {p.plan_etiqueta ? ` · ${p.plan_etiqueta}` : ""}
                      </span>
                      <span className="block text-xs text-muted-foreground">
                        {fechaCorta(p.fecha)} · {p.metodo}
                      </span>
                    </span>
                    <span className="shrink-0 text-sm font-semibold tabular-nums">{pesos(p.monto)}</span>
                  </button>
                </li>
              ))}
            </ul>
            <div className="mt-4 hidden overflow-x-auto sm:block">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="pb-2 font-medium">Fecha</th>
                    <th className="pb-2 font-medium">Concepto</th>
                    <th className="pb-2 font-medium">Período cubierto</th>
                    <th className="pb-2 font-medium">Método</th>
                    <th className="pb-2 font-medium">Estado</th>
                    <th className="pb-2 text-right font-medium">Importe</th>
                    <th className="pb-2" />
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {filtrados.map((p, i) => (
                    <tr key={p.id ?? `${p.fecha}-${i}`}>
                      <td className="whitespace-nowrap py-2.5">{fechaCorta(p.fecha)}</td>
                      <td className="py-2.5">
                        {p.tipo_etiqueta ?? "Pago"}
                        {p.plan_etiqueta && <span className="text-muted-foreground"> · {p.plan_etiqueta}</span>}
                      </td>
                      <td className="py-2.5 text-muted-foreground">
                        {p.periodo_desde ? `${fechaCorta(p.periodo_desde)} — ${fechaCorta(p.periodo_hasta)}` : "—"}
                      </td>
                      <td className="py-2.5 text-muted-foreground">{p.metodo}</td>
                      <td className="py-2.5">
                        <span className="text-emerald-700 dark:text-emerald-400">Acreditado</span>
                      </td>
                      <td className="py-2.5 text-right font-semibold tabular-nums">{pesos(p.monto)}</td>
                      <td className="py-2.5 text-right">
                        <button
                          type="button"
                          onClick={() => setAbierto(p)}
                          className="text-xs font-medium underline underline-offset-4 hover:text-foreground"
                        >
                          Detalle
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <Dialog open={abierto !== null} onOpenChange={(v) => !v && setAbierto(null)}>
        <DialogContent className="max-w-md">
          {abierto && (
            <>
              <DialogHeader>
                <DialogTitle>{pesos(abierto.monto)}</DialogTitle>
                <DialogDescription>
                  {abierto.tipo_etiqueta ?? "Pago"} acreditado el {fechaLarga(abierto.fecha)}
                </DialogDescription>
              </DialogHeader>
              <dl className="divide-y text-sm">
                <Fila etiqueta="Concepto" valor={abierto.tipo_etiqueta ?? "Pago"} />
                <Fila etiqueta="Plan" valor={abierto.plan_etiqueta ?? "—"} />
                <Fila
                  etiqueta="Período cubierto"
                  valor={abierto.periodo_desde ? `${fechaLarga(abierto.periodo_desde)} al ${fechaLarga(abierto.periodo_hasta)}` : "—"}
                />
                <Fila etiqueta="Método" valor={abierto.metodo} />
                <Fila etiqueta="Estado" valor="Acreditado" />
                <Fila etiqueta="Referencia" valor={abierto.referencia ?? "Sin referencia externa"} />
              </dl>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Filtro({
  etiqueta,
  valor,
  onCambio,
  opciones,
}: {
  etiqueta: string;
  valor: string;
  onCambio: (v: string) => void;
  opciones: { valor: string; texto: string }[];
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-muted-foreground">
      {etiqueta}
      <select
        value={valor}
        onChange={(e) => onCambio(e.target.value)}
        className="h-9 rounded-lg border bg-background px-2.5 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {opciones.map((o) => (
          <option key={o.valor} value={o.valor}>
            {o.texto}
          </option>
        ))}
      </select>
    </label>
  );
}

function Fila({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="flex justify-between gap-4 py-2.5">
      <dt className="text-muted-foreground">{etiqueta}</dt>
      <dd className="text-right font-medium">{valor}</dd>
    </div>
  );
}
