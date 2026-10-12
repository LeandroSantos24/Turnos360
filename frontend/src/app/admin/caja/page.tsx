"use client";

/**
 * Caja y cierres (/admin/caja).
 *
 * La caja es calculada: sale de los pagos acreditados y de las devoluciones
 * confirmadas. No es el saldo del banco ni de Mercado Pago; para eso está la
 * conciliación. Un cierre congela los totales de un período cerrado; si
 * después aparece un movimiento en ese período, se ve la diferencia y el
 * cierre se puede reabrir con un motivo.
 */

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2, Lock, RotateCcw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import {
  conciliarPago,
  confirmarCierre,
  descartarCierre,
  listarCierres,
  prepararCierre,
  reabrirCierre,
  verCaja,
  type Caja,
  type Cierre,
} from "@/lib/admin-api";
import { useConfirmar } from "@/components/confirmar";
import { Button } from "@/components/ui/button";
import { Encabezado, METODOS, Periodo, Tile, Vacio, fecha, fechaHora, hoyISO, pesos } from "../_ui";

const ESTADO_CIERRE: Record<Cierre["estado"], [string, string]> = {
  borrador: ["Borrador", "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200"],
  cerrado: ["Cerrado", "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200"],
  reabierto: ["Reabierto", "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200"],
  anulado: ["Descartado", "bg-muted text-muted-foreground"],
};

const iso = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);

function periodoAnterior(tipo: "semana" | "mes"): [string, string] {
  const hoy = new Date(`${hoyISO()}T12:00:00`);
  if (tipo === "mes") return [iso(new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1)), iso(new Date(hoy.getFullYear(), hoy.getMonth(), 0))];
  const lunes = new Date(hoy.getTime() - ((hoy.getDay() + 6) % 7) * 86400000 - 7 * 86400000);
  return [iso(lunes), iso(new Date(lunes.getTime() + 6 * 86400000))];
}

const err = (e: unknown, def: string) => (e instanceof ApiError ? e.message : def);

