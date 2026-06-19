"use client";

/**
 * Panel lateral con el detalle de un turno.
 *
 * Muestra los datos del turno, botones para cambiar su estado (según las
 * transiciones válidas), y un acceso a la ficha del cliente. Las acciones
 * "peligrosas" (finalizar, cancelar) piden confirmación antes.
 */

import { useRouter } from "next/navigation";
import { Turno, EstadoTurno, cambiarEstadoTurno } from "@/lib/turnos-api";
import { TRANSICIONES, ACCION_LABEL, labelAccion, esReapertura } from "@/lib/turno-estados";
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface TurnoDetalleProps {
  turno: Turno | null;
  abierto: boolean;
  onCerrar: () => void;
  onCambio: () => void; // refrescar la agenda tras un cambio
}

// Estados que requieren confirmación antes de aplicarse (no se deshacen fácil).
const ESTADOS_PELIGROSOS: EstadoTurno[] = ["finalizado", "cancelado"];

export function TurnoDetalle({
  turno,
  abierto,
  onCerrar,
  onCambio,
}: TurnoDetalleProps) {
  const router = useRouter();
  const [procesando, setProcesando] = useState(false);
  // Acción peligrosa pendiente de confirmar (null = no hay)
  const [confirmar, setConfirmar] = useState<EstadoTurno | null>(null);

  if (!turno) return null;

  const color = colorEstadoHex(turno.estado);
  const acciones = TRANSICIONES[turno.estado];

  /** Ejecuta el cambio de estado (ya confirmado si era peligroso). */
  async function ejecutarAccion(destino: EstadoTurno) {
    if (!turno) return;
    setProcesando(true);
    try {
      await cambiarEstadoTurno(turno.id, destino);
      toast.success(`Turno ${labelEstado(destino).toLowerCase()}`);
      onCambio();
      onCerrar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cambiar");
    } finally {
      setProcesando(false);
      setConfirmar(null);
    }
  }

  /** Maneja el clic en un botón de acción: si es peligrosa, pide confirmar. */
  function onAccion(destino: EstadoTurno) {
    // Las acciones peligrosas (finalizar/cancelar) y las reaperturas confirman.
    if (ESTADOS_PELIGROSOS.includes(destino) || esReapertura(turno.estado)) {
      setConfirmar(destino);
    } else {
      ejecutarAccion(destino);
    }
  }

  return (
    <>
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
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Importe</span>
                  <span className="flex items-center gap-2">
                    {turno.cubierto_por_abono && (
                      <span className="inline-block rounded-full bg-amber-400/20 px-2 py-0.5 text-xs font-bold text-amber-600 dark:text-amber-400">
                        PRO
                      </span>
                    )}
                    <span className="font-medium">
                      ${Number(turno.importe_previsto).toLocaleString("es-AR")}
                    </span>
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
                      onClick={() => onAccion(destino)}
                    >
                      {labelAccion(turno.estado, destino)}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {/* Acceso a la ficha del cliente */}
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

      {/* Confirmación para acciones peligrosas */}
      <AlertDialog open={confirmar !== null} onOpenChange={(o) => !o && setConfirmar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {esReapertura(turno.estado)
                ? "¿Reabrir el turno?"
                : confirmar === "cancelado"
                  ? "¿Cancelar el turno?"
                  : "¿Finalizar el turno?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {esReapertura(turno.estado)
                ? "El turno volverá a estar activo. Usalo para corregir un error."
                : confirmar === "cancelado"
                  ? "El turno se cancelará y el horario quedará libre. Esta acción no se puede deshacer."
                  : "El turno se marcará como finalizado. Esta acción no se puede deshacer."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={procesando}>No, volver</AlertDialogCancel>
            <AlertDialogAction
              disabled={procesando}
              onClick={() => confirmar && ejecutarAccion(confirmar)}
              className={
                confirmar === "cancelado"
                  ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  : ""
              }
            >
              {esReapertura(turno.estado)
                ? "Sí, reabrir"
                : confirmar === "cancelado"
                  ? "Sí, cancelar"
                  : "Sí, finalizar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}