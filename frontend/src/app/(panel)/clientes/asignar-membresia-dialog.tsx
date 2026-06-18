"use client";

/**
 * Diálogo para asignar una membresía a un cliente.
 *
 * Elegís un plan de abono + las fechas (desde/hasta). El backend valida que
 * el cliente no tenga ya una membresía activa (una a la vez).
 */

import { useState, useEffect } from "react";
import { format, addMonths } from "date-fns";
import { toast } from "sonner";

import { listarPlanes, crearMembresia, PlanAbono } from "@/lib/membresias-api";
import { ApiError } from "@/lib/api";

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

interface AsignarMembresiaDialogProps {
  clienteId: number;
  abierto: boolean;
  onCerrar: () => void;
  onAsignada: () => void;
}

export function AsignarMembresiaDialog({
  clienteId,
  abierto,
  onCerrar,
  onAsignada,
}: AsignarMembresiaDialogProps) {
  const [planes, setPlanes] = useState<PlanAbono[]>([]);
  const [planId, setPlanId] = useState<string>("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [guardando, setGuardando] = useState(false);

  // Cargar planes y precargar fechas (hoy → un mes) al abrir
  useEffect(() => {
    if (!abierto) return;
    listarPlanes().then(setPlanes).catch(() => {});
    const hoy = new Date();
    setDesde(format(hoy, "yyyy-MM-dd"));
    setHasta(format(addMonths(hoy, 1), "yyyy-MM-dd"));
    setPlanId("");
  }, [abierto]);

  async function asignar() {
    if (!planId) return toast.error("Elegí un plan");
    if (!desde || !hasta) return toast.error("Elegí las fechas");

    setGuardando(true);
    try {
      await crearMembresia({
        cliente_id: clienteId,
        plan_id: Number(planId),
        fecha_desde: desde,
        fecha_hasta: hasta,
      });
      toast.success("Membresía asignada");
      onAsignada();
      onCerrar();
    } catch (err) {
      // 409 = ya tiene una membresía activa
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
          <DialogTitle>Asignar membresía</DialogTitle>
          <DialogDescription>
            Elegí el plan de abono y el período de vigencia.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Plan */}
          <div className="space-y-2">
            <Label>Plan de abono *</Label>
            {planes.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No hay planes creados. Creá uno en la sección Membresías.
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
              <Label htmlFor="m-desde">Desde *</Label>
              <Input
                id="m-desde"
                type="date"
                value={desde}
                onChange={(e) => setDesde(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="m-hasta">Hasta *</Label>
              <Input
                id="m-hasta"
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