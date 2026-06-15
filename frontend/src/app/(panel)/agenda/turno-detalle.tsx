"use client";

/**
 * Panel lateral con el detalle de un turno.
 *
 * Muestra los datos del turno, botones para cambiar su estado (según las
 * transiciones válidas), y un acceso a la ficha del cliente.
 */

import { useRouter } from "next/navigation";
import { Turno, EstadoTurno, cambiarEstadoTurno } from "@/lib/turnos-api";
import { TRANSICIONES, ACCION_LABEL } from "@/lib/turno-estados";
import { colorEstadoHex, labelEstado, horaDe, inicialDe } from "@/lib/turno-visual";
import { ApiError } from "@/lib/api";
import { toast } from "sonner";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

interface TurnoDetalleProps {
  turno: Turno | null;
  abierto: boolean;
  onCerrar: () => void;
  onCambio: () => void; // refrescar la agenda tras un cambio
}

export function TurnoDetalle({
  turno,
  abierto,
  onCerrar,
  onCambio,
}: TurnoDetalleProps) {
  const router = useRouter();
  const [procesando, setProcesando] = useState(false);

  if (!turno) return null;

  const color = colorEstadoHex(turno.estado);
  const acciones = TRANSICIONES[turno.estado];

  async function ejecutarAccion(destino: EstadoTurno) {
    if (!turno) return;
    // Para cancelar, pedimos un motivo simple
    let motivo: string | undefined;
    if (destino === "cancelado") {
      motivo = window.prompt("Motivo de la cancelación (opcional):") || undefined;
    }
    setProcesando(true);
    try {
      await cambiarEstadoTurno(turno.id, destino, motivo);
      toast.success(`Turno ${labelEstado(destino).toLowerCase()}`);
      onCambio();
      onCerrar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cambiar");
    } finally {
      setProcesando(false);
    }
  }

  return (
    <Sheet open={abierto} onOpenChange={(o) => !o && onCerrar()}>
      <SheetContent className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Detalle del turno</SheetTitle>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Cliente */}
          <div className="flex items-center gap-3">
            <div
              className="flex h-12 w-12 items-center justify-center rounded-full text-lg font-semibold text-white"
              style={{ backgroundColor: color }}
            >
              {inicialDe(turno.cliente_nombre)}
            </div>
            <div>
              <p className="text-lg font-semibold">{turno.cliente_nombre}</p>
              <span
                className="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium"
                style={{ backgroundColor: `${color}22`, color }}
              >
                {labelEstado(turno.estado)}
              </span>
            </div>
          </div>

          {/* Datos */}
          <div className="space-y-2 rounded-lg border p-4 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Horario</span>
              <span className="font-medium">
                {turno.fecha_inicio && horaDe(turno.fecha_inicio)}
                {turno.fecha_fin && ` – ${horaDe(turno.fecha_fin)}`}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Servicio</span>
              <span className="font-medium">
                {turno.servicio_nombre ?? "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Profesional</span>
              <span className="font-medium">
                {turno.recurso_nombre ?? "—"}
              </span>
            </div>
            {turno.importe_previsto != null && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Importe</span>
                <span className="font-medium">
                  ${Number(turno.importe_previsto).toLocaleString("es-AR")}
                </span>
              </div>
            )}
            {turno.es_sobreturno && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Sobreturno</span>
                <span className="font-medium">Sí</span>
              </div>
            )}
          </div>

          {/* Acciones de estado */}
          {acciones.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">
                Acciones
              </p>
              <div className="flex flex-wrap gap-2">
                {acciones.map((destino) => (
                  <Button
                    key={destino}
                    variant={destino === "cancelado" ? "outline" : "default"}
                    size="sm"
                    disabled={procesando}
                    onClick={() => ejecutarAccion(destino)}
                  >
                    {ACCION_LABEL[destino]}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {/* Acceso a la ficha del cliente (futuro) */}
          <Button
            variant="outline"
            className="w-full"
            onClick={() => router.push(`/clientes/${turno.cliente_id}`)}
          >
            Ver ficha del cliente →
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}