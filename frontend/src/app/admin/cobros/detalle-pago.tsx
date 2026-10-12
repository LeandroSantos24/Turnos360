"use client";

/**
 * Detalle de un pago de cuota, al costado de la lista.
 *
 * Muestra el pago original (que nunca se modifica), sus devoluciones con el
 * estado real, el historial y las acciones que el backend habilita
 * (`acciones`). Cada acción con plata pide confirmación con el monto y el
 * motivo a la vista. Una devolución pedida no se muestra como devuelta hasta
 * que está «aprobada».
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import {
  anularPago,
  conciliarPago,
  confirmarDevolucion,
  devolverPago,
  refrescarDevolucion,
  verPago,
  type DetallePago,
} from "@/lib/admin-api";
import { useConfirmar } from "@/components/confirmar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ChipEstado, METODOS, fecha, fechaHora, pesos } from "../_ui";

const ESTADO_DEV: Record<string, string> = {
  solicitada: "Solicitada",
  en_proceso: "En proceso en Mercado Pago",
  aprobada: "Devuelta",
  rechazada: "Rechazada",
};

export function DetallePagoPanel({
  pagoId,
  onCerrar,
  onCambio,
}: {
  pagoId: number | null;
  onCerrar: () => void;
  onCambio: () => void;
}) {
  const [p, setP] = useState<DetallePago | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [modo, setModo] = useState<"ver" | "devolver" | "anular">("ver");
  const [monto, setMonto] = useState("");
  const [motivo, setMotivo] = useState("");
  const [referencia, setReferencia] = useState("");
  const [yaHecha, setYaHecha] = useState(false);
  const [clave, setClave] = useState(() => crypto.randomUUID());
  const [refConc, setRefConc] = useState("");
  const confirmar = useConfirmar();

  const cargar = useCallback(() => {
    if (pagoId === null) return;
    verPago(pagoId)
      .then((d) => {
        setP(d);
        setRefConc(d.referencia_banco ?? "");
      })
      .catch((e) => toast.error(e instanceof ApiError ? e.message : "No se pudo abrir el pago"));
  }, [pagoId]);

  useEffect(() => {
    setP(null);
    setModo("ver");
    cargar();
  }, [cargar]);

  async function correr(fn: () => Promise<DetallePago>, ok: string) {
    setOcupado(true);
    try {
      const d = await fn();
      setP(d);
      toast.success(ok);
      onCambio();
      setModo("ver");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo completar");
      cargar();
    } finally {
      setOcupado(false);
    }
  }

  async function devolver() {
    if (!p) return;
    const m = Number(monto.replace(",", "."));
    if (!m || m <= 0 || m > p.devolvible) {
      toast.error(`El monto tiene que estar entre $1 y ${pesos(p.devolvible)}`);
      return;
    }
    if (motivo.trim().length < 4) {
      toast.error("Escribí el motivo");
      return;
    }
    const porMP = p.acciones.devolver_mp;
    const ok = await confirmar({
      titulo: `¿Devolver ${pesos(m)}?`,
      descripcion: porMP
        ? `Se le pide a Mercado Pago que devuelva ${pesos(m)} del pago ${p.mp_payment_id} a ${p.empresa}. Puede quedar «en proceso»: recién cuando MP la apruebe cuenta como devuelta.`
        : yaHecha
          ? `Se registra que ya le transferiste ${pesos(m)} a ${p.empresa} (ref. ${referencia}).`
          : `Se registra la devolución como pendiente. Cuando la hagas, la confirmás con la referencia.`,
      textoAccion: "Sí, devolver",
      destructivo: true,
    });
    if (!ok) return;
    await correr(
      () => devolverPago(p.id, { monto: m, motivo: motivo.trim(), referencia: referencia.trim() || undefined, confirmada: !porMP && yaHecha, clave }),
      porMP ? "Devolución pedida a Mercado Pago" : yaHecha ? "Devolución registrada" : "Devolución pendiente registrada",
    );
    setClave(crypto.randomUUID());
    setMonto("");
    setMotivo("");
    setReferencia("");
    setYaHecha(false);
  }

  async function anular() {
    if (!p) return;
    if (motivo.trim().length < 4) {
      toast.error("Escribí por qué se anula");
      return;
    }
    const ok = await confirmar({
      titulo: "¿Anular este pago?",
      descripcion: `El pago de ${pesos(p.monto)} queda registrado como anulado (no se borra) y el vencimiento de ${p.empresa} vuelve a como estaba. Es para cargas equivocadas, no para devolver plata.`,
      textoAccion: "Sí, anular",
      destructivo: true,
    });
    if (!ok) return;
    await correr(() => anularPago(p.id, motivo.trim()), "Pago anulado");
    setMotivo("");
  }

  return (
    <Sheet open={pagoId !== null} onOpenChange={(o) => !o && onCerrar()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Pago #{pagoId}</SheetTitle>
          <SheetDescription>{p ? `${p.empresa} · ${p.concepto}` : "Cargando…"}</SheetDescription>
        </SheetHeader>
        {!p ? (
          <div className="flex justify-center py-10"><Loader2 className="h-5 w-5 animate-spin" /></div>
        ) : (
          <div className="space-y-5 px-4 pb-6 text-sm">
            <div className="flex items-center justify-between">
              <ChipEstado estado={p.estado} etiqueta={p.estado_etiqueta} />
              <Link href={`/admin/empresas/${p.empresa_id}`} className="text-xs underline">Ver empresa</Link>
            </div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
              <dt className="text-muted-foreground">Importe acreditado</dt><dd className="text-right font-semibold tabular-nums">{pesos(p.monto)} {p.moneda}</dd>
              <dt className="text-muted-foreground">Devuelto</dt><dd className="text-right tabular-nums">{pesos(p.devuelto)}</dd>
              {p.devolucion_pendiente > 0 && (<><dt className="text-muted-foreground">Devolución pendiente</dt><dd className="text-right tabular-nums">{pesos(p.devolucion_pendiente)}</dd></>)}
              <dt className="text-muted-foreground">Comisión</dt><dd className="text-right tabular-nums">{p.comision === null ? "Sin dato" : pesos(p.comision)}</dd>
              <dt className="text-muted-foreground">Método</dt><dd className="text-right">{METODOS[p.metodo] ?? p.metodo}</dd>
              <dt className="text-muted-foreground">Acreditado el</dt><dd className="text-right">{fecha(p.fecha)}</dd>
              <dt className="text-muted-foreground">Registrado</dt><dd className="text-right">{fechaHora(p.creado_en)}</dd>
              <dt className="text-muted-foreground">Registró</dt><dd className="truncate text-right">{p.registrado_por ?? "—"}</dd>
              {p.mp_payment_id && (<><dt className="text-muted-foreground">Id Mercado Pago</dt><dd className="text-right font-mono">{p.mp_payment_id}</dd></>)}
              {p.periodo_desde && (<><dt className="text-muted-foreground">Período</dt><dd className="text-right">{fecha(p.periodo_desde)} – {fecha(p.periodo_hasta)}</dd></>)}
            </dl>
            {p.aviso && (
              <p className="rounded-xl bg-muted/50 p-3 text-xs">
                Transferencia informada{p.aviso.referencia ? ` (ref. ${p.aviso.referencia})` : ""}. Verificada por {p.aviso.resuelto_por ?? "—"} el {fechaHora(p.aviso.resuelto_en)}.
              </p>
            )}
            {p.anulado && (
              <p className="rounded-xl bg-muted p-3 text-xs">
                Anulado por {p.anulado_por} el {fechaHora(p.anulado_en)}{p.anulado_motivo ? `: ${p.anulado_motivo}` : ""}.
              </p>
            )}

            {/* Conciliación */}
            {p.acciones.conciliar && (
              <section className="rounded-xl border p-3">
                <h3 className="font-semibold">Conciliación</h3>
                {p.conciliado ? (
                  <p className="mt-1 flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400">
                    <CheckCircle2 className="h-4 w-4" aria-hidden /> Conciliado por {p.conciliado_por} el {fechaHora(p.conciliado_en)}
                    {p.referencia_banco ? ` · ref. ${p.referencia_banco}` : ""}
                  </p>
                ) : (
                  <p className="mt-1 text-muted-foreground">Todavía no se marcó como visto en el banco o en la cuenta de Mercado Pago.</p>
                )}
                <div className="mt-2 flex gap-2">
                  <Input aria-label="Referencia bancaria" placeholder="Referencia (opcional)" value={refConc} onChange={(e) => setRefConc(e.target.value)} maxLength={120} />
                  <Button variant="outline" disabled={ocupado}
                    onClick={() => correr(() => conciliarPago(p.id, !p.conciliado, refConc), p.conciliado ? "Marcado sin conciliar" : "Pago conciliado")}>
                    {p.conciliado ? "Desconciliar" : "Conciliar"}
                  </Button>
                </div>
              </section>
            )}

            {/* Devoluciones */}
            <section>
              <h3 className="font-semibold">Devoluciones</h3>
              {p.devoluciones.length === 0 ? (
                <p className="mt-1 text-muted-foreground">Sin devoluciones.</p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {p.devoluciones.map((d) => (
                    <li key={d.id} className="rounded-xl border p-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold tabular-nums">{pesos(d.monto)}</span>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${d.estado === "aprobada" ? "bg-emerald-100 text-emerald-900" : d.estado === "rechazada" ? "bg-red-100 text-red-900" : "bg-amber-100 text-amber-900"}`}>
                          {ESTADO_DEV[d.estado]}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {d.metodo === "mercadopago" ? "Mercado Pago" : "Manual"} · {d.motivo}
                        {d.mp_refund_id ? ` · id ${d.mp_refund_id}` : ""}{d.referencia ? ` · ref. ${d.referencia}` : ""}
                      </p>
                      <p className="text-xs text-muted-foreground">Pedida por {d.solicitada_por} el {fechaHora(d.solicitada_en)}{d.confirmada_en ? ` · confirmada el ${fechaHora(d.confirmada_en)}` : ""}</p>
                      {d.error && <p className="mt-1 text-xs text-red-700">{d.error}</p>}
                      {d.metodo === "mercadopago" && (d.estado === "solicitada" || d.estado === "en_proceso") && (
                        <Button size="sm" variant="ghost" className="mt-1" disabled={ocupado} onClick={() => correr(() => refrescarDevolucion(d.id), "Estado actualizado")}>
                          <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Consultar estado en MP
                        </Button>
                      )}
                      {d.metodo === "manual" && d.estado === "solicitada" && (
                        <ConfirmarManual onConfirmar={(ref) => correr(() => confirmarDevolucion(d.id, ref), "Devolución confirmada")} ocupado={ocupado} />
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* Acciones */}
            {modo === "ver" && (p.acciones.devolver_mp || p.acciones.devolver_manual || p.acciones.anular) && (
              <div className="flex flex-wrap gap-2">
                {(p.acciones.devolver_mp || p.acciones.devolver_manual) && (
                  <Button variant="outline" onClick={() => { setModo("devolver"); setMonto(String(p.devolvible)); }}>Devolver</Button>
                )}
                {p.acciones.anular && <Button variant="ghost" onClick={() => setModo("anular")}>Anular (carga equivocada)</Button>}
              </div>
            )}
            {!p.acciones.devolver_mp && p.metodo === "mercadopago" && p.devolvible > 0 && !p.anulado && (
              <p className="text-xs text-muted-foreground">Para devolver por Mercado Pago hace falta la cuenta de Turnos360 configurada (ver Integraciones).</p>
            )}

            {modo === "devolver" && (
              <section className="space-y-3 rounded-xl border p-3">
                <h3 className="font-semibold">Devolver {p.acciones.devolver_mp ? "por Mercado Pago" : "(transferencia o efectivo)"}</h3>
                <p className="text-xs text-muted-foreground">Se puede devolver hasta {pesos(p.devolvible)} (lo acreditado menos lo ya devuelto o pedido).</p>
                <div className="space-y-1.5">
                  <Label htmlFor="d-monto">Importe</Label>
                  <Input id="d-monto" inputMode="decimal" value={monto} onChange={(e) => setMonto(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="d-motivo">Motivo</Label>
                  <Input id="d-motivo" value={motivo} maxLength={300} onChange={(e) => setMotivo(e.target.value)} placeholder="Ej.: pagó dos veces" />
                </div>
                {!p.acciones.devolver_mp && (
                  <>
                    <div className="space-y-1.5">
                      <Label htmlFor="d-ref">Referencia de la transferencia de vuelta</Label>
                      <Input id="d-ref" value={referencia} maxLength={120} onChange={(e) => setReferencia(e.target.value)} />
                    </div>
                    <label className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={yaHecha} onChange={(e) => setYaHecha(e.target.checked)} />
                      Ya la hice (con la referencia de arriba)
                    </label>
                  </>
                )}
                <div className="flex gap-2">
                  <Button onClick={devolver} disabled={ocupado}>{ocupado && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}Continuar</Button>
                  <Button variant="ghost" onClick={() => setModo("ver")}>Cancelar</Button>
                </div>
              </section>
            )}

            {modo === "anular" && (
              <section className="space-y-3 rounded-xl border p-3">
                <h3 className="font-semibold">Anular por carga equivocada</h3>
                <p className="text-xs text-muted-foreground">El pago no se borra: queda anulado con el motivo y quién lo hizo. Si hubo plata, no es esto: es «Devolver».</p>
                <div className="space-y-1.5">
                  <Label htmlFor="a-motivo">Motivo</Label>
                  <Input id="a-motivo" value={motivo} maxLength={300} onChange={(e) => setMotivo(e.target.value)} />
                </div>
                <div className="flex gap-2">
                  <Button variant="destructive" onClick={anular} disabled={ocupado}>Continuar</Button>
                  <Button variant="ghost" onClick={() => setModo("ver")}>Cancelar</Button>
                </div>
              </section>
            )}

            {p.historial.length > 0 && (
              <section>
                <h3 className="font-semibold">Historial</h3>
                <ol className="mt-2 space-y-1.5 border-l pl-3">
                  {p.historial.map((h, i) => (
                    <li key={i} className={`text-xs ${h.revertido ? "text-muted-foreground line-through" : ""}`}>
                      <span className="text-muted-foreground">{fechaHora(h.fecha)}</span> · {h.detalle ?? h.tipo}
                      {h.hecho_por && <span className="text-muted-foreground"> — {h.hecho_por}</span>}
                    </li>
                  ))}
                </ol>
              </section>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function ConfirmarManual({ onConfirmar, ocupado }: { onConfirmar: (ref: string) => void; ocupado: boolean }) {
  const [ref, setRef] = useState("");
  return (
    <div className="mt-2 flex gap-2">
      <Input aria-label="Referencia de la devolución" placeholder="Referencia de la transferencia" value={ref} onChange={(e) => setRef(e.target.value)} maxLength={120} />
      <Button size="sm" disabled={!ref.trim() || ocupado} onClick={() => onConfirmar(ref.trim())}>Confirmar</Button>
    </div>
  );
}