export default function CajaAdmin() {
  const [[desde, hasta], setRango] = useState<[string, string]>(() => [`${hoyISO().slice(0, 8)}01`, hoyISO()]);
  const [caja, setCaja] = useState<Caja | null>(null);
  const [cierres, setCierres] = useState<Cierre[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [motivos, setMotivos] = useState<Record<number, string>>({});
  const confirmar = useConfirmar();

  const cargar = useCallback(() => {
    setError(null);
    verCaja(desde, hasta).then(setCaja).catch((e) => setError(err(e, "No se pudo calcular la caja.")));
    listarCierres().then(setCierres).catch(() => setCierres([]));
  }, [desde, hasta]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function correr(clave: string, f: () => Promise<unknown>, ok: string) {
    setOcupado(clave);
    try {
      await f();
      toast.success(ok);
      cargar();
    } catch (e) {
      toast.error(err(e, "No se pudo hacer."));
    } finally {
      setOcupado(null);
    }
  }

  async function preparar(a: string, b: string) {
    const ok = await confirmar({
      titulo: `¿Preparar el cierre del ${fecha(a)} al ${fecha(b)}?`,
      descripcion: "Queda como borrador con los totales de hoy. Revisalo y después confirmalo.",
      textoAccion: "Preparar borrador",
    });
    if (ok) await correr("preparar", () => prepararCierre(a, b), "Borrador de cierre preparado");
  }

  async function cerrar(c: Cierre) {
    const ok = await confirmar({
      titulo: "¿Cerrar la caja de este período?",
      descripcion: `Del ${fecha(c.desde)} al ${fecha(c.hasta)}: neto ${pesos(c.totales.neto)}. Los totales quedan congelados; si algo cambia después, vas a ver la diferencia.`,
      textoAccion: "Sí, cerrar",
    });
    if (ok) await correr(`c${c.id}`, () => confirmarCierre(c.id), "Caja cerrada");
  }

  async function reabrir(c: Cierre) {
    const motivo = (motivos[c.id] ?? "").trim();
    if (motivo.length < 4) {
      toast.error("Escribí por qué se reabre");
      return;
    }
    const ok = await confirmar({
      titulo: "¿Reabrir este cierre?",
      descripcion: `Del ${fecha(c.desde)} al ${fecha(c.hasta)}. Queda registrado quién lo reabrió y por qué.`,
      textoAccion: "Sí, reabrir",
      destructivo: true,
    });
    if (ok) {
      await correr(`r${c.id}`, () => reabrirCierre(c.id, motivo), "Cierre reabierto");
      setMotivos((m) => ({ ...m, [c.id]: "" }));
    }
  }

  async function descartar(c: Cierre) {
    const ok = await confirmar({
      titulo: "¿Descartar este borrador?",
      descripcion: "No se borra: queda como descartado en el historial.",
      textoAccion: "Descartar",
      destructivo: true,
    });
    if (ok) await correr(`d${c.id}`, () => descartarCierre(c.id), "Borrador descartado");
  }

  async function conciliar(pagoId: number, valor: boolean) {
    await correr(`p${pagoId}`, () => conciliarPago(pagoId, valor), valor ? "Marcado como conciliado" : "Conciliación quitada");
  }

  const t = caja?.totales;
  const [semA, semB] = periodoAnterior("semana");
  const [mesA, mesB] = periodoAnterior("mes");

  return (
    <div>
      <Encabezado
        titulo="Caja y cierres"
        bajada="Caja calculada con los cobros acreditados y las devoluciones confirmadas. No es el saldo del banco: lo que coincide con el extracto se marca como conciliado."
      />
      <div className="mb-6">
        <Periodo desde={desde} hasta={hasta} onCambio={(a, b) => setRango([a, b])} />
      </div>
      {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}

      {!caja || !t ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-24 animate-pulse rounded-2xl bg-muted" />)}
        </div>
      ) : (
        <div className="space-y-6">
          {caja.cierre && (
            <p className="rounded-xl border bg-card px-3 py-2 text-sm">
              Este período tiene un cierre <b>{ESTADO_CIERRE[caja.cierre.estado][0].toLowerCase()}</b>
              {caja.diferencias_con_cierre && Object.keys(caja.diferencias_con_cierre).length > 0 ? (
                <span className="text-red-800 dark:text-red-300">
                  {" "}y hay diferencias con lo de hoy:{" "}
                  {Object.entries(caja.diferencias_con_cierre).map(([k, v]) => `${k.replace(/_/g, " ")} ${v > 0 ? "+" : ""}${pesos(v)}`).join(" · ")}
                </span>
              ) : (
                " y coincide con lo calculado hoy."
              )}
            </p>
          )}

          <section aria-labelledby="t-totales">
            <h2 id="t-totales" className="sr-only">Totales del período</h2>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Tile etiqueta="Saldo inicial" valor={pesos(caja.saldo_inicial)} nota="Calculado desde el primer cobro" />
              <Tile etiqueta="Cobros" valor={pesos(t.cobros)} nota={`${t.cantidad_cobros} acreditado(s)`} tono="ok" />
              <Tile etiqueta="Devoluciones y comisiones" valor={pesos(t.devoluciones + t.comisiones)}
                nota={`${pesos(t.devoluciones)} devuelto · ${pesos(t.comisiones)} comisiones`} />
              <Tile etiqueta="Saldo final" valor={pesos(caja.saldo_final)} nota="Calculado, no es saldo bancario" />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Tile etiqueta="Transferencias" valor={pesos(t.transferencias_verificadas)} />
              <Tile etiqueta="Mercado Pago" valor={pesos(t.mercadopago)}
                nota={t.pagos_mp_sin_comision ? `${t.pagos_mp_sin_comision} pago(s) sin comisión informada` : undefined} />
              <Tile etiqueta="Sin conciliar" valor={pesos(t.sin_conciliar.monto)} nota={`${t.sin_conciliar.cantidad} cobro(s)`}
                tono={t.sin_conciliar.cantidad ? "aviso" : "neutro"} />
            </div>
          </section>

          <section aria-labelledby="t-ingresos" className="rounded-2xl border bg-card">
            <h2 id="t-ingresos" className="border-b px-4 py-3 text-sm font-semibold">Ingresos ({caja.ingresos.length})</h2>
            {caja.ingresos.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">No hubo cobros acreditados en el período.</p>
            ) : (
              <ul className="divide-y">
                {caja.ingresos.map((i) => (
                  <li key={i.pago_id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-sm">
                    <span className="w-20 shrink-0 tabular-nums text-muted-foreground">{fecha(i.fecha)}</span>
                    <span className="min-w-0 flex-1">
                      <span className="font-medium">{i.empresa}</span>
                      <span className="block text-xs text-muted-foreground">
                        {METODOS[i.metodo] ?? i.metodo} · {i.concepto}
                        {i.comision ? ` · comisión ${pesos(i.comision)}` : ""}
                        {i.referencia ? ` · ref. ${i.referencia}` : ""}
                      </span>
                    </span>
                    <span className="font-semibold tabular-nums">{pesos(i.monto)}</span>
                    <Button size="sm" variant={i.conciliado ? "ghost" : "outline"} disabled={ocupado === `p${i.pago_id}`}
                      onClick={() => conciliar(i.pago_id, !i.conciliado)}
                      aria-label={i.conciliado ? `Quitar conciliación del pago ${i.pago_id}` : `Conciliar el pago ${i.pago_id}`}>
                      {i.conciliado ? <><CheckCircle2 className="h-4 w-4 text-emerald-600" /> Conciliado</> : "Conciliar"}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="t-devol" className="rounded-2xl border bg-card">
            <h2 id="t-devol" className="border-b px-4 py-3 text-sm font-semibold">Devoluciones confirmadas ({caja.devoluciones.length})</h2>
            {caja.devoluciones.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground">No hubo devoluciones confirmadas en el período.</p>
            ) : (
              <ul className="divide-y">
                {caja.devoluciones.map((d) => (
                  <li key={d.devolucion_id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-sm">
                    <span className="w-20 shrink-0 tabular-nums text-muted-foreground">{fecha(d.fecha)}</span>
                    <span className="min-w-0 flex-1">
                      <span className="font-medium">{d.empresa}</span>
                      <span className="block text-xs text-muted-foreground">
                        Pago #{d.pago_id} · {METODOS[d.metodo] ?? d.metodo}{d.referencia ? ` · ref. ${d.referencia}` : ""}
                      </span>
                    </span>
                    <span className="font-semibold tabular-nums text-red-800 dark:text-red-300">−{pesos(d.monto)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      <section aria-labelledby="t-cierres" className="mt-10">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="t-cierres" className="text-lg font-bold">Cierres</h2>
            <p className="text-sm text-muted-foreground">Solo de períodos que ya terminaron, sin superponerse.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" disabled={ocupado === "preparar"} onClick={() => preparar(semA, semB)}>
              Cerrar semana pasada
            </Button>
            <Button size="sm" variant="outline" disabled={ocupado === "preparar"} onClick={() => preparar(mesA, mesB)}>
              Cerrar mes pasado
            </Button>
            <Button size="sm" disabled={ocupado === "preparar"} onClick={() => preparar(desde, hasta)}>
              {ocupado === "preparar" && <Loader2 className="h-4 w-4 animate-spin" />} Cerrar el período elegido
            </Button>
          </div>
        </div>
        {!cierres ? (
          <div className="h-20 animate-pulse rounded-2xl bg-muted" />
        ) : cierres.length === 0 ? (
          <Vacio>Todavía no hay cierres.</Vacio>
        ) : (
          <ul className="space-y-3">
            {cierres.map((c) => {
              const [et, color] = ESTADO_CIERRE[c.estado];
              return (
                <li key={c.id} className="rounded-2xl border bg-card p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold">
                        {fecha(c.desde)} al {fecha(c.hasta)}{" "}
                        <span className={`ml-1 rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>{et}</span>
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Preparó {c.preparado_por} el {fechaHora(c.preparado_en)}
                        {c.cerrado_por && ` · cerró ${c.cerrado_por} el ${fechaHora(c.cerrado_en)}`}
                        {c.reabierto_por && ` · reabrió ${c.reabierto_por} el ${fechaHora(c.reabierto_en)} («${c.motivo_reapertura}»)`}
                      </p>
                    </div>
                    <dl className="grid grid-cols-3 gap-x-4 text-right text-sm tabular-nums">
                      <div><dt className="text-xs text-muted-foreground">Cobros</dt><dd>{pesos(c.totales.cobros)}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Devol.</dt><dd>{pesos(c.totales.devoluciones)}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Neto</dt><dd className="font-semibold">{pesos(c.totales.neto)}</dd></div>
                    </dl>
                  </div>
                  {c.observaciones && <p className="mt-2 text-sm text-muted-foreground">{c.observaciones}</p>}
                  {(c.estado === "borrador" || c.estado === "reabierto") && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button size="sm" disabled={ocupado === `c${c.id}`} onClick={() => cerrar(c)}>
                        <Lock className="h-4 w-4" /> {c.estado === "reabierto" ? "Volver a cerrar" : "Confirmar cierre"}
                      </Button>
                      {c.estado === "borrador" && (
                        <Button size="sm" variant="ghost" disabled={ocupado === `d${c.id}`} onClick={() => descartar(c)}>
                          <Trash2 className="h-4 w-4" /> Descartar
                        </Button>
                      )}
                    </div>
                  )}
                  {c.estado === "cerrado" && (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <label className="sr-only" htmlFor={`motivo-${c.id}`}>Motivo para reabrir</label>
                      <input id={`motivo-${c.id}`} value={motivos[c.id] ?? ""} maxLength={300}
                        onChange={(e) => setMotivos((m) => ({ ...m, [c.id]: e.target.value }))}
                        placeholder="Motivo para reabrir"
                        className="min-w-0 flex-1 rounded-lg border bg-background px-3 py-1.5 text-sm sm:max-w-xs" />
                      <Button size="sm" variant="outline" disabled={ocupado === `r${c.id}`} onClick={() => reabrir(c)}>
                        <RotateCcw className="h-4 w-4" /> Reabrir
                      </Button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
