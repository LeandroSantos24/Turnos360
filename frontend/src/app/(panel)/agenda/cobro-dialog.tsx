"use client";

/**
 * Diálogo de cobro de un turno (E10 · N-52, N-54).
 *
 * Muestra el total a cobrar y permite registrarlo con uno o varios métodos
 * (pago dividido). La comisión de cada método la calcula el backend; acá solo
 * se arman las líneas (método + monto).
 */

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";

import {
  listarMetodos,
  registrarCobro,
  MetodoPago,
  PagoLinea,
} from "@/lib/finanzas-api";
import { ApiError } from "@/lib/api";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface CobroDialogProps {
  turnoId: number | null;
  total: number;
  /**
   * Lo que el cliente ya pagó por adelantado (seña acreditada).
   * Sin esto, el diálogo proponía cobrar el total completo de un turno
   * señado y la recepción le cobraba la seña dos veces.
   */
  senado?: number;
  abierto: boolean;
  onCerrar: () => void;
  onCobrado: () => void;
}

interface LineaForm {
  metodo_pago_id: string;
  monto: string;
}

export function CobroDialog({
  turnoId,
  total,
  senado = 0,
  abierto,
  onCerrar,
  onCobrado,
}: CobroDialogProps) {
  // Lo que falta cobrar de verdad. Es el número que manda en todo el
  // diálogo: la línea inicial, el "falta asignar" y el aviso de exceso.
  const aCobrar = Math.round(Math.max(total - senado, 0) * 100) / 100;
  const [metodos, setMetodos] = useState<MetodoPago[]>([]);
  const [lineas, setLineas] = useState<LineaForm[]>([]);
  const [registrando, setRegistrando] = useState(false);

  // Al abrir: traer métodos activos y arrancar con una línea por el total.
  useEffect(() => {
    if (!abierto) return;
    listarMetodos()
      .then((m) => {
        const activos = m.filter((x) => x.activo);
        setMetodos(activos);
        setLineas([
          {
            metodo_pago_id: activos[0] ? String(activos[0].id) : "",
            monto: aCobrar > 0 ? String(aCobrar) : "",
          },
        ]);
      })
      .catch(() => setMetodos([]));
  }, [abierto, aCobrar]);

  const sumaLineas = lineas.reduce((acc, l) => acc + (Number(l.monto) || 0), 0);
  const restante = Math.round((aCobrar - sumaLineas) * 100) / 100;

  function agregarLinea() {
    setLineas((prev) => [
      ...prev,
      {
        metodo_pago_id: metodos[0] ? String(metodos[0].id) : "",
        monto: restante > 0 ? String(restante) : "",
      },
    ]);
  }

  function quitarLinea(i: number) {
    setLineas((prev) => prev.filter((_, idx) => idx !== i));
  }

  function setLinea(i: number, campo: keyof LineaForm, valor: string) {
    setLineas((prev) =>
      prev.map((l, idx) => (idx === i ? { ...l, [campo]: valor } : l)),
    );
  }

  async function registrar() {
    if (!turnoId) return;
    const pagos: PagoLinea[] = lineas
      .filter((l) => Number(l.monto) > 0)
      .map((l) => ({
        metodo_pago_id: l.metodo_pago_id ? Number(l.metodo_pago_id) : null,
        monto: Number(l.monto),
      }));
    if (pagos.length === 0) {
      toast.error("Cargá al menos un pago");
      return;
    }
    setRegistrando(true);
    try {
      const cobro = await registrarCobro(turnoId, pagos);
      const neto = cobro.neto.toLocaleString("es-AR");
      const comision = cobro.total_comision;
      toast.success(
        comision > 0
          ? `Cobrado. Neto $${neto} (comisión $${comision.toLocaleString("es-AR")})`
          : `Cobro registrado: $${cobro.total_cobrado.toLocaleString("es-AR")}`,
      );
      onCobrado();
      onCerrar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cobrar");
    } finally {
      setRegistrando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={(o) => !o && onCerrar()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Registrar cobro</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-1">
          {/* Total a cobrar. Con seña pagada se muestra el desglose completo:
              el número correcto sin que se vea de dónde sale es la mitad del
              arreglo — la recepción tiene que poder explicárselo al cliente. */}
          <div className="space-y-1.5 rounded-2xl bg-muted/40 px-4 py-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Total del turno</span>
              <span
                className={
                  senado > 0
                    ? "text-sm tabular-nums text-muted-foreground"
                    : "text-xl font-bold tabular-nums"
                }
                style={senado > 0 ? undefined : { fontFamily: "Syne, sans-serif" }}
              >
                ${total.toLocaleString("es-AR")}
              </span>
            </div>
            {senado > 0 && (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-emerald-700">
                    Seña ya cobrada
                  </span>
                  <span className="text-sm tabular-nums text-emerald-700">
                    −${senado.toLocaleString("es-AR")}
                  </span>
                </div>
                <div className="flex items-center justify-between border-t pt-1.5">
                  <span className="text-sm font-medium">A cobrar ahora</span>
                  <span
                    className="text-xl font-bold tabular-nums"
                    style={{ fontFamily: "Syne, sans-serif" }}
                  >
                    ${aCobrar.toLocaleString("es-AR")}
                  </span>
                </div>
              </>
            )}
          </div>

          {/* Líneas de pago */}
          <div className="space-y-2">
            {lineas.map((l, i) => (
              <div key={i} className="flex items-center gap-2">
                <Select
                  value={l.metodo_pago_id}
                  onValueChange={(v) => setLinea(i, "metodo_pago_id", v)}
                >
                  <SelectTrigger className="flex-1">
                    <SelectValue placeholder="Método" />
                  </SelectTrigger>
                  <SelectContent>
                    {metodos.map((m) => (
                      <SelectItem key={m.id} value={String(m.id)}>
                        {m.nombre}
                        {m.comision_pct > 0 && ` (${m.comision_pct}%)`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  type="number"
                  inputMode="numeric"
                  placeholder="$"
                  value={l.monto}
                  onChange={(e) => setLinea(i, "monto", e.target.value)}
                  className="w-28"
                />
                {lineas.length > 1 && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => quitarLinea(i)}
                    aria-label="Quitar"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}

            <Button variant="outline" size="sm" onClick={agregarLinea}>
              <Plus className="mr-1.5 h-4 w-4" /> Dividir pago
            </Button>
          </div>

          {/* Aviso de restante / exceso */}
          {Math.abs(restante) > 0.01 && (
            <p
              className={
                restante > 0
                  ? "text-sm text-amber-600 dark:text-amber-400"
                  : "text-sm text-destructive"
              }
            >
              {restante > 0
                ? `Falta asignar $${restante.toLocaleString("es-AR")}`
                : `Te pasaste por $${Math.abs(restante).toLocaleString("es-AR")}`}
            </p>
          )}

          {metodos.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No tenés métodos de pago cargados. Podés cobrar igual (sin método) o
              cargarlos en Finanzas → Métodos de pago.
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCerrar}>
            Cancelar
          </Button>
          <Button onClick={registrar} disabled={registrando}>
            {registrando ? "Registrando…" : "Registrar cobro"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}