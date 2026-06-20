"use client";

/**
 * Diálogo para asignar una membresía desde la pantalla de Membresías.
 *
 * A diferencia del de la ficha (donde el cliente ya está fijo), acá se elige
 * TODO: el cliente (con el selector buscar-o-crear), el plan y las fechas.
 */

import { useState, useEffect } from "react";
import { format, addMonths } from "date-fns";
import { toast } from "sonner";

import { Cliente } from "@/lib/clientes-api";
import { listarPlanes, crearMembresia, PlanAbono } from "@/lib/membresias-api";
import { ApiError } from "@/lib/api";
import { SelectorCliente } from "../agenda/selector-cliente";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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

interface AsignarAClienteDialogProps {
  abierto: boolean;
  onCerrar: () => void;
  onAsignada: () => void;
}

export function AsignarAClienteDialog({
  abierto,
  onCerrar,
  onAsignada,
}: AsignarAClienteDialogProps) {
  const [planes, setPlanes] = useState<PlanAbono[]>([]);
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [planId, setPlanId] = useState<string>("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [guardando, setGuardando] = useState(false);

  // Cargar planes y precargar fechas al abrir
  useEffect(() => {
    if (!abierto) return;
    listarPlanes().then(setPlanes).catch(() => {});
    const hoy = new Date();
    setDesde(format(hoy, "yyyy-MM-dd"));
    setHasta(format(addMonths(hoy, 1), "yyyy-MM-dd"));
    setCliente(null);
    setPlanId("");
  }, [abierto]);

  async function asignar() {
    if (!cliente) return toast.error("Elegí un cliente");
    if (!planId) return toast.error("Elegí un plan");
    if (!desde || !hasta) return toast.error("Elegí las fechas");

    setGuardando(true);
    try {
      await crearMembresia({
        cliente_id: cliente.id,
        plan_id: Number(planId),
        fecha_desde: desde,
        fecha_hasta: hasta,
      });
      toast.success(`Membresía asignada a ${cliente.nombre}`);
      onAsignada();
      onCerrar();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error("Este cliente ya tiene una membresía activa");
      } else {
        toast.error(err instanceof ApiError ? err.message : "No se pudo asignar");
      }
    } finally {
      setGuardando(false);
    }
  }

  const planElegido = planes.find((p) => String(p.id) === planId);

  return (
    <Dialog open={abierto} onOpenChange={(o) => !o && onCerrar()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Asignar membresía a un cliente</DialogTitle>
          <DialogDescription>
            Elegí el cliente, el plan de abono y el período de vigencia.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Cliente */}
          <div className="space-y-2">
            <Label>Cliente *</Label>
            <SelectorCliente clienteElegido={cliente} onSeleccion={setCliente} />
          </div>

          {/* Plan */}
          <div className="space-y-2">
            <Label>Plan de abono *</Label>
            {planes.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No hay planes creados. Creá uno primero.
              </p>
            ) : (
              <Select value={planId} onValueChange={setPlanId}>
                <SelectTrigger>
                  <SelectValue placeholder="Elegí un plan" />
                </SelectTrigger>
                <SelectContent>
                  {planes.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>
                      {p.nombre} · ${p.precio.toLocaleString("es-AR")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Fechas */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="aac-desde">Desde *</Label>
              <Input
                id="aac-desde"
                type="date"
                value={desde}
                onChange={(e) => setDesde(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="aac-hasta">Hasta *</Label>
              <Input
                id="aac-hasta"
                type="date"
                value={hasta}
                onChange={(e) => setHasta(e.target.value)}
              />
            </div>
          </div>

          {/* Resumen del plan elegido */}
          {planElegido && (
            <div className="rounded-xl border bg-muted/30 p-3 text-sm">
              <p className="font-medium">{planElegido.nombre}</p>
              <p className="text-muted-foreground">
                {planElegido.ilimitado
                  ? "Cortes ilimitados"
                  : `${planElegido.cantidad_cupos} cortes incluidos`}
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onCerrar} disabled={guardando}>
            Cancelar
          </Button>
          <Button onClick={asignar} disabled={guardando || planes.length === 0}>
            {guardando ? "Asignando…" : "Asignar membresía"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}