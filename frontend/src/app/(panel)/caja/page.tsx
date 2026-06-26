"use client";

/**
 * Caja (/caja). El centro de operaciones financieras del día (E10).
 *
 * - Si no hay caja abierta: botón para abrirla con saldo inicial.
 * - Si hay una abierta: resumen (inicial, ingresos, egresos, esperado),
 *   registrar gastos y cerrar la caja viendo la diferencia.
 */

import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Plus, Lock, ArrowDownRight, ArrowUpRight, Printer } from "lucide-react";

import {
  cajaActual,
  abrirCaja,
  cerrarCaja,
  listarMovimientos,
  listarCajas,
  CajaResumen,
  Caja,
  Movimiento,
} from "@/lib/finanzas-api";
import { ApiError } from "@/lib/api";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { GastoDialog } from "./gasto-dialog";

const NUM: React.CSSProperties = {
  fontFamily: "Syne, sans-serif",
  fontVariantNumeric: "lining-nums tabular-nums",
};

function pesos(n: number): string {
  return `$${Number(n).toLocaleString("es-AR")}`;
}

function fechaHora(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function CajaPage() {
  const [resumen, setResumen] = useState<CajaResumen | null>(null);
  const [movimientos, setMovimientos] = useState<Movimiento[]>([]);
  const [cajas, setCajas] = useState<Caja[]>([]);
  const [cargando, setCargando] = useState(true);
  const [abriendo, setAbriendo] = useState(false);
  const [cerrando, setCerrando] = useState(false);
  const [gastando, setGastando] = useState(false);
  const [saldoInicial, setSaldoInicial] = useState("");
  const [saldoReal, setSaldoReal] = useState("");
  const [procesando, setProcesando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const [r, m, cs] = await Promise.all([
        cajaActual(),
        listarMovimientos(),
        listarCajas(),
      ]);
      setResumen(r);
      setMovimientos(m);
      setCajas(cs);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function confirmarAbrir() {
    setProcesando(true);
    try {
      await abrirCaja({ saldo_inicial: Number(saldoInicial) || 0 });
      toast.success("Caja abierta");
      setAbriendo(false);
      setSaldoInicial("");
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo abrir");
    } finally {
      setProcesando(false);
    }
  }

  async function confirmarCerrar() {
    setProcesando(true);
    try {
      const res = await cerrarCaja({ saldo_real: Number(saldoReal) || 0 });
      const dif = res.diferencia ?? 0;
      toast.success(
        Math.abs(dif) < 0.01
          ? "Caja cerrada — cuadra perfecto"
          : `Caja cerrada. Diferencia: ${pesos(dif)}`,
      );
      setCerrando(false);
      setSaldoReal("");
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cerrar");
    } finally {
      setProcesando(false);
    }
  }

  const esperado = resumen?.saldo_esperado ?? 0;
  const difViva = (Number(saldoReal) || 0) - esperado;

  return (
    <div className="p-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: "Syne, sans-serif" }}>
            Caja
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            El control del dinero del día: apertura, cobros, gastos y cierre.
          </p>
        </div>
        <a
          href="/imprimir/dia"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium hover:bg-muted/50"
        >
          <Printer className="h-4 w-4" /> Parte del día
        </a>
      </div>

      {cargando ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : !resumen ? (
        // ── Caja cerrada ──
        <div className="rounded-2xl border bg-card p-12 text-center">
          <p className="text-sm text-muted-foreground">
            No hay una caja abierta. Abrí la caja para empezar a registrar el día.
          </p>
          <Button className="mt-4" onClick={() => setAbriendo(true)}>
            <Plus className="mr-1.5 h-4 w-4" /> Abrir caja
          </Button>
        </div>
      ) : (
        // ── Caja abierta ──
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div className="rounded-2xl border bg-card p-5">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Saldo inicial
              </p>
              <p className="mt-1 text-2xl font-bold" style={NUM}>
                {pesos(resumen.caja.saldo_inicial)}
              </p>
            </div>
            <div className="rounded-2xl border bg-card p-5">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Ingresos
              </p>
              <p className="mt-1 text-2xl font-bold" style={{ ...NUM, color: "#10b981" }}>
                {pesos(resumen.total_ingresos)}
              </p>
            </div>
            <div className="rounded-2xl border bg-card p-5">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Gastos
              </p>
              <p className="mt-1 text-2xl font-bold" style={{ ...NUM, color: "#ef4444" }}>
                {pesos(resumen.total_egresos)}
              </p>
            </div>
            <div className="rounded-2xl border bg-card p-5">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Saldo esperado
              </p>
              <p className="mt-1 text-2xl font-bold" style={NUM}>
                {pesos(resumen.saldo_esperado)}
              </p>
            </div>
          </div>

          <div className="mb-8 flex gap-2">
            <Button variant="outline" onClick={() => setGastando(true)}>
              <Plus className="mr-1.5 h-4 w-4" /> Registrar gasto
            </Button>
            <Button onClick={() => setCerrando(true)}>
              <Lock className="mr-1.5 h-4 w-4" /> Cerrar caja
            </Button>
          </div>

          {resumen.por_metodo && resumen.por_metodo.length > 0 && (
            <div className="mb-8">
              <h2 className="mb-3 text-lg font-bold">Ingresos por método</h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {resumen.por_metodo.map((pm) => (
                  <div key={pm.metodo} className="rounded-2xl border bg-card p-4">
                    <p className="text-xs text-muted-foreground">{pm.metodo}</p>
                    <p className="mt-1 text-lg font-bold tabular-nums" style={NUM}>
                      {pesos(pm.total)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <h2 className="mb-3 text-lg font-bold">Movimientos</h2>
          {movimientos.length === 0 ? (
            <div className="rounded-2xl border bg-card p-10 text-center">
              <p className="text-sm text-muted-foreground">
                Todavía no hay movimientos. Los cobros y gastos aparecen acá.
              </p>
            </div>
          ) : (
            <div className="divide-y overflow-hidden rounded-2xl border bg-card">
              {movimientos.map((m) => {
                const esIngreso = m.tipo === "ingreso";
                return (
                  <div key={m.id} className="flex items-center gap-3 px-4 py-3">
                    <div
                      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                        esIngreso
                          ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                          : "bg-red-500/15 text-red-600 dark:text-red-400"
                      }`}
                    >
                      {esIngreso ? (
                        <ArrowUpRight className="h-4 w-4" />
                      ) : (
                        <ArrowDownRight className="h-4 w-4" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {m.concepto ?? (esIngreso ? "Ingreso" : "Gasto")}
                        {m.metodo_pago && (
                          <span className="ml-2 rounded-md bg-muted px-1.5 py-0.5 text-xs font-normal text-muted-foreground">
                            {m.metodo_pago}
                          </span>
                        )}
                      </p>
                      {m.descripcion && (
                        <p className="truncate text-xs text-muted-foreground">
                          {m.descripcion}
                        </p>
                      )}
                    </div>
                    <span
                      className="text-sm font-semibold tabular-nums"
                      style={{ color: esIngreso ? "#10b981" : "#ef4444" }}
                    >
                      {esIngreso ? "+" : "−"}
                      {pesos(m.monto)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Historial de cajas */}
      {cajas.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-lg font-bold">Historial de cajas</h2>
          <div className="divide-y overflow-hidden rounded-2xl border bg-card">
            {cajas.map((c) => {
              const abierta = c.estado === "abierta";
              return (
                <div key={c.id} className="flex items-center gap-4 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium tabular-nums">
                      {fechaHora(c.fecha_apertura)}
                      {abierta ? " · en curso" : ` → ${fechaHora(c.fecha_cierre)}`}
                    </p>
                    <p className="text-xs text-muted-foreground tabular-nums">
                      Inicial {pesos(c.saldo_inicial)}
                      {c.saldo_final != null && ` · Cierre ${pesos(c.saldo_final)}`}
                    </p>
                  </div>
                  <a
                    href={`/imprimir/caja/${c.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 text-xs text-muted-foreground underline hover:text-foreground"
                  >
                    Imprimir
                  </a>
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${
                      abierta
                        ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {abierta ? "Abierta" : "Cerrada"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Abrir caja */}
      <Dialog open={abriendo} onOpenChange={(o) => !o && setAbriendo(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Abrir caja</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 py-1">
            <Label htmlFor="saldo-inicial">Saldo inicial</Label>
            <Input
              id="saldo-inicial"
              type="number"
              inputMode="numeric"
              value={saldoInicial}
              onChange={(e) => setSaldoInicial(e.target.value)}
              placeholder="Con cuánto efectivo arrancás"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAbriendo(false)}>
              Cancelar
            </Button>
            <Button onClick={confirmarAbrir} disabled={procesando}>
              {procesando ? "Abriendo…" : "Abrir caja"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cerrar caja */}
      <Dialog open={cerrando} onOpenChange={(o) => !o && setCerrando(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cerrar caja</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-1">
            <div className="flex items-center justify-between rounded-2xl bg-muted/40 px-4 py-3">
              <span className="text-sm text-muted-foreground">Saldo esperado</span>
              <span className="font-bold tabular-nums" style={NUM}>
                {pesos(esperado)}
              </span>
            </div>
            <div className="space-y-2">
              <Label htmlFor="saldo-real">Saldo real (lo que contás)</Label>
              <Input
                id="saldo-real"
                type="number"
                inputMode="numeric"
                value={saldoReal}
                onChange={(e) => setSaldoReal(e.target.value)}
                placeholder="$"
                autoFocus
              />
            </div>
            {saldoReal !== "" && (
              <div
                className={`flex items-center justify-between rounded-2xl px-4 py-3 ${
                  Math.abs(difViva) < 0.01
                    ? "bg-emerald-500/10"
                    : "bg-amber-500/10"
                }`}
              >
                <span className="text-sm font-medium">Diferencia</span>
                <span
                  className="font-bold tabular-nums"
                  style={{
                    ...NUM,
                    color: Math.abs(difViva) < 0.01 ? "#10b981" : "#f59e0b",
                  }}
                >
                  {difViva >= 0 ? "+" : "−"}
                  {pesos(Math.abs(difViva))}
                </span>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCerrando(false)}>
              Cancelar
            </Button>
            <Button onClick={confirmarCerrar} disabled={procesando}>
              {procesando ? "Cerrando…" : "Cerrar caja"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Registrar gasto */}
      <GastoDialog
        abierto={gastando}
        onCerrar={() => setGastando(false)}
        onRegistrado={cargar}
      />
    </div>
  );
}